# Motor control

The new motor GUI has two views: **alignment**, with a directional pad and a
selected-axis positioning panel, and **console**, with controls for every axis.
It replaces the old motor GUI and its network command protocol. The desktop
uses a black theme with dark panels and high-contrast status indicators.

The architecture follows [core_concepts.md](core_concepts.md):

`Widget -> MotorisedStageClient -> MotorisedStageZMQServer -> stage driver`

The widget never opens serial ports or instantiates drivers. The client provides
commands and background network polling; scheduling and stop priority belong to
the server. Serial framing and unit conversion belong to each driver. The
simulator lives in `SimulatedStage.py` and is selected like any other driver.
There is no separate control/adapter module between these objects.

## Try it without hardware

From the repository root:

```sh
PYTHONPATH=src python -m JazLabs.hardware.MotorisedStages.MotorisedStage_Widget --demo-mirror
PYTHONPATH=src python -m JazLabs.hardware.MotorisedStages.MotorisedStage_Widget --demo-axes 1
PYTHONPATH=src python -m JazLabs.hardware.MotorisedStages.MotorisedStage_Widget --demo-axes 3 --layout console
```

After installing the project, the same options are available through
`jazlabs-motors`. Tkinter must be available in the Python installation. The
simulator requires no serial controller, and labels itself as simulated. The
launcher starts a localhost server on an unused port and gives its client to
the widget. Closing that demo closes the client and its owned server.

## Named motor configurations and notebook

`JazLabs.launchers.configs.motorised_mounts` defines `MOTOR_SERVERS` entries for:

- `newport_tip_tilt`: CONEX-AGAP / AG-M100D, U/V in degrees, port 50941.
- `newport_translation`: CONEX-AGP, X with an mm unit label, port 50942.
- `thorlabs_umc2`: UMC2, X/Y in native counts, port 50943.
- `simulation`: a two-axis simulation, port 50944.

Edit `stage_kwargs.port` for hardware entries, or override it at launch. Calibrate
`limits` for the installed mechanism before enabling position sliders. Verify the
AGP preset's unit label against the fitted translation stage; the label does not
configure its firmware or calibrate it.

```sh
jazlabs-motors --serve --config motorised_mounts --name newport_tip_tilt --port COM5
jazlabs-motors --serve --config motorised_mounts --name newport_translation --port COM6
jazlabs-motors --serve --config motorised_mounts --name thorlabs_umc2 --port COM7
jazlabs-motors --connect 127.0.0.1 --config motorised_mounts --name newport_tip_tilt
```

CLI options override the selected config. The notebook
`notebooks/instrument_clients/motorised_mount_client.ipynb` loads the same entries,
prints a matching server command, verifies the connected stage type and units,
and demonstrates feedback, homing, relative/absolute moves, stop, and disconnect.
Motion is disabled by default; it never opens a serial driver directly.

## Connect hardware locally

Install serial support with `pip install -e '.[serial]'`. Close any other program
using the controller's serial port, then use one of:

```sh
jazlabs-motors --stage KST201Serial --port COM5
jazlabs-motors --stage UMC2Serial --port COM6 --limits '{"X": [-10000, 10000], "Y": [-10000, 10000]}'
jazlabs-motors --stage CONEXAGAPSerial --port COM7 --limits '{"U": [-0.5, 0.5], "V": [-0.5, 0.5]}'
jazlabs-motors --stage CONEXAGPSerial --port COM8 --driver-options '{"units": "mm"}' --limits '{"X": [0, 10]}'
```

**The limits above are examples, not a calibration of your mechanism.** Use
limits measured for the installed mount. JSON examples use POSIX shell quoting;
on Windows, pass equivalent JSON using your shell's quoting rules.

Supported hardware selections are `KST201Serial`, `KDC101Serial`, `BSC203Serial`,
`UMC2Serial`, `CONEXAGPSerial`, and `CONEXAGAPSerial`.

- KST201 displays millimetres using its actuator profile. Existing configured
  travel and safety margin are preserved; GUI limits may only narrow them.
- KDC101, BSC203, and UMC2 display native controller counts. No physical scaling
  is guessed. The UMC2 readout is its trajectory position, not an assumed
  encoder-to-physical conversion. BSC203 axes follow the existing Z, X, Y order, including custom
  slot order supplied through `--driver-options`.
- AGAP displays U/V angles in degrees and uses absolute sensors, so there is no
  home action. AGP uses the stage's configured physical units; `units` is only
  a label and does not reconfigure the controller.
- A slider is available only when both finite travel endpoints are configured.
  Dragging previews a target; releasing sends one absolute move. Endpoint
  validation also happens in the hardware worker, including for network clients.
- Speed controls appear for drivers that expose velocity configuration. The
  simulator supports them. Current serial drivers do not expose verified
  physical-unit velocity configuration, so hardware speed controls are disabled.
  The GUI does not invent a speed conversion from position scaling.

