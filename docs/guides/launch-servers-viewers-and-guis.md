# Launch Servers, Viewers, and Control GUIs

JazLabs separates hardware access from viewing and control. A **server** owns
the hardware connection and keeps running while one or more **clients** read
its state, display live data, or send commands. A client can be a graphical
viewer, a control GUI, or Python experiment code. Starting the server first
ensures that none of these clients need to open the hardware directly.

The exact processes depend on where the hardware is connected:

- A camera server and its clients can run on the same computer.
- An SLM can use a hardware-facing server on Windows and a bridge/server on
  Linux. Linux clients then use the local bridge and shared-memory image.

The examples use `src/JazLabs/launchers/configs/default_lab.py`. Edit its
connection details for your hardware before launching. Additional instrument
examples are disabled for bulk launch until configured; an explicit `--name`
command still selects that entry.

## Before You Start

- Install JazLabs on every computer that will run a server, bridge, or client.
- Power on the hardware and install any required vendor drivers or SDKs.
- Check the selected file under `src/JazLabs/launchers/configs/`.
- Set `camera_serial_number` for every camera entry. JazLabs does not select a
  camera by discovery index; startup fails if the requested serial is missing
  or not detected.
- Confirm that configured hosts and ports are correct and not already in use.
- For a connection between computers, confirm that the hosts can reach each
  other and that the configured ports are allowed through their firewalls.

The server and clients must use matching configuration values. A server can
bind to `0.0.0.0` to accept remote connections, but a client must connect to a
real host name or IP address rather than `0.0.0.0`.

## General Workflow

Bringing a supported instrument online normally follows the same pattern:

1. Add or select a hardware entry in a launcher configuration. Define its
   hardware type or identifier, server host, command port, and any data-stream
   ports or shared-memory names required by that instrument stack.
2. Start the hardware-facing server and leave it running. This process owns the
   vendor driver and physical device connection.
3. Start the matching viewer or control GUI with the same configuration. Use
   it to confirm that data and status are updating.
4. Connect experiment code through the instrument's client class, using the
   same host, ports, and stream settings as the server.
5. Close client objects when the experiment finishes, then stop the server.

The camera and SLM examples below show this pattern with two different data
paths: local camera shared memory and a networked SLM bridge.

The sections below also cover motors, Time Taggers, DAC/DAQ controllers,
optical switches, digital holography, and direct power-meter connections.

Minimal Python clients for the other instrument stacks are indexed in the
[`Instrument Client Examples`](instrument-client-examples.md) guide.

Jump to an instrument:

