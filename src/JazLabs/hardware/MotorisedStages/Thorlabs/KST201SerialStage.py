"""
Serial (APT protocol) control for a Thorlabs KST201 stepper controller.

The default actuator profile is the ZFS13B. Native APT positions are Trinamic
microsteps; convenience methods are supplied for positions in millimetres.
"""

from dataclasses import dataclass
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
    - ``MoveAbs`` and ``MoveRel`` use native controller microsteps.
    - ``MoveAbsMM`` and ``MoveRelMM`` use millimetres of actuator motion.
    - One KST201 drives one actuator. A two-axis mount uses two controllers.
    """

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
    ) -> None:
        self.port = port
        self.baudrate = int(baudrate)
        self.timeout = float(timeout)
        self.move_timeout = float(move_timeout)
        if self.move_timeout <= 0:
            raise ValueError("move_timeout must be positive.")
        self.actuator = self._resolve_actuator(actuator)
        self.mount = self._resolve_mount(mount)
        self.mount_axis = self._resolve_mount_axis(mount_axis)
        self.channel = 1

        self.source = 0x01
        self.destination = 0x50

        self.MGMSG_HW_NO_FLASH_PROGRAMMING = 0x0018
        self.MGMSG_MOT_REQ_POSCOUNTER = 0x0411
        self.MGMSG_MOT_GET_POSCOUNTER = 0x0412
        self.MGMSG_MOT_REQ_STATUSBITS = 0x0429
        self.MGMSG_MOT_GET_STATUSBITS = 0x042A
        self.MGMSG_MOT_MOVE_HOME = 0x0443
        self.MGMSG_MOT_MOVE_RELATIVE = 0x0448
        self.MGMSG_MOT_MOVE_ABSOLUTE = 0x0453
        self.MGMSG_MOT_MOVE_COMPLETED = 0x0464
        self.MGMSG_MOT_SET_TSTACTUATORTYPE = 0x04FE

        self.minimum_mm, self.maximum_mm = self._build_motion_limits(
            minimum_mm, maximum_mm, safety_margin_mm
        )
        self.minimum_counts = self.actuator.mm_to_counts(self.minimum_mm)
        self.maximum_counts = self.actuator.mm_to_counts(self.maximum_mm)

        if self.mount is not None and minimum_mm is None and maximum_mm is None:
            warnings.warn(
                f"{self.mount.name} selected without calibrated actuator limits. "
                "Moves are restricted to the ZFS13B travel with the requested "
                "safety margin, but this cannot guarantee protection of the mount.",
                UserWarning,
                stacklevel=2,
            )

        self.serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
        )

        self._send_short(self.MGMSG_HW_NO_FLASH_PROGRAMMING, 0x00)
        time.sleep(0.05)

        if configure_actuator:
            self.ConfigureActuator()

        self.GetPositions()

    def __del__(self):
        try:
            self.CloseStage()
        except Exception:
            pass

    @staticmethod
    def _resolve_actuator(actuator: str | ActuatorProfile) -> ActuatorProfile:
        if isinstance(actuator, ActuatorProfile):
            return actuator
        key = str(actuator).strip().upper()
        try:
            return _ACTUATORS[key]
        except KeyError as exc:
            raise ValueError(f"Unknown KST201 actuator '{actuator}'. Supported: ZFS13B.") from exc

    @staticmethod
    def _resolve_mount(mount: str | MountProfile | None) -> MountProfile | None:
        if mount is None or isinstance(mount, MountProfile):
            return mount
        key = str(mount).strip().upper()
        try:
            return _MOUNTS[key]
        except KeyError as exc:
            raise ValueError(f"Unknown KST201 mount '{mount}'. Supported: PY004/M.") from exc

    def _resolve_mount_axis(self, mount_axis: str | None) -> str | None:
        if self.mount is None:
            if mount_axis is not None:
                raise ValueError("mount_axis can only be specified when mount is specified.")
            return None
        if self.actuator.name not in self.mount.supported_actuators:
            raise ValueError(f"{self.actuator.name} is not listed for mount {self.mount.name}.")
        if mount_axis is None:
            raise ValueError("Specify mount_axis='PITCH' or mount_axis='YAW' for PY004/M.")
        axis = str(mount_axis).strip().upper()
        self.mount.angle_range_deg(axis)
        return axis

    def _build_motion_limits(
        self,
        minimum_mm: float | None,
        maximum_mm: float | None,
        safety_margin_mm: float,
    ) -> tuple[float, float]:
        margin = float(safety_margin_mm)
        if margin < 0:
            raise ValueError("safety_margin_mm must be non-negative.")
        lower = 0.0 if minimum_mm is None else float(minimum_mm)
        upper = self.actuator.travel_mm if maximum_mm is None else float(maximum_mm)
        if lower < 0 or upper > self.actuator.travel_mm or lower >= upper:
            raise ValueError(
                f"Motion endpoints must satisfy 0 <= minimum_mm < maximum_mm <= "
                f"{self.actuator.travel_mm:g} for {self.actuator.name}."
            )
        lower += margin
        upper -= margin
        if lower >= upper:
            raise ValueError("safety_margin_mm leaves no usable actuator travel.")
        return (lower, upper)

    def _check_axis(self, axis) -> None:
        valid = {0, 1, "0", "1", "X", "x", "U", "u"}
        if self.mount_axis is not None:
            valid.update({self.mount_axis, self.mount_axis.lower()})
        if axis not in valid:
            extra = f", '{self.mount_axis}'" if self.mount_axis else ""
            raise ValueError(f"Invalid KST201 axis. Use one of: 0, 1, 'X', 'U'{extra}.")

    def _check_target_counts(self, value: int | float) -> int:
        target = int(round(value))
        if not self.minimum_counts <= target <= self.maximum_counts:
            target_mm = self.actuator.counts_to_mm(target)
            raise ValueError(
                f"Target {target} microsteps ({target_mm:.6f} mm) is outside "
                f"the allowed range {self.minimum_counts}..{self.maximum_counts} "
                f"microsteps ({self.minimum_mm:g}..{self.maximum_mm:g} mm)."
            )
        return target

    def _send_short(self, msg_id: int, param1: int, param2: int = 0) -> None:
        msg = struct.pack(
            "<HBBBB",
            msg_id,
            int(param1),
            int(param2),
            self.destination,
            self.source,
        )
        self.serial.write(msg)

    def _send_data(self, msg_id: int, payload: bytes) -> None:
        header = struct.pack(
            "<HHBB",
            msg_id,
            len(payload),
            self.destination | 0x80,
            self.source,
        )
        self.serial.write(header + payload)

    def _read_exact(self, nbytes: int) -> bytes:
        data = self.serial.read(nbytes)
        if len(data) != nbytes:
            raise TimeoutError(f"Timed out reading {nbytes} bytes (got {len(data)})")
        return data

    def _read_packet(self) -> tuple[int, bytes]:
        header = self._read_exact(6)
        msg_id = struct.unpack("<H", header[:2])[0]
        if (header[4] & 0x80) == 0:
            return (msg_id, b"")
        payload_len = struct.unpack("<H", header[2:4])[0]
        return (msg_id, self._read_exact(payload_len))

    def _wait_for_payload(self, response_id: int, timeout_s: float = 2.0) -> bytes:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                msg_id, payload = self._read_packet()
            except TimeoutError:
                continue
            if msg_id == response_id:
                return payload
        raise TimeoutError(f"Timeout waiting for APT response 0x{response_id:04X}")

    def _wait_move_completed(self, timeout_s: float | None = None) -> None:
        timeout_s = self.move_timeout if timeout_s is None else float(timeout_s)
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            try:
                msg_id, payload = self._read_packet()
            except TimeoutError:
                continue
            if msg_id == self.MGMSG_MOT_MOVE_COMPLETED:
                if len(payload) < 2 or struct.unpack("<H", payload[:2])[0] == self.channel:
                    return
        raise TimeoutError(f"Timeout waiting {timeout_s:g} s for KST201 move complete")

    def ConfigureActuator(self) -> None:
        """Tell the KST201 to use its built-in configuration for this actuator."""
        self._send_short(self.MGMSG_MOT_SET_TSTACTUATORTYPE, self.actuator.actuator_type_id)

    def GetProperties(self) -> dict:
        angle_range = None
        if self.mount is not None and self.mount_axis is not None:
            angle_range = self.mount.angle_range_deg(self.mount_axis)
        return {
            "stage_type": "KST201Serial",
            "port": self.port,
            "baudrate": self.baudrate,
            "timeout": self.timeout,
            "move_timeout": self.move_timeout,
            "channel": self.channel,
            "units": "controller_microsteps",
            "actuator": self.actuator.name,
            "microsteps_per_mm": self.actuator.microsteps_per_mm,
            "actuator_travel_mm": self.actuator.travel_mm,
            "allowed_position_mm": (self.minimum_mm, self.maximum_mm),
            "allowed_position_counts": (self.minimum_counts, self.maximum_counts),
            "mount": None if self.mount is None else self.mount.name,
            "mount_axis": self.mount_axis,
            "mount_angle_range_deg": angle_range,
            "mount_note": None if self.mount is None else self.mount.note,
        }

    def GetPositions(self) -> list[float]:
        self._send_short(self.MGMSG_MOT_REQ_POSCOUNTER, self.channel)
        payload = self._wait_for_payload(self.MGMSG_MOT_GET_POSCOUNTER)
        if len(payload) < 6:
            raise RuntimeError("KST201 returned an invalid position response.")
        channel, position = struct.unpack("<Hi", payload[:6])
        if channel != self.channel:
            raise RuntimeError(f"KST201 returned position for unexpected channel {channel}.")
        return [float(position)]

    def GetPositionsMM(self) -> list[float]:
        return [self.actuator.counts_to_mm(position) for position in self.GetPositions()]

    def MoveAbs(self, axis, value, wait: bool = False) -> None:
        self._check_axis(axis)
        target = self._check_target_counts(value)
        self._send_data(self.MGMSG_MOT_MOVE_ABSOLUTE, struct.pack("<Hi", self.channel, target))
        if wait:
            self._wait_move_completed()

    def MoveAbsMM(self, axis, value_mm: float, wait: bool = False) -> None:
        self.MoveAbs(axis, self.actuator.mm_to_counts(value_mm), wait=wait)

    def MoveRel(self, axis, value, wait: bool = False) -> None:
        self._check_axis(axis)
        delta = int(round(value))
        current = int(round(self.GetPositions()[0]))
        self._check_target_counts(current + delta)
        self._send_data(self.MGMSG_MOT_MOVE_RELATIVE, struct.pack("<Hi", self.channel, delta))
        if wait:
            self._wait_move_completed()

    def MoveRelMM(self, axis, value_mm: float, wait: bool = False) -> None:
        self.MoveRel(axis, self.actuator.mm_to_counts(value_mm), wait=wait)

    def GetStatusBits(self) -> dict:
        self._send_short(self.MGMSG_MOT_REQ_STATUSBITS, self.channel)
        payload = self._wait_for_payload(self.MGMSG_MOT_GET_STATUSBITS)
        if len(payload) < 6:
            raise RuntimeError("KST201 returned invalid status bits.")
        channel, bits = struct.unpack("<HI", payload[:6])
        if channel != self.channel:
            raise RuntimeError(f"KST201 returned status for unexpected channel {channel}.")
        return {
            "raw": bits,
            "cw_hardware_limit": bool(bits & 0x00000001),
            "ccw_hardware_limit": bool(bits & 0x00000002),
            "homing": bool(bits & 0x00000200),
            "homed": bool(bits & 0x00000400),
        }

    def HomeAll(self) -> None:
        self._send_short(self.MGMSG_MOT_MOVE_HOME, self.channel)

    def SetNominal(self, wait: bool = False) -> None:
        midpoint_mm = (self.minimum_mm + self.maximum_mm) / 2.0
        self.MoveAbsMM(self.mount_axis or "X", midpoint_mm, wait=wait)

    def CloseStage(self) -> None:
        if self.serial is not None and self.serial.is_open:
            self.serial.close()
