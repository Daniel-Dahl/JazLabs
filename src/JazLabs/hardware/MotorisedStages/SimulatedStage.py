"""Hardware-free motor driver using the same public API as the serial drivers.

Translation axes use mm; the absolute-sensor mirror uses degrees. Counts use
an explicit simulated calibration, never a calibration for a real mechanism.
Use one caller at a time, or connect multiple clients through the motor server.
"""
from copy import deepcopy
import math
import time


class SimulatedStage:
    def __init__(self, axes=2, absolute_sensor=False, limits=None,
                 counts_per_unit=1000.0, move_timeout=60.0):
        # Choose the simulated mechanism and validate its timing and axis settings.
        if axes not in (1, 2, 3):
            raise ValueError("Simulation supports one, two or three axes")
        if absolute_sensor and axes != 2:
            raise ValueError("The simulated mirror has two axes")
        self.move_timeout = float(move_timeout)
        if not math.isfinite(self.move_timeout) or self.move_timeout <= 0:
            raise ValueError("move_timeout must be positive and finite")
        self.name = "Simulated mirror mount" if absolute_sensor else "Simulated translation stage"
        names = (["U", "V"] if absolute_sensor else ["X", "Y", "Z"])[:axes]
        units = "deg" if absolute_sensor else "mm"
        if set(limits or {}) - set(names):
            raise ValueError("Travel limit keys must match configured axes")
        if isinstance(counts_per_unit, dict) and set(counts_per_unit) != set(names):
            raise ValueError("counts_per_unit must supply a calibration for every configured axis")

        # Keep configuration in the same per-axis layout returned by GetStatus().
        self.axes = {}
        self.positions = {}
        self.targets = {}
        self.homed = {}
        self.homing = set()
        self.velocity = {}
        self.enabled = {}
        for index, axis in enumerate(names):
            scale = counts_per_unit[axis] if isinstance(counts_per_unit, dict) else counts_per_unit
            scale = float(scale)
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError(f"{axis}: counts_per_unit must be positive and finite")
            physical_lower, physical_upper = (-0.75, 0.75) if absolute_sensor else (0.0, 25.0)

            # Configured bounds may narrow physical travel; unknown bounds allow readout only.
            lower, upper = (limits or {}).get(axis, (physical_lower, physical_upper))
            if any(value is not None and not math.isfinite(value) for value in (lower, upper)):
                raise ValueError(f"Invalid travel limits for {axis}")
            if lower is not None and upper is not None and lower >= upper:
                raise ValueError(f"Invalid travel limits for {axis}")
            if ((lower is not None and not physical_lower <= lower <= physical_upper) or
                    (upper is not None and not physical_lower <= upper <= physical_upper)):
                raise ValueError("Limits cannot widen the driver's allowed travel")
            self.axes[axis] = {
                "label": {"U": "Yaw U", "V": "Pitch V"}.get(axis, axis), "units": units,
                "limits": [lower, upper], "resolution": 1 / scale, "tolerance": 2 / scale,
                "step": 0.005 if absolute_sensor else 0.01,
                "unit_scales": {"counts": 1.0, units: scale},
                "supports": {"home": not absolute_sensor, "stop": True, "speed": True},
                "speed_minimum": 0.01, "speed_maximum": 2.0, "speed_units": f"{units}/s"}
            initial_position = 0.0 if absolute_sensor else 5.0 + index
            self.positions[axis] = min(physical_upper if upper is None else upper,
                                       max(physical_lower if lower is None else lower, initial_position))
            self.targets[axis] = self.positions[axis]
            self.homed[axis] = absolute_sensor or index == 0
            self.velocity[axis] = 0.2 if absolute_sensor else 1.0
            self.enabled[axis] = True
        self.last_update = time.perf_counter()
        self.is_open = True

    def _advance_positions(self):
        """Advance all axes to the current time for feedback and stop commands."""
        if not self.is_open:
            raise RuntimeError("Simulated stage connection is closed")
        now = time.perf_counter()
        elapsed = now - self.last_update
        self.last_update = now
        for axis in self.axes:
            if not self.enabled[axis]:
                continue
            difference = self.targets[axis] - self.positions[axis]
            distance = min(abs(difference), elapsed * self.velocity[axis])
            self.positions[axis] += math.copysign(distance, difference)
            if abs(self.targets[axis] - self.positions[axis]) < 1e-9 and axis in self.homing:
                self.homing.remove(axis)
                self.homed[axis] = True

    def GetStatus(self, axis=None):
        """Return configuration, calibrated positions and live motion feedback."""
        if axis is not None and axis not in self.axes:
            raise ValueError(f"Unknown axis {axis!r}; choose from {list(self.axes)}")
        self._advance_positions()
        names = list(self.axes) if axis is None else [axis]
        result = {"controller": "simulation", "name": self.name,
                  "move_timeout": self.move_timeout, "axes": {}}
        for name in names:
            spec = deepcopy(self.axes[name])
            scales = spec["unit_scales"]
            scale = scales[spec["units"]]
            lower, upper = spec["limits"]

            # Report positions, limits and jog increments in each available unit.
            counts = round(self.positions[name] * scale)
            spec.update(
                position=counts / scale,
                positions={unit: counts / unit_scale for unit, unit_scale in scales.items()},
                limits_by_unit={unit: [None if lower is None else lower * scale / unit_scale,
                                      None if upper is None else upper * scale / unit_scale]
                                for unit, unit_scale in scales.items()},
                resolution_by_unit={unit: 1 / unit_scale for unit, unit_scale in scales.items()},
                step_by_unit={unit: spec["step"] * scale / unit_scale for unit, unit_scale in scales.items()},
                moving=abs(self.targets[name] - self.positions[name]) > 1e-9,
                homed=self.homed[name], homing=name in self.homing,
                enabled=self.enabled[name], fault=None, speed=self.velocity[name])
            result["axes"][name] = spec
        return result

    def MoveAbs(self, axis, target, wait=True, timeout=None, units=None):
        """Check an absolute destination and wait for stopped feedback by default."""
        # Validate timeout, units and the requested position before changing the target.
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        status = self.GetStatus(axis)["axes"][axis]
        target = float(target)
        requested_units = status["units"] if units is None else units
        if requested_units == "counts" and (not math.isfinite(target) or target != int(target)):
            raise ValueError("Counts must be finite integers")
        target = self.ConvertPosition(axis, target, requested_units, status["units"])

        # Require both endpoints and check the requested and count-rounded destination.
        lower, upper = status["limits"]
        if lower is None or upper is None:
            raise ValueError(f"{axis}: configure travel limits before moving")
        if not lower <= target <= upper:
            raise ValueError("Target is outside the simulated travel limits")
        scale = status["unit_scales"][status["units"]]
        counts = round(target * scale)
        rounded_target = counts / scale
        if not lower <= rounded_target <= upper:
            raise ValueError("Rounded target is outside the simulated travel limits")
        if not -(2**31) <= counts < 2**31:
            raise ValueError("Target exceeds signed 32-bit controller counts")

        # Do not replace an active command or move a disabled/unreferenced axis.
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before issuing another move")
        if not status["enabled"] or not status["homed"]:
            raise RuntimeError("Enable and home this axis before moving")
        self.targets[axis] = rounded_target
        if not wait:
            return None

        # Time drives the model; brief sleeps yield CPU because there is no serial read.
        deadline = time.perf_counter() + timeout
        try:
            while time.perf_counter() < deadline:
                current = self.GetStatus(axis)["axes"][axis]
                if current["fault"]:
                    raise RuntimeError(current["fault"])
                if not current["enabled"]:
                    raise RuntimeError("Axis disabled before the target was reached")
                if not current["homed"] and not current["homing"]:
                    raise RuntimeError("Axis lost its home reference during the move")
                if (not current["moving"] and not current["homing"]
                        and abs(current["position"] - rounded_target) <= current["tolerance"]):
                    return current
                time.sleep(.001)
            raise TimeoutError(f"{axis} did not finish its move within {timeout:g} s")
        except Exception:
            self.StopAll()
            raise

    def MoveRel(self, axis, distance, wait=True, timeout=None, units=None):
        """Convert the increment, then use the absolute move's travel and state checks."""
        status = self.GetStatus(axis)["axes"][axis]
        requested_units = status["units"] if units is None else units
        distance = float(distance)
        if requested_units == "counts" and (not math.isfinite(distance) or distance != int(distance)):
            raise ValueError("Counts must be finite integers")
        distance = self.ConvertPosition(axis, distance, requested_units, status["units"])
        if status["moving"] or status["homing"]:
            raise RuntimeError("Wait for this axis to stop before issuing another move")
        return self.MoveAbs(axis, status["position"] + distance, wait=wait, timeout=timeout)

    def SetNominal(self, wait=True, timeout=None):
        """Move every axis halfway between its limits, rounded to a native count."""
        # Check every axis before moving any, including when wait=False.
        for axis, spec in self.axes.items():
            lower, upper = spec["limits"]
            if lower is None or upper is None:
                raise ValueError(f"{axis}: configure travel limits before moving to nominal")
        for axis, spec in self.axes.items():
            scale = spec["unit_scales"][spec["units"]]
            target = round(sum(spec["limits"]) / 2 * scale) / scale
            self.MoveAbs(axis, target, wait=wait, timeout=timeout)

    def HomeAxis(self, axis, wait=True, timeout=None):
        """Home a translation axis; absolute-sensor mirror axes do not need homing."""
        timeout = self.move_timeout if timeout is None else float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        status = self.GetStatus(axis)["axes"][axis]
        if not status["supports"]["home"]:
            raise ValueError("This axis has an absolute sensor; no homing")
        if status["moving"] or status["homing"] or not status["enabled"]:
            raise RuntimeError("Enable a stopped axis before homing")

        # Homing can reach physical zero outside narrowed ordinary-move limits.
        self.homed[axis] = False
        self.homing.add(axis)
        self.targets[axis] = 0.0
        if not wait:
            return None
        deadline = time.perf_counter() + timeout
        try:
            while time.perf_counter() < deadline:
                current = self.GetStatus(axis)["axes"][axis]
                if current["fault"]:
                    raise RuntimeError(current["fault"])
                if not current["enabled"]:
                    raise RuntimeError("Axis disabled before homing finished")
                if current["homed"] and not current["moving"] and not current["homing"]:
                    return current
                time.sleep(.001)
            raise TimeoutError(f"{axis} did not finish homing within {timeout:g} s")
        except Exception:
            self.StopAll()
            raise

    def EnableAxis(self, axis, enabled=True):
        # Disabling cancels the current command; re-enabling does not restart it.
        self.GetStatus(axis)
        self.enabled[axis] = bool(enabled)
        if not enabled:
            self.targets[axis] = self.positions[axis]
            self.homing.discard(axis)

    def StopAll(self):
        # Advance to the stop time before cancelling every axis's target and home command.
        if not self.is_open:
            return
        self._advance_positions()
        self.targets = dict(self.positions)
        self.homing.clear()

    def SetSpeed(self, axis, value):
        """Set speed in the axis's physical units per second."""
        if axis not in self.axes:
            raise ValueError(f"Unknown axis {axis!r}")
        value = float(value)
        spec = self.axes[axis]
        if not math.isfinite(value) or not spec["speed_minimum"] <= value <= spec["speed_maximum"]:
            raise ValueError("Speed is outside the supported range")
        # Apply the old speed up to this instant, then use the new speed going forward.
        self._advance_positions()
        self.velocity[axis] = value

    def ConvertPosition(self, axis, value, from_units, to_units):
        """Convert with this simulated axis's explicitly configured counts scale."""
        if axis not in self.axes:
            raise ValueError(f"Unknown axis {axis!r}")
        scales = self.axes[axis]["unit_scales"]
        if from_units not in scales or to_units not in scales:
            raise ValueError(f"{axis}: units unavailable; choose from {list(scales)}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Position must be finite")
        return value * scales[from_units] / scales[to_units]

    def CloseStage(self):
        self.StopAll()
        self.is_open = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.CloseStage()
