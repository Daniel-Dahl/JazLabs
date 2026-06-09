import enum
import time

import pyvisa
from pyvisa import constants as vc


class Axes(enum.Enum):
    YAW = "U"
    PITCH = "V"


class NewportM100D_VISA:
    """
    PyVISA driver for Newport CONEX-AG-M100D (CONEX-AGAP controller).

    Client-style API:
      - GetProperties
      - GetPositions
      - MoveAbs
      - MoveRel
      - HomeAll (not supported)
      - SetNominal
      - CloseStage
    """

    def __init__(self, resource: str, address: int = 1, timeout_ms: int = 500, backend: str = "@py"):
        self.address = int(address)
        self.resource = resource
        self.backend = backend
        self.timeout_ms = int(timeout_ms)

        self.rm = pyvisa.ResourceManager(backend)
        self.inst = self.rm.open_resource(resource)

        self.inst.baud_rate = 921600
        self.inst.data_bits = 8
        self.inst.parity = vc.Parity.none
        self.inst.stop_bits = vc.StopBits.one
        self.inst.flow_control = vc.VI_ASRL_FLOW_XON_XOFF

        self.inst.write_termination = "\r\n"
        self.inst.read_termination = "\r\n"
        self.inst.timeout = self.timeout_ms

    def _build_cmd(self, body: str) -> str:
        return f"{self.address}{body}"

    def write(self, body: str):
        self.inst.write(self._build_cmd(body))

    def query(self, body: str) -> str:
        return self.inst.query(self._build_cmd(body)).strip()

    def get_status_raw(self) -> str:
        return self.query("TS")

    def is_ready(self) -> bool:
        ts = self.get_status_raw()
        if len(ts) < 2:
            return False
        state_hex = ts[-2:]
        moving_states = {"28", "29", "46"}
        return state_hex not in moving_states

    def wait_until_ready(self, poll_period=0.05, timeout=5.0):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_ready():
                return True
            time.sleep(poll_period)
        return False

    def _get_position_axis(self, axis: str = "U") -> float:
        resp = self.query(f"TP{axis}")
        return float(resp.split(axis)[-1])

    def GetProperties(self):
        return {
            "stage_type": "NewportM100D_VISA",
            "resource": self.resource,
            "address": self.address,
            "backend": self.backend,
            "timeout_ms": self.timeout_ms,
            "axes": ["U", "V"],
            "units": "deg",
        }

    def GetPositions(self):
        return {"U": self._get_position_axis("U"), "V": self._get_position_axis("V")}

    def MoveAbs(self, axis, value, wait: bool = True):
        ax = str(axis).upper()
        if ax not in ("U", "V"):
            raise ValueError("Invalid axis. Valid: 'U', 'V'")
        cmd = f"PA{ax}{float(value):.6f}"
        self.write(cmd)
        if wait and not self.wait_until_ready():
            raise TimeoutError("Timeout waiting for absolute move to finish")

    def MoveRel(self, axis, value, wait: bool = True):
        ax = str(axis).upper()
        if ax not in ("U", "V"):
            raise ValueError("Invalid axis. Valid: 'U', 'V'")
        cmd = f"PR{ax}{float(value):.6f}"
        self.write(cmd)
        if wait and not self.wait_until_ready():
            raise TimeoutError("Timeout waiting for relative move to finish")

    def HomeAll(self):
        raise NotImplementedError("HomeAll is not implemented for NewportM100D_VISA.")

    def SetNominal(self):
        self.MoveAbs("U", 0.0, wait=False)
        self.MoveAbs("V", 0.0, wait=False)

    def CloseStage(self):
        try:
            self.inst.close()
        except Exception:
            pass
        try:
            self.rm.close()
        except Exception:
            pass

    def __del__(self):
        self.CloseStage()
