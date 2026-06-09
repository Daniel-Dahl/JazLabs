import time

import serial


class NewportESP300:
    """
    Serial driver for Newport ESP300 Motion Controller.

    Client-style API:
      - GetProperties
      - GetPositions
      - MoveAbs
      - MoveRel
      - HomeAll
      - SetNominal
      - CloseStage
    """

    class HomeMode:
        ZERO = 0
        SWITCH_INDEX = 1
        SWITCH_ONLY = 2

    def __init__(self, port: str, baudrate: int = 19200, timeout: float = 1.0, axes=(1,)):
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.axes = [int(a) for a in axes]

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

    def motion_done(self, axis: int) -> bool:
        return self.query_axis(axis, "MD").endswith("1")

    def wait_until_done(self, axis: int, poll_interval: float = 0.05, timeout: float = 60.0):
        t0 = time.time()
        while True:
            if self.motion_done(axis):
                return
            if time.time() - t0 > timeout:
                raise TimeoutError(f"Axis {axis} motion timeout")
            time.sleep(poll_interval)

    def move_abs(self, axis: int, pos: float, wait: bool = True):
        self.write_axis(axis, f"PA{pos}")
        if wait:
            self.wait_until_done(axis)

    def move_rel(self, axis: int, delta: float, wait: bool = True):
        self.write_axis(axis, f"PR{delta}")
        if wait:
            self.wait_until_done(axis)

    def get_position(self, axis: int) -> float:
        resp = self.query_axis(axis, "TP")
        return float(resp.split()[-1])

    def set_home_mode(self, axis: int, mode: int):
        if mode not in (0, 1, 2):
            raise ValueError("Invalid home mode")
        self.write_axis(axis, f"OM{mode}")

    def home(self, axis: int, mode: int = 1, wait: bool = True, timeout: float = 120.0):
        self.set_home_mode(axis, mode)
        self.write_axis(axis, "OR")
        if wait:
            self.wait_until_done(axis, timeout=timeout)

    def GetProperties(self):
        return {
            "stage_type": "NewportESP300",
            "port": self.port,
            "axes": self.axes,
            "baudrate": self.baudrate,
            "timeout": self.timeout,
            "units": "controller_units",
        }

    def GetPositions(self):
        return {str(a): self.get_position(a) for a in self.axes}

    def MoveAbs(self, axis, value, wait: bool = True):
        self.move_abs(int(axis), float(value), wait=wait)

    def MoveRel(self, axis, value, wait: bool = True):
        self.move_rel(int(axis), float(value), wait=wait)

    def HomeAll(self):
        for a in self.axes:
            self.home(a, mode=self.HomeMode.SWITCH_INDEX, wait=True)

    def SetNominal(self):
        for a in self.axes:
            self.MoveAbs(a, 0.0, wait=False)

    def CloseStage(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.CloseStage()