Thorlabs drivers share low-level APT wire mechanics inside
`Thorlabs/apt_serial_motion.py`. The server uses driver methods and never builds
serial packets. Newport commands remain in their individual driver files. Connection itself does not home or enable motors. If an axis is disabled,
use **Enable axis** before homing/moving. An unreferenced AGP can be homed directly.

## Jogging and stopping

Enable **Keyboard control** before using the keys:

- A/D: first axis, negative/positive.
- W/S: second axis, positive/negative.
- Q/E: third axis, negative/positive.
- Tap: one relative step of the configured distance.
- Hold: after a short initial delay, issue another step whenever the current
  move completes. The application owns repetition; OS key-repeat events cannot
  build a queue. Only one direction/axis moves at a time.
- Release: finish the current step and cancel further repetition. Choose a small
  step when you need a short release distance. Changing layout, editing a value,
  minimizing, or losing application focus disarms keyboard control.
- Escape or **STOP ALL AXES**: interrupt motion using each controller's stop
  command, discard pending intents and held-key leases, and latch movement off.
  Use **Re-enable motion** after feedback confirms all axes are stopped.

Stop remains available while moving or homing. It bypasses ordinary intents;
APT status reads check for it during finite serial waits. A Newport transaction
already awaiting a reply can delay transmission until its serial timeout.
This is a software stop, not a physical emergency-stop circuit. A lost serial
link cannot deliver a stop; the GUI reports stale feedback and disables moves.
Closing the GUI requests a stop and closes its connection. Closing a remote GUI
stops the mount but leaves its server running.

Measured position and reference state come from live controller feedback. The
GUI shows homed, needs homing, homing, disabled, moving, absolute sensor, fault,
or stale feedback. It does not declare an axis homed merely because a home
command was sent. Invalid targets, resolution-sized moves, and motion timeouts
are reported explicitly. Newport target precision is six decimal places;
completion uses a 0.001 displayed-unit tolerance, not a claim of encoder accuracy.

## Run the service on the hardware computer

```sh
jazlabs-motors --serve --stage KST201Serial --port COM5
jazlabs-motors --connect 127.0.0.1 --layout alignment
```

For a trusted lab network, explicitly bind the hardware service with
`--bind 0.0.0.0`, then point `--connect` at that computer. The service defaults to
localhost and port 50931; change both ends with `--command-port`. This protocol
has no authentication and should be kept on a trusted network.

The network thread acknowledges intents without waiting for motion completion.
One hardware worker owns the driver; all clients read cached snapshots. Normal
commands have one pending slot. Stops use a separate event and invalidate queued
work. Held-key jogs must be renewed and expire after 350 ms without renewal, so
loss of a GUI/network connection cannot create an endless sequence of moves.
An absolute move already accepted by the controller can finish if the GUI
crashes; the lease applies to repeated jogging, not arbitrary moves.

Scripts can use the motor client without the GUI:

```python
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient

client = MotorisedStageClient()
try:
    print(client.GetMotionCapabilities())
    print(client.GetAxisState("X"))
    # client.MoveTo("X", 1.0)
    # Poll state until commanded/moving/homing are false before the next move.
    # client.StopAll()
finally:
    client.close()
```

For direct serial access, instantiate the driver instead. The same basic
capability, state, movement and homing methods are provided by the driver:

```python
from JazLabs.hardware.MotorisedStages.Newport import NewportAGPSerialStage

stage = NewportAGPSerialStage(port="COM5", units="mm")
try:
    print(stage.GetMotionCapabilities())
    print(stage.GetAxisState("X"))
    # stage.HomeAxis("X")
    # stage.MoveTo("X", 1.0)
finally:
    stage.CloseStage()
```

Direct driver use bypasses server scheduling and additional server travel limits;
the script must poll completion and handle its own motion sequence. `MoveTo`
uses the units advertised by `GetMotionCapabilities` (KST201: mm). The existing
Thorlabs `MoveAbs`/`MoveRel` methods still use their documented native counts.

Commands are `state`, `absolute`, `relative`, `home`, `enable`, `speed`, `jog`,
`release_jog`, `stop`, `resume`, and `shutdown`. An acknowledgement means the
intent was submitted; check the subsequent snapshot for acceptance/completion
and errors. A timeout on a motion request has an unknown outcome; do not blindly
retry it. The GUI requests a stop before reconnecting after a transport failure.

## Validation

```sh
PYTHONPATH=src python -m pytest -q tests/test_motor_control.py tests/test_serial_mount_protocols.py tests/test_motor_control_network.py
JAZLABS_TEST_MOTOR_GUI=1 PYTHONPATH=src python -m pytest -q tests/test_motor_control_gui.py
```

GUI tests require a desktop display. Network tests use temporary localhost ports.
Protocol tests use simulated serial responses, not physical motors. Verify routing,
limits, homing and stop behavior on the installed controller before lab use.
