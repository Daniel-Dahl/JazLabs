"""

Use one caller at a time for this driver/serial port.
Serial (APT protocol) control for a Thorlabs KST201 stepper controller.

The default actuator profile is the ZFS13B. Native APT positions are Trinamic
microsteps; MoveAbs/MoveRel use mm by default and accept units="counts".
"""

from dataclasses import dataclass
import math
import struct
import time
import warnings

import serial

__all__ = [
    "ActuatorProfile",
    "MountProfile",
    "KST201SerialStage",
    "PY004_M_MOUNT",
    "ZFS13B_ACTUATOR",
]


@dataclass(frozen=True)
class ActuatorProfile:
    """Physical actuator data needed to convert and constrain a linear move."""

    name: str
    actuator_type_id: int
    travel_mm: float
    microsteps_per_mm: float
    maximum_velocity_mm_s: float | None = None
    maximum_acceleration_mm_s2: float | None = None

    def mm_to_counts(self, value_mm: float) -> int:
        return int(round(float(value_mm) * self.microsteps_per_mm))

    def counts_to_mm(self, value: int | float) -> float:
        return float(value) / self.microsteps_per_mm


@dataclass(frozen=True)
class MountProfile:
    """
    Information about the mechanical assembly driven by one actuator.

    ``axis_ranges_deg`` documents mount angular travel. It does not by itself
    define actuator-position limits because the fitted actuator datum and
    preload position are assembly-dependent.
    """

    name: str
    supported_actuators: tuple[str, ...]
    axis_ranges_deg: tuple[tuple[str, float, float], ...]
    note: str = ""

    def angle_range_deg(self, axis: str) -> tuple[float, float]:
        requested = axis.strip().upper()
        for name, minimum, maximum in self.axis_ranges_deg:
            if name == requested:
                return (minimum, maximum)
        valid = ", ".join(name for name, _, _ in self.axis_ranges_deg)
        raise ValueError(f"Invalid mount axis '{axis}'. Use one of: {valid}.")


# ETN013372-D02: ZFS13B, 13 mm travel, KST201 driver, 2048
# microsteps/full step, 24 steps/rev, and a 400:9 gear reduction.
ZFS13B_ACTUATOR = ActuatorProfile(
    name="ZFS13B",
    actuator_type_id=0x41,  # APT ZFS_NEW_13MM
    travel_mm=13.0,
    microsteps_per_mm=24 * 2048 * 400 / 9,
    maximum_velocity_mm_s=2.0,
    maximum_acceleration_mm_s2=10.0,
)


# ETN011941-D02 documents ZFS13B as a compact-stepper option for the
# user-configurable PY004 platform family, with the angular range below.
PY004_M_MOUNT = MountProfile(
    name="PY004/M",
    supported_actuators=("ZFS13B",),
    axis_ranges_deg=(("PITCH", -2.5, 2.5), ("YAW", -4.0, 4.0)),
    note=(
        "The platform may reach a mechanical stop before the actuator limit "
        "switch. Supply calibrated minimum_mm and maximum_mm for installed "
        "mount protection."
    ),
)


_ACTUATORS = {"ZFS13B": ZFS13B_ACTUATOR}
_MOUNTS = {"PY004/M": PY004_M_MOUNT, "PY004": PY004_M_MOUNT}


