import time

import serial


class NewportAgilisAxis:
    """
    Single-axis serial Agilis helper.

    Client-style API:
      - GetProperties
      - GetPositions
      - MoveAbs
      - MoveRel
      - HomeAll (not supported)
      - SetNominal
      - CloseStage
    """

    def __init__(self, port: str, axis: int = 1, baudrate: int = 921600, timeout: float = 0.5):
        self.port = port
        self.axis = int(axis)
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)

        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        self._write("OR")
        self._write("HT4")

    def _write(self, cmd: str) -> None:
        self.ser.write(f"{self.axis}{cmd}\r\n".encode("ascii"))

    def _query(self, cmd: str) -> str:
        self._write(cmd)
        return self.ser.readline().decode("ascii", errors="ignore").strip()

    def get_status(self) -> int:
        resp = self._query("TS")
        for prefix in (f"{self.axis}TS", "TS"):
            if resp.startswith(prefix):
                return int(resp[len(prefix):])
        return int(resp)

    def wait_ready(self, poll_delay: float = 0.05, timeout: float = 30.0):
        t0 = time.time()
        while True:
            if self.get_status() == 0:
                return
            if time.time() - t0 > timeout:
                raise TimeoutError("Axis did not become ready in time.")
            time.sleep(poll_delay)

    def get_position(self) -> float:
        resp = self._query("TP")
        for prefix in (f"{self.axis}TP", "TP"):
            if resp.startswith(prefix):
                return float(resp[len(prefix):])
        return float(resp)

    def move_absolute(self, position: float, wait: bool = True):
        self._write(f"PA{float(position)}")
        diff = 10**12
        while diff > 0.005:
            current = self.get_position()
            diff = abs(current - position)
        if wait:
            self.wait_ready()

    def move_relative(self, delta_steps, wait: bool = True):
        self._write(f"PR{delta_steps}")
        if wait:
            self.wait_ready()

    def GetProperties(self):
        return {
            "stage_type": "NewportAgilisAxis",
            "port": self.port,
            "axis": self.axis,
            "baudrate": self.baudrate,
            "timeout": self.timeout,
            "units": "steps",
        }

    def GetPositions(self):
        return [self.get_position()]

    def MoveAbs(self, axis, value, wait: bool = True):
        _ = axis
        self.move_absolute(float(value), wait=wait)

    def MoveRel(self, axis, value, wait: bool = True):
        _ = axis
        self.move_relative(value, wait=wait)

    def HomeAll(self):
        raise NotImplementedError("HomeAll is not implemented for NewportAgilisAxis.")

    def SetNominal(self):
        self.MoveAbs(0, 0.0, wait=False)

    def CloseStage(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def stop(self):
        self._write("ST")
