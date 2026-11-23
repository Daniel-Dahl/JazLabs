import math
import time

import serial


class NewportESP300:
    """
    Serial driver for Newport ESP300 Motion Controller.

    Use one caller at a time for this driver/serial port.

    GetStatus returns configuration and live per-axis feedback together.
    """

    class HomeMode:
        ZERO = 0
        SWITCH_INDEX = 1
        SWITCH_ONLY = 2

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 1.0, axes=(1,),
                 limits=None, move_timeout: float = 60.0, tolerance: float = .001):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.axes = [int(a) for a in axes]
        self.move_timeout = float(move_timeout)
        self.tolerance = float(tolerance)
        if not math.isfinite(self.move_timeout) or self.move_timeout <= 0:
            raise ValueError("move_timeout must be positive and finite")
        if not math.isfinite(self.tolerance) or self.tolerance <= 0:
            raise ValueError("tolerance must be positive and finite")
        self.limits = {}
        for axis, endpoints in (limits or {}).items():
            axis = int(axis)
            if axis not in self.axes or len(endpoints) != 2:
                raise ValueError(f"Invalid travel limits for {axis}")
            lower, upper = map(float, endpoints)
            if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
                raise ValueError("Travel limits must be finite and minimum < maximum")
            self.limits[axis] = (lower, upper)

        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
            rtscts=True,
        )

        self.term = "\r"
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

    def _write(self, cmd: str):
        self.ser.write((cmd + self.term).encode("ascii"))

    def _read(self) -> str:
        return self.ser.readline().decode("ascii", errors="ignore").strip()

    def write_axis(self, axis: int, cmd: str):
        self._write(f"{axis}{cmd}")

    def query_axis(self, axis: int, cmd: str) -> str:
        self.write_axis(axis, cmd)
        return self._read()

    def _check_command_error(self):
        self._write("TE?")
        error = int(self._read())
        if error:
            raise RuntimeError(f"ESP300 controller error {error}")

    def GetStatus(self, axis=None):
        """Read configured axes, or one selected axis, into a single dictionary."""
        selected_axes = self.axes if axis is None else [int(axis)]
        if any(name not in self.axes for name in selected_axes):
            raise ValueError(f"Unknown axis {axis}")
        result = {"controller": "NewportESP300", "port": self.port,
                  "baudrate": self.baudrate, "timeout": self.timeout,
                  "move_timeout": self.move_timeout, "axes": {}}
        for name in selected_axes:
            done = self.query_axis(name, "MD?")
            if done not in ("0", "1"):
                raise RuntimeError(f"Invalid ESP300 motion status: {done!r}")
            position = float(self.query_axis(name, "TP?"))
            if not math.isfinite(position):
                raise RuntimeError(f"Invalid position feedback for {name}")
            result["axes"][str(name)] = {
                "label": str(name), "position": position, "units": "controller_units",
                "limits": list(self.limits.get(name, (None, None))),
                "tolerance": self.tolerance,
                "supports": {"home": True, "stop": True, "speed": False},
                "moving": done == "0", "homing": None, "homed": None,
                "enabled": None, "speed": None}
        self._write("TE?")
        error = int(self._read())
        result["controller_error"] = error
        for feedback in result["axes"].values():
            feedback["fault"] = f"ESP300 controller error {error}" if error else None
        return result

    def _wait_until_done(self, axis, timeout, target=None):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            status = self.GetStatus(axis)["axes"][str(axis)]
            if status["fault"]:
                raise RuntimeError(status["fault"])
            if not status["moving"]:
                if target is None or abs(status["position"] - target) <= self.tolerance:
                    return status
        raise TimeoutError(f"Axis {axis} motion timeout")

    def _set_home_mode(self, axis: int, mode: int):
        if mode not in (0, 1, 2):
            raise ValueError("Invalid home mode")
        self.write_axis(axis, f"OM{mode}")

    def HomeAxis(self, axis: int, mode: int = 1, wait: bool = True, timeout: float = 120.0):
        axis = int(axis)
        if axis not in self.axes:
            raise ValueError(f"Unknown axis {axis}")
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        self._set_home_mode(axis, mode)
        self.write_axis(axis, "OR")
        if wait:
            try:
                self._wait_until_done(axis, timeout=timeout)
            except Exception:
                self.StopAll()
                raise

    def StopAll(self):
        for axis in self.axes:
            self.write_axis(axis, "ST")

    def MoveAbs(self, axis, value, wait=True, timeout=None):
        """Move within configured limits and verify stopped position feedback."""
        axis = int(axis)
        target = float(value)
        if axis not in self.axes:
            raise ValueError(f"Unknown axis {axis}")
        if not math.isfinite(target):
            raise ValueError("Position must be finite")
        if axis not in self.limits:
            raise ValueError(f"Configure travel limits for {axis} before moving")
        lower, upper = self.limits[axis]
        if not lower <= target <= upper:
            raise ValueError(f"Target is outside {axis} travel limits [{lower}, {upper}]")
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        try:
            self.write_axis(axis, f"PA{target}")
            self._check_command_error()
            if wait:
                return self._wait_until_done(axis, timeout=timeout, target=target)
        except Exception as exc:
            try:
                self.StopAll()
            except Exception as stop_exc:
                raise RuntimeError(f"{exc}; stop could not be confirmed: {stop_exc}") from exc
            raise

    def MoveRel(self, axis, value, wait=True, timeout=None):
        axis = int(axis)
        delta = float(value)
        if axis not in self.axes:
            raise ValueError(f"Unknown axis {axis}")
        if not math.isfinite(delta):
            raise ValueError("Displacement must be finite")
        status = self.GetStatus(axis)["axes"][str(axis)]
        if status["fault"]:
            raise RuntimeError(status["fault"])
        if status["moving"]:
            raise RuntimeError("Wait for this axis to stop before a relative move")
        target = status["position"] + delta
        return self.MoveAbs(axis, target, wait=wait, timeout=timeout)

    def HomeAll(self):
        for a in self.axes:
            self.HomeAxis(a, mode=self.HomeMode.SWITCH_INDEX, wait=True)

    def SetNominal(self, wait=True):
        """Move each configured axis to the midpoint of its travel limits."""
        if any(axis not in self.limits for axis in self.axes):
            raise ValueError("Configure travel limits for all axes before setting nominal")
        for axis in self.axes:
            lower, upper = self.limits[axis]
            self.MoveAbs(axis, (lower + upper) / 2, wait=wait)

    def CloseStage(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.CloseStage()
