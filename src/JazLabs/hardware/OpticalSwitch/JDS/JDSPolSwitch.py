# pip install pyserial
import serial
import time
from typing import Optional

class OpticalSwitchObject:
    """
    JDSU SC-Series fibre-optic switch (SC-C/SC-D/SC-E/SC-F) RS-232 controller.

    Protocol:
      - 1200 baud, 8N1, no parity
      - Commands end with CR ('\\r')
      - Responses are ASCII, typically end with CR too
    """
    def __init__(self, port: str, timeout: float = 2.0, rtscts: bool = True, dsrdtr: bool = True):
        self.ser = serial.Serial(
            port=port,
            baudrate=1200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            rtscts=rtscts,   # CTS/RTS handshaking (recommended by pinout)
            dsrdtr=dsrdtr,   # Some USB dongles like DSR/DTR asserted
            write_timeout=timeout,
        )

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def _write(self, cmd: str) -> None:
        """Send a single command (auto-append CR)."""
        if not cmd.endswith("\r"):
            cmd = cmd + "\r"
        self.ser.reset_input_buffer()
        self.ser.write(cmd.encode("ascii"))

    def _ask(self, cmd: str, strip: bool = True) -> str:
        """Send a command and read a single line terminated by CR."""
        self._write(cmd)
        # The switch terminates with CR; read until CR or timeout
        resp = self.ser.read_until(b"\r")
        text = resp.decode("ascii", errors="replace")
        return text.strip("\r\n") if strip else text

    # ----------- High-level controls ------------

    def set_channel(self, n: int, wait_settle: bool = True, settle_timeout: float = 10.0) -> None:
        """
        Route COMMON -> channel n (0 = open). Optionally wait until the mechanism settles.
        For dual-common models, this sets/returns the B path position (A = B-1 on SC-E; see manual).
        """
        if n < 0:
            raise ValueError("Channel must be >= 0")
        self._write(f"CLOSE {n}")
        if wait_settle:
            self.wait_until_settled(timeout=settle_timeout)

    def get_channel(self) -> Optional[int]:
        """
        Return current path for 'CLOSE?' (B path for dual-common units).
        Returns None if response is empty/unexpected.
        """
        resp = self._ask("CLOSE?")
        try:
            return int(resp)
        except (ValueError, TypeError):
            return None

    def max_channel(self) -> Optional[int]:
        resp = self._ask("CLOSE? MAX")
        try:
            return int(resp)
        except (ValueError, TypeError):
            return None

    def min_channel(self) -> Optional[int]:
        resp = self._ask("CLOSE? MIN")
        try:
            return int(resp)
        except (ValueError, TypeError):
            return None

    def get_status_register(self) -> Optional[int]:
        """
        STB? returns an integer status byte. Bit 2 == 1 when 'settled'.
        Note: STB? also clears the register if SRQ bit was set.
        """
        resp = self._ask("STB?")
        try:
            return int(resp)
        except (ValueError, TypeError):
            return None

    def is_settled(self) -> bool:
        sr = self.get_status_register()
        if sr is None:
            return False
        # Bit 2 == 1 means 'settled'
        return bool(sr & (1 << 2))

    def wait_until_settled(self, timeout: float = 10.0, poll_interval: float = 0.1) -> None:
        """
        Poll STB? until settled bit is 1 or timeout occurs.
        """
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.is_settled():
                return
            time.sleep(poll_interval)
        raise TimeoutError("Switch did not report 'settled' before timeout")

    # ----------- Driver outputs (optional) ------------

    def set_driver(self, i: int, on: bool) -> None:
        """
        Control a single driver (1..8). on=True -> 1, on=False -> 0.
        """
        if not (1 <= i <= 8):
            raise ValueError("Driver index must be 1..8")
        self._write(f"XDR {i} {1 if on else 0}")

    def set_drivers_mask(self, mask: int) -> None:
        """
        Set all 8 drivers at once using the binary-weighted mask (0..255).
        """
        if not (0 <= mask <= 255):
            raise ValueError("Mask must be in 0..255")
        self._write(f"XDRS {mask}")

    def get_drivers_mask(self) -> Optional[int]:
        resp = self._ask("XDRS?")
        try:
            return int(resp)
        except (ValueError, TypeError):
            return None

    # ----------- Utility ------------

    def idn(self) -> str:
        return self._ask("IDN?")

    def reset(self) -> None:
        self._write("RESET")

