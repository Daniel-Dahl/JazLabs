"""Synchronous ZMQ motor client, used by scripts and the Tkinter widget.

Every call communicates directly with the server. GUI callbacks use wait=False
for moves; the widget's Tkinter timer handles status polling and held-key input.
"""
import math
import time
import uuid

import zmq


class MotorCommandRejected(RuntimeError):
    """The server replied but did not accept the requested command."""


class MotorisedStageClient:
    def __init__(self, host="127.0.0.1", command_port=50931, timeout_ms=500):
        self.endpoint = f"tcp://{host}:{int(command_port)}"
        self.timeout_ms = int(timeout_ms)
        self.context = zmq.Context()
        self.host = host
        self.command_port = command_port
        self.closed = False

    def request(self, command, axis=None, value=None, operation_id=None, stop_reason=None):
        if self.closed:
            raise RuntimeError("Motor client connection is closed")
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
        """Request the server's current status; feedback age comes from the server."""
        status = dict(self.request("state"))
        if axis is not None:
            if axis not in status["axes"]:
                raise ValueError(f"Unknown or unavailable axis {axis!r}")
            status["axes"] = {axis: status["axes"][axis]}
        return status

    def MoveAbs(self, axis, target, wait=True, timeout=None, units=None):
        """Move to an absolute target and wait for stopped feedback by default."""
        return self._submit_and_wait_for_motion("absolute", axis, target, wait, timeout, units)

    def MoveRel(self, axis, distance, wait=True, timeout=None, units=None):
        """Move by an increment using the driver's checked relative-move method."""
        return self._submit_and_wait_for_motion("relative", axis, distance, wait, timeout, units)

    def HomeAxis(self, axis, wait=True, timeout=None):
        """Home an axis and wait for stopped, referenced feedback by default."""
        return self._submit_and_wait_for_motion("home", axis, None, wait, timeout, None)

    def SetNominal(self, wait=True, timeout=None):
        """Move each axis to its limits' midpoint using the server's motion scheduler."""
        result = self._submit_and_wait_for_motion("nominal", None, None, wait, timeout, None)
        if not wait:
            return result

    def ConvertPosition(self, axis, value, from_units, to_units):
        """Convert using the calibration in this axis's status dictionary."""
        spec = self.GetStatus(axis)["axes"][axis]
        scales = spec.get("unit_scales", {spec["units"]: 1.0})
        if from_units not in scales or to_units not in scales:
            raise ValueError(f"{axis}: units unavailable; choose from {list(scales)}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Position must be finite")
        return value * scales[from_units] / scales[to_units]

    def _submit_and_wait_for_motion(self, command, axis, value, wait, timeout, units):
        """Share submission, completion tracking and stop-on-error across motion calls."""
        status = self.GetStatus(axis)
        if command not in ("home", "nominal"):
            spec = status["axes"][axis]
            value = float(value)
            if not math.isfinite(value):
                raise ValueError("Position must be finite")
            requested_units = spec["units"] if units is None else units
            scales = spec.get("unit_scales", {spec["units"]: 1.0})
            if requested_units not in scales:
                raise ValueError(f"{axis}: units {requested_units!r} unavailable")
            if requested_units == "counts" and value != int(value):
                raise ValueError("Counts must be integers")
            value = value * scales[requested_units] / scales[spec["units"]]
        if timeout is None:
            timeout = status.get("move_timeout", 60.0)
            if command == "nominal":
                timeout *= len(status["axes"])
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        operation_id = uuid.uuid4().hex
        stop_required = True
        try:
            self.request(command, axis, value, operation_id=operation_id)
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
                feedback = snapshot["axes"].values() if axis is None else [snapshot["axes"].get(axis)]
                for current in feedback:
                    if current is not None and (current.get("fault") or current.get("age", 999) >= 1):
                        raise RuntimeError(current.get("fault") or "Motor feedback is stale")
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

    def EnableAxis(self, axis, enabled=True):
        return self.request("enable", axis, bool(enabled))

    def StopAll(self, reason=None):
        return self.request("stop", stop_reason=reason)

    def SetSpeed(self, axis, value):
        return self.request("speed", axis, value)

    def CloseStage(self):
        """Close this client's connection; the hardware server remains running."""
        if not self.closed:
            self.closed = True
            self.context.term()
