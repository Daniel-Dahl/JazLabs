"""Single-axis CONEX-AGP controller with encoder feedback.
Positions use the fitted stage's configured physical units.

Pyserial: 921600 baud, 8N1, XON/XOFF, CRLF. Connection does not move
or configure the mount.
"""
import math
import threading
import time

import serial


class NewportAGPSerialStage:
    def __init__(self, port, address=1, timeout=0.5, move_timeout=30.0,
                 units="stage_units"):
        if not 1 <= address <= 31 or int(address) != address:
            raise ValueError("address must be an integer in 1..31")
        if timeout <= 0 or move_timeout <= 0:
            raise ValueError("timeouts must be positive")
        self.port = port
        self.address = int(address)
        self.timeout = timeout
        self.move_timeout = move_timeout
        self.units = units
        self._lock = threading.RLock()
        self.serial = serial.Serial(port=port, baudrate=921600, timeout=timeout,
                                    write_timeout=timeout, xonxoff=True,
                                    bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE)

    def write(self, body):
        if '\r' in body or '\n' in body:
            raise ValueError("Command must not contain a line terminator")
        with self._lock:
            self.serial.write(f"{self.address}{body}\r\n".encode("ascii"))

    def query(self, body):
        with self._lock:
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

    def GetStatus(self):
        response = self.query("TS")
        value = response[len(f"{self.address}TS"):]
        if len(value) != 6:
            raise RuntimeError(f"Malformed CONEX status: {response!r}")
        return {"error": int(value[:4], 16), "state": int(value[4:], 16)}

    def get_status_raw(self):
        return self.query("TS")

    def is_ready(self):
        status = self.GetStatus()
        if status["error"]:
            raise RuntimeError(f"CONEX positioner error 0x{status['error']:04X}")
        ready_states = {0x32, 0x33, 0x34}
        if status["state"] in ready_states:
            return True
        moving_states = {0x1E, 0x28}
        if status["state"] not in moving_states:
            raise RuntimeError(f"CONEX is not ready: state 0x{status['state']:02X}")
        return False

    def wait_until_ready(self, poll_period=0.05, timeout=None):
        if poll_period <= 0:
            raise ValueError("poll_period must be positive")
        deadline = time.monotonic() + (self.move_timeout if timeout is None else timeout)
        with self._lock:
            while time.monotonic() < deadline:
                if self.is_ready():
                    return True
                time.sleep(poll_period)
        raise TimeoutError("CONEX did not become ready before the move timeout")

    def _axis_suffix(self, axis):
        if axis not in (0, 1, "X", "x"):
            raise ValueError("Single axis: use 0, 1 or X")
        return ""

    def GetPositions(self):
        with self._lock:
            response = self.query("TP")
            return [float(response[len(f"{self.address}TP"):])]

    def MoveAbs(self, axis, value, wait=True):
        suffix = self._axis_suffix(axis)
        if not math.isfinite(float(value)):
            raise ValueError("Position must be finite")
        with self._lock:
            self.write(f"PA{suffix}{float(value):.9g}")
            self._check_command_error()
            if wait:
                self.wait_until_ready()

    def MoveRel(self, axis, value, wait=True):
        suffix = self._axis_suffix(axis)
        if not math.isfinite(float(value)):
            raise ValueError("Displacement must be finite")
        with self._lock:
            self.write(f"PR{suffix}{float(value):.9g}")
            self._check_command_error()
            if wait:
                self.wait_until_ready()

    def HomeAll(self, wait=True):
        with self._lock:
            self.write("OR")
            self._check_command_error()
            if wait:
                self.wait_until_ready()

    def SetNominal(self, wait=True):
        self.MoveAbs(0, 0, wait=wait)

    def Stop(self):
        self.write("ST")

    def Enable(self, enabled=True):
        self.write(f"MM{int(bool(enabled))}")

    def GetProperties(self):
        return {"stage_type": "CONEXAGPSerial", "port": self.port,
                "address": self.address, "baudrate": 921600, "timeout": self.timeout,
                "move_timeout": self.move_timeout, "units": self.units,
                "axes": ["X"]}

    def CloseStage(self):
        with self._lock:
            if self.serial.is_open:
                self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.CloseStage()

    def GetMotionCapabilities(self):
        capabilities = []
        for axis in ("X",):
            capabilities.append({"id": axis, "label": axis, "units": self.units,
                "minimum": None, "maximum": None, "resolution": .000001, "tolerance": .001,
                "step": .01, "home": True, "stop": True, "speed": False})
        return capabilities

    def GetAxisState(self, axis):
        suffix = self._axis_suffix(axis)
        with self._lock:
            response = self.query(f"TP{suffix}")
            position = float(response[len(f"{self.address}TP{suffix}"):])
            status = self.GetStatus()
        state = status["state"]
        ready = {0x32, 0x33, 0x34}
        referenced = ready | {0x28, 0x3C, 0x3D}
        return {"position": position, "moving": state in (0x1E, 0x28, 0x29, 0x46),
                "homing": state == 0x1E, "homed": state in referenced,
                "enabled": state in ready or state in (0x1E, 0x28, 0x29, 0x46) or 0x0A <= state <= 0x10,
                "fault": f"Positioner error 0x{status['error']:04X}" if status["error"] else None,
                "speed": None}

    def MoveTo(self, axis, target):
        self.MoveAbs(axis, target, wait=False)

    def HomeAxis(self, axis):
        self._axis_suffix(axis)
        self.HomeAll(wait=False)

    def EnableAxis(self, axis):
        self._axis_suffix(axis)
        self.Enable(True)

    def StopAll(self):
        self.Stop()
