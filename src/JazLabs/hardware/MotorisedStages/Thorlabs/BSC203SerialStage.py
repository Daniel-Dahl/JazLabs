"""BSC203 APT driver. Use one caller per serial connection.

Configured slots map to axes Z, X, Y in that order. Each slot uses channel 1
at destination 0x21 + slot. Supply limits in the configured units before moving.
"""
import math
import struct
import time

import serial


class BSC203SerialStage:
    controller = "BSC203Serial"

    def __init__(self, port, slots=(0, 1, 2), baudrate=115200, timeout=.25,
                 move_timeout=30., units="counts", counts_per_mm=None, limits=None):
        # Check installed slots and map them to public axes Z, X, Y in that order.
        slots = list(slots)
        if not slots or any(slot not in (0, 1, 2) for slot in slots) or len(set(slots)) != len(slots):
            raise ValueError("slots must contain distinct values from 0, 1, 2")
        routes = dict(zip(("Z", "X", "Y"), (0x21 + slot for slot in slots)))

        # Each axis can have its own counts/mm calibration.
        profiles = {}
        for axis in routes:
            scale = counts_per_mm.get(axis) if isinstance(counts_per_mm, dict) else counts_per_mm
            if units not in ("counts", "mm") or (units == "mm" and scale is None):
                raise ValueError(f"{axis}: mm requires a configured counts_per_mm calibration")
            profiles[axis] = {"units": units, "counts_per_unit": scale if units == "mm" else 1.,
                              "counts_per_mm": scale}

        # Open one serial connection for all configured motor cards.
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.move_timeout = move_timeout
        self._controller_settings = {"slots": slots}
        self._received = bytearray()
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout,
                                    write_timeout=timeout, bytesize=serial.EIGHTBITS,
                                    parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE)
        try:
            self.serial.reset_input_buffer()

            # Save each axis's bay address and initialise its calibration and limits.
            self._axis_destinations = dict(routes)
            self._axis_profiles = profiles
            self._limits = {}
            if any(not math.isfinite(value) or value <= 0 for value in (self.timeout, self.move_timeout)):
                raise ValueError("timeout and move_timeout must be positive and finite")
            if set(limits or {}) - set(routes):
                raise ValueError("Travel limit keys must match configured axes")
            for axis, profile in profiles.items():
                # Build conversions only for units with a known, positive scale.
                profile.setdefault("label", axis)
                scale = float(profile["counts_per_unit"])
                if not math.isfinite(scale) or scale <= 0:
                    raise ValueError(f"Invalid counts_per_unit for {axis}")
                profile["counts_per_unit"] = scale
                profile["unit_scales"] = {"counts": 1.0}
                if profile["units"] != "counts":
                    profile["unit_scales"][profile["units"]] = scale
                if profile.get("counts_per_mm") is not None:
                    mm_scale = float(profile["counts_per_mm"])
                    if not math.isfinite(mm_scale) or mm_scale <= 0:
                        raise ValueError(f"Invalid counts_per_mm for {axis}")
                    profile["unit_scales"]["mm"] = mm_scale

                # Validate this axis's configured endpoints; unknown limits prevent moves.
                lower, upper = (limits or {}).get(axis, (None, None))
                if any(value is not None and not math.isfinite(value) for value in (lower, upper)):
                    raise ValueError(f"Travel limits for {axis} must be finite")
                if lower is not None and upper is not None and lower >= upper:
                    raise ValueError(f"Invalid travel limits for {axis}")
                self._limits[axis] = (lower, upper)

            # Keep individual serial reads short; query() handles the overall deadline.
            self.serial.timeout = min(float(self.serial.timeout or .05), .05)
        except Exception:
            self.CloseStage()
            raise

    def write(self, message, destination, param1=1, param2=0, payload=None):
        """Send an APT command to a controller/bay using its binary header."""
        if payload is None:
            packet = struct.pack("<HBBBB", message, param1, param2, destination, 1)
        else:
            # The destination's high bit marks a message carrying a payload.
            packet = struct.pack("<HHBB", message, len(payload), destination | 0x80, 1) + payload
        # Send the assembled bytes to the controller.
        self.serial.write(packet)

    def query(self, message, response, destination, timeout=.5):
        """Send an APT request and read its complete reply from the selected bay."""
        self.write(message, destination)
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            # Read the six-byte header before checking for an optional payload.
            if len(self._received) >= 6:
                header = bytes(self._received[:6])
                payload_length = struct.unpack_from("<H", header, 2)[0] if header[4] & 0x80 else 0
                if payload_length > 4096:
                    raise RuntimeError("Invalid APT payload length")

                # Decode only complete packets; keep partial replies buffered.
                if len(self._received) >= 6 + payload_length:
                    payload = bytes(self._received[6:6 + payload_length])
                    del self._received[:6 + payload_length]
                    reply_id = struct.unpack_from("<H", header)[0]
                    if reply_id in (0x0080, 0x0081):
                        raise RuntimeError(f"APT controller error: {header.hex()} {payload.hex()}")

                    # Match the expected reply, its source bay and motor channel.
                    if reply_id == response and header[5] == destination:
                        if len(payload) < 2 or struct.unpack_from("<H", payload)[0] != 1:
                            raise RuntimeError("Unexpected APT channel")
                        return payload
                    continue

            # Serial reads can return fragments; append them until a packet is complete.
            self._received.extend(self.serial.read(max(1, min(4096, self.serial.in_waiting))))
        raise TimeoutError(f"No APT 0x{response:04X} response from 0x{destination:02X}")

    def GetStatus(self, axis=None):
        """Read configuration and live feedback into one dictionary.

        Positions and limits use the axis's default units. The positions and
        limits_by_unit dictionaries also include every calibrated alternative.
        """
        # Select one axis, or read every configured axis when none is specified.
        axes = list(self._axis_destinations) if axis is None else [axis]
        if any(name not in self._axis_destinations for name in axes):
            raise ValueError(f"Unknown axis {axis!r}; choose from {list(self._axis_destinations)}")
        result = {"controller": self.controller, "port": self.port,
                  "baudrate": self.baudrate, "timeout": self.timeout,
                  "move_timeout": self.move_timeout,
                  **self._controller_settings, "axes": {}}
        for name in axes:
            destination = self._axis_destinations[name]
            # Read the native position counts, then the motor status flags.
            payload = self.query(0x0411, 0x0412, destination)
            if len(payload) != 6:
                raise RuntimeError("Invalid APT position packet")
            position = struct.unpack_from("<i", payload, 2)[0]
            payload = self.query(0x0429, 0x042A, destination)
            if len(payload) != 6:
                raise RuntimeError("Invalid APT status packet")
            bits = struct.unpack_from("<I", payload, 2)[0]
            profile = self._axis_profiles[name]
            scale = profile["counts_per_unit"]
            lower, upper = self._limits[name]
            step = 100 if profile["units"] == "counts" else .01

            # Convert the position into every calibrated unit before assembling feedback.
            positions = {unit: position / unit_scale for unit, unit_scale in profile["unit_scales"].items()}
            fault_mask = 0x40000000 | 0x00020000 | 0x00040000 | 0x00080000 | 0x02000000 | 0x08000000
            # Include active-command and initialising flags after direction flags clear.
            busy_bits = 0xF0 | 0x800 | 0x20000000

            # Return configuration and decoded feedback together for this axis.
            result["axes"][name] = {
                "label": profile["label"], "units": profile["units"],
                "limits": [lower, upper], "resolution": 1 / scale, "tolerance": 2 / scale,
                "step": step, "unit_scales": dict(profile["unit_scales"]),
                "step_by_unit": {unit: step * scale / unit_scale for unit, unit_scale in profile["unit_scales"].items()},
                "resolution_by_unit": {unit: 1 / unit_scale for unit, unit_scale in profile["unit_scales"].items()},
                "limits_by_unit": {
                    unit: [None if lower is None else lower * scale / unit_scale,
                           None if upper is None else upper * scale / unit_scale]
                    for unit, unit_scale in profile["unit_scales"].items()},
                "supports": {"home": True, "stop": True, "speed": False},
                "position": positions[profile["units"]], "positions": positions,
                "controller_status_bits": bits, "moving": bool(bits & busy_bits),
                "homing": bool(bits & 0x200), "homed": bool(bits & 0x400),
                "enabled": bool(bits & 0x80000000),
                "cw_hardware_limit": bool(bits & 1), "ccw_hardware_limit": bool(bits & 2),
                "fault": f"APT fault 0x{bits:08X}" if bits & fault_mask else None, "speed": None}
        return result

    def MoveAbs(self, axis, target, wait=True, timeout=None, units=None):
        """Move within driver limits; wait for stopped, in-tolerance feedback by default.

        Omit units to use the axis's configured units, or specify 'counts'/'mm'.
        Nonblocking moves have the same checks before sending the command.
        """
        # Check the wait timeout before preparing or sending a move.
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")

        # Validate the target and convert the requested units into this mount's default units.
        profile = self._axis_profiles[axis]
        scale = profile["counts_per_unit"]
        target = float(target)
        if not math.isfinite(target):
            raise ValueError("Target must be finite")
        requested_units = profile["units"] if units is None else units
        if requested_units == "counts" and target != int(target):
            raise ValueError("Counts must be integers")
        target = self.ConvertPosition(axis, target, requested_units, profile["units"])

        # Both travel endpoints must be known before any ordinary move is allowed.
        lower, upper = self._limits[axis]
        if lower is None or upper is None:
            raise ValueError(f"{axis}: configure travel limits before moving")

        # Check the requested target against the allowed travel.
        if not lower <= target <= upper:
            raise ValueError("Target is outside the configured actuator travel")

        # Round to a controller count, then check the actual destination and integer range.
        counts = round(target * scale)
        rounded_target = counts / scale
        if not lower <= rounded_target <= upper:
            raise ValueError("Rounded target is outside the configured actuator travel")
        if not -(2**31) <= counts < 2**31:
            raise ValueError("Target exceeds signed 32-bit controller counts")

        # Read fresh feedback: the mount must be stopped, enabled, homed and fault-free.
        status = self.GetStatus(axis)["axes"][axis]
        if status["fault"]:
            raise RuntimeError(status["fault"])
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before issuing another move")
        if not status["enabled"] or not status["homed"]:
            raise RuntimeError("Enable and home this axis before moving")

        # Pack channel 1 and its target count into the command payload.
        payload = struct.pack("<Hi", 1, counts)
        try:
            # This write sends the absolute-move command to the selected bay.
            self.write(0x0453, self._axis_destinations[axis], payload=payload)

            # Nonblocking callers take over monitoring once the command has been sent.
            if not wait:
                return None

            # Blocking callers poll feedback until stopped at the rounded target or timed out.
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                status = self.GetStatus(axis)["axes"][axis]
                if status["fault"]:
                    raise RuntimeError(status["fault"])
                if not status["enabled"]:
                    raise RuntimeError("Axis disabled before the target was reached")
                if not status["homed"] and not status["homing"]:
                    raise RuntimeError("Axis lost its home reference during the move")

                # A stopped motor is successful only when its position is within two counts.
                if (not status["moving"] and not status["homing"]
                        and abs(status["position"] - rounded_target) <= 2 / scale):
                    return status
            raise TimeoutError(f"{axis} did not finish its move within {timeout:g} s")

        # Request a stop on both mounts if sending or monitoring the move fails.
        except Exception as exc:
            try:
                self.StopAll()
            except Exception as stop_exc:
                raise RuntimeError(f"{exc}; stop failed: {stop_exc}") from exc
            raise

    def MoveRel(self, axis, distance, wait=True, timeout=None, units=None):
        """Compute an absolute destination so relative moves obey the same limits."""
        # Validate the increment and express it in this mount's default units.
        profile = self._axis_profiles[axis]
        requested_units = profile["units"] if units is None else units
        distance = float(distance)
        if requested_units == "counts" and (not math.isfinite(distance) or distance != int(distance)):
            raise ValueError("Counts must be finite integers")
        distance = self.ConvertPosition(axis, distance, requested_units, profile["units"])

        # Read a stopped position so the relative destination has a stable starting point.
        status = self.GetStatus(axis)["axes"][axis]
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before issuing another move")

        # Use the absolute-move checks for the resulting destination, including travel limits.
        return self.MoveAbs(axis, status["position"] + distance, wait=wait, timeout=timeout)

    def SetNominal(self, wait=True, timeout=None):
        """Move each axis halfway between its allowed travel endpoints."""
        # Check every mount's limits before starting any nominal move.
        for axis, (lower, upper) in self._limits.items():
            if lower is None or upper is None:
                raise ValueError(f"{axis}: configure travel limits before moving to nominal")

        # Move each mount to its travel midpoint, rounded to a whole controller count.
        for axis, (lower, upper) in self._limits.items():
            scale = self._axis_profiles[axis]["counts_per_unit"]
            midpoint = round((lower + upper) / 2 * scale) / scale
            self.MoveAbs(axis, midpoint, wait=wait, timeout=timeout)

    def HomeAxis(self, axis, wait=True, timeout=None):
        """Home one axis and wait for stopped, homed feedback by default."""
        # Validate the timeout and check the mount is enabled, stopped and fault-free.
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        status = self.GetStatus(axis)["axes"][axis]
        if status["fault"]:
            raise RuntimeError(status["fault"])
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before homing")
        if not status["enabled"]:
            raise RuntimeError("Enable this axis before homing")

        # Send the home command; ordinary-move travel limits do not constrain homing.
        try:
            self.write(0x0443, self._axis_destinations[axis])
            if not wait:
                return None

            # Wait for the controller to report a stopped mount with a home reference.
            deadline = time.perf_counter() + timeout
            while time.perf_counter() < deadline:
                status = self.GetStatus(axis)["axes"][axis]
                if status["fault"]:
                    raise RuntimeError(status["fault"])
                if not status["enabled"]:
                    raise RuntimeError("Axis disabled before homing finished")
                if status["homed"] and not status["moving"] and not status["homing"]:
                    return status
            raise TimeoutError(f"{axis} did not finish homing within {timeout:g} s")

        # Request a stop on both mounts if sending or monitoring homing fails.
        except Exception as exc:
            try:
                self.StopAll()
            except Exception as stop_exc:
                raise RuntimeError(f"{exc}; stop failed: {stop_exc}") from exc
            raise

    def EnableAxis(self, axis, enabled=True):
        # APT uses state 1 to enable the motor output and state 2 to disable it.
        self.write(0x0210, self._axis_destinations[axis], 1, 1 if enabled else 2)

    def StopAll(self):
        # Attempt an immediate stop on both bays, even if one write fails.
        failures = []
        for destination in self._axis_destinations.values():
            try:
                self.write(0x0465, destination, 1, 1)
            except Exception as exc:
                failures.append(str(exc))
        if failures:
            raise RuntimeError("; ".join(failures))

    def ConvertPosition(self, axis, value, from_units, to_units):
        """Convert using this channel's calibration; never assume a counts/mm ratio."""
        # Only allow units for which this mount has a calibration.
        scales = self._axis_profiles[axis]["unit_scales"]
        if from_units not in scales or to_units not in scales:
            raise ValueError(f"{axis}: units unavailable; choose from {list(scales)}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Position must be finite")

        # Convert to native counts first, then from counts to the requested units.
        return value * scales[from_units] / scales[to_units]

    def CloseStage(self):
        if self.serial.is_open:
            self.serial.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.CloseStage()
