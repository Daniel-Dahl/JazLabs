"""Shared APT wire mechanics used by the Thorlabs serial drivers.

This is driver implementation code: it knows APT packets and hardware routing.
The server only calls the public driver methods below.
"""
import math
import struct
import threading
import time


class APTSerialMotion:
    def _configure_motion(self, routes, units="counts", counts_per_unit=1.0, limits=None, umc_status=False):
        self._motion_routes = dict(routes)
        self._motion_units = units
        self._motion_scale = counts_per_unit
        self._motion_limits = dict(limits or {})
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
            lower, upper = self._motion_limits.get(axis, (None, None))
            capabilities.append({"id": axis, "label": axis, "units": self._motion_units,
                "minimum": lower, "maximum": upper, "resolution": 1 / self._motion_scale,
                "tolerance": 2 / self._motion_scale,
                "step": 100 if self._motion_units == "counts" else .01,
                "home": True, "stop": True, "speed": False})
        return capabilities

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
            return {"position": position / self._motion_scale, "moving": bool(bits & 0xF0),
                    "homing": bool(bits & 0x200), "homed": bool(bits & 0x400),
                    "enabled": bool(bits & 0x80000000),
                    "fault": f"APT fault 0x{bits:08X}" if bits & fault_mask else None, "speed": None}

    def MoveTo(self, axis, target, wait=True, timeout=None):
        if timeout is None:
            timeout = self.GetProperties().get("move_timeout", 60.0)
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        target = float(target)
        if not math.isfinite(target):
            raise ValueError("Target must be finite")
        lower, upper = self._motion_limits.get(axis, (None, None))
        if (lower is not None and target < lower) or (upper is not None and target > upper):
            raise ValueError("Target is outside the configured actuator travel")
        counts = round(target * self._motion_scale)
        if not -(2**31) <= counts < 2**31:
            raise ValueError("Target exceeds signed 32-bit controller counts")
        with self._motion_lock:
            payload = struct.pack("<Hi", 1, counts)
            self.serial.write(struct.pack("<HHBB", 0x0453, 6, self._motion_routes[axis] | 0x80, 1) + payload)

        target = counts / self._motion_scale
        tolerance = 2 / self._motion_scale
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

    def GetPosition(self, axis):
        return self.GetAxisStatus(axis)["position"]

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
