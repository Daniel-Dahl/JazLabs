from copy import deepcopy
import logging
import math
import multiprocessing as mp
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


def create_motorised_stage(stage_type, stage_kwargs=None, limits=None):
    """Construct the configured hardware driver without opening unused drivers."""
    stage_kwargs = {} if stage_kwargs is None else dict(stage_kwargs)
    # Every driver receives bounds, including when the server narrows
    # configured travel. Direct driver calls therefore enforce the same limits.
    driver_limits = dict(stage_kwargs.get("limits") or {})
    for axis, endpoints in (limits or {}).items():
        if len(endpoints) != 2:
            raise ValueError(f"Invalid travel limits for {axis}")
        lower, upper = map(float, endpoints)
        if axis in driver_limits:
            current_lower, current_upper = driver_limits[axis]
            if ((current_lower is not None and lower < current_lower) or
                    (current_upper is not None and upper > current_upper)):
                raise ValueError("Limits cannot widen the driver's allowed travel")
        driver_limits[axis] = (lower, upper)
    stage_kwargs["limits"] = driver_limits

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
    """One server loop receives requests, polls feedback and advances motion.

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
            client.CloseStage()
            self.process.join(timeout=3)
        if self.process.is_alive():
            raise RuntimeError("Motor server did not confirm shutdown")

    def run_forever(self, ready_connection=None):
        """Own the driver and network socket in the same thread, like Camera_Server.

        Moves start with wait=False. Each loop handles a request, then reads one
        axis and checks completion. Serial calls have driver-defined timeouts;
        a request arriving during a serial read waits for that read to return.
        """
        driver = None
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.SNDTIMEO, 500)
        state = {"connected": False, "name": "Connecting…",
                 "axes": {}, "stopped": False, "stop_pending": False,
                 "error": None, "message": "Connecting…", "sequence": 0,
                 "operations": {}, "stop_reason": None}
        pending_command = None
        nominal_moves = []
        held_jog = None
        active_axis = None
        active_operation = None
        intent_operation = None
        target = None
        homing = False
        started_at = 0.0
        stop_reason = None
        motion_timeout = 60.0
        poll_interval = 0.08
        next_poll_at = 0.0
        next_axis = 0
        running = True
        try:
            if self.command_port == 0:
                self.command_port = socket.bind_to_random_port(f"tcp://{self.host}")
            else:
                socket.bind(f"tcp://{self.host}:{self.command_port}")
            driver = create_motorised_stage(self.stage_type, self.stage_kwargs, self.limits)
            device_status = driver.GetStatus()
            state.update(deepcopy(device_status))
            state["name"] = getattr(driver, "name", device_status["controller"])
            axis_names = list(state["axes"])
            if not axis_names:
                raise ValueError("Motor driver did not report any axes")
            for feedback in state["axes"].values():
                feedback["updated_at"] = time.perf_counter()
                feedback["commanded"] = False
            motion_timeout = device_status.get("move_timeout", motion_timeout)
            if ready_connection is not None:
                ready_connection.send({"command_port": self.command_port})
                ready_connection.close()
                ready_connection = None

            while running:
                # Read requests before the next hardware poll. There is no
                # hardware worker, shared-state lock or inter-thread queue.
                wait_ms = max(0, min(20, int((next_poll_at - time.perf_counter()) * 1000)))
                if socket.poll(wait_ms):
                    try:
                        message = socket.recv_json()
                        command = message["command"]
                        axis = message.get("axis")
                        value = message.get("value")
                        operation_id = message.get("operation_id")
                        if command == "shutdown":
                            running = False
                            stop_reason = "Server shutdown"
                        elif command == "stop":
                            stop_reason = str(message.get("stop_reason") or "Stop requested by client")
                        elif command == "release_jog":
                            held_jog = None
                        elif command == "state":
                            pass
                        else:
                            if command not in {"absolute", "relative", "home", "nominal", "jog", "resume", "speed", "enable"}:
                                raise ValueError(f"Unknown motion command {command}")
                            if (state["stopped"] or stop_reason is not None) and command != "resume":
                                raise RuntimeError("Motion is stopped; resume first")
                            if nominal_moves:
                                raise RuntimeError("Wait for the nominal move to finish before another command")
                            if command == "jog":
                                value = float(value)
                                if not math.isfinite(value) or value == 0:
                                    raise ValueError("Jog distance must be finite and nonzero")
                                if held_jog and (axis, value) != held_jog[:2]:
                                    raise RuntimeError("Release the current jog before changing direction")
                                held_jog = (axis, value, time.perf_counter() + 0.35)
                            else:
                                if held_jog:
                                    raise RuntimeError("Release keyboard jog before another command")
                                if operation_id is not None:
                                    if command not in ("absolute", "relative", "home", "nominal") or not isinstance(operation_id, str):
                                        raise ValueError("An operation ID must be a string for a movement or homing command")
                                    if operation_id in state["operations"]:
                                        raise ValueError("Duplicate motion operation ID; command was not repeated")
                                if pending_command is not None:
                                    if not (command == "relative" and operation_id is None
                                            and pending_command[0] == "relative" and pending_command[3] is None):
                                        raise RuntimeError("A motor command is already pending")
                                # Keep one pending step while a move is active.
                                # Rapid untracked GUI taps replace that step.
                                pending_command = (command, axis, value, operation_id)
                                if operation_id is not None:
                                    operations = state["operations"]
                                    operations[operation_id] = {"axis": axis, "status": "queued", "error": None}
                                    while len(operations) > 64:
                                        removable = next((key for key, item in operations.items()
                                                          if item["status"] not in ("queued", "running")), None)
                                        if removable is None:
                                            break
                                        del operations[removable]
                        if stop_reason is not None:
                            state["stop_pending"] = True
                        response_state = deepcopy(state)
                        now = time.perf_counter()
                        for feedback in response_state["axes"].values():
                            feedback["age"] = now - feedback.pop("updated_at", now)
                        response = {"ok": True, "state": response_state}
                    except Exception as exc:
                        response = {"ok": False, "error": str(exc)}
                    try:
                        socket.send_json(response)
                    except zmq.Again:
                        break

                if stop_reason is not None:
                    # Invalidate pending commands and held keys before stopping.
                    held_jog = None
                    pending_command = None
                    nominal_moves.clear()
                    for operation in state["operations"].values():
                        if operation["status"] in ("queued", "running"):
                            operation.update(status="stopped", error="Motion interrupted by stop")
                    if stop_reason not in ("Stop requested by client", "Server shutdown", state["stop_reason"]):
                        logger.warning("Motor motion stopped: %s", stop_reason)
                    state.update(stopped=True, stop_reason=stop_reason)
                    try:
                        driver.StopAll()
                        state["message"] = f"Motion stopped: {stop_reason}"
                    except Exception as exc:
                        state.update(message="Stop failed", error=str(exc))
                    active_axis = None
                    active_operation = None
                    state["stop_pending"] = False
                    stop_reason = None
                if not running:
                    break
                if time.perf_counter() < next_poll_at:
                    continue
                # Even failed reads are rate limited, allowing network requests
                # between retries. Read just one axis before returning above.
                next_poll_at = time.perf_counter() + poll_interval / len(axis_names)
                intent_operation = None
                try:
                    axis = axis_names[next_axis]
                    try:
                        device_status = driver.GetStatus(axis)
                        feedback = device_status["axes"][axis]
                        for key, value in device_status.items():
                            if key != "axes":
                                state[key] = value
                    except Exception as exc:
                        raise OSError(f"Feedback from {axis} failed: {exc}") from exc
                    if not math.isfinite(feedback["position"]):
                        raise RuntimeError(f"Invalid position from {axis}")
                    feedback["updated_at"] = time.perf_counter()
                    feedback["commanded"] = axis == active_axis
                    state["axes"][axis] = feedback
                    if feedback["fault"]:
                        raise RuntimeError(f"{axis}: {feedback['fault']}")
                    next_axis = (next_axis + 1) % len(axis_names)
                    next_poll_at = time.perf_counter() + poll_interval / len(axis_names)
                    now = time.perf_counter()
                    state["connected"] = all(now - item["updated_at"] < 1 for item in state["axes"].values())
                    if not state["connected"]:
                        continue
                    state["sequence"] += 1
                    if active_axis:
                        current = state["axes"][active_axis]
                        tolerance = current.get("tolerance", current["resolution"] * 2)
                        complete = current["homed"] if homing else abs(current["position"] - target) <= tolerance
                        if not current["moving"] and not current["homing"] and complete and now - started_at >= 0.15:
                            if active_operation is not None and not nominal_moves:
                                state["operations"][active_operation].update(
                                    status="completed", result=dict(current, commanded=False))
                            active_operation = None
                            active_axis = None
                            state["message"] = "Ready"
                            for feedback in state["axes"].values():
                                feedback["commanded"] = False
                        elif now - started_at > motion_timeout:
                            raise TimeoutError("Motion did not complete before its timeout")
                    intent_operation = None
                    if held_jog and held_jog[2] < now:
                        held_jog = None
                    # One in-flight axis is deliberate: hold repetition never
                    # creates hidden queued moves or simultaneous directions.
                    intent = None
                    if not active_axis and nominal_moves:
                        intent = nominal_moves.pop(0)
                    elif not active_axis and pending_command is not None:
                        intent = pending_command
                        pending_command = None
                    elif not active_axis and not state["stopped"] and held_jog:
                        axis, delta, expires = held_jog
                        intent = ("relative", axis, delta, None)
                    if intent:
                        command, axis, value, intent_operation = intent
                        if command == "resume":
                            if active_axis or any(s["moving"] or s["homing"] for s in state["axes"].values()):
                                raise ValueError("Wait for all axes to stop before resuming")
                            state.update(stopped=False, error=None, stop_reason=None, message="Ready · keyboard off")
                            continue
                        if active_axis or any(s["moving"] or s["homing"] for s in state["axes"].values()):
                            raise ValueError("Wait for motion to complete")
                        if command == "nominal":
                            # Validate every endpoint before starting the first axis.
                            for name, feedback in state["axes"].items():
                                lower, upper = feedback["limits"]
                                if lower is None or upper is None:
                                    raise ValueError(f"{name}: configure travel limits before moving to nominal")
                            nominal_moves = [("absolute", name, sum(feedback["limits"]) / 2, intent_operation)
                                             for name, feedback in state["axes"].items()]
                            command, axis, value, intent_operation = nominal_moves.pop(0)
                        if axis not in state["axes"]:
                            raise ValueError(f"Unknown axis {axis}")
                        spec = state["axes"][axis]
                        current = state["axes"][axis]
                        if now - current["updated_at"] > 1:
                            raise ValueError("Position feedback is stale")
                        if command == "enable":
                            driver.EnableAxis(axis, enabled=True if value is None else bool(value))
                            continue
                        if command == "home":
                            if not spec["supports"]["home"]:
                                raise ValueError("This axis has an absolute sensor; no homing")
                            if not current["enabled"]:
                                raise ValueError("Enable this axis before homing")
                            homing = True
                            driver.HomeAxis(axis, wait=False)
                        elif command in ("absolute", "relative"):
                            if not current["enabled"]:
                                raise ValueError("Enable this axis before moving")
                            if spec["supports"]["home"] and not current["homed"]:
                                raise ValueError("Home this axis before moving")
                            value = float(value)
                            if not math.isfinite(value):
                                raise ValueError("Position must be finite")
                            target = current["position"] + value if command == "relative" else value
                            target = round(target / spec["resolution"]) * spec["resolution"]
                            if spec["limits"][0] is not None and target < spec["limits"][0]:
                                raise ValueError("Target is below the configured travel limit")
                            if spec["limits"][1] is not None and target > spec["limits"][1]:
                                raise ValueError("Target is above the configured travel limit")
                            if abs(current["position"] - target) < spec["resolution"] / 2:
                                if command == "relative":
                                    raise ValueError("Requested step is smaller than the axis resolution")
                                if intent_operation is not None and not nominal_moves:
                                    state["operations"][intent_operation].update(
                                        status="completed", result=dict(current, commanded=False))
                                state.update(error=None, message="Ready")
                                continue
                            homing = False
                            if command == "relative":
                                driver.MoveRel(axis, target - current["position"], wait=False)
                            else:
                                driver.MoveAbs(axis, target, wait=False)
                        elif command == "speed":
                            if not spec["supports"]["speed"]:
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
                            state["operations"][active_operation]["status"] = "running"
                        started_at = time.perf_counter()
                        state["axes"][axis]["commanded"] = True
                        state.update(error=None, message=f"{'Homing' if homing else 'Moving'} {axis}")
                except ValueError as exc:
                    # A rejected intent does not mean the link disappeared. Stop
                    # active motion on a hardware error, then require explicit resume.
                    held_jog = None
                    nominal_moves.clear()
                    if intent_operation is not None:
                        state["operations"][intent_operation].update(status="failed", error=str(exc))
                    state.update(error=str(exc), message=str(exc))
                    if active_axis or any(s.get("fault") for s in state["axes"].values()):
                        stop_reason = str(exc)
                except Exception as exc:
                    held_jog = None
                    for operation_id in (active_operation, intent_operation):
                        if operation_id is not None:
                            state["operations"][operation_id].update(status="failed", error=str(exc))
                    state.update(connected=False, error=str(exc), message="Feedback unavailable")
                    stop_reason = str(exc)
        except Exception as exc:
            if ready_connection is not None:
                ready_connection.send({"error": str(exc)})
                ready_connection.close()
                ready_connection = None
            raise
        finally:
            try:
                if driver is not None:
                    try:
                        driver.StopAll()
                    finally:
                        driver.CloseStage()
            finally:
                socket.close()
                context.term()


def _run_motor_server(host, command_port, stage_type, stage_kwargs, limits, ready_connection):
    server = MotorisedStageZMQServer(host, command_port, stage_type, stage_kwargs, limits)
    server.run_forever(ready_connection)
