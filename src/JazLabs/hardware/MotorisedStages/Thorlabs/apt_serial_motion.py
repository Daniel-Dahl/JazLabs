"""Shared APT wire mechanics used by the Thorlabs serial drivers.

This is driver implementation code: it knows APT packets and hardware routing.
The server only calls the public driver methods below.
"""
import math
import struct
import threading
import time


class APTSerialMotion:
    def _configure_motion(self, routes, units="counts", counts_per_unit=1.0, limits=None, umc_status=False, axis_profiles=None):
        self._motion_routes = dict(routes)
        self._motion_limits = dict(limits or {})
        self._motion_profiles = {}
        for axis in self._motion_routes:
            profile = {"units": units, "counts_per_unit": counts_per_unit, "label": axis}
            profile.update((axis_profiles or {}).get(axis, {}))
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
                if profile["units"] == "mm" and mm_scale != scale:
                    raise ValueError(f"Inconsistent millimetre calibration for {axis}")
                profile["unit_scales"]["mm"] = mm_scale
            if "limits" in profile:
                self._motion_limits[axis] = profile["limits"]
            lower, upper = self._motion_limits.get(axis, (None, None))
            if any(value is not None and not math.isfinite(value) for value in (lower, upper)):
                raise ValueError(f"Travel limits for {axis} must be finite")
            if lower is not None and upper is not None and lower >= upper:
                raise ValueError(f"Invalid travel limits for {axis}")
            self._motion_profiles[axis] = profile
        self._motion_umc_status = umc_status
        self._motion_received = bytearray()
        self._motion_lock = threading.RLock()
        self._motion_stop_requested = lambda: False
        self.serial.timeout = min(float(self.serial.timeout or 0.05), 0.05)

    def SetStopRequested(self, callback):
        self._motion_stop_requested = callback

    def GetMotionCapabilities(self):
        capabilities = []
        for axis in self._motion_routes:
            profile = self._motion_profiles[axis]
            scale = profile["counts_per_unit"]
            lower, upper = self._motion_limits.get(axis, (None, None))
            unit_limits = {}
            for unit, unit_scale in profile["unit_scales"].items():
                unit_limits[unit] = [None if lower is None else lower * scale / unit_scale,
                                     None if upper is None else upper * scale / unit_scale]
            step = profile.get("step", 100 if profile["units"] == "counts" else .01)
            capabilities.append({"id": axis, "label": profile["label"], "units": profile["units"],
                "minimum": lower, "maximum": upper, "resolution": 1 / scale,
                "tolerance": 2 / scale,
                "step": step,
                "step_by_unit": {unit: step * scale / unit_scale for unit, unit_scale in profile["unit_scales"].items()},
                "resolution_by_unit": {unit: 1 / unit_scale for unit, unit_scale in profile["unit_scales"].items()},
                "unit_scales": dict(profile["unit_scales"]), "limits_by_unit": unit_limits,
                "independent_mount": profile.get("independent_mount", False),
                "stage": profile.get("stage"), "calibration_note": profile.get("calibration_note"),
                "home": True, "stop": True, "speed": False})
        return capabilities

    def ConvertPosition(self, axis, value, from_units, to_units):
        """Convert using this channel's calibration; never assume a counts/mm ratio."""
        scales = self._motion_profiles[axis]["unit_scales"]
        if from_units not in scales or to_units not in scales:
            raise ValueError(f"{axis}: units unavailable; choose from {list(scales)}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Position must be finite")
        return value * scales[from_units] / scales[to_units]

    def _apt_short(self, message, destination, param1=1, param2=0):
        self.serial.write(struct.pack("<HBBBB", message, param1, param2, destination, 1))

    def _apt_response(self, message, destination):
        deadline = time.monotonic() + 0.5
        while time.monotonic() < deadline:
            if self._motion_stop_requested():
                raise InterruptedError("Status read interrupted for stop")
            if len(self._motion_received) >= 6:
                header = bytes(self._motion_received[:6])
                length = struct.unpack_from("<H", header, 2)[0] if header[4] & 0x80 else 0
                if length > 4096:
                    raise RuntimeError("Invalid APT payload length")
                if len(self._motion_received) >= 6 + length:
                    payload = bytes(self._motion_received[6:6 + length])
                    del self._motion_received[:6 + length]
                    response = struct.unpack_from("<H", header)[0]
                    if response in (0x0080, 0x0081):
                        raise RuntimeError(f"APT controller error: {header.hex()} {payload.hex()}")
                    if response == message and header[5] == destination:
                        if len(payload) < 2 or struct.unpack_from("<H", payload)[0] != 1:
                            raise RuntimeError("Unexpected APT channel")
                        return payload
                    continue
            self._motion_received.extend(self.serial.read(max(1, min(4096, self.serial.in_waiting))))
        raise TimeoutError(f"No APT 0x{message:04X} response from 0x{destination:02X}")


    def GetAxisStatus(self, axis):
        with self._motion_lock:
            destination = self._motion_routes[axis]
            if self._motion_umc_status:
                self._apt_short(0x0493, destination)
                payload = self._apt_response(0x0494, destination)
                if len(payload) != 18:
                    raise RuntimeError("Invalid UMC status packet")
                _, position, encoder, velocity, current, bits = struct.unpack("<HiiHhI", payload)
            else:
                self._apt_short(0x0411, destination)
                payload = self._apt_response(0x0412, destination)
                if len(payload) != 6:
                    raise RuntimeError("Invalid APT position packet")
                position = struct.unpack_from("<i", payload, 2)[0]
                if self._motion_stop_requested():
                    raise InterruptedError("Status read interrupted for stop")
                self._apt_short(0x0429, destination)
                payload = self._apt_response(0x042A, destination)
                if len(payload) != 6:
                    raise RuntimeError("Invalid APT status packet")
                bits = struct.unpack_from("<I", payload, 2)[0]
            fault_mask = 0x40000000 | 0x00020000 | 0x00040000 | 0x00080000 | 0x02000000 | 0x08000000
            profile = self._motion_profiles[axis]
            positions = {unit: position / scale for unit, scale in profile["unit_scales"].items()}
            return {"position": positions[profile["units"]], "positions": positions, "units": profile["units"], "moving": bool(bits & 0xF0),
                    "homing": bool(bits & 0x200), "homed": bool(bits & 0x400),
                    "enabled": bool(bits & 0x80000000),
                    "fault": f"APT fault 0x{bits:08X}" if bits & fault_mask else None, "speed": None}

    def MoveTo(self, axis, target, wait=True, timeout=None, units=None):
        if timeout is None:
            timeout = self.GetProperties().get("move_timeout", 60.0)
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        profile = self._motion_profiles[axis]
        scale = profile["counts_per_unit"]
        target = float(target)
        if not math.isfinite(target):
            raise ValueError("Target must be finite")
        if units is not None:
            if units == "counts" and target != int(target):
                raise ValueError("Counts must be integers")
            target = self.ConvertPosition(axis, target, units, profile["units"])
        target = float(target)
        if not math.isfinite(target):
            raise ValueError("Target must be finite")
        lower, upper = self._motion_limits.get(axis, (None, None))
        if (lower is not None and target < lower) or (upper is not None and target > upper):
            raise ValueError("Target is outside the configured actuator travel")
        counts = round(target * scale)
        rounded_target = counts / scale
        if (lower is not None and rounded_target < lower) or (upper is not None and rounded_target > upper):
            raise ValueError("Rounded target is outside the configured actuator travel")
        if not -(2**31) <= counts < 2**31:
            raise ValueError("Target exceeds signed 32-bit controller counts")
        with self._motion_lock:
            payload = struct.pack("<Hi", 1, counts)
            self.serial.write(struct.pack("<HHBB", 0x0453, 6, self._motion_routes[axis] | 0x80, 1) + payload)

        target = counts / scale
        tolerance = 2 / scale
        if not wait:
            return None
        deadline = time.monotonic() + timeout
        try:
            while time.monotonic() < deadline:
                status = self.GetAxisStatus(axis)
                if status["fault"]:
                    raise RuntimeError(status["fault"])
                if not status["enabled"]:
                    raise RuntimeError("Axis disabled before the target was reached")
                if (not status["moving"] and not status["homing"]
                        and abs(status["position"] - target) <= tolerance):
                    return status
                time.sleep(.05)
            raise TimeoutError(f"{axis} did not finish its move within {timeout:g} s")
        except Exception as exc:
            try:
                self.StopAll()
            except Exception as stop_exc:
                raise RuntimeError(f"{exc}; stop could not be confirmed: {stop_exc}") from exc
            raise

    def GetPosition(self, axis, units=None):
        status = self.GetAxisStatus(axis)
        if units is None:
            return status["position"]
        if units not in status["positions"]:
            raise ValueError(f"{axis}: units {units!r} are unavailable")
        return status["positions"][units]

    def HomeAxis(self, axis):
        with self._motion_lock:
            self._apt_short(0x0443, self._motion_routes[axis])

    def EnableAxis(self, axis):
        with self._motion_lock:
            self._apt_short(0x0210, self._motion_routes[axis], 1, 1)

    def StopAll(self):
        failures = []
        with self._motion_lock:
            for destination in self._motion_routes.values():
                try:
                    self._apt_short(0x0465, destination, 1, 1)
                except Exception as exc:
                    failures.append(str(exc))
        if failures:
            raise RuntimeError("; ".join(failures))
