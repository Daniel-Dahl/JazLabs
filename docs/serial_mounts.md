# Serial mount drivers

Install the serial extra with `pip install -e '.[serial]'`. Use an OS serial
port, e.g. `COM5` on Windows or `/dev/ttyUSB0` on Linux. Close Kinesis,
Newport's GUI, and other programs using that port first.

```python
from JazLabs.hardware.MotorisedStages.Thorlabs.UMC2SerialStage import UMC2SerialStage
from JazLabs.hardware.MotorisedStages.Newport.newport_agp_serial_stage import NewportAGPSerialStage
from JazLabs.hardware.MotorisedStages.Newport.newport_agap_serial_stage import NewportM100DSerialStage, Axes

with UMC2SerialStage("COM5") as stage:
    print(stage.GetPositions())  # [X, Y], native controller counts
    print(stage.GetStatusBits("X"))  # trajectory and encoder separately
    # stage.Enable("X")
    # stage.HomeAll(wait=True)
    # stage.MoveRel("X", 100, wait=True)

with NewportAGPSerialStage("COM6", units="mm") as stage:
    print(stage.GetPositions())  # one axis; units depend on fitted stage
    # stage.HomeAll(wait=True)  # explicit homing, required before AGP moves
    # stage.MoveAbs("X", 1.0, wait=True)

with NewportM100DSerialStage("COM7") as mount:
    print(mount.GetPositions())  # {"U": ..., "V": ...}, degrees
    # mount.MoveAbs(Axes.YAW, 0.1, wait=True)
```

Movement lines are commented so running the example only reads positions.
Choose motion targets suitable for the installed mechanism. Connection does
not home, enable motors, or change actuator configuration. `SetNominal` moves
to native zero; it is not a calibrated mechanical midpoint. UMC2 has no assumed
millimetre scaling or software travel limits because these depend on the fitted
stage. Its axes 0/X and 1/Y address bays 0x21 and 0x22 with channel 1. Custom bay
addresses can be supplied with `destinations`. A new move on an axis already
moving is rejected; poll `GetStatusBits` before another asynchronous move.

Newport drivers use CRLF and XON/XOFF at 921600 baud. `wait=True` polls the
model's documented ready states, reports controller errors, and times out after
`move_timeout` seconds. `wait=False` checks command acceptance but does not wait
for motion. AGAP uses absolute sensors and has no homing command. AGP uses the
stage's configured physical units, rather than uncalibrated Agilis step counts.
Setting `units` labels these values; it does not configure the controller.

The Newport package contains only three controller implementations:

- `newport_agp_serial_stage.py`: `NewportAGPSerialStage` (single axis).
- `newport_agap_serial_stage.py`: `NewportM100DSerialStage` and `Axes` (U/V).
- `newport_esp300.py`: `NewportESP300` (serial ESP300 controller).

All use pyserial directly, with an OS port name rather than a VISA resource.
Legacy VISA drivers, import hubs, aliases, and the old Agilis helpers have been
removed. AG-UC8 is not supported by these CONEX drivers; it needs its own verified
serial implementation if that controller is needed again. ESP300 already writes
ASCII commands directly over pyserial and does not need a VISA conversion.

The Newport tip/tilt alignment routine now uses the serial AGAP and AGP APIs.
Focus optimisation uses absolute AGP positions and requires an explicit
`d_FOCUS` in the stage's configured units; the old open-loop step-size default
is not carried over to physical-unit AGP stages.

The new motor console and snapshot/intent service are documented in
[motor_control.md](motor_control.md). The old motor network command protocol has
been replaced; use `CONEXAGAPSerial` with a `port` argument for the M100D mount.

Protocol references:

- Local `apt_communications_protocol.pdf`, issue 48: UMC applicability pp. 31–32,
  bay routing p. 39, UMC status pp. 142–146.
- [Newport AGP controller documentation](https://api.p1.mks.com/medias/sys_master/resources/h63/h6e/10140496101406/CONEX-AGP%20-%20Controller%20Documentation/CONEX-AGP-Controller-Documentation.pdf).
- [Newport AGAP controller documentation](https://www.newport.com/medias/sys_master/images/images/h55/h76/8948435550238/CONEX-AGAP-Controller-Documentation.pdf).

Tests use simulated serial ports; physical hardware validation is still needed.
