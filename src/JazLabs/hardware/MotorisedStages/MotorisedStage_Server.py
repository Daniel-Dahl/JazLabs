from copy import deepcopy
import logging
import math
import multiprocessing as mp
import queue
import threading
import time

import zmq

logger = logging.getLogger(__name__)

SUPPORTED_STAGE_TYPES = (
    "simulation",
    "BSC203Serial",
    "KDC101Serial",
    "KST201Serial",
    "UMC2Serial",
    "CONEXAGPSerial",
    "CONEXAGAPSerial",
)


def create_motorised_stage(stage_type, stage_kwargs=None):
    """Construct the configured hardware driver without opening unused drivers."""
    stage_kwargs = {} if stage_kwargs is None else dict(stage_kwargs)
    if stage_type == "simulation":
        from .SimulatedStage import SimulatedStage
        return SimulatedStage(**stage_kwargs)

    if stage_type == "UMC2Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.UMC2SerialStage import UMC2SerialStage

        return UMC2SerialStage(**stage_kwargs)

    if stage_type in ("CONEXAGPSerial", "CONEXAGAPSerial"):
        if stage_type == "CONEXAGPSerial":
            from JazLabs.hardware.MotorisedStages.Newport.newport_agp_serial_stage import NewportAGPSerialStage

            return NewportAGPSerialStage(**stage_kwargs)
        from JazLabs.hardware.MotorisedStages.Newport.newport_agap_serial_stage import NewportM100DSerialStage

        return NewportM100DSerialStage(**stage_kwargs)

    if stage_type == "BSC203Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.BSC203SerialStage import (
            BSC203SerialStage,
        )

        return BSC203SerialStage(**stage_kwargs)

    if stage_type == "KDC101Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.KDC101SerialStage import (
            KDC101SerialStage,
        )

        return KDC101SerialStage(**stage_kwargs)

    if stage_type == "KST201Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.KST201SerialStage import (
            KST201SerialStage,
        )

        return KST201SerialStage(**stage_kwargs)

    supported_types = ", ".join(SUPPORTED_STAGE_TYPES)
    raise ValueError(
        f"Unknown stage_type: {stage_type}. Supported stage types: {supported_types}"
    )


class MotorisedStageZMQServer:
    """Network loop stays responsive while the hardware worker polls or moves.

    New protocol only: request `state`, `absolute`, `relative`, `home`, `jog`,
    `release_jog`, `stop`, `resume`, `speed`, `enable` or `shutdown`.
    Bind to localhost unless a trusted lab network is explicitly selected.
    """
    def __init__(self, host="127.0.0.1", command_port=50931,
                 stage_type="simulation", stage_kwargs=None, limits=None):
        self.host = host
        self.command_port = int(command_port)
        self.stage_type = stage_type
        self.stage_kwargs = dict(stage_kwargs or {})
        self.limits = limits
        self.process = None

    def start(self):
        if self.process and self.process.is_alive():
            raise RuntimeError("Motion server is already running")
        parent_ready, child_ready = mp.Pipe(duplex=False)
        self.process = mp.Process(target=_run_motor_server,
            args=(self.host, self.command_port, self.stage_type, self.stage_kwargs, self.limits, child_ready),
            daemon=False)
        self.process.start()
        child_ready.close()
        try:
            if not parent_ready.poll(5):
                raise TimeoutError("Motor server did not open its command port")
            reply = parent_ready.recv()
            if "error" in reply:
                raise RuntimeError(reply["error"])
            self.command_port = reply["command_port"]
        finally:
            parent_ready.close()

    def stop(self):
        if self.process is None or not self.process.is_alive():
            return
        from .MotorisedStage_Client import MotorisedStageClient
        client = MotorisedStageClient(self.host, self.command_port)
        try:
            client.request("shutdown")
        finally:
            client.close()
            self.process.join(timeout=3)
        if self.process.is_alive():
            raise RuntimeError("Motor server did not confirm shutdown")

    def run_forever(self, ready_connection=None):
        worker = StageServerWorker(
            lambda: create_motorised_stage(self.stage_type, self.stage_kwargs), limits=self.limits
        )
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.SNDTIMEO, 500)
        try:
            if self.command_port == 0:
                self.command_port = socket.bind_to_random_port(f"tcp://{self.host}")
            else:
                socket.bind(f"tcp://{self.host}:{self.command_port}")
            if ready_connection is not None:
                ready_connection.send({"command_port": self.command_port})
                ready_connection.close()
                ready_connection = None
            worker.start()
            running = True
            while running:
                if not socket.poll(50):
                    continue
                try:
                    message = socket.recv_json()
                    command = message["command"]
                    if command == "shutdown":
                        worker.close()
                        running = False
                    elif command != "state":
                        if command not in {"absolute", "relative", "home", "jog", "release_jog",
                                           "stop", "resume", "speed", "enable"}:
                            raise ValueError(f"Unknown motion command {command}")
                        worker.submit(command, message.get("axis"), message.get("value"),
                                      operation_id=message.get("operation_id"), stop_reason=message.get("stop_reason"))
                    response = {"ok": True, "state": worker.get_state()}
                except Exception as exc:
                    response = {"ok": False, "error": str(exc)}
                try:
                    socket.send_json(response)
                except zmq.Again:
                    break
        finally:
            if worker.thread.is_alive():
                worker.close()
                worker.thread.join(timeout=3)
            socket.close()
            context.term()
            if ready_connection is not None:
                ready_connection.send({"error": "Motor server could not bind its command port"})
                ready_connection.close()


