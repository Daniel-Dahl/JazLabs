"""CONEX-AGAP controller for the two-axis AG-M100D mirror mount.
U/V positions are degrees; absolute sensors require no homing.

Pyserial: 921600 baud, 8N1, XON/XOFF, CRLF. Connection does not move
or configure the mount. Use one caller at a time for this driver/serial port;
multiple clients should communicate through the motor server.
"""
import enum
import math
import time

import serial


class Axes(enum.Enum):
    YAW = "U"
    PITCH = "V"


class NewportM100DSerialStage:
    def __init__(self, port, address=1, timeout=0.5, move_timeout=30.0, limits=None):
        if not 1 <= address <= 31 or int(address) != address:
            raise ValueError("address must be an integer in 1..31")
        if timeout <= 0 or move_timeout <= 0:
            raise ValueError("timeouts must be positive")
        self.port = port
        self.address = int(address)
        self.timeout = timeout
        self.move_timeout = move_timeout
        self.units = "deg"
        # Limits use the same physical units as position commands. Missing
        # limits allow readout, but movement must be explicitly configured.
        self.limits = {}
        for axis, endpoints in (limits or {}).items():
            if axis not in ("U", "V") or len(endpoints) != 2:
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
        axis = axis.value if isinstance(axis, Axes) else str(axis).upper()
        if axis not in ("U", "V"):
            raise ValueError("Use axis U/YAW or V/PITCH (Axes enum)")
        return axis

    def MoveAbs(self, axis, value, wait=True, timeout=None):
        """Move to an absolute position, checking limits and stopped feedback."""
        axis = self._axis_suffix(axis)
        suffix = axis
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
        axis = self._axis_suffix(axis)
        delta = float(value)
        if not math.isfinite(delta):
            raise ValueError("Displacement must be finite")
        status = self.GetStatus(axis)["axes"][axis]
        if status["fault"]:
            raise RuntimeError(status["fault"])
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before a relative move")
        if not status["enabled"]:
            raise RuntimeError("Enable this axis before moving")
        return self.MoveAbs(axis, status["position"] + delta, wait=wait, timeout=timeout)

    def SetNominal(self, wait=True):
        """Move both axes to the midpoints of their configured travel limits."""
        if any(axis not in self.limits for axis in ("U", "V")):
            raise ValueError("Configure travel limits for U and V before setting nominal")
        for axis in ("U", "V"):
            lower, upper = self.limits[axis]
            self.MoveAbs(axis, (lower + upper) / 2, wait=wait)

    def StopAll(self):
        self.write("ST")

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
        axes = ("U", "V") if axis is None else (self._axis_suffix(axis),)
        positions = {}
        for name in axes:
            response = self.query(f"TP{name}")
            position = float(response[len(f"{self.address}TP{name}"):])
            if not math.isfinite(position):
                raise RuntimeError(f"Invalid position feedback for {name}")
            positions[name] = position
        error, state = self._read_controller_status()
        ready = {0x32, 0x33, 0x34, 0x35, 0x36}
        result = {"controller": "CONEXAGAPSerial", "port": self.port,
                  "address": self.address, "baudrate": 921600, "timeout": self.timeout,
                  "move_timeout": self.move_timeout, "controller_state": state,
                  "controller_error": error, "axes": {}}
        for name, position in positions.items():
            result["axes"][name] = {
                "label": {"U": "Yaw U", "V": "Pitch V"}[name], "position": position, "units": self.units,
                "limits": list(self.limits.get(name, (None, None))),
                "resolution": .000001, "tolerance": .001, "step": .005,
                "supports": {"home": False, "stop": True, "speed": False},
                "moving": state in (0x1E, 0x28, 0x29, 0x46), "homing": state == 0x1E,
                "homed": None,
                "enabled": state in ready or state in (0x1E, 0x28, 0x29, 0x46),
                "fault": f"Positioner error 0x{error:04X}" if error else None,
                "speed": None}
        return result
