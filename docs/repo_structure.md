# JazLabs Repository Structure

JazLabs is a Python package for connecting laboratory instruments, running
optics procedures, and launching small server/viewer stacks for hardware such
as cameras, DAQs, SLMs, lasers, stages, and related tools.

## Top-Level Layout

```text
JazLabs/
|-- pyproject.toml          # Package metadata and console-script entry points
|-- README.md               # Concise project overview and documentation links
|-- LICENSE
|-- docs/                   # Architecture, concepts, and task-based guides
|-- examples/               # Runnable example scripts for hardware/procedures
|-- notebooks/              # Exploratory notebooks and saved console/wisdom files
|-- src/                    # Installable Python source tree
|-- data/                   # Runtime/user data placeholders by subsystem
|-- calibrations/           # Calibration output/placeholders by subsystem
|-- tests/                  # Test package placeholder
`-- build/                  # Generated build artifacts; do not edit as source
```

The documentation is split between project-wide reference material and
task-based operating guides:

```text
docs/
|-- README.md
|-- DesignRequirements.md
|-- core_concepts.md
|-- repo_structure.md
`-- guides/
    |-- camera-dark-frames.md
    |-- instrument-client-examples.md
    |-- time-tagger-server-bridge-client.md
    |-- launch-servers-viewers-and-guis.md
    `-- intensity-based-slm-centre-alignment.md
```

Use `docs/guides/` for practical instructions that take an operator through a
specific lab task. The existing
[`launch-servers-viewers-and-guis.md`](guides/launch-servers-viewers-and-guis.md)
guide explains how to start the camera and SLM servers and connect their
viewers and control GUI.
The same folder contains guides for
[`capturing camera dark frames`](guides/camera-dark-frames.md) and
[`performing intensity-based SLM centre alignment`](guides/intensity-based-slm-centre-alignment.md).
The
[`Time Tagger server, bridge server, and client`](guides/time-tagger-server-bridge-client.md)
guide documents the networked Time Tagger stack.
Add future operator procedures here as well.

## Package Source

The installable package lives under:

```text
JazLabs/src/JazLabs/
|-- hardware/       # Instrument drivers, clients, servers, widgets, viewers
|-- launchers/      # Console entry points and lab setup configuration
|-- procedures/     # Higher-level measurement, alignment, and calibration flows
|-- Simulator/      # Optical simulation and analysis utilities
`-- utils/          # Shared array, camera, plotting, Zernike, and mask helpers
```

### `hardware/`

Instrument-specific code is grouped by device family. Most device folders
contain a low-level object/driver, while stack-style devices can also include
client, server, bridge, widget, or viewer modules.

Most active instrument stacks follow the server/client architecture described
in `docs/DesignRequirements.md`: the server owns the hardware connection, while
clients, viewers, widgets, notebooks, and scripts can interact with it.
Bridge modules are used where controls or streamed data need to be exposed from
the hardware machine to other computers on the same network.

```text
hardware/
|-- Cameras/            # Camera stack plus vendor implementations
|-- DAQ_Controller/     # NI, MCC, Coremorrow, and DAQ client/server stack
|-- DeformableMirror/   # Deformable mirror object/library bindings
|-- digHolo/            # digHolo Python wrappers plus bundled vendor SDK files
|-- Lasers/             # Laser drivers by vendor
|-- MokuLab/            # MokuLab object and notebook
|-- MotorisedStages/    # Stage stack plus Thorlabs, Newport, Luminos drivers
|-- OpticalSwitch/      # Optical switch stack and JDS drivers
|-- OSA/                # Optical spectrum analyzer utilities/manuals
|-- Oscilloscope/       # Oscilloscope helper libraries
|-- PowerMeters/        # Thorlabs and Santec power meter utilities
|-- SLM/                # SLM stacks, viewers, phase masks, and vendor backends
|-- TimeTagger/         # Time Tagger server, bridge, client, and measurements
`-- VOA/                # Variable optical attenuator drivers
```

Camera vendor implementations currently include Allied Vision, First Light,
FLIR, Lucid Vision, NiT, Point Grey, QImaging, and Xenic cameras. SLM support
includes SLMStack, the separate pyMilk-based SLMStackMilk, HDMI SLM, and
Meadowlark backends.

digHolo support is split between `hardware/digHolo/digHolo_v1.0.0/`, which
contains the upstream `joelacarpenter/digHolo` library and reference material,
and `hardware/digHolo/digHolo_pylibs/`, which contains JazLabs' Python wrapper,
viewer, and widget code.

DAQ support is intentionally separated from higher-level physical instruments.
`hardware/DAQ_Controller/` contains reusable voltage IO and DAQ stack code, but
a DAQ-driven VOA, laser, stage, mirror, or future device should still usually
have its own hardware abstraction that matches the physical instrument in the
lab.

### `launchers/`

Launcher modules are designed to be called either as Python modules or through
console scripts defined in `pyproject.toml`.

```text
launchers/
|-- launch_camera_server.py
|-- launch_camera_bridge.py
|-- launch_camera_viewer.py
|-- launch_daq_server.py
|-- launch_daq_bridge.py
|-- launch_slm_server.py
|-- launch_slm_bridge.py
|-- launch_slm_milk_server.py
|-- launch_slm_milk_bridge.py
|-- launch_time_tagger_server.py
|-- launch_time_tagger_bridge.py
|-- launch_slm_viewer.py
|-- launch_slm_milk_viewer.py
|-- launch_viewers.py
|-- tmux.py
|-- config.py
`-- configs/
    |-- HDStokes.py
    |-- OAH_setup.py
    |-- OAH_setup_ben.py
    `-- default_lab.py
