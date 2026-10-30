"""User-facing motor client; synchronous RPCs and optional GUI polling.

Scripts call request(). Widgets call start(), submit() and get_state() on the
same client. Only the client's network thread handles asynchronous RPCs; it
never imports or accesses a hardware driver.
"""
import math
import time
import uuid
from copy import deepcopy

import zmq

class MotorCommandRejected(RuntimeError):
    """The server replied but did not accept the requested command."""


class MotorisedStageClient:
    def __init__(self, host="127.0.0.1", command_port=50931, timeout_ms=500):
        import queue
        import threading
        self.endpoint = f"tcp://{host}:{int(command_port)}"
        self.timeout_ms = int(timeout_ms)
        self.context = zmq.Context()
        self.host = host
        self.command_port = command_port
        self.lock = threading.RLock()
        self.commands = queue.Queue(maxsize=1)
        self.stop_requested = threading.Event()
        self.release_requested = threading.Event()
        self.closing = threading.Event()
        self.wake = threading.Event()
        self.held_jog = None
        self.received_at = None
        self.communication_stop_reason = None
        self.snapshot = {"connected": False, "name": "Connecting…", "capabilities": [],
                         "axes": {}, "stopped": False, "stop_pending": False,
                         "message": "Connecting…", "error": None, "sequence": 0}
        self.thread = threading.Thread(target=self.run, name="motor-network-owner", daemon=True)

    def request(self, command, axis=None, value=None, operation_id=None, stop_reason=None):
        socket = self.context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        try:
            socket.connect(self.endpoint)
            socket.send_json({"command": command, "axis": axis, "value": value,
                              "operation_id": operation_id, "stop_reason": stop_reason})
            response = socket.recv_json()
            if not response.get("ok"):
                raise MotorCommandRejected(response.get("error", "Motion service rejected request"))
            return response.get("state")
        except zmq.Again as exc:
            raise TimeoutError("Motion service did not respond") from exc
        finally:
            socket.close()

    def GetStatus(self, axis=None):
        """Return configuration and cached live feedback in one dictionary.

        Newport uses the driver's GetStatus shape. Other controllers expose the
        same axes/configuration layout from their server feedback and metadata.
        """
        snapshot = self.request("state")
        if "device_status" in snapshot:
            status = deepcopy(snapshot["device_status"])
            status["axes"] = deepcopy(snapshot["axes"])
        else:
            status = dict(snapshot.get("properties", {}))
            status["controller"] = status.get("stage_type", snapshot.get("name"))
            status["axes"] = deepcopy(snapshot["axes"])
            for spec in snapshot["capabilities"]:
                name = spec["id"]
                if name not in status["axes"]:
                    continue
                feedback = status["axes"][name]
                feedback.update(label=spec["label"], units=spec["units"],
                                limits=[spec["minimum"], spec["maximum"]],
                                resolution=spec["resolution"], tolerance=spec.get("tolerance"),
                                step=spec["step"], supports={"home": spec["home"],
                                "stop": spec["stop"], "speed": spec["speed"]})
        if axis is not None:
            if axis not in status["axes"]:
                raise ValueError(f"Axis {axis!r} has no feedback")
            status["axes"] = {axis: status["axes"][axis]}
        status.update(connected=snapshot["connected"], stopped=snapshot["stopped"],
                      error=snapshot.get("error"), message=snapshot.get("message"))
        return status

    def GetMotionCapabilities(self):
        return self.request("state")["capabilities"]

    def GetAxisStatus(self, axis):
        return self.request("state")["axes"][axis]

    def GetProperties(self):
        return self.request("state").get("properties", {})

    def GetPosition(self, axis, units=None):
        """Return one position in the units advertised for this axis."""
        snapshot = self.request("state")
        status = snapshot["axes"].get(axis)
        if status is None:
            raise ValueError(f"Unknown or unavailable axis {axis}")
        if not snapshot["connected"] or status.get("age", 999) >= 1:
            raise RuntimeError("Motor position feedback is unavailable or stale")
        if units is None:
            return status["position"]
        positions = status.get("positions", {})
        if units not in positions:
            raise ValueError(f"{axis}: units {units!r} unavailable")
        return positions[units]

    def GetPositions(self, units=None):
        """Return all current positions in advertised units from one snapshot."""
        snapshot = self.request("state")
        if not snapshot["connected"] or any(status.get("age", 999) >= 1 for status in snapshot["axes"].values()):
            raise RuntimeError("Motor position feedback is unavailable or stale")
        if units is None:
            return {axis: status["position"] for axis, status in snapshot["axes"].items()}
        positions = {}
        for axis, status in snapshot["axes"].items():
            if units not in status.get("positions", {}):
                raise ValueError(f"{axis}: units {units!r} unavailable")
            positions[axis] = status["positions"][units]
        return positions

    def MoveAbs(self, axis, target, wait=True, timeout=None, units=None):
        """Move to an absolute target; by default wait for this operation to finish.

        Waiting polls the server rather than blocking its command loop. StopAll
        remains available from another client or thread. A stop, controller
        fault, lost feedback or deadline raises instead of reporting completion.
        wait=False returns an operation ID immediately after submission.
        """
        target = float(target)
        if not math.isfinite(target):
            raise ValueError("Target must be finite")
        if units is not None:
            capabilities = {spec["id"]: spec for spec in self.GetMotionCapabilities()}
            if axis not in capabilities:
                raise ValueError(f"Unknown axis {axis}")
            spec = capabilities[axis]
            scales = spec.get("unit_scales", {spec["units"]: 1.0})
            if units not in scales:
                raise ValueError(f"{axis}: units {units!r} unavailable")
            if units == "counts" and target != int(target):
                raise ValueError("Counts must be integers")
            target = target * scales[units] / scales[spec["units"]]
        if timeout is None:
            timeout = self.GetProperties().get("move_timeout", 60.0)
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        operation_id = uuid.uuid4().hex
        stop_required = True
        try:
            self.request("absolute", axis, target, operation_id=operation_id)
            if not wait:
                return {"operation_id": operation_id}
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                snapshot = self.request("state")
                operation = snapshot.get("operations", {}).get(operation_id)
                if operation is None:
                    raise RuntimeError("The server lost this movement's completion record")
                if operation["status"] in ("failed", "stopped"):
                    # The server has already rejected/stopped this operation.
                    # Do not stop an unrelated move after a validation rejection.
                    stop_required = False
                    raise RuntimeError(operation.get("error") or "Movement did not complete")
                if operation["status"] == "completed":
                    result = dict(operation["result"])
                    result.pop("updated_at", None)
                    if result["moving"] or result["homing"]:
                        raise RuntimeError("Controller still reports motion after completion")
                    return result
                if not snapshot["connected"]:
                    raise RuntimeError(snapshot.get("error") or "Motor feedback is unavailable")
                status = snapshot["axes"].get(axis)
                if status is not None and (status.get("fault") or status.get("age", 999) >= 1):
                    raise RuntimeError(status.get("fault") or "Motor feedback is stale")
            raise TimeoutError(f"{axis} did not finish its move within {timeout:g} s")
        except MotorCommandRejected:
            # A rejected RPC did not start this move; leave other motion alone.
            raise
        except Exception as exc:
            if stop_required:
                try:
                    self.StopAll()
                except Exception as stop_exc:
                    raise RuntimeError(f"{exc}; stop could not be confirmed: {stop_exc}") from exc
            raise

    def HomeAxis(self, axis):
        return self.request("home", axis)

    def EnableAxis(self, axis):
        return self.request("enable", axis)

    def StopAll(self):
        return self.request("stop")

    def SetSpeed(self, axis, value):
        return self.request("speed", axis, value)

    def start(self):
        self.thread.start()

    def submit(self, command, axis=None, value=None):
        import queue
        import time
        with self.lock:
            if command == "stop":
                self.held_jog = None
                while not self.commands.empty():
                    self.commands.get_nowait()
                self.snapshot["stop_pending"] = True
                self.communication_stop_reason = None
                self.stop_requested.set()
            elif command == "release_jog":
                self.held_jog = None
                # A tap's first step must survive an immediate key release.
                # Cancel the lease separately, without erasing that first intent.
                self.release_requested.set()
            elif command == "jog":
                self.held_jog = (axis, value, time.monotonic() + 0.3)
            else:
                try:
                    self.commands.put_nowait((command, axis, value))
                except queue.Full as exc:
                    pending = self.commands.get_nowait()
                    if command == "relative" and pending[0] == "relative":
                        self.commands.put_nowait((command, axis, value))
                    else:
                        self.commands.put_nowait(pending)
                        raise RuntimeError("A motor command is already pending") from exc
        self.wake.set()

    def get_state(self):
        from copy import deepcopy
        import time
        with self.lock:
            state = deepcopy(self.snapshot)
            elapsed = time.monotonic() - self.received_at if self.received_at else 0
            for axis in state["axes"].values():
                axis["age"] = axis.get("age", 0) + elapsed
            return state

    def close(self):
        if self.closing.is_set():
            return
        self.closing.set()
        if self.thread.is_alive():
            self.submit("stop")
        else:
            self.context.term()

    def run(self):
        import time
        try:
            while True:
                self.wake.clear()
                with self.lock:
                    stopping = self.stop_requested.is_set()
                    if stopping:
                        command, axis, value = "stop", None, None
                    elif self.release_requested.is_set():
                        command, axis, value = "release_jog", None, None
                        self.release_requested.clear()
                    elif not self.commands.empty():
                        command, axis, value = self.commands.get_nowait()
                    elif self.held_jog and self.held_jog[2] > time.monotonic():
                        axis, value, expiry = self.held_jog
                        command = "jog"
                    else:
                        self.held_jog = None
                        command, axis, value = "state", None, None
                try:
                    if stopping:
                        state = self.request(command, axis, value, stop_reason=self.communication_stop_reason)
                    else:
                        state = self.request(command, axis, value)
                    with self.lock:
                        self.snapshot = state
                        self.received_at = time.monotonic()
                        if stopping:
                            self.stop_requested.clear()
                            self.communication_stop_reason = None
                    if self.closing.is_set() and stopping:
                        break
                except MotorCommandRejected as exc:
                    # A valid rejection is not a lost reply or a broken link.
                    with self.lock:
                        self.snapshot.update(error=str(exc), message="Command rejected")
                        self.held_jog = None
                        self.release_requested.set()
                except Exception as exc:
                    with self.lock:
                        waiting_for_initial_connection = (
                            isinstance(exc, TimeoutError)
                            and self.received_at is None and command == "state")
                        if not waiting_for_initial_connection and not self.stop_requested.is_set():
                            self.communication_stop_reason = f"Client {command} request failed: {exc}"
                        self.snapshot.update(connected=False, error=str(exc),
                            message="Waiting for motor server" if waiting_for_initial_connection else "Motion service unavailable")
                        self.held_jog = None
                        while not self.commands.empty():
                            self.commands.get_nowait()
                        # Initial state polls cannot have started a move. Once
                        # connected, or after any command attempt, request a stop
                        # before accepting work after a lost response.
                        if not waiting_for_initial_connection:
                            self.stop_requested.set()
                    if self.closing.is_set():
                        break
                self.wake.wait(0.1)
        finally:
            self.context.term()