class KST201SerialStage:
    """
    Control one ZFS13B actuator on a KST201 controller using APT messages.

    Parameters
    ----------
    actuator:
        An :class:`ActuatorProfile` or the supported name ``"ZFS13B"``.
    mount, mount_axis:
        Optional driven assembly information. For ``"PY004/M"``, specify
        either ``"PITCH"`` or ``"YAW"``.
    minimum_mm, maximum_mm:
        Optional calibrated actuator positions allowed by the installed
        mechanical assembly. Values must be within the actuator travel.
    safety_margin_mm:
        Distance kept inside each configured endpoint for ordinary moves.
        Homing is deliberately not subject to this software margin.
    configure_actuator:
        Send ``MGMSG_MOT_SET_TSTACTUATORTYPE`` at startup so the KST201 uses
        its built-in ZFS 13 mm actuator configuration.

    Notes
    -----
    - ``MoveAbs`` and ``MoveRel`` use mm unless units="counts" is specified.
    - One KST201 drives one actuator. A two-axis mount uses two controllers.
    """

    controller = "KST201Serial"

    def __init__(
        self,
        port: str,
        actuator: str | ActuatorProfile = "ZFS13B",
        mount: str | MountProfile | None = None,
        mount_axis: str | None = None,
        minimum_mm: float | None = None,
        maximum_mm: float | None = None,
        safety_margin_mm: float = 0.1,
        configure_actuator: bool = True,
        baudrate: int = 115200,
        timeout: float = 0.25,
        move_timeout: float = 30.0,
        limits=None,
    ) -> None:
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.move_timeout = float(move_timeout)
        # Select the configured actuator/mount and validate calibration and limits.
        if any(not math.isfinite(value) or value <= 0 for value in (self.timeout, self.move_timeout)):
            raise ValueError("timeout and move_timeout must be positive and finite")
        self._identify_stage_parameters(actuator, mount, mount_axis,
            minimum_mm, maximum_mm, safety_margin_mm, limits)

        # Open the single motor channel after its configuration has been checked.
        self._received = bytearray()
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
            self.serial.timeout = min(float(self.serial.timeout or .05), .05)
            self.write(0x0018, 0x50, 0)  # Disable flash programming.
            time.sleep(.05)  # Let the controller settle after startup configuration.

            # Tell the controller which actuator is fitted when configuration is enabled.
            if configure_actuator:
                self.write(0x04FE, 0x50, self.actuator.actuator_type_id)
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

    def _identify_stage_parameters(self, actuator, mount, mount_axis,
                                   minimum_mm, maximum_mm, safety_margin_mm, limits):
        """Use the supplied profiles to identify calibration and allowed travel.

        Unlike UMC2, this driver selects a configured actuator; it does not query
        the attached motor for an automatically detected stage description.
        """
        # Resolve an actuator name or accept a supplied actuator profile.
        if isinstance(actuator, ActuatorProfile):
            self.actuator = actuator
        else:
            key = str(actuator).strip().upper()
            if key not in _ACTUATORS:
                raise ValueError(f"Unknown KST201 actuator '{actuator}'. Supported: ZFS13B.")
            self.actuator = _ACTUATORS[key]

        # The optional mount describes the assembly driven by the linear actuator.
        if mount is None or isinstance(mount, MountProfile):
            self.mount = mount
        else:
            key = str(mount).strip().upper()
            if key not in _MOUNTS:
                raise ValueError(f"Unknown KST201 mount '{mount}'. Supported: PY004/M.")
            self.mount = _MOUNTS[key]

        # A mount must support the actuator and name one of its documented axes.
        self.mount_axis = None
        if self.mount is None:
            if mount_axis is not None:
                raise ValueError("mount_axis can only be specified when mount is specified.")
        else:
            if self.actuator.name not in self.mount.supported_actuators:
                raise ValueError(f"{self.actuator.name} is not listed for mount {self.mount.name}.")
            if mount_axis is None:
                raise ValueError("Specify mount_axis='PITCH' or mount_axis='YAW' for PY004/M.")
            self.mount_axis = str(mount_axis).strip().upper()
            self.mount.angle_range_deg(self.mount_axis)
        axis = self.mount_axis or "X"

        # Check the actuator's conversion from millimetres to controller counts.
        scale = float(self.actuator.microsteps_per_mm)
        if not math.isfinite(scale) or scale <= 0:
            raise ValueError("Actuator microsteps_per_mm must be positive and finite")

        # Start with actuator travel or calibrated endpoints for the installed mount.
        margin = float(safety_margin_mm)
        if not math.isfinite(margin) or margin < 0:
            raise ValueError("safety_margin_mm must be non-negative.")
        lower = 0.0 if minimum_mm is None else float(minimum_mm)
        upper = self.actuator.travel_mm if maximum_mm is None else float(maximum_mm)
        if not all(math.isfinite(v) for v in (lower, upper)) or lower < 0 or upper > self.actuator.travel_mm or lower >= upper:
            raise ValueError(
                f"Motion endpoints must satisfy 0 <= minimum_mm < maximum_mm <= "
                f"{self.actuator.travel_mm:g} for {self.actuator.name}."
            )

        # Keep ordinary moves inside both endpoints by the requested safety margin.
        lower += margin
        upper -= margin
        if lower >= upper:
            raise ValueError("safety_margin_mm leaves no usable actuator travel.")
        self.minimum_mm, self.maximum_mm = lower, upper
        self.minimum_counts = self.actuator.mm_to_counts(lower)
        self.maximum_counts = self.actuator.mm_to_counts(upper)

        # Additional limits may narrow this allowed travel, but cannot widen it.
        if set(limits or {}) - {axis}:
            raise ValueError(f"Travel limit key must be {axis}")
        lower, upper = (limits or {}).get(axis, (lower, upper))
        if any(value is None or not math.isfinite(value) for value in (lower, upper)) or lower >= upper:
            raise ValueError(f"Invalid travel limits for {axis}")
        if lower < self.minimum_mm or upper > self.maximum_mm:
            raise ValueError("Limits cannot widen the driver's allowed travel")
        self._limits = {axis: (lower, upper)}

        # Save the channel address, mm/counts calibration and descriptive metadata.
        self._axis_destinations = {axis: 0x50}
        self._axis_profiles = {axis: {"label": axis, "units": "mm",
            "counts_per_unit": scale, "unit_scales": {"counts": 1., "mm": scale}}}
        self._controller_settings = {
            "actuator": self.actuator.name, "microsteps_per_mm": self.actuator.microsteps_per_mm,
            "actuator_travel_mm": self.actuator.travel_mm,
            "mount": None if self.mount is None else self.mount.name,
            "mount_axis": self.mount_axis,
            "mount_angle_range_deg": None if self.mount is None else self.mount.angle_range_deg(axis),
            "mount_note": None if self.mount is None else self.mount.note}
        if self.mount is not None and minimum_mm is None and maximum_mm is None:
            warnings.warn(
                f"{self.mount.name} selected without calibrated actuator limits. "
                "Moves are restricted to the ZFS13B travel with the requested "
                "safety margin, but this cannot guarantee protection of the mount.",
                UserWarning,
                stacklevel=3,
            )

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
