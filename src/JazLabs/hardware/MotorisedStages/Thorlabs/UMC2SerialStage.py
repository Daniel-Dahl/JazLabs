"""Two-bay UMC2 control using APT (DOC-103274, issue 48).

Each bay is an independent mount on a shared serial connection. Startup reads
stage-axis parameters without homing, moving, or writing controller settings.
Counts are always available. Millimetres require a positive calibration and an
explicit physical_units="mm" declaration for the fitted linear mechanism.
"""
import math
import struct
import threading
import time

import serial

from JazLabs.hardware.MotorisedStages.Thorlabs.apt_serial_motion import APTSerialMotion


class UMC2SerialStage(APTSerialMotion):
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.25,
                 move_timeout: float = 60.0, destinations=(0x21, 0x22),
                 detect_stages=True, mounts=None):
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

        routes = dict(zip(("X", "Y"), self.destinations))
        if set(mounts or {}) - set(routes):
            self.CloseStage()
            raise ValueError("Mount keys must be X and/or Y")
        profiles = {}
        try:
            for index, (axis, destination) in enumerate(routes.items(), start=1):
                options = dict((mounts or {}).get(axis, {}))
                stage = None
                note = "Stage detection disabled"
                if detect_stages:
                    try:
                        stage = self.ReadStageParameters(axis)
                        note = "Controller-reported stage parameters"
                    except (TimeoutError, RuntimeError, ValueError) as exc:
                        note = f"Stage detection unavailable: {exc}"
                mm_scale = options.get("counts_per_mm")
                physical_units = options.get("physical_units")
                if physical_units not in (None, "mm"):
                    raise ValueError("UMC2 linear mounts use physical_units='mm'; otherwise leave it unset")
                if mm_scale is None and physical_units == "mm" and stage is not None:
                    mm_scale = stage["counts_per_unit"] or None
                if options.get("counts_per_mm") is not None:
                    note += "; using configured counts_per_mm"
                if mm_scale is not None:
                    mm_scale = float(mm_scale)
                    if not math.isfinite(mm_scale) or mm_scale <= 0:
                        raise ValueError(f"{axis}: counts_per_mm must be positive and finite")
                units = options.get("units", "auto")
                if units == "auto":
                    units = "mm" if mm_scale is not None else "counts"
                if units not in ("mm", "counts") or (units == "mm" and mm_scale is None):
                    raise ValueError(f"{axis}: mm requires detected or configured counts_per_mm")
                scale = mm_scale if units == "mm" else 1.0
                lower, upper = (stage["minimum_counts"], stage["maximum_counts"]) if stage else (None, None)
                if lower is not None and lower >= upper:
                    lower, upper = None, None
                if "limits_mm" in options:
                    if mm_scale is None:
                        raise ValueError(f"{axis}: limits_mm requires counts_per_mm")
                    requested_lower, requested_upper = (float(v) * mm_scale for v in options["limits_mm"])
                    if not all(math.isfinite(v) for v in (requested_lower, requested_upper)) or requested_lower >= requested_upper:
                        raise ValueError(f"{axis}: invalid limits_mm")
                    if (lower is not None and requested_lower < lower) or (upper is not None and requested_upper > upper):
                        raise ValueError(f"{axis}: limits_mm cannot widen controller travel")
                    lower, upper = requested_lower, requested_upper
                if mm_scale is None:
                    note += "; mm unavailable: specify physical_units='mm' with usable stage data, or counts_per_mm"
                # A jog increment is an application choice, not a stage property.
                # Default to 10 um or 100 counts, reduced for very short travel.
                step = max(1 / scale, .01 if units == "mm" else 100.0)
                if lower is not None and upper is not None:
                    step = min(step, max(1 / scale, (upper - lower) / scale / 100))
                step = float(options.get("step", step))
                if not math.isfinite(step) or step < 1 / scale:
                    raise ValueError(f"{axis}: step must be finite and at least one count")
                profiles[axis] = {"label": options.get("label", f"Mount {index}"),
                    "units": units, "counts_per_unit": scale, "counts_per_mm": mm_scale,
                    "limits": (None if lower is None else lower / scale, None if upper is None else upper / scale),
                    "independent_mount": True, "step": step, "stage": stage, "calibration_note": note}
            self._configure_motion(routes, umc_status=True, axis_profiles=profiles)
            # Raw-count methods and the public motion API share one wire parser.
            self._motion_received = self._received
            self._motion_lock = self._lock
        except Exception:
            self.CloseStage()
            raise

    def ReadStageParameters(self, axis):
        """Read 0x04F2; the wire format does not identify mm versus degrees."""
        with self._lock:
            destination = self._destination(axis)
            self._send_short(0x04F1, destination, 1)
            payload = self._wait_response(0x04F2, destination, self.timeout)
            if len(payload) != 74:
                raise RuntimeError(f"Invalid stage-axis packet length: {len(payload)}")
            stage_id, axis_id = struct.unpack_from("<HH", payload, 2)
            part_number = payload[6:22].split(b"\0", 1)[0].decode("ascii").strip()
            serial_number, counts_per_unit = struct.unpack_from("<II", payload, 22)
            minimum, maximum, acceleration, deceleration, velocity = struct.unpack_from("<iiiii", payload, 30)
            return {"stage_id": stage_id, "axis_id": axis_id, "part_number": part_number,
                    "serial_number": serial_number, "counts_per_unit": counts_per_unit,
                    "minimum_counts": minimum, "maximum_counts": maximum,
                    "maximum_acceleration_counts_per_cycle_squared": acceleration,
                    "maximum_deceleration_counts_per_cycle_squared": deceleration,
                    "maximum_velocity_counts_per_cycle": velocity}

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
                "destinations": self.destinations,
                "mounts": self.GetMotionCapabilities()}

    def CloseStage(self):
        with self._lock:
            if self.serial.is_open:
                self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.CloseStage()
