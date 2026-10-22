"""Two-bay UMC2 control using APT (DOC-103274, issue 48).

Positions and moves use native controller counts. The fitted stage determines
physical scaling; this driver does not assume a particular actuator or home it
on connection. Axes X/Y (or integer 0/1) address bays 0/1, each with channel 1.
"""
import math
import struct
import threading
import time

import serial

from JazLabs.hardware.MotorisedStages.Thorlabs.apt_serial_motion import APTSerialMotion


class UMC2SerialStage(APTSerialMotion):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.25,
                 move_timeout: float = 60.0, destinations=(0x21, 0x22)):
        if timeout <= 0 or move_timeout <= 0:
            raise ValueError("timeout and move_timeout must be positive")
        if len(destinations) != 2 or len(set(destinations)) != 2:
            raise ValueError("Supply two distinct bay destinations")
        if any(not 0x21 <= address <= 0x2A for address in destinations):
            raise ValueError("Bay destinations must be in 0x21..0x2A")
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.move_timeout = move_timeout
        self.destinations = tuple(destinations)
        self._lock = threading.RLock()
        self._received = bytearray()
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout,
                                    write_timeout=timeout, rtscts=True,
                                    bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE)
        try:
            for destination in self.destinations:
                self._send_short(0x0012, destination)  # Stop unsolicited status updates.
                self._send_short(0x046C, destination)  # Resume end-of-move messages.
        except Exception:
            self.CloseStage()
            raise

        self._configure_motion(dict(zip(("X", "Y"), self.destinations)), umc_status=True)

    def _destination(self, axis):
        if axis in (0, "X", "x"):
            return self.destinations[0]
        if axis in (1, "Y", "y"):
            return self.destinations[1]
        raise ValueError("Use axis 0/'X' or 1/'Y'")

    def _send_short(self, message, destination, param1=0, param2=0):
        self.serial.write(struct.pack("<HBBBB", message, param1, param2, destination, 1))

    def _validate_counts(self, value):
        if not math.isfinite(value) or value != int(value) or not -(2**31) <= value < 2**31:
            raise ValueError("Position must be a signed 32-bit integer count")

    def _send_move(self, message, destination, value):
        payload = struct.pack("<Hi", 1, int(value))
        self.serial.write(struct.pack("<HHBB", message, len(payload), destination | 0x80, 1) + payload)

    def _wait_response(self, message, destination, timeout):
        # Preserve partial headers/payloads across serial timeouts. Match the bay
        # source as well as the message ID so the other axis cannot finish this wait.
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self._received) >= 6:
                header = bytes(self._received[:6])
                payload_length = struct.unpack_from("<H", header, 2)[0] if header[4] & 0x80 else 0
                if len(self._received) >= 6 + payload_length:
                    payload = bytes(self._received[6:6 + payload_length])
                    del self._received[:6 + payload_length]
                    response = struct.unpack_from("<H", header)[0]
                    if response in (0x0080, 0x0081):
                        raise RuntimeError(f"APT controller error: {header.hex()} {payload.hex()}")
                    channel = struct.unpack_from("<H", payload)[0] if payload else header[2]
                    if response == message and header[5] == destination and channel == 1:
                        return payload
                    continue
            self._received.extend(self.serial.read(max(1, self.serial.in_waiting)))
        raise TimeoutError(f"Waiting for APT 0x{message:04X} from bay 0x{destination:02X}")

    def GetPositions(self):
        with self._lock:
            positions = []
            for destination in self.destinations:
                self._send_short(0x0411, destination, 1)
                payload = self._wait_response(0x0412, destination, 2.0)
                if len(payload) != 6:
                    raise RuntimeError("Invalid APT position payload")
                positions.append(float(struct.unpack_from("<i", payload, 2)[0]))
            return positions

    def GetStatusBits(self, axis=0):
        with self._lock:
            destination = self._destination(axis)
            self._send_short(0x0493, destination, 1)
            payload = self._wait_response(0x0494, destination, 2.0)
            if len(payload) != 18:
                raise RuntimeError("Invalid UMC status payload")
            channel, trajectory, encoder, velocity, current, bits = struct.unpack("<HiiHhI", payload)
            return {"raw": bits, "trajectory_position": trajectory,
                    "encoder_position": encoder, "velocity": velocity,
                    "motor_current_ma": current, "homing": bool(bits & 0x200),
                    "homed": bool(bits & 0x400), "moving": bool(bits & 0xF0),
                    "enabled": bool(bits & 0x80000000)}

    def MoveAbs(self, axis, value, wait=False):
        with self._lock:
            destination = self._destination(axis)
            self._validate_counts(value)
            status = self.GetStatusBits(axis)
            if status["moving"] or status["homing"]:
                raise RuntimeError("Wait for this UMC2 axis to stop before issuing another move")
            self._send_move(0x0453, destination, value)
            if wait:
                self._wait_response(0x0464, destination, self.move_timeout)

    def MoveRel(self, axis, value, wait=False):
        with self._lock:
            destination = self._destination(axis)
            self._validate_counts(value)
            status = self.GetStatusBits(axis)
            if status["moving"] or status["homing"]:
                raise RuntimeError("Wait for this UMC2 axis to stop before issuing another move")
            self._send_move(0x0448, destination, value)
            if wait:
                self._wait_response(0x0464, destination, self.move_timeout)

    def HomeAll(self, wait=False):
        with self._lock:
            # Sequential homing avoids discarding another bay's completion.
            for axis, destination in enumerate(self.destinations):
                status = self.GetStatusBits(axis)
                if status["moving"] or status["homing"]:
                    raise RuntimeError("Wait for this UMC2 axis to stop before homing")
                self._send_short(0x0443, destination, 1)
                if wait:
                    self._wait_response(0x0444, destination, self.move_timeout)

    def Stop(self, axis, immediate=False):
        with self._lock:
            self._send_short(0x0465, self._destination(axis), 1, 1 if immediate else 2)

    def Enable(self, axis, enabled=True):
        with self._lock:
            self._send_short(0x0210, self._destination(axis), 1, 1 if enabled else 2)

    def SetNominal(self, wait=False):
        """Move each axis to native zero; the installed stage defines that datum."""
        for axis in (0, 1):
            self.MoveAbs(axis, 0, wait=wait)

    def GetProperties(self):
        return {"stage_type": "UMC2Serial", "port": self.port,
                "baudrate": self.baudrate, "timeout": self.timeout,
                "move_timeout": self.move_timeout, "axes": ["X", "Y"],
                "destinations": self.destinations, "units": "controller_counts"}

    def CloseStage(self):
        with self._lock:
            if self.serial.is_open:
                self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.CloseStage()