```

Configured console commands include:

- `jazlabs-server-camera`
- `jazlabs-server-daq`
- `jazlabs-server-slm`
- `jazlabs-bridge-slm`
- `jazlabs-server-slm-milk`
- `jazlabs-bridge-slm-milk`
- `jazlabs-bridge-camera`
- `jazlabs-bridge-daq`
- `jazlabs-server-time-tagger`
- `jazlabs-bridge-time-tagger`
- `jazlabs-view`
- `jazlabs-view-camera`
- `jazlabs-view-slm`
- `jazlabs-view-slm-milk`
- `jazlabs-tmux`
- `jazlabs-slm-center-alignment`
- `jazlabs-camera-dark-frame`

### `procedures/`

Procedure modules combine one or more hardware components into experiment-level
workflows.

```text
procedures/
|-- Camera/                         # Camera frame comparison routines
|-- DeformableMirror/               # Deformable mirror alignment routines
|-- digholo/                        # digHolo measurement and mode-generation tools
|-- MotorisedStages/                # Stage and waveplate alignment/calibration
|-- Multi_Instrument_Measurement_Routines/
|-- SLM/                            # SLM phase/time/center/multidimensional calibration
|-- TipTiltMirror/                  # Tip-tilt calibration scan and core logic
`-- VOA/                            # VOA calibration
```

The `procedures/digholo/` folder contains higher-level digHolo workflows, such
as batch processing, transform-matrix generation, mode measurements, and
MPLC-related routines built on top of the hardware wrapper.

### `Simulator/`

Simulation support is collected under `Simulator/`. It includes mode index
files, optical operators, Gaussian beam basis tools, MPLC functions, fitting,
FWHM helpers, coupling matrix analysis, and a mask simulation notebook.

```text
Simulator/
|-- MPLCMaskSimulation.ipynb
|-- ModeIndex/
`-- libs/
```

### `utils/`

Shared utilities cover array manipulation, alignment helpers, camera helpers,
simple phase mask generation, Zernike modes, spot-array analysis, and plotting.

```text
utils/
|-- AlignmentFunctions.py
|-- ArrayManipulators.py
|-- camera_tools.py
|-- camera_utils.py
|-- GenerateSimplePhaseMasks.py
|-- ZernikeModule.py
|-- PlotingFunctions/
`-- SpotArrayAnalysis/
```

## Examples And Notebooks

`examples/instrument_clients/` contains the current minimal scripts for the SLM,
camera, motorised mounts, lasers, optical switches, DACs, and digital
holography. `notebooks/instrument_clients/` contains the same examples as
Jupyter notebooks. See the
[`Instrument Client Examples`](guides/instrument-client-examples.md) guide for
the operation covered by each pair.

Earlier scripts, notebooks, and supporting files are preserved under
`examples/legacy/` and `notebooks/legacy/`. They remain useful references for
longer calibration and experiment workflows, but are separated from the small
starting examples.

## Documentation

`docs/core_concepts.md` explains the reasoning behind important helper objects,
including the SLM phase-mask object used to manage centered masks, Zernike
corrections, mask sets, and multi-plane light converter workflows. It also
explains how JazLabs wraps the external `joelacarpenter/digHolo` library for
batch and live off-axis holography workflows, and how DAQ controllers are used
as low-level voltage IO beneath higher-level physical instrument classes.

`docs/guides/` contains short, task-based instructions for operating JazLabs.
Start with
[`docs/guides/launch-servers-viewers-and-guis.md`](guides/launch-servers-viewers-and-guis.md)
when launching a camera or SLM server and connecting the corresponding viewer
or control GUI. The folder also contains the
[`camera dark-frame`](guides/camera-dark-frames.md) and
[`intensity-based SLM centre-alignment`](guides/intensity-based-slm-centre-alignment.md)
procedures, plus the
[`Time Tagger server, bridge server, and client`](guides/time-tagger-server-bridge-client.md)
guide. Keep future calibration and operator procedures in the same folder so
they are easy to find.

## Data And Calibration Directories

The repository keeps placeholder folders for data and calibration outputs.
These folders are intended for local experiment products and are currently
tracked mostly via `.gitkeep` files.

```text
data/
|-- Camera/
|-- SLM/
|   |-- MaskFiles/
|   `-- MaskProperties/
`-- VOA/

calibrations/
|-- Camera/
|-- SLM/
|   `-- CustomLutFiles/
`-- VOA/
```

Large or run-specific data products should normally stay out of git unless
there is a deliberate reason to version them.

## Generated, Vendor, And Legacy Content

- `build/` is generated package output and should not be edited as the source
  of truth.
- Several hardware folders contain vendor SDKs, DLLs, PDFs, ZIPs, old versions,
  or examples. Treat those as reference/vendor material unless a task is
  explicitly about updating that integration.
- `oldversion/` and similarly named folders contain legacy code.
  Prefer active stack modules when adding new behavior.

## Where To Add New Code

- Add a new hardware driver under `src/JazLabs/hardware/<DeviceFamily>/`.
- Add server/client/viewer wrappers beside the relevant hardware family if the
  device needs remote control or GUI tooling.
- Add experiment workflows under `src/JazLabs/procedures/<ProcedureArea>/`.
- Add shared, hardware-agnostic helpers under `src/JazLabs/utils/`.
- Add runnable usage examples under `examples/`.
- Add task-based operating instructions under `docs/guides/`.
- Add console entry points in `pyproject.toml` only when the launcher is meant
  to be installed as a command.