class StageServerWorker:
    """One hardware owner, one pending command, leased keyboard jogging.

    UI and network threads only enqueue intents or read snapshots. They never
    call the serial driver. A stop invalidates pending work and latches motion
    off until an explicit resume. A held key is a short lease, not a move queue.
    """
    def __init__(self, driver_factory, poll_interval=0.08, motion_timeout=60.0, limits=None):
        self.limits = dict(limits or {})
        self.driver_factory = driver_factory
        self.poll_interval = poll_interval
        self.motion_timeout = motion_timeout
        self.commands = queue.Queue(maxsize=1)
        self.lock = threading.RLock()
        self.wake = threading.Event()
        self.stop_requested = threading.Event()
        self.closing = threading.Event()
        self.held_jog = None
        self.epoch = 0
        self.snapshot = {"connected": False, "name": "Connecting…", "capabilities": [],
                         "axes": {}, "stopped": False, "stop_pending": False,
                         "error": None, "message": "Connecting…", "sequence": 0, "operations": {},
                         "stop_reason": None, "last_stop_reason": None}
        self.thread = threading.Thread(target=self.run, name="motor-hardware-owner", daemon=True)

    def start(self):
        self.thread.start()

    def get_state(self):
        with self.lock:
            result = deepcopy(self.snapshot)
            # Age is measured by the hardware owner's clock, not a remote GUI's.
            now = time.monotonic()
            for state in result["axes"].values():
                state["age"] = now - state.pop("updated_at", now)
            return result

    def submit(self, command, axis=None, value=None, operation_id=None, stop_reason=None):
        with self.lock:
            if self.closing.is_set():
                raise RuntimeError("Motion service is closing")
            if command == "stop":
                reason = str(stop_reason or "Stop requested by client")
                if not self.stop_requested.is_set():
                    if not self.snapshot["stopped"] or reason != self.snapshot["last_stop_reason"]:
                        logger.warning("Motor motion stopped: %s", reason)
                    self.snapshot.update(stop_reason=reason, last_stop_reason=reason)
                self.epoch += 1
                self.held_jog = None
                self.snapshot["stop_pending"] = True
                self.stop_requested.set()
                self.wake.set()
                return
            if command == "release_jog":
                self.held_jog = None
                return
            if command == "jog":
                if self.snapshot["stopped"] or self.stop_requested.is_set():
                    raise RuntimeError("Motion is stopped; resume first")
                value = float(value)
                if not math.isfinite(value) or value == 0:
                    raise ValueError("Jog distance must be finite and nonzero")
                if self.held_jog and (axis, value) != self.held_jog[:2]:
                    raise RuntimeError("Release the current jog before changing direction")
                self.held_jog = (axis, value, time.monotonic() + 0.35)
                self.wake.set()
                return
            if self.snapshot["stopped"] and command != "resume":
                raise RuntimeError("Motion is stopped; resume first")
            if self.held_jog:
                raise RuntimeError("Release keyboard jog before another command")
            if operation_id is not None:
                if command not in ("absolute", "relative", "home") or not isinstance(operation_id, str):
                    raise ValueError("An operation ID must be a string for a movement or homing command")
                if operation_id in self.snapshot["operations"]:
                    raise ValueError("Duplicate motion operation ID; command was not repeated")
            try:
                self.commands.put_nowait((self.epoch, command, axis, value, operation_id))
            except queue.Full as exc:
                raise RuntimeError("A motor command is already pending") from exc
            if operation_id is not None:
                operations = self.snapshot["operations"]
                operations[operation_id] = {"axis": axis, "status": "queued", "error": None}
                while len(operations) > 64:
                    removable = next((key for key, item in operations.items()
                                      if item["status"] not in ("queued", "running")), None)
                    if removable is None:
                        break
                    del operations[removable]
            self.wake.set()

    def close(self):
        with self.lock:
            if self.closing.is_set():
                return
            self.submit("stop")
            self.closing.set()
            self.wake.set()

    def run(self):
        driver = None
        active_axis = None
        target = None
        homing = False
        started_at = 0.0
        active_operation = None
        intent_operation = None
        try:
            driver = self.driver_factory()
            if hasattr(driver, "SetStopRequested"):
                driver.SetStopRequested(self.stop_requested.is_set)
            self.motion_timeout = driver.GetProperties().get("move_timeout", self.motion_timeout)
            capabilities = {axis["id"]: axis for axis in driver.GetMotionCapabilities()}
            for axis, endpoints in self.limits.items():
                if axis not in capabilities or len(endpoints) != 2:
                    raise ValueError(f"Invalid travel limits for {axis}")
                lower, upper = map(float, endpoints)
                spec = capabilities[axis]
                if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
                    raise ValueError("Travel limits must be finite and minimum < maximum")
                if ((spec["minimum"] is not None and lower < spec["minimum"]) or
                        (spec["maximum"] is not None and upper > spec["maximum"])):
                    raise ValueError("Limits cannot widen the driver's allowed travel")
                spec.update(minimum=lower, maximum=upper)
            with self.lock:
                self.snapshot.update(
                    name=getattr(driver, "name", driver.GetProperties().get("stage_type", type(driver).__name__)),
                    properties=driver.GetProperties(), capabilities=deepcopy(list(capabilities.values())))
            while True:
                intent_operation = None
                self.wake.clear()
                if self.stop_requested.is_set():
                    # Normal intents and held-key leases are invalidated before
                    # sending any stop commands. Failure never reports success.
                    with self.lock:
                        self.held_jog = None
                        while not self.commands.empty():
                            self.commands.get_nowait()
                        for operation in self.snapshot["operations"].values():
                            if operation["status"] in ("queued", "running"):
                                operation.update(status="stopped", error="Motion interrupted by stop")
                        self.snapshot.update(stopped=True, stop_pending=True)
                    try:
                        driver.StopAll()
                        with self.lock:
                            self.snapshot.update(message=f"Motion stopped: {self.snapshot['stop_reason']}")
                    except Exception as exc:
                        with self.lock:
                            self.snapshot.update(message="Stop failed", error=str(exc))
                    active_axis = None
                    active_operation = None
                    with self.lock:
                        self.snapshot["stop_pending"] = False
                        self.stop_requested.clear()
                if self.closing.is_set():
                    break
                try:
                    for axis in capabilities:
                        try:
                            state = driver.GetAxisStatus(axis)
                        except InterruptedError:
                            raise
                        except Exception as exc:
                            raise OSError(f"Feedback from {axis} failed: {exc}") from exc
                        if not math.isfinite(state["position"]):
                            raise RuntimeError(f"Invalid position from {axis}")
                        state["updated_at"] = time.monotonic()
                        with self.lock:
                            state["commanded"] = axis == active_axis
                            self.snapshot["axes"][axis] = state
                        if state["fault"]:
                            raise RuntimeError(f"{axis}: {state['fault']}")
                        if self.stop_requested.is_set():
                            break
                    if self.stop_requested.is_set():
                        continue
                    now = time.monotonic()
                    self.snapshot["connected"] = True
                    self.snapshot["sequence"] += 1
                    if active_axis:
                        current = self.snapshot["axes"][active_axis]
                        tolerance = capabilities[active_axis].get("tolerance", capabilities[active_axis]["resolution"] * 2)
                        complete = current["homed"] if homing else abs(current["position"] - target) <= tolerance
                        if not current["moving"] and not current["homing"] and complete and now - started_at >= 0.15:
                            with self.lock:
                                if active_operation is not None:
                                    self.snapshot["operations"][active_operation].update(
                                        status="completed", result=dict(current, commanded=False))
                            active_operation = None
                            active_axis = None
                            self.snapshot["message"] = "Ready"
                            for state in self.snapshot["axes"].values():
                                state["commanded"] = False
                        elif now - started_at > self.motion_timeout:
                            raise TimeoutError("Motion did not complete before its timeout")
                    intent_operation = None
                    with self.lock:
                        if self.held_jog and self.held_jog[2] < now:
                            self.held_jog = None
                        # One in-flight axis is deliberate: hold repetition never
                        # creates hidden queued moves or simultaneous directions.
                        intent = None
                        if not active_axis and not self.snapshot["stopped"] and self.held_jog:
                            axis, delta, expires = self.held_jog
                            intent = (self.epoch, "relative", axis, delta, None)
                        elif not self.commands.empty():
                            intent = self.commands.get_nowait()
                    if intent:
                        epoch, command, axis, value, intent_operation = intent
                        if epoch != self.epoch:
                            continue
                        if self.stop_requested.is_set():
                            continue
                        if command == "resume":
                            if active_axis or any(s["moving"] or s["homing"] for s in self.snapshot["axes"].values()):
                                raise ValueError("Wait for all axes to stop before resuming")
                            self.snapshot.update(stopped=False, error=None, stop_reason=None, message="Ready · keyboard off")
                            continue
                        if active_axis or any(s["moving"] or s["homing"] for s in self.snapshot["axes"].values()):
                            raise ValueError("Wait for motion to complete")
                        if axis not in capabilities:
                            raise ValueError(f"Unknown axis {axis}")
                        spec = capabilities[axis]
                        current = self.snapshot["axes"][axis]
                        if now - current["updated_at"] > 1:
                            raise ValueError("Position feedback is stale")
                        if command == "enable":
                            driver.EnableAxis(axis)
                            continue
                        if command == "home":
                            if not spec["home"]:
                                raise ValueError("This axis has an absolute sensor; no homing")
                            if not current["enabled"]:
                                raise ValueError("Enable this axis before homing")
                            homing = True
                            driver.HomeAxis(axis)
                        elif command in ("absolute", "relative"):
                            if not current["enabled"]:
                                raise ValueError("Enable this axis before moving")
                            if spec["home"] and not current["homed"]:
                                raise ValueError("Home this axis before moving")
                            value = float(value)
                            if not math.isfinite(value):
                                raise ValueError("Position must be finite")
                            target = current["position"] + value if command == "relative" else value
                            target = round(target / spec["resolution"]) * spec["resolution"]
                            if spec["minimum"] is not None and target < spec["minimum"]:
                                raise ValueError("Target is below the configured travel limit")
                            if spec["maximum"] is not None and target > spec["maximum"]:
                                raise ValueError("Target is above the configured travel limit")
                            if abs(current["position"] - target) < spec["resolution"] / 2:
                                if command == "relative":
                                    raise ValueError("Requested step is smaller than the axis resolution")
                                if intent_operation is not None:
                                    with self.lock:
                                        self.snapshot["operations"][intent_operation].update(
                                            status="completed", result=dict(current, commanded=False))
                                self.snapshot.update(error=None, message="Ready")
                                continue
                            homing = False
                            driver.MoveTo(axis, target, wait=False)
                        elif command == "speed":
                            if not spec["speed"]:
                                raise ValueError("Speed control is unavailable for this driver")
                            value = float(value)
                            if not math.isfinite(value) or not spec["speed_minimum"] <= value <= spec["speed_maximum"]:
                                raise ValueError("Speed is outside the supported range")
                            driver.SetSpeed(axis, value)
                            continue
                        else:
                            raise ValueError(f"Unknown command {command}")
                        active_axis = axis
                        active_operation = intent_operation
                        if active_operation is not None:
                            with self.lock:
                                self.snapshot["operations"][active_operation]["status"] = "running"
                        started_at = time.monotonic()
                        self.snapshot["axes"][axis]["commanded"] = True
                        self.snapshot.update(error=None, message=f"{'Homing' if homing else 'Moving'} {axis}")
                except InterruptedError:
                    continue
                except ValueError as exc:
                    # A rejected intent does not mean the link disappeared. Stop
                    # active motion on a hardware error, then require explicit resume.
                    with self.lock:
                        self.held_jog = None
                        if intent_operation is not None:
                            self.snapshot["operations"][intent_operation].update(status="failed", error=str(exc))
                        self.snapshot.update(error=str(exc), message=str(exc))
                    if active_axis or any(s.get("fault") for s in self.snapshot["axes"].values()):
                        self.submit("stop", stop_reason=str(exc))
                except Exception as exc:
                    with self.lock:
                        self.held_jog = None
                        for operation_id in (active_operation, intent_operation):
                            if operation_id is not None:
                                self.snapshot["operations"][operation_id].update(status="failed", error=str(exc))
                        self.snapshot.update(connected=False, error=str(exc), message="Feedback unavailable")
                    self.submit("stop", stop_reason=str(exc))
                self.wake.wait(self.poll_interval)
        except Exception as exc:
            with self.lock:
                self.snapshot.update(connected=False, error=str(exc), message="Connection failed")
        finally:
            if driver is not None:
                try:
                    driver.StopAll()
                except Exception as exc:
                    with self.lock:
                        self.snapshot["error"] = f"Stop during disconnect failed: {exc}"
                finally:
                    try:
                        driver.CloseStage()
                    except Exception as exc:
                        with self.lock:
                            self.snapshot["error"] = f"Disconnect failed: {exc}"
            with self.lock:
                self.snapshot["connected"] = False


def _run_motor_server(host, command_port, stage_type, stage_kwargs, limits, ready_connection):
    server = MotorisedStageZMQServer(host, command_port, stage_type, stage_kwargs, limits)
    server.run_forever(ready_connection)
