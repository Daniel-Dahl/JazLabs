# JazLabs

JazLabs is a Python lab-control playground for bringing different instruments
together into one controllable experiment stack. It is aimed at optics and
photonics workflows where cameras, DAQs, SLMs, lasers, stages, power meters,
and other devices need to be watched and controlled at the same time.

The project is intended to grow over time. As more people use JazLabs, clean up
examples, add drivers, and contribute procedures, the number of supported
instruments and reusable lab workflows should keep expanding. The aim is not to
be a closed, finished control package, but a shared place where instrument
interfaces and experiment patterns can accumulate.

The guiding idea is that instruments can run as servers. A server owns the
physical hardware connection, viewers/widgets can show live feeds, and notebooks
or scripts can create clients that control the same instruments. In practice,
that lets you keep the lab alive visually while still driving it from Python:
open a camera feed, keep an SLM server running, then control everything from a
notebook or automated procedure as if it were a virtual lab bench.

Bridge processes extend the same idea across the lab network. If an instrument
has to stay plugged into a particular hardware computer, another machine on the
same network should still be able to access its controls and data through a
client, viewer, notebook, or script. The aim is to avoid needing to SSH or
remote desktop into the setup just to operate equipment.

You do not have to use the server/client stack for every task. Most instruments
also expose a direct object that can be imported and used in a normal Python
script. Direct use is useful for debugging, driver development, and very small
experiments. The server/client path adds a little overhead from process
communication, ZeroMQ messaging, and shared memory, but it gives you persistent
hardware processes, live viewers, and multi-process control.

## Repository Map

- `src/JazLabs/hardware/` contains instrument drivers, servers, clients,
  viewers, widgets, and bridges.
- `src/JazLabs/launchers/` contains command-line launchers for common servers
  and viewers.
- `src/JazLabs/procedures/` contains higher-level calibrations, alignments, and
  multi-instrument measurement routines.
- `src/JazLabs/utils/` contains shared camera, array, plotting, mask, Zernike,
  and alignment helpers.
- `src/JazLabs/Simulator/` contains optical simulation and analysis utilities.
- `examples/` contains runnable scripts. These are useful references, but still
  need cleanup and standardisation.
- `notebooks/` contains interactive examples and lab notebooks. These also need
  cleanup before they should be treated as polished tutorials.
- `data/` and `calibrations/` contain local experiment/calibration placeholders.

See `docs/repo_structure.md` for a fuller map and `docs/DesignRequirements.md`
for the architecture notes. See `docs/core_concepts.md` for explanations of
important helper objects such as the SLM phase-mask object.

## Installation

JazLabs requires Python 3.10 or newer.

For editable development install:

```bash
python -m pip install -e .
```

For the common scientific, viewer, and server/client stack, the project
dependencies in `pyproject.toml` cover the main pip-installable packages used by
the shared code.

Optional instrument extras are available for device families that use
pip-installable libraries:

```bash
python -m pip install -e ".[notebooks]"
python -m pip install -e ".[visa]"
python -m pip install -e ".[serial]"
python -m pip install -e ".[ni]"
python -m pip install -e ".[zaber]"
python -m pip install -e ".[optimization]"
```

Some instruments also need vendor SDKs, DLLs, drivers, or proprietary Python
packages that cannot be handled cleanly by pip. Install those only for the
specific hardware you intend to use.

## Console Commands

The package defines launchers for common lab processes:

```text
jazlabs-server-camera
jazlabs-server-laser
jazlabs-server-daq
jazlabs-server-optical-switch
jazlabs-server-slm-linux
jazlabs-server-slm-windows
jazlabs-server-slm-stack
jazlabs-bridge-camera
jazlabs-bridge-daq
jazlabs-view
jazlabs-view-camera
jazlabs-view-optical-switch
jazlabs-view-slm
jazlabs-view-slm-stack
jazlabs-view-laser
jazlabs-tmux
jazlabs-slm-center-alignment
jazlabs-camera-dark-frame
```

These commands are configured in `pyproject.toml` and implemented under
`src/JazLabs/launchers/` and `src/JazLabs/procedures/`.

## Direct Object Example

For a simple script or driver debugging session, load the instrument object
directly:

```python
from JazLabs.hardware.Cameras.NiT.NiTCameraObj import NiTCameraObject

camera = NiTCameraObject()
frame = camera.GetFrame()
```

The exact class and setup arguments depend on the instrument.

## Server/Client Example

For normal virtual-lab operation, start the appropriate server or viewer, then
connect from a notebook, script, or procedure using the matching client class.
That keeps the hardware process alive while allowing multiple pieces of code to
observe or control it.

For networked operation, run the server or bridge on the machine physically
connected to the instrument, then connect from a client on another machine on
the same network.

The exact client constructor depends on the instrument stack, so use the current
examples and launcher configs as the reference until the examples are cleaned
up.

### Laser server and remote control

Configure a laser entry in `src/JazLabs/launchers/configs/HDStokes.py`. Run the
server on the computer connected to the laser (use `host="0.0.0.0"` when a
remote client must connect):

```bash
jazlabs-server-laser --name tunable_laser
```

On the control computer, open the GUI by pointing it at that machine's address:

```bash
jazlabs-view-laser --name tunable_laser --host 192.168.1.25
```

The same controls are available from Python through `LaserClient`:

```python
from JazLabs.hardware.Lasers.Laser_Client import LaserClient

with LaserClient(host="192.168.1.25", command_port=50931) as laser:
    laser.set_wavelength_nm(1550.0)
    laser.set_power_dbm(-10.0)
    laser.laser_on()
```

The server supports the Anritsu MG963x, JDS tunable, Santec swept, and FYLA
Horizon drivers. Drivers that do not implement wavelength or power control
report those controls as unavailable in the GUI; the physical laser's
interlock and operating procedures remain authoritative.
