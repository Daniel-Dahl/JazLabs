import time

import pyvisa
from pyvisa import constants as pv


class AgilisUC8Stage:
    """
    AG-UC8 single-axis helper.

    Client-style API:
      - GetProperties
      - GetPositions
      - MoveAbs
      - MoveRel
      - HomeAll (not supported)
      - SetNominal
      - CloseStage
    """

    def __init__(self, resource_name: str, channel: int = 1, motor: int = 1, travel_mm: float = 12.0, timeout: float = 0.5):
        if not (1 <= int(motor) <= 8):
            raise ValueError("motor must be in [1..8] for AG-UC8")

        self.resource_name = resource_name
        self.channel = int(channel)
        self.motor = int(motor)
        self.axis = 1
        self.travel_mm = travel_mm
        self.default_timeout_ms = int(timeout * 1000)

        self.rm = pyvisa.ResourceManager("@py")
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = self.default_timeout_ms

        self.inst.baud_rate = 921600
        self.inst.data_bits = 8
        self.inst.stop_bits = pv.StopBits.one
        self.inst.parity = pv.Parity.none
        self.inst.flow_control = pv.VI_ASRL_FLOW_NONE

        self.inst.write_termination = "\r\n"
        self.inst.read_termination = "\r\n"

        self._ensure_remote()
        self._select_channel()

    def _ensure_remote(self):
        try:
            self.inst.write("MR")
        except Exception:
            pass

    def _select_channel(self):
        self._ensure_remote()
        self.inst.write(f"CC{self.channel}")

    def _write_axis(self, cmd: str):
        self.inst.write(f"{self.axis}{cmd}")

    def _query_axis(self, cmd: str) -> str:
        self._select_channel()
        return self.inst.query(f"{self.axis}{cmd}").strip()

    def get_stepsFromZero(self, retries=20, delay=0.05):
        for _ in range(retries):
            try:
                self.inst.write(f"{self.axis}TP")
                reply = self.inst.read().strip()
                if "TP" in reply:
                    for prefix in (f"{self.axis}TP", "TP", "TTP"):
                        if reply.startswith(prefix):
                            return int(reply[len(prefix):])
                time.sleep(delay)
            except Exception:
                time.sleep(delay)
        raise TimeoutError(f"Failed to get valid TP response after {retries} tries")

    def move_relative_steps(self, nsteps: int):
        self.inst.write(f"{self.axis}PR{int(nsteps)}")
        previous = self.get_stepsFromZero()
        diff = 10**12
        while diff > 2:
            current = self.get_stepsFromZero()
            diff = abs(current - previous)
            previous = current
        return self.get_stepsFromZero()

    def move_absolute_1000(self, pos_1000: int, timeout: float = 120.0):
        if not (0 <= int(pos_1000) <= 1000):
            raise ValueError("pos_1000 must be in [0..1000]")
        self._ensure_remote()
        self._select_channel()
        old_timeout = self.inst.timeout
        self.inst.timeout = int(timeout * 1000)
        try:
            self.inst.write(f"{self.axis}PA{int(pos_1000)}")
            reply = self.inst.read().strip()
        finally:
            self.inst.timeout = old_timeout

        for prefix in (f"{self.axis}PA", "PA"):
            if reply.startswith(prefix):
                return int(reply[len(prefix):])
        raise RuntimeError(f"Unexpected PA reply: {reply!r}")

    def GetProperties(self):
        return {
            "stage_type": "AgilisUC8Stage",
            "resource_name": self.resource_name,
            "channel": self.channel,
            "motor": self.motor,
            "axis": self.axis,
            "travel_mm": self.travel_mm,
            "units": "steps_from_zero",
        }

    def GetPositions(self):
        return [float(self.get_stepsFromZero())]

    def MoveAbs(self, axis, value, wait: bool = True):
        # axis argument accepted for API consistency; single-axis object
        _ = axis
        self.move_absolute_1000(int(value))

    def MoveRel(self, axis, value, wait: bool = True):
        _ = axis
        self.move_relative_steps(int(value))

    def HomeAll(self):
        raise NotImplementedError("HomeAll is not implemented for AgilisUC8Stage.")

    def SetNominal(self):
        self.MoveAbs(0, 0, wait=False)

    def CloseStage(self):
        try:
            self.inst.close()
        except Exception:
            pass
        try:
            self.rm.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.CloseStage()