- [Camera](#example-1-camera-server-and-clients-on-one-computer)
- [SLM](#example-2-regular-slm-server-bridge-and-viewer)
- [Laser](#example-3-laser-server-gui-and-client)
- [Motors](#example-4-motor-server-bridge-and-control-gui)
- [Time Tagger](#example-5-time-tagger-server-bridge-and-client)
- [DAC/DAQ](#example-6-dacdaq-server-bridge-and-voltage-gui)
- [Optical switches](#example-7-optical-switch-server-and-gui)
- [Digital holography](#example-8-digital-holography-viewer)
- [Power meters](#example-9-power-meter-connection)

## Example 1: Camera Server and Clients on One Computer

In this arrangement, the camera, server, live viewer, and control GUI are all
on the camera computer:

```text
Camera hardware
      |
      v
Camera server
      |
      +----> Live image viewer
      |
      `----> Camera control GUI
```

The `default_lab` configuration sets `CAMERA_HOST` to `127.0.0.1`, so the clients
connect back to the server on the same computer.

### 1. Start the camera server

In the first terminal, run:

```bash
jazlabs-server-camera --config default_lab --name cam_slm
```

The server opens the configured camera, creates the frame stream, and listens
on the configured command and frame-publication ports. Wait until it reports
that it is running, then leave this terminal open.

### 2. Start the client viewer and control GUI

In a second terminal on the same computer, run:

```bash
jazlabs-view-camera --config default_lab --name cam_slm
```

This client launcher opens two windows:

- the live viewer, which displays frames received from the server; and
- the control GUI, which reads camera status and sends acquisition, trigger,
  exposure, gain, frame-rate, pixel-format, and ROI commands to the server.

The client is connected when the GUI reports `alive: True`. During continuous
acquisition it should also report `acquisition: True`, and the viewer's frame
counter should keep increasing.

![Example live camera feed with frame information](assets/server-client-viewers/camera-live-feed.png)

The information panel beneath the image shows the frame shape and counter,
pixel format, raw minimum and maximum, saturation state, display contrast,
zoom, cursor value, and any selected display ROI. Contrast and zoom affect the
viewer only; hardware acquisition settings are changed through the control
GUI.

![Camera control GUI connected to a running server](assets/server-client-viewers/camera-control-gui.png)

The control GUI communicates with the server rather than opening the camera
itself. This allows the server to remain the single owner of the hardware
connection.

To open only one client window, use:

```bash
# Live image only
jazlabs-view-camera --config default_lab --name cam_slm --no-widget

# Camera controls only
jazlabs-view-camera --config default_lab --name cam_slm --no-viewer
```

To open clients for all camera entries that are enabled in the configuration,
start their servers first and then run:

```bash
jazlabs-view-camera --config default_lab --all
```

For integrated spot-power readout from the same camera, use the optional
`SPOT_POWER_VIEWERS` example and enter spot centres in its GUI or supply a
centres file in the config:

```bash
jazlabs-view-spot-power --config default_lab --name cam_slm_spots
```

### 3. Connect from Python code

Experiment code connects to the same camera server as the viewer and GUI. It
must use the server's reachable host, command port, and frame-publication port.
For `cam_slm` in the `default_lab` configuration, a minimal client is:

```python
from JazLabs.hardware.Cameras.Camera_Client import CameraClient


camera_client = None

try:
    camera_client = CameraClient(
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        timeout_ms=60_000,
        client_id="camera_connection_example",
    )

    print("Server alive:", camera_client.IsServerAlive())
    print("Camera serial number:", camera_client.GetSerialNumber())
    print("Exposure [us]:", camera_client.GetExposureTime())

    previous_counter = camera_client.GetFrameCounter()
    frame = camera_client.GetFrame(
        WaitForNewFrame=True,
        LastFrameCounter=previous_counter,
    )
    print("Received frame:", frame.shape, frame.dtype)
finally:
    if camera_client is not None:
        camera_client.close()
```

The two ports have different jobs:

- `command_port` carries requests and replies, such as reading exposure or
  changing trigger mode.
- `frame_pub_port` announces new frames; the client reads the corresponding
  image from server-owned shared memory.

These values must match the selected entry in `CAMERA_SERVERS`. This camera
example deliberately runs the server and client on the same computer because
the current camera stack stores frame pixels in local shared memory. Changing
`127.0.0.1` to a remote IP is not enough to make that shared memory available
on another computer; use the camera bridge stack when remote frame access is
required. Give concurrent clients distinct `client_id` values so server logs
and errors identify the caller.

Always close the client in a `finally` block. Closing a client releases its
network sockets and shared-memory attachments; it does not shut down the
camera server or prevent another client from remaining connected.

## Example 2: Regular SLM Server, Bridge, and Viewer

The standard SLM stack is `SLMStack`. It uses `SLM_SERVER`, `SLM_BRIDGE`, and
`SLM_VIEWER` in `default_lab.py` and does not require pyMilk. Select the SLM type,
monitor or board number, and LUT for the attached hardware.

### 1. Start the hardware server

On the computer connected to the SLM:

```bash
jazlabs-server-slm --config default_lab
```

The example server listens on command port `5555` and display-publication port
`5556`. The regular stack supports a local server and clients as well as a
bridge to another computer.

### 2. Start the bridge

On the control computer, use the reachable address of the SLM computer:

```bash
jazlabs-bridge-slm --config default_lab --remote-host 192.168.1.25
```

For a same-computer example, omit `--remote-host`: the config uses `127.0.0.1`.
The bridge connects to server ports `5555`/`5556`, exposes local ports
`5565`/`5566`, and maintains a local shared-memory image for clients and viewers.
Distinct local and remote ports allow both processes to run on one computer.

### 3. Open the viewer or connect a client

The default viewer connects to the local bridge:

```bash
jazlabs-view-slm --config default_lab
```

To view a same-computer server directly, skip the bridge and override the ports:

```bash
jazlabs-view-slm --config default_lab --command-port 5555 --display-pub-port 5556
```

Python clients use the bridge's local endpoint:

```python
from JazLabs.hardware.SLM.SLMStack.SLM_Client import SLMClient

slm = SLMClient(host="127.0.0.1", command_port=5565, display_pub_port=5566)
try:
    print(slm.GetProperties())
finally:
    slm.close()
```

See `examples/instrument_clients/slm_client.py` for displaying phase masks.
A direct connection to a server on another computer does not provide access to
its local shared memory; run the bridge on the client computer instead.

### Optional: MILK integration

`SLMStackMilk` is an additional transport for workflows that need pyMilk/ImageStreamIO
shared-memory streams. It is separate from the regular stack above. Uncomment
and configure the optional `SLM_MILK_*` settings in `default_lab.py`, including
the hardware computer's `server_host`, then start `jazlabs-server-slm-milk`,
`jazlabs-bridge-slm-milk`, and `jazlabs-view-slm-milk` in that order, each with
`--config default_lab`. The bridge/viewer require pyMilk on the control computer.
Run this stack instead of the regular SLM stack when using its example ports.

## Example 3: Laser Server, GUI, and Client

Configure a laser entry in `src/JazLabs/launchers/configs/default_lab.py`. On the
computer connected to the laser, start the named server:

```bash
jazlabs-server-laser --config default_lab --name tunable_laser
```

For clients on another computer, configure the server to bind to `0.0.0.0` and
allow the command port through the hardware computer's firewall. Then launch
the control GUI with the hardware computer's reachable address:

```bash
jazlabs-view-laser \
    --config default_lab \
    --name tunable_laser \
    --host 192.168.1.25
```

Python code uses the same address and configured command port:

```python
from JazLabs.hardware.Lasers.Laser_Client import LaserClient

laser = LaserClient(host="192.168.1.25", command_port=50921)
laser.set_wavelength_nm(1550.0)
print(laser.get_power())
laser.close()
```

Only request values that are safe for the connected laser and optical setup.
The physical interlock and operating procedure remain authoritative. A driver
that does not implement a control reports that capability as unavailable.

## Example 4: Motor Server, Bridge, and Control GUI

Motors follow the same separately launched server/bridge/client pattern as the
other instruments. The widget never starts a server or opens a serial port.

```text
Serial motor controller
        |
        v
Motor server (hardware computer)
        |
        +----> Motor client / GUI on the same computer
        |
        `----> Motor bridge (control computer)
                       |
                       +----> Motor control GUI
                       `----> Motor client / experiment notebook
```

There is no continuous image stream or shared memory for motors. Commands and
position/status snapshots travel over the command endpoint. All serial commands
stay in the stage driver; the hardware server schedules motion and polls status.
Users can also instantiate a serial driver directly from a script when a server
is not wanted. The widget always uses the client.

### 1. Configure the mount

The presets in `src/JazLabs/launchers/configs/default_lab.py` use
`MOTOR_SERVERS`, with one named entry per controller:

| Name | Controller | Axes and displayed units | Server port | Local bridge port |
|---|---|---|---:|---:|
| `newport_tip_tilt` | CONEX-AGAP / AG-M100D | U = yaw, V = pitch; degrees | 50941 | 51941 |
| `newport_translation` | CONEX-AGP | X; configured physical units, labelled mm in the preset | 50942 | 51942 |
| `thorlabs_umc2` | UMC2 | Separate mounts X/Y; counts and calibrated mm | 50943 | 51943 |
| `simulation` | Simulated translation stage | X/Y; mm | 50944 | 51944 |

For serial hardware, install `pip install -e '.[serial]'`, then replace
`stage_kwargs.port = None` with the hardware computer's port, such as `COM5` or
`/dev/ttyUSB0`. A `--serial-port` override is also available. Close Kinesis,
Newport's GUI, and other programs using that port first. These drivers use
pyserial directly and do not require a VISA backend. The AGP translation preset
is not an AG-UC8 driver; check the controller model before selecting it.

Configure these fields for the selected mount:

- `host` / `command_port`: where the hardware server binds.
- `client_host`: reachable hardware-server address for a direct client.
- `stage_type` / `stage_kwargs`: controller selection and driver settings.
- `stage_kwargs.limits`: calibrated lower/upper endpoints for each
  axis in the driver's configured units. Thorlabs can also use detected/profile
  bounds. The wrapper checks every absolute and relative destination, including `wait=False` calls. Missing limits allow
  readout but prevent movement. The example limits must match the installed stage.
- Top-level `limits`: optional narrower server endpoints. The server
  passes these into each serial driver; they cannot widen its configured travel limits.
  A slider is disabled without both endpoints.
- `local_host` / `local_command_port`: where a bridge binds on the control computer.
- `remote_host`: the hardware-server address a bridge connects to; it can also
  be supplied using `--remote-host`.

The UMC2 driver queries each bay's stage-axis parameters (`0x04F1/0x04F2`) on
connection. It exposes the reported part number, stage serial number, scale and
travel endpoints through `GetStatus()["axes"]`. These are controller-reported
parameters; they may reflect an assigned stage profile rather than identifying
an arbitrary attached mechanism. No homing, movement or parameter writes occur
during detection. Restart the server after changing fitted stages.

Each UMC2 bay is shown as a separate mount panel in the same GUI, with its own
label, units selector, relative step, target and slider. The units selector is
beside the position readout. The GUI prefers mm when calibrated, even if the
server's canonical units are counts, and converts a custom step when units change.
Without counts/mm calibration, it shows a disabled counts selector and an explicit
millimetre-unavailable message. Both panels share one server and COM port. The current scheduler performs one move at a time; keyboard
A/D controls the first mount and W/S the second. STOP ALL AXES stops both mounts.

The driver recognises DRV250 and NRT100(/M) as linear mechanisms. For other linear
stages, declare `physical_units="mm"` in `stage_kwargs.mounts`. It reads the
controller's `positionScale` calibration from the stage-axis packet, as defined
by `TLMC_StageAxisParams` in the [XA 1.12 SDK](https://www.thorlabs.com/software-pages/motion_control?tabName=XA%20Software).
Those float fields were marked reserved in the APT protocol document; the separate
`countsPerUnit` encoder field may be zero for a stepper mount. Older packets with
no usable position scale can use a positive counts-per-unit calibration instead.
No scale is inferred by dividing nominal travel by reported limits.
With `units="auto"`, usable millimetre calibration selects mm as the
server's canonical units; otherwise the mount stays in counts and the GUI explains
what is missing. Detection is read-only and can be disabled with `detect_stages=False`.
Use a verified `counts_per_mm` override and optional `limits_mm` if the controller
cannot report its calibration. Configured limits cannot widen detected travel.

The driver reports `unit_scales`, `limits_by_unit`, `resolution_by_unit` and
`step_by_unit` for each mount. Resolution is one native count. The suggested jog
step is an application default (0.01 mm or 100 counts, reduced for short travel),
not a motor specification; override each mount's `step` in its canonical units.
A stage's maximum velocity/acceleration fields are retained with their raw
counts-per-controller-cycle units; they do not enable GUI speed control.

KST201 uses its existing actuator profile for mm and counts. KDC101 and BSC203
accept explicit `counts_per_mm`, `units` and `limits` driver options; BSC203 accepts
a per-axis calibration dictionary. Their limits use the selected canonical units.
Do not copy calibration between different stages or controller types. For an
actuator driving an angular mount, mm refers to actuator displacement, not angle.
Verify the AGP stage's configured units: `units="mm"` is a label, not firmware
configuration or calibration.

Client examples for a calibrated Thorlabs mount:

```python
status = mount.GetStatus("X")
status["axes"]["X"]["positions"]["mm"]
status["axes"]["X"]["positions"]["counts"]
# mount.MoveRel("X", .01, units="mm")  # Checked relative move; waits by default.
# mount.MoveAbs("X", 1.0, units="mm")  # Waits for completion by default.
# mount.MoveAbs("X", 1000, units="counts")
```

An omitted `units` uses the axis's advertised canonical units. Unavailable unit
conversions raise an error rather than assuming a scale. The client and direct Thorlabs drivers both use `MoveAbs` and `MoveRel`, with
optional `units="mm"` or `units="counts"`. KST201 defaults to mm; UMC2 defaults to
mm when calibrated. KDC101/BSC203 use their configured units (counts by default).
The old native-count and millimetre-specific method variants are removed.

### 2. Start the motor server on the hardware computer

For the tip/tilt mount:

```bash
jazlabs-server-motor --config default_lab --name newport_tip_tilt --serial-port COM5
```

For the other hardware presets, in separate terminals as needed:

```bash
jazlabs-server-motor --config default_lab --name newport_translation --serial-port COM6
jazlabs-server-motor --config default_lab --name thorlabs_umc2 --serial-port COM7
```

Replace the serial port names with the actual ones, or omit `--serial-port`
once they are saved in the config. The server owns that serial port until it
stops. Driver startup does not home or enable the motors. The GUI will report
connection/startup failures rather than assume that hardware is ready.

To accept clients or a bridge from another computer, add `--host 0.0.0.0` and
allow the configured command port through the firewall on a trusted lab network.
Clients must use the computer's real address, not `0.0.0.0`. The motor protocol
has no authentication; do not expose it to an untrusted network.

### 3. Open the motor control GUI

With the server running, open another terminal on the same computer:

```bash
jazlabs-view-motor --config default_lab --name newport_tip_tilt
```

The black control GUI offers an **alignment** pad and an **axis console**:

```bash
jazlabs-view-motor --config default_lab --name newport_translation --layout console
```

For a direct connection from a different computer, supply its reachable address:

```bash
jazlabs-view-motor --config default_lab --name newport_tip_tilt --host 192.168.1.25
```

The GUI reports live position, homed/needs homing, homing, moving, disabled,
fault, and stale-feedback states. AGAP absolute sensors require no homing.
Use **Enable axis** if needed before homing or moving an incremental stage.

- Enable **Keyboard control**: A/D jog the first axis, W/S the second, and Q/E
  the third. A tap sends one configured relative step; holding repeats one step
  at a time after the preceding move completes. The server keeps at most one
  pending step while busy; additional tracked movement requests are rejected.
  Release finishes the current step and cancels further held-key repetition.
  Choose a small step for fine alignment.
- Absolute targets use the axis's displayed units. Slider dragging previews a
  target; release sends one absolute move within the configured travel limits.
- Speed controls are available only when the driver advertises support. The
  simulator supports them; physical-unit velocity configuration is currently
  unavailable through the serial drivers, so those controls remain disabled.
- Escape or **STOP ALL AXES** sends controller stop commands, clears pending
  motion, and latches motion off. **Re-enable motion** requires stopped feedback.
  This button clears the server's stop latch; **Enable axis** controls the
  controller's motor enable separately. Automatic stops show their triggering
  reason in the GUI and server terminal. Re-enabling clears the current stop
  reason. Normal user stops and client shutdowns do not produce warning logs.
  This software stop cannot replace a physical emergency stop or deliver a
  command over a disconnected serial link.

Editing a value, changing layout, minimizing, or losing application focus
releases/disarms keyboard jogging. Held-key requests expire at the hardware
server after 350 ms without renewal, so a lost client cannot queue endless jog
steps. A step or absolute move already accepted by hardware can still finish.
Closing the GUI requests a stop and closes its client; the server stays running.

### 4. Optional: bridge to the control computer

Start the hardware server first with a reachable bind address. Then, on the
control computer, start the bridge in a second terminal:

```bash
jazlabs-bridge-motor --config default_lab --name newport_tip_tilt --remote-host 192.168.1.25
```

The preset above forwards local `127.0.0.1:51941` to the hardware server's
`192.168.1.25:50941`. Distinct local ports also allow server and bridge testing
on the same computer. Override ports using `--local-command-port` and
`--remote-command-port` when needed, and give clients the matching local port.

In another terminal on the control computer:

```bash
jazlabs-view-motor --config default_lab --name newport_tip_tilt --bridge
```

The bridge forwards requests and replies and never imports a hardware driver.
It preserves position-feedback age and adds its relay time. A timed-out movement
request has an unknown outcome and is never automatically retried. Keep the
link responsive for held-key jogging; use `--timeout-ms` only to change the
finite request timeout, not the hardware server's jog lease.

### 5. Use a client or the notebook

A script connects to the same server or bridge endpoint as the GUI:

```python
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient

# Direct server: 50941. Local bridge: 51941.
mount = MotorisedStageClient(host="127.0.0.1", command_port=51941)
try:
    status = mount.GetStatus()
    print(status)                       # Configuration, limits, support flags and feedback.
    print(status["axes"]["U"]["position"])
    # mount.MoveAbs("U", 0.1)             # Waits for stopped/target feedback by default.
    # mount.MoveRel("U", 0.01)            # Checked relative move; also waits by default.
    # mount.MoveAbs("U", 0.1, wait=False) # Submit without waiting; poll status yourself.
    # mount.StopAll()
finally:
    mount.CloseStage()
```

The notebook `notebooks/instrument_clients/motorised_mount_client.ipynb` contains
short client examples, like the camera notebook. Set `HOST`, `COMMAND_PORT` and
`AXIS` to match your server (or the bridge's local endpoint). It reads positions
and status; uncomment individual move, home or stop examples when needed.
CONEX-AGP Home is available only when referencing is needed. An already referenced
controller rejects another home command in READY, so the GUI disables that button.
Enable **Keyboard control** to use A/D for the first axis, W/S for the second,
and Q/E for the third. Holding a key continues movement; releasing it stops jogging.
Typing in a number field disarms keyboard movement; enable the checkbox again to resume.

`GetStatus()` returns connection settings and an `axes` dictionary containing
position, units, limits, resolution, support flags and moving/homed/enabled/fault
feedback. `GetStatus("U")` keeps the same dictionary shape but selects one axis.
Newport and Thorlabs drivers use this one public getter; the raw-status, properties,
capabilities and separate position/status getters have been removed. For example,
`status["axes"]["U"]["supports"]["home"]` states whether homing is supported.
A direct driver call reads serial feedback; a client call reads the server's
latest cached feedback, including its age and connection state. Controller state
and error codes are retained as dictionary fields rather than separate getters.
The client and simulator also use this one getter; separate properties,
capabilities, position and axis-status getters are removed. Read a position with
`mount.GetStatus("X")["axes"]["X"]["position"]`; calibrated alternatives are in
that axis's `positions` dictionary. Connection health and axis `age` remain
visible in the same status dictionary.

`MoveAbs(axis, target, wait=True, timeout=None)` waits for that specific operation
to complete and returns its stopped axis status. The default timeout comes from
the controller's `move_timeout`, or 60 seconds. Faults, rejected moves, stop,
lost feedback and timeout raise instead of reporting success; a deadline or
unavailable feedback triggers a stop request. The client polls completion, so
the server remains responsive to a GUI or another client's Stop command. Direct
Newport/Thorlabs-driver `MoveAbs` calls also wait by default; the server explicitly
uses `wait=False` when scheduling them. The client uses the same `MoveAbs` name
for every controller. There is no `MoveTo` alias on the client, simulator or Newport/Thorlabs drivers.

The motor client follows the camera/SLM pattern: method calls communicate directly
through ZMQ, with no internal Python thread, command queue or cached status.
`GetStatus()` requests the server's current snapshot. The widget uses Tkinter
`after()` callbacks to poll status and refresh held-key jog requests, and calls
movement methods with `wait=False`. Each network call may hold the callback until
the configured reply timeout. The widget requests a stop after an established
connection fails or a command reply is lost, and explicitly stops on close.

The motor server follows the camera server's single-loop structure. The same
thread receives network requests, reads one axis's feedback at a time and tracks
move completion. There is no separate hardware worker thread. A move starts
without waiting, so the loop can continue handling requests while the motor
travels. A stop request arriving during a serial call must wait for that call to
return or time out; serial communication is not interrupted by another thread.
The command-line launcher calls `run_forever()` directly. The optional Python
`server.start()` method launches a separate process containing that same loop.

The client exposes `MoveAbs`, `MoveRel` and `HomeAxis` with `wait=True` by default,
matching the drivers. With `wait=False`, these return an `operation_id` after
submission; its completion record is in `GetStatus()["operations"]`. Lower-level
`request("absolute", ...)`, `request("relative", ...)` and `request("home", ...)`
acknowledge submission only. Never blindly retry a relative move after a timeout.
`SetNominal()` schedules each axis's midpoint in sequence and waits by default;
all travel limits are checked before the first axis moves. `EnableAxis(axis,
enabled=False)` disables an axis, and omitting `enabled` enables it.
`CloseStage()` closes the client connection. Closing a synchronous notebook/script
client does not stop the server or an active move; explicitly request `StopAll()`
when that is your intention.

Direct Newport-driver use requires explicit limits, for example:

```python
from JazLabs.hardware.MotorisedStages.Newport import NewportAGPSerialStage

with NewportAGPSerialStage("COM4", units="mm", limits={"X": [0, 27]}) as stage:
    # Replace these example limits with the calibrated limits of your stage.
    status = stage.GetStatus()
    position = status["axes"]["X"]["position"]
    # stage.MoveAbs("X", 1.0)  # Checks limits, then waits for stopped target feedback.
    # stage.MoveRel("X", .1)   # Checks the resulting absolute destination too.
```

`MoveAbs` returns the final axis-status dictionary when waiting. ESP300 reads
motion, position and error feedback using the [ESP300 manual's queries](https://www.newport.com/medias/sys_master/images/images/h2f/haa/8797091299358/ESP300-User-Manual.pdf).
The serial drivers require stopped, in-tolerance feedback. Faults or timeout
raise and request a stop.
The fixed 50 ms delay was removed from the absolute-move wait loops; each poll
waits for serial or network replies. Homing follows the controller's reference
procedure and can travel outside limits configured for ordinary moves.

The AGP wrapper exposes `HomeAxis("X", wait=True)`; the AGAP wrapper does not
expose homing because it uses absolute sensors. `StopAll` and `EnableAxis` are the
public stop/enable operations, with no duplicate `Stop` or `Enable` aliases.

Serial-driver `SetNominal(wait=True)` moves each axis to the midpoint of its
configured limits using `MoveAbs`. For example, limits `[0, 27]` give a nominal
position of `13.5`. Every axis must have limits before any nominal moves start.

Each Thorlabs driver is self-contained in its controller's Python file. The
local `write()` packs APT commands into bytes; `query()` sends a request and
reads a matching reply. Status decoding, calibration, limits and motion methods
are also local to that file; no shared APT class is required.

Direct Thorlabs-driver use follows the same pattern:

```python
from JazLabs.hardware.MotorisedStages.Thorlabs.UMC2SerialStage import UMC2SerialStage

with UMC2SerialStage("COM6") as stage:
    status = stage.GetStatus()
    mount_1 = status["axes"]["X"]
    position_mm = mount_1["positions"].get("mm")
    position_counts = mount_1["positions"]["counts"]
    # stage.HomeAxis("X")                 # Waits for homing to finish.
    # stage.MoveAbs("X", 1.0, units="mm")  # Checks limits and waits for completion.
    # stage.MoveRel("X", 100, units="counts")
    # stage.SetNominal()                  # Each mount's allowed-travel midpoint.
```

`GetStatus()` is the sole public read method on each Thorlabs wrapper; it includes
raw status bits and UMC2 stage parameters along with decoded feedback. If travel
bounds are unavailable, readout still works but ordinary moves are rejected.
Provide `limits={"X": [lower, upper], ...}` in the configured axis units.
Configured bounds may narrow detected/profile travel but cannot widen it.
KST201's optional `mount_axis` determines its axis key (for example `"PITCH"`);
KDC101 uses `"X"`, and BSC203 maps configured slots to `"Z"`, `"X"`, `"Y"` in order.

For a hardware-free test, use two terminals:

```bash
# Terminal 1
jazlabs-server-motor --config default_lab --name simulation

# Terminal 2
jazlabs-view-motor --config default_lab --name simulation
```

The simulator uses the same `GetStatus`, `MoveAbs`, `MoveRel`, `HomeAxis`,
`SetNominal`, `EnableAxis`, `SetSpeed` and `CloseStage` API as the motor system.
Its unit selector offers counts alongside mm for translation axes or degrees
for the absolute-sensor mirror. The default simulated calibration is 1000 counts
per physical unit; set `stage_kwargs.counts_per_unit` to a positive number or a
per-axis dictionary to exercise other calibrations. These are simulated scales.
Speed and travel checks also apply to direct driver calls. Disabling an axis
cancels its current command; enabling it again does not restart that command.

For direct, hardware-free use:

```python
from JazLabs.hardware.MotorisedStages.SimulatedStage import SimulatedStage

with SimulatedStage(axes=1) as stage:
    stage.MoveRel("X", 10, units="counts")  # Waits for the 0.01 mm move.
    print(stage.GetStatus("X")["axes"]["X"]["positions"])
```

The three independent module launchers can also be used without console scripts:

```bash
python -m JazLabs.launchers.launch_motorised_stage_server --config default_lab --name simulation
python -m JazLabs.launchers.launch_motorised_stage_bridge --config default_lab --name simulation --remote-host 127.0.0.1
python -m JazLabs.launchers.launch_motorised_stage_widget --config default_lab --name simulation --bridge
```

Run each in its own terminal, in the order shown. Reinstall the editable project
with `pip install -e .` if the new `jazlabs-server-motor`, `jazlabs-bridge-motor`,
and `jazlabs-view-motor` entry points are not yet available in your environment.

## Example 5: Time Tagger Server, Bridge, and Client

JazLabs operates the Time Tagger through three explicit roles:

```text
Time Tagger hardware
        |
        v
Time Tagger server on the hardware computer
        |
        | ZeroMQ request/reply connection
        v
Time Tagger bridge server on the experiment computer
        |
        v
TimeTaggerClient used by scripts, procedures, or the live window
```

The hardware server is the only process that imports the Swabian Instruments
`TimeTagger` package or creates the physical Time Tagger object. The bridge
server forwards commands and measurement results between computers. Client
code uses the same interface whether it connects to a bridge or directly to a
server.

Unlike a camera stream, Time Tagger measurements return finite arrays or
summary values. They are therefore returned with the command reply rather than
placed in shared memory.

### Configure the Time Tagger

Add an entry to `TIME_TAGGER_SERVERS` in the selected file under
`src/JazLabs/launchers/configs/`. The `default_lab` configuration includes a
disabled example:

```python
TIME_TAGGER_SERVERS = [
    {
        "name": "time_tagger",
        "host": "0.0.0.0",
        "command_port": 50931,
        "serial": None,
        "create_kwargs": {},
        "poll_timeout_ms": 100,
        "enabled": False,
    },
]
```

Set `serial` when a computer has multiple Time Taggers. Install the vendor
drivers and Python package on the hardware computer. They are not required on
the bridge or client computer.

### 1. Start the hardware server

On the computer physically connected to the Time Tagger, run:

```bash
jazlabs-server-time-tagger \
    --config default_lab \
    --name time_tagger
```

The server creates the vendor device object and listens on the configured
command port. Leave it running while measurements are being performed.

### 2. Start the bridge server

On the experiment computer, start a local bridge and give it the reachable IP
address or host name of the hardware computer:

```bash
jazlabs-bridge-time-tagger \
    --config default_lab \
    --name time_tagger \
    --remote-host 10.196.0.67
```

By default, the bridge exposes the same command port on `127.0.0.1`. Use
`--local-command-port` if that port is already occupied. Use
`--remote-command-port` when the remote server uses a different port.

### 3. Connect a client

Experiment code connects to the local bridge:

```python
from JazLabs.hardware.TimeTagger.TimeTagger_Client import TimeTaggerClient


time_tagger = TimeTaggerClient(
    host="127.0.0.1",
    command_port=50931,
    timeout_ms=120_000,
    client_id="coincidence_measurement",
)

try:
    time_tagger.SetTriggerLevel(channel=1, voltage=0.5)
    time_tagger.SetTriggerLevel(channel=2, voltage=0.5)

    result = time_tagger.MeasureCoincidences(
        channels=[1, 2],
        coincidence_window=100,
        counting_time=1.0,
    )
    print(result.coincidence_rate)
    print(result.contrast_CAR)
finally:
    time_tagger.close()
```

The client supports trigger levels, input delays, count rates, binned counts,
correlations, coincidences, and combined coincidence/correlation measurements.
Long measurements automatically extend the client receive timeout beyond the
requested counting time.

Existing helpers in `TimeTaggerFunction.py` accept a `TimeTaggerClient` and
delegate supported measurements to the server. The runnable wiring example is
`examples/legacy/example_time_tagger_client.py`.

### Stopping the stack

Close client objects first. Then stop the bridge and hardware server with
`Ctrl+C` in their terminals. `TimeTaggerClient.ShutdownServer()` is available
for controlled shutdown from Python, but should only be used by code that owns
the server lifecycle.

### Troubleshooting

- If the hardware server cannot import `TimeTagger`, install the Swabian
  Instruments software and its Python package on that computer.
- If the bridge times out, confirm the remote host, command port, firewall,
  and hardware-server terminal.
- If a client times out during a measurement, make sure the bridge timeout is
  longer than the requested counting time.
- If the wrong device opens, set its serial number in `TIME_TAGGER_SERVERS` or
  pass `--serial` to the hardware-server command.

## Example 6: DAC/DAQ Server, Bridge, and Voltage GUI

DAC voltage outputs use the DAQ stack. Configure the `daq` entry in
`DAQ_SERVERS` in `default_lab.py`: select `ni_daq`, `mcc_daq`, or
`coremorrow_daq`, the device number, channel count, and voltage limits. Serial
CoreMorrow controllers also need `serial_port`. Install the selected vendor
backend on the hardware computer.

Start the server on the hardware computer:

```bash
jazlabs-server-daq --config default_lab --name daq
```

It exposes command port `50831` and voltage-publication port `50832`. For a
remote control computer, bind the server with `--host 0.0.0.0`, then start a
bridge on the control computer:

```bash
jazlabs-bridge-daq --config default_lab --name daq --remote-host 192.168.1.25
```

The bridge uses local ports `50831`/`50832` by default. If testing server and
bridge on the same computer, choose distinct local ports with
`--local-command-port` and `--local-voltage-pub-port` and pass them to clients.

Open the voltage GUI on the server computer or on the computer running its bridge:

```bash
python -m JazLabs.hardware.DAQ_Controller.DAQ_stack.DAQ_Widget
```

That module uses `127.0.0.1:50831/50832`, matching the default example. For other
endpoints, construct the window explicitly in Python:

```python
from JazLabs.hardware.DAQ_Controller.DAQ_stack.DAQ_Widget import DAQControlWindow

window = DAQControlWindow(host="127.0.0.1", command_port=50831, voltage_pub_port=50832)
window.run()
```

`examples/instrument_clients/dac_client.py` and its matching notebook demonstrate
`DAQClient.SetVoltage()` and `GetVoltage()`. Check the example voltage against
the connected load before running it. There is currently no dedicated
`jazlabs-view-daq` command.

## Example 7: Optical Switch Server and GUI

`OPTICAL_SWITCH_SERVERS` in `default_lab.py` includes a JDS optical switch named
`optical_switch` on command port `50841`, and a polarization switch named
`pol_switch` on `50842`. Set each serial port for your hardware, then run:

```bash
jazlabs-server-optical-switch --config default_lab --name optical_switch
```

Open its control GUI:

```bash
jazlabs-view-optical-switch --config default_lab --name optical_switch
```

Use `--name pol_switch` with both commands for the polarization switch. For
network access, start the server with `--host 0.0.0.0` and give the GUI
`--host <switch-host>`. The GUI and Python client connect directly to the server;
this stack has no separate bridge launcher.

`examples/instrument_clients/optical_switch_client.py` and its notebook use
`OpticalSwitchClient.GetChannel()` and `SetChannel()`. Set the requested channel
for the connected switch before running the example.

## Example 8: Digital Holography Viewer

Digital holography processes frames from a camera client; it does not need a
separate instrument server. Start the default camera server first:

```bash
jazlabs-server-camera --config default_lab --name cam_slm
```

Install the digHolo native library and use a local GUI environment. Set the
camera pixel size, wavelength, FFT radius, and maximum mode group in
`DIGITAL_HOLOGRAPHY_CONFIG` in `default_lab.py`, then run from the repository root:

```bash
python examples/instrument_clients/digital_holography_viewer.py
```

The example reads the configured camera connection, constructs a `digholoWindow`,
applies the analysis settings, and auto-aligns. Its constructor launches the live
viewer. Press Enter in the terminal to close the viewer and camera client.
For a remote camera, first run the camera bridge on the viewer computer and
point the example at that bridge's local camera endpoint.

## Example 9: Power Meter Connection

Power meters currently provide direct drivers rather than a server/bridge/GUI
launcher stack. `POWER_METER_CONFIG` in `default_lab.py` contains example
settings for the Santec driver. Install PyVISA and the device's VISA backend,
and replace the resource string with the address reported by your system.
Run this on the computer connected to the meter:

```python
from JazLabs.launchers.config import load_config
from JazLabs.hardware.PowerMeters.Santec.PowerMeter_Santec_lib import PowerMeterObject

settings = load_config("default_lab")["POWER_METER_CONFIG"]
meter = PowerMeterObject(PWRMeterID=settings["resource"])
try:
    meter.SetUnits(settings["units"])
    print(meter.GetPower())
finally:
    del meter  # The current wrapper closes its VISA connection in its destructor.
```

Thorlabs meter wrappers are under `hardware/PowerMeters/Thorlabs`; their backend
and wavelength settings differ from Santec. They currently include a legacy
notebook widget, rather than a launcher GUI. No `jazlabs-server-power-meter` or
`jazlabs-view-power-meter` command is provided.

## Launch Order at a Glance

### Same-computer camera

| Order | Computer | Process | Command |
|---:|---|---|---|
| 1 | Camera computer | Camera server | `jazlabs-server-camera --config default_lab --name cam_slm` |
| 2 | Camera computer | Viewer and control clients | `jazlabs-view-camera --config default_lab --name cam_slm` |

### Bridged SLM

| Order | Computer | Process | Command |
|---:|---|---|---|
| 1 | SLM computer | Hardware-facing server | `jazlabs-server-slm --config default_lab` |
| 2 | Control computer | SLM bridge | `jazlabs-bridge-slm --config default_lab --remote-host <slm-host>` |
| 3 | Control computer | Shared-memory viewer client | `jazlabs-view-slm --config default_lab` |

### Networked laser

| Order | Computer | Process | Command |
|---:|---|---|---|
| 1 | Laser computer | Laser server | `jazlabs-server-laser --config default_lab --name tunable_laser` |
| 2 | Control computer | Laser GUI | `jazlabs-view-laser --config default_lab --name tunable_laser --host <laser-host>` |

### Bridged motor mount

| Order | Computer | Process | Command |
|---:|---|---|---|
| 1 | Hardware computer | Motor server | `jazlabs-server-motor --config default_lab --name newport_tip_tilt --host 0.0.0.0` |
| 2 | Control computer | Motor bridge | `jazlabs-bridge-motor --config default_lab --name newport_tip_tilt --remote-host <motor-host>` |
| 3 | Control computer | Motor GUI | `jazlabs-view-motor --config default_lab --name newport_tip_tilt --bridge` |

## Stopping the Processes

Close GUI windows normally. For a long-running server, bridge, or terminal
viewer, return to its terminal and press `Ctrl+C`. Stop clients before their
server so they do not continue waiting for a connection that has disappeared.
For motors, close the GUI/clients first, then the bridge, then the hardware
server. `shutdown_bridge` sent to a motor bridge stops only that bridge;
`shutdown` requests shutdown of the hardware server. The server requests a stop
before closing the serial port.

## Troubleshooting

- **A client times out:** check that the server or bridge is still running and
  that both processes use the same host and port values.
- **The camera client cannot connect on the same computer:** confirm that both
  commands use the same configuration and camera name, and that
  `CAMERA_HOST` is `127.0.0.1` or another local address.
- **The camera window opens but does not update:** confirm that the GUI reports
  `alive: True` and `acquisition: True`, and watch whether the frame counter
  advances.
- **The SLM bridge cannot reach the server:** verify `SLM_BRIDGE.remote_host`, remote ports `5555`/`5556`,
  firewall rules, and that the hardware server was started first.
- **The SLM viewer reports missing shared memory:** start the regular bridge on the viewer computer and
  confirm that the viewer uses its local ports `5565`/`5566`. Shared memory is
  local to a computer.
- **The SLM viewer changes but the hardware does not:** inspect the bridge
  and hardware server for LUT or hardware errors. The viewer alone does not
  confirm that the physical SLM updated.

- **Motor sliders are unavailable:** set calibrated axis endpoints in `limits`;
  no range is invented for an unknown fitted stage.
- **Motor moves are disabled:** check the connection age, homing and enable
  indicators, controller errors, and the latched stop state.
- **Motor GUI reaches the wrong endpoint:** use the server port for a direct
  connection, or `--bridge` / its local command port for a bridged connection.
