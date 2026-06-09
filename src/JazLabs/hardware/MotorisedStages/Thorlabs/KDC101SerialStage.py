"""
Simple serial (APT protocol) control for a Thorlabs KDC101.

Method names are aligned to MotorisedStage_Client style.
"""

import struct
import time

import serial

__all__ = ["KDC101SerialStage"]


class KDC101SerialStage:
    """
    Control a single-channel KDC101 using APT messages over serial.

    Notes
    -----
    - Uses native controller position counts.
    - Axis is single-channel. Accepted axis values: 0, 1, "1", "X", "U".
    """

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.25) -> None:
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)

        # APT routing bytes for single USB device
        self.source = 0x01
        self.destination = 0x50

        # Message IDs
        self.MGMSG_HW_NO_FLASH_PROGRAMMING = 0x0018
        self.MGMSG_MOT_REQ_POSCOUNTER = 0x0411
        self.MGMSG_MOT_GET_POSCOUNTER = 0x0412
        self.MGMSG_MOT_MOVE_HOME = 0x0443
        self.MGMSG_MOT_MOVE_RELATIVE = 0x0448
        self.MGMSG_MOT_MOVE_ABSOLUTE = 0x0453
        self.MGMSG_MOT_MOVE_COMPLETED = 0x0464

        self.channel = 1  # KDC101 single channel

        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        # Required startup message
        msg = struct.pack(
            "<HBBBB",
            self.MGMSG_HW_NO_FLASH_PROGRAMMING,
            0x00,
            0x00,
            self.destination,
            self.source,
        )
        self.serial.write(msg)
        time.sleep(0.05)

        # Prime comms
        self.GetPositions()

    def __del__(self):
        try:
            self.CloseStage()
        except Exception:
            pass

    def _read_exact(self, nbytes: int) -> bytes:
        data = self.serial.read(nbytes)
        if len(data) != nbytes:
            raise TimeoutError(f"Timed out reading {nbytes} bytes (got {len(data)})")
        return data

    def _check_axis(self, axis):
        valid = {0, 1, "0", "1", "X", "x", "U", "u"}
        if axis not in valid:
            raise ValueError("Invalid axis for KDC101. Use one of: 0, 1, '1', 'X', 'U'.")

    def GetProperties(self):
        return {
            "stage_type": "KDC101Serial",
            "port": self.port,
            "baudrate": self.baudrate,
            "timeout": self.timeout,
            "channel": self.channel,
            "units": "controller_counts",
        }

    def GetPositions(self):
        req = struct.pack(
            "<HBBBB",
            self.MGMSG_MOT_REQ_POSCOUNTER,
            self.channel,
            0x00,
            self.destination,
            self.source,
        )
        self.serial.write(req)

        position = 0
        t0 = time.time()
        while time.time() - t0 < 2.0:
            hdr = self._read_exact(6)
            msg_id = struct.unpack("<H", hdr[:2])[0]

            if (hdr[4] & 0x80) != 0:
                payload_len = struct.unpack("<H", hdr[2:4])[0]
                payload = self._read_exact(payload_len)
            else:
                payload = b""

            if msg_id == self.MGMSG_MOT_GET_POSCOUNTER and len(payload) >= 6:
                ch, pos = struct.unpack("<Hi", payload[:6])
                if ch == self.channel:
                    position = int(pos)
                    break

        return [float(position)]

    def MoveAbs(self, axis, value, wait: bool = False):
        self._check_axis(axis)

        payload = struct.pack("<Hi", self.channel, int(value))
        header = struct.pack(
            "<HHBB",
            self.MGMSG_MOT_MOVE_ABSOLUTE,
            len(payload),
            self.destination | 0x80,
            self.source,
        )
        self.serial.write(header + payload)

        if wait:
            t0 = time.time()
            while time.time() - t0 < 10.0:
                hdr = self._read_exact(6)
                msg_id = struct.unpack("<H", hdr[:2])[0]
                if (hdr[4] & 0x80) != 0:
                    payload_len = struct.unpack("<H", hdr[2:4])[0]
                    _ = self._read_exact(payload_len)
                if msg_id == self.MGMSG_MOT_MOVE_COMPLETED:
                    break

    def MoveRel(self, axis, value, wait: bool = False):
        self._check_axis(axis)

        payload = struct.pack("<Hi", self.channel, int(value))
        header = struct.pack(
            "<HHBB",
            self.MGMSG_MOT_MOVE_RELATIVE,
            len(payload),
            self.destination | 0x80,
            self.source,
        )
        self.serial.write(header + payload)

        if wait:
            t0 = time.time()
            while time.time() - t0 < 10.0:
                hdr = self._read_exact(6)
                msg_id = struct.unpack("<H", hdr[:2])[0]
                if (hdr[4] & 0x80) != 0:
                    payload_len = struct.unpack("<H", hdr[2:4])[0]
                    _ = self._read_exact(payload_len)
                if msg_id == self.MGMSG_MOT_MOVE_COMPLETED:
                    break

    def HomeAll(self):
        msg = struct.pack(
            "<HBBBB",
            self.MGMSG_MOT_MOVE_HOME,
            self.channel,
            0x00,
            self.destination,
            self.source,
        )
        self.serial.write(msg)

    def SetNominal(self):
        self.MoveAbs(axis=1, value=0, wait=False)

    def CloseStage(self):
        if self.serial is not None and self.serial.is_open:
            self.serial.close()
