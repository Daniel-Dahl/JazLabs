"""Single-axis CONEX-AGP controller with encoder feedback.
Positions use the fitted stage's configured physical units.

Pyserial: 921600 baud, 8N1, XON/XOFF, CRLF. Connection does not move
or configure the mount. Use one caller at a time for this driver/serial port;
multiple clients should communicate through the motor server.
"""
import math
import time

import serial


class NewportAGPSerialStage:
    def __init__(self, port, address=1, timeout=0.5, move_timeout=30.0,
                 units="stage_units", limits=None):
        if not 1 <= address <= 31 or int(address) != address:
            raise ValueError("address must be an integer in 1..31")
        if timeout <= 0 or move_timeout <= 0:
            raise ValueError("timeouts must be positive")
        self.port = port
        self.address = int(address)
        self.timeout = timeout
        self.move_timeout = move_timeout
        self.units = units
        # Limits use the same physical units as position commands. Missing
        # limits allow readout, but movement must be explicitly configured.
        self.limits = {}
        for axis, endpoints in (limits or {}).items():
            if axis not in ("X",) or len(endpoints) != 2:
                raise ValueError(f"Invalid travel limits for {axis}")
            lower, upper = map(float, endpoints)
            if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
                raise ValueError("Travel limits must be finite and minimum < maximum")
            self.limits[axis] = (lower, upper)
        self.serial = serial.Serial(port=port, baudrate=921600, timeout=timeout,
                                    write_timeout=timeout, xonxoff=True,
                                    bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE)

    def write(self, body):
        if '\r' in body or '\n' in body:
            raise ValueError("Command must not contain a line terminator")
        self.serial.write(f"{self.address}{body}\r\n".encode("ascii"))

    def query(self, body):
        self.write(body)
        reply = self.serial.read_until(b"\r\n")
        if not reply.endswith(b"\r\n"):
            raise TimeoutError(f"Incomplete CONEX reply to {body}: {reply!r}")
        response = reply.decode("ascii").strip()
        prefix = f"{self.address}{body.rstrip('?')}"
        if not response.startswith(prefix):
            raise RuntimeError(f"Expected {prefix!r}, received {response!r}")
        return response

    def _check_command_error(self):
        response = self.query("TE")
        error = response[len(f"{self.address}TE"):]
        if error != "@":
            raise RuntimeError(f"CONEX rejected command: error {error!r}")

    def _read_controller_status(self):
        """Decode TS for GetStatus and controller-specific home/stop checks."""
        response = self.query("TS")
        value = response[len(f"{self.address}TS"):]
        if len(value) != 6:
            raise RuntimeError(f"Malformed CONEX status: {response!r}")
        return int(value[:4], 16), int(value[4:], 16)

    def _axis_suffix(self, axis):
        if axis not in (0, 1, "X", "x"):
            raise ValueError("Single axis: use 0, 1 or X")
        return ""

    def MoveAbs(self, axis, value, wait=True, timeout=None):
        """Move to an absolute position, checking limits and stopped feedback."""
        suffix = self._axis_suffix(axis)
        axis = "X"
        target = float(value)
        if not math.isfinite(target):
            raise ValueError("Position must be finite")
        if axis not in self.limits:
            raise ValueError(f"Configure travel limits for {axis} before moving")
        lower, upper = self.limits[axis]
        # Validate both the requested target and the value sent on the wire.
        command_target = float(f"{target:.9g}")
        if not lower <= target <= upper or not lower <= command_target <= upper:
            raise ValueError(f"Target is outside {axis} travel limits [{lower}, {upper}]")
        target = command_target
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        tolerance = .001
        try:
            self.write(f"PA{suffix}{target:.9g}")
            self._check_command_error()
            if not wait:
                return None
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                status = self.GetStatus(axis)["axes"][axis]
                if status["fault"]:
                    raise RuntimeError(status["fault"])
                if not status["enabled"]:
                    raise RuntimeError("Axis disabled before the target was reached")
                if (not status["moving"] and not status["homing"]
                        and abs(status["position"] - target) <= tolerance):
                    return status
            raise TimeoutError(f"{axis} did not finish its move within {timeout:g} s")
        except Exception as exc:
            try:
                self.StopAll()
            except Exception as stop_exc:
                raise RuntimeError(f"{exc}; stop could not be confirmed: {stop_exc}") from exc
            raise

    def MoveRel(self, axis, value, wait=True, timeout=None):
        """Check the relative destination using the same absolute move path."""
        self._axis_suffix(axis)
        axis = "X"
        delta = float(value)
        if not math.isfinite(delta):
            raise ValueError("Displacement must be finite")
        status = self.GetStatus(axis)["axes"][axis]
        if status["fault"]:
            raise RuntimeError(status["fault"])
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before a relative move")
        if not status["homed"]:
            raise RuntimeError("Home this axis before a relative move")
        if not status["enabled"]:
            raise RuntimeError("Enable this axis before moving")
        return self.MoveAbs(axis, status["position"] + delta, wait=wait, timeout=timeout)

    def HomeAxis(self, axis="X", wait=True, timeout=None):
        self._axis_suffix(axis)
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        error, state = self._read_controller_status()
        if error:
            raise RuntimeError(f"CONEX positioner error 0x{error:04X}")
        if state in (0x32, 0x33, 0x34, 0x3C, 0x3D):
            return  # Already referenced; OR is rejected in READY/DISABLE.
        if state != 0x1E:
            if not 0x0A <= state <= 0x10:
                raise RuntimeError(f"Cannot home CONEX in controller state 0x{state:02X}")
            self.write("OR")
            self._check_command_error()
        if not wait:
            return
        deadline = time.perf_counter() + timeout
        try:
            while time.perf_counter() < deadline:
                error, state = self._read_controller_status()
                if error:
                    raise RuntimeError(f"CONEX positioner error 0x{error:04X}")
                if state in (0x32, 0x33, 0x34):
                    return
                if state != 0x1E:
                    raise RuntimeError(f"CONEX is not ready: state 0x{state:02X}")
            raise TimeoutError("CONEX did not become ready before the move timeout")
        except Exception as exc:
            try:
                self.StopAll()
            except Exception as stop_exc:
                raise RuntimeError(f"{exc}; stop could not be confirmed: {stop_exc}") from exc
            raise

    def SetNominal(self, wait=True):
        """Move to the midpoint of the configured X travel limits."""
        if "X" not in self.limits:
            raise ValueError("Configure travel limits for X before setting nominal")
        lower, upper = self.limits["X"]
        return self.MoveAbs("X", (lower + upper) / 2, wait=wait)

    def StopAll(self):
        # Send the stop immediately, without delaying it for a status query.
        self.write("ST")
        response = self.query("TE")
        error = response[len(f"{self.address}TE"):]
        if error == "@":
            return
        # ST is valid only during motion. Consume its error so an idle
        # stop cannot leave a rejection for the next move to read.
        if error in ("H", "I", "J", "K"):
            positioner_error, state = self._read_controller_status()
            already_idle = (
                (error == "H" and 0x0A <= state <= 0x10)
                or (error == "I" and state == 0x14)
                or (error == "J" and state in (0x3C, 0x3D))
                or (error == "K" and state in (0x32, 0x33, 0x34)))
            if positioner_error:
                raise RuntimeError(f"CONEX stop reported positioner error 0x{positioner_error:04X}")
            if already_idle:
                return
            raise RuntimeError(f"CONEX rejected ST: error {error!r}, controller state 0x{state:02X}")
        raise RuntimeError(f"CONEX rejected ST: error {error!r}")

    def EnableAxis(self, axis, enabled=True):
        self._axis_suffix(axis)
        self.write(f"MM{int(bool(enabled))}")

    def CloseStage(self):
        if self.serial.is_open:
            self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.CloseStage()

    def GetStatus(self, axis=None):
        """Read live feedback and return it with configuration in one dictionary.

        Omit axis to read every axis. Selecting one axis retains the same shape
        and lets the server handle network requests between serial transactions.
        """
        if axis is not None:
            self._axis_suffix(axis)
        axes = ("X",)
        positions = {}
        for name in axes:
            response = self.query("TP")
            position = float(response[len(f"{self.address}TP"):])
            if not math.isfinite(position):
                raise RuntimeError(f"Invalid position feedback for {name}")
            positions[name] = position
        error, state = self._read_controller_status()
        ready = {0x32, 0x33, 0x34}
        result = {"controller": "CONEXAGPSerial", "port": self.port,
                  "address": self.address, "baudrate": 921600, "timeout": self.timeout,
                  "move_timeout": self.move_timeout, "controller_state": state,
                  "controller_error": error, "axes": {}}
        for name, position in positions.items():
            result["axes"][name] = {
                "label": name, "position": position, "units": self.units,
                "limits": list(self.limits.get(name, (None, None))),
                "resolution": .000001, "tolerance": .001, "step": .01,
                "supports": {"home": True, "home_when_referenced": False, "stop": True, "speed": False},
                "moving": state in (0x1E, 0x28, 0x29, 0x46), "homing": state == 0x1E,
                "homed": state in ready or state in (0x28, 0x3C, 0x3D),
                "enabled": state in ready or state in (0x1E, 0x28, 0x29, 0x46) or 0x0A <= state <= 0x10,
                "fault": f"Positioner error 0x{error:04X}" if error else None,
                "speed": None}
        return result
