"""
Simple serial (APT protocol) control for a Thorlabs BSC203.

Method names are aligned to MotorisedStage_Client style.
"""

import struct
import time

import serial

__all__ = ["BSC203SerialStage"]


class BSC203SerialStage:
    """
    Control a BSC203 using APT messages over serial.

    Notes
    -----
    - Uses native controller position counts.
    - A BSC203 axis is a single-channel card slot. Slots 0, 1, and 2 are
      addressed at APT destinations 0x21, 0x22, and 0x23 with channel id 1.
    - Axis can be an int index into configured slots or strings like "X", "Y",
      and "Z".
    """

    def __init__(
        self,
        port: str,
        slots=(0, 1, 2),
        baudrate: int = 115200,
        timeout: float = 0.25,
        move_timeout: float = 30.0,
    ) -> None:
        self.port = port
        self.slots = [int(slot) for slot in slots]
        if not self.slots or any(slot not in (0, 1, 2) for slot in self.slots):
            raise ValueError("slots must contain one or more values from: 0, 1, 2.")
        if len(set(self.slots)) != len(self.slots):
            raise ValueError("slots must not contain duplicate values.")
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.move_timeout = float(move_timeout)
        if self.move_timeout <= 0:
            raise ValueError("move_timeout must be positive.")

        # A BSC203 contains single-channel card slots behind one serial link.
        self.source = 0x01
        self.motherboard = 0x11
        self.channel = 1

        # Message IDs
        self.MGMSG_HW_RESPONSE = 0x0080
        self.MGMSG_HW_RICHRESPONSE = 0x0081
        self.MGMSG_HW_REQ_INFO = 0x0005
        self.MGMSG_HW_GET_INFO = 0x0006
        self.MGMSG_RACK_REQ_BAYUSED = 0x0060
        self.MGMSG_RACK_GET_BAYUSED = 0x0061
        self.MGMSG_MOD_SET_CHANENABLESTATE = 0x0210
        self.MGMSG_MOD_REQ_CHANENABLESTATE = 0x0211
        self.MGMSG_MOD_GET_CHANENABLESTATE = 0x0212
        self.MGMSG_MOT_REQ_POSCOUNTER = 0x0411
        self.MGMSG_MOT_GET_POSCOUNTER = 0x0412
        self.MGMSG_MOT_REQ_STATUSBITS = 0x0429
        self.MGMSG_MOT_GET_STATUSBITS = 0x042A
        self.MGMSG_MOT_MOVE_HOME = 0x0443
        self.MGMSG_MOT_MOVE_HOMED = 0x0444
        self.MGMSG_MOT_MOVE_RELATIVE = 0x0448
        self.MGMSG_MOT_MOVE_ABSOLUTE = 0x0453
        self.MGMSG_MOT_MOVE_COMPLETED = 0x0464

        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        try:
            self.serial.reset_input_buffer()
            time.sleep(0.05)

            # Prime communications and report connection/routing problems here.
            self.GetPositions()
        except Exception:
            self.CloseStage()
            raise

    def __del__(self):
        try:
            self.CloseStage()
        except Exception:
            pass

    @staticmethod
    def _slot_destination(slot: int) -> int:
        return 0x21 + int(slot)

    def _send_short(
        self, msg_id: int, destination: int, param1: int, param2: int = 0
    ) -> None:
        msg = struct.pack(
            "<HBBBB",
            msg_id,
            int(param1),
            int(param2),
            int(destination),
            self.source,
        )
        self.serial.write(msg)

    def _send_data(self, msg_id: int, destination: int, payload: bytes) -> None:
        header = struct.pack(
            "<HHBB",
            msg_id,
            len(payload),
            int(destination) | 0x80,
            self.source,
        )
        self.serial.write(header + payload)

    def _read_exact(self, nbytes: int) -> bytes:
        data = self.serial.read(nbytes)
        if len(data) != nbytes:
            raise TimeoutError(f"Timed out reading {nbytes} bytes (got {len(data)})")
        return data

    def _read_message(self) -> tuple[int, bytes, int, int, int]:
        hdr = self._read_exact(6)
        msg_id = struct.unpack("<H", hdr[:2])[0]
        source = hdr[5]
        if (hdr[4] & 0x80) != 0:
            payload_len = struct.unpack("<H", hdr[2:4])[0]
            return msg_id, self._read_exact(payload_len), source, 0, 0
        return msg_id, b"", source, hdr[2], hdr[3]

    @staticmethod
    def _decode_hardware_error(msg_id: int, payload: bytes, param1: int, param2: int) -> str:
        if msg_id == 0x0080:
            code = param1 | (param2 << 8)
            return f"APT hardware error response (return code 0x{code:04X})."
        code = struct.unpack("<H", payload[2:4])[0] if len(payload) >= 4 else None
        notes = payload[4:68].split(b"\x00", 1)[0].decode("ascii", errors="replace")
        detail = f" code 0x{code:04X}" if code is not None else ""
        if notes:
            detail += f": {notes}"
        return f"APT rich hardware error response{detail}."

    def _raise_if_hardware_error(
        self, msg_id: int, payload: bytes, param1: int, param2: int
    ) -> None:
        if msg_id in (self.MGMSG_HW_RESPONSE, self.MGMSG_HW_RICHRESPONSE):
            raise RuntimeError(self._decode_hardware_error(msg_id, payload, param1, param2))

    def _axis_to_slot(self, axis):
        if isinstance(axis, int) and 0 <= axis < len(self.slots):
            return self.slots[axis]

        if isinstance(axis, str):
            ax = axis.strip().upper()
            if ax.isdigit():
                n = int(ax)
                if n in self.slots:
                    return n
                if 0 <= n < len(self.slots):
                    return self.slots[n]
            name_map = {"Z": 0, "X": 1, "Y": 2, "U": 0, "V": 1, "W": 2}
            if ax in name_map and name_map[ax] < len(self.slots):
                return self.slots[name_map[ax]]

        raise ValueError(
            f"Invalid axis '{axis}'. Use index 0..{len(self.slots)-1}, "
            f"a slot string in {[str(slot) for slot in self.slots]}, or Z/X/Y."
        )

    def _wait_motion_message(
        self, slot: int, expected_id: int, description: str, timeout_s: float | None = None
    ):
        timeout_s = self.move_timeout if timeout_s is None else float(timeout_s)
        source = self._slot_destination(slot)
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                msg_id, payload, packet_source, param1, param2 = self._read_message()
            except TimeoutError:
                continue
            self._raise_if_hardware_error(msg_id, payload, param1, param2)

            if msg_id != expected_id or packet_source != source:
                continue

            if len(payload) < 2 or struct.unpack("<H", payload[:2])[0] == self.channel:
                return

        raise TimeoutError(
            f"Timeout waiting {timeout_s:g} s for {description} on BSC203 slot {slot}."
        )

    def GetProperties(self):
        return {
            "stage_type": "BSC203Serial",
            "port": self.port,
            "slots": self.slots,
            "channel_per_slot": self.channel,
            "destinations": [self._slot_destination(slot) for slot in self.slots],
            "baudrate": self.baudrate,
            "timeout": self.timeout,
            "move_timeout": self.move_timeout,
            "units": "controller_counts",
        }

    def GetPositions(self):
        positions = []

        for slot in self.slots:
            destination = self._slot_destination(slot)
            self._send_short(
                self.MGMSG_MOT_REQ_POSCOUNTER,
                destination=destination,
                param1=self.channel,
            )

            position = None
            t0 = time.time()
            while time.time() - t0 < 2.0:
                try:
                    msg_id, payload, source, param1, param2 = self._read_message()
                except TimeoutError:
                    continue
                self._raise_if_hardware_error(msg_id, payload, param1, param2)

                if (
                    msg_id != self.MGMSG_MOT_GET_POSCOUNTER
                    or source != destination
                    or len(payload) < 6
                ):
                    continue

                channel, value = struct.unpack("<Hi", payload[:6])
                if channel == self.channel:
                    position = float(value)
                    break

            if position is None:
                raise TimeoutError(
                    f"No position response from BSC203 slot {slot} "
                    f"(destination 0x{destination:02X}) on {self.port}. "
                    "Verify the serial port/VCP connection and include only "
                    "populated slots in `slots`."
                )
            positions.append(position)

        return positions

    def EnableAll(self):
        for slot in self.slots:
            self._send_short(
                self.MGMSG_MOD_SET_CHANENABLESTATE,
                destination=self._slot_destination(slot),
                param1=self.channel,
                param2=0x01,
            )

    def DisableAll(self):
        for slot in self.slots:
            self._send_short(
                self.MGMSG_MOD_SET_CHANENABLESTATE,
                destination=self._slot_destination(slot),
                param1=self.channel,
                param2=0x02,
            )

    def GetOccupiedSlots(self):
        """Ask the BSC203 motherboard which protocol slots are populated."""
        occupancy = []
        for slot in (0, 1, 2):
            self._send_short(
                self.MGMSG_RACK_REQ_BAYUSED,
                destination=self.motherboard,
                param1=slot,
            )
            t0 = time.time()
            while time.time() - t0 < 2.0:
                try:
                    msg_id, payload, _source, param1, param2 = self._read_message()
                except TimeoutError:
                    continue
                self._raise_if_hardware_error(msg_id, payload, param1, param2)
                if msg_id == self.MGMSG_RACK_GET_BAYUSED and not payload:
                    occupancy.append(
                        {
                            "slot": slot,
                            "destination": self._slot_destination(slot),
                            "occupied": param2 == 0x01,
                            "raw_state": param2,
                        }
                    )
                    break
            else:
                raise TimeoutError(f"No slot occupancy response for BSC203 slot {slot}.")
        return occupancy

    def GetEnableStates(self):
        """Read the module enable state using the APT enable-state query."""
        states = []
        for slot in self.slots:
            self._send_short(
                self.MGMSG_MOD_REQ_CHANENABLESTATE,
                destination=self._slot_destination(slot),
                param1=self.channel,
            )
            t0 = time.time()
            while time.time() - t0 < 2.0:
                try:
                    msg_id, payload, source, param1, param2 = self._read_message()
                except TimeoutError:
                    continue
                self._raise_if_hardware_error(msg_id, payload, param1, param2)
                if (
                    msg_id == self.MGMSG_MOD_GET_CHANENABLESTATE
                    and source == self._slot_destination(slot)
                    and not payload
                    and param1 == self.channel
                ):
                    states.append({"slot": slot, "enabled": param2 == 0x01, "raw_state": param2})
                    break
            else:
                raise TimeoutError(f"No enable-state response from BSC203 slot {slot}.")
        return states

    def GetHardwareInfo(self):
        """Read the identity of each selected BSC203 motor slot."""
        information = []
        for slot in self.slots:
            destination = self._slot_destination(slot)
            self._send_short(self.MGMSG_HW_REQ_INFO, destination=destination, param1=0x00)
            t0 = time.time()
            while time.time() - t0 < 2.0:
                try:
                    msg_id, payload, source, param1, param2 = self._read_message()
                except TimeoutError:
                    continue
                self._raise_if_hardware_error(msg_id, payload, param1, param2)
                if msg_id == self.MGMSG_HW_GET_INFO and source == destination and len(payload) >= 84:
                    model = payload[4:12].split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()
                    information.append(
                        {
                            "slot": slot,
                            "destination": destination,
                            "serial_number": struct.unpack("<I", payload[0:4])[0],
                            "model": model,
                            "hardware_type": struct.unpack("<H", payload[12:14])[0],
                            "firmware_version": tuple(payload[14:18]),
                            "hardware_version": struct.unpack("<H", payload[78:80])[0],
                            "modification_state": struct.unpack("<H", payload[80:82])[0],
                            "channels": struct.unpack("<H", payload[82:84])[0],
                        }
                    )
                    break
            else:
                raise TimeoutError(f"No hardware-info response from BSC203 slot {slot}.")
        return information

    def GetStatusBits(self):
        status = []
        for slot in self.slots:
            destination = self._slot_destination(slot)
            self._send_short(
                self.MGMSG_MOT_REQ_STATUSBITS,
                destination=destination,
                param1=self.channel,
            )

            payload = None
            t0 = time.time()
            while time.time() - t0 < 2.0:
                try:
                    msg_id, message_payload, source, param1, param2 = self._read_message()
                except TimeoutError:
                    continue
                self._raise_if_hardware_error(msg_id, message_payload, param1, param2)
                if (
                    msg_id == self.MGMSG_MOT_GET_STATUSBITS
                    and source == destination
                    and len(message_payload) >= 6
                ):
                    payload = message_payload
                    break
            if payload is None:
                raise TimeoutError(f"No status response from BSC203 slot {slot}.")

            channel, bits = struct.unpack("<HI", payload[:6])
            if channel != self.channel:
                raise RuntimeError(f"BSC203 slot {slot} returned status for channel {channel}.")
            status.append(
                {
                    "slot": slot,
                    "raw": bits,
                    "cw_hardware_limit": bool(bits & 0x00000001),
                    "ccw_hardware_limit": bool(bits & 0x00000002),
                    "in_motion_cw": bool(bits & 0x00000010),
                    "in_motion_ccw": bool(bits & 0x00000020),
                    "homing": bool(bits & 0x00000200),
                    "homed": bool(bits & 0x00000400),
                    "power_ok": bool(bits & 0x10000000),
                    "active": bool(bits & 0x20000000),
                    "error": bool(bits & 0x40000000),
                    "enabled": bool(bits & 0x80000000),
                }
            )
        return status

    def MoveAbs(self, axis, value, wait: bool = False):
        slot = self._axis_to_slot(axis)
        destination = self._slot_destination(slot)
        payload = struct.pack("<Hi", self.channel, int(value))
        self._send_data(self.MGMSG_MOT_MOVE_ABSOLUTE, destination, payload)

        if wait:
            self._wait_motion_message(slot, self.MGMSG_MOT_MOVE_COMPLETED, "move complete")

    def MoveRel(self, axis, value, wait: bool = False):
        slot = self._axis_to_slot(axis)
        destination = self._slot_destination(slot)
        payload = struct.pack("<Hi", self.channel, int(value))
        self._send_data(self.MGMSG_MOT_MOVE_RELATIVE, destination, payload)

        if wait:
            self._wait_motion_message(slot, self.MGMSG_MOT_MOVE_COMPLETED, "move complete")

    def HomeAll(self, wait: bool = False):
        for slot in self.slots:
            self._send_short(
                self.MGMSG_MOT_MOVE_HOME,
                destination=self._slot_destination(slot),
                param1=self.channel,
            )
            if wait:
                self._wait_motion_message(slot, self.MGMSG_MOT_MOVE_HOMED, "homing complete")

    def SetNominal(self, wait: bool = False):
        for axis_index in range(len(self.slots)):
            self.MoveAbs(axis_index, 0, wait=wait)

    def CloseStage(self):
        if self.serial is not None and self.serial.is_open:
            self.serial.close()
