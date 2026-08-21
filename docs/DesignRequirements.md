# JazLabs Design Requirements

This document describes the intended architecture of JazLabs. The repository is
still being cleaned up, but the central design idea is already clear: each
instrument should be usable as part of a live, networked lab stack, while still
remaining available as a direct Python object when that is the simpler choice.

## Instrument Server/Client Architecture

The main philosophy of JazLabs is that instruments can run as independent
servers. A server owns the physical hardware connection, keeps that connection
alive, and exposes commands and data to the rest of the lab. Viewers and widgets
can attach to those servers to show live feeds or controls, while notebooks,
scripts, and procedures can spin up clients that control the same instruments.

That means the lab can behave like a virtual lab bench:

- a camera server can keep acquiring frames
- a camera viewer can show the live feed
- an SLM or DAQ server can keep its own hardware state alive
- a notebook can create a client and control the instruments programmatically
- an automated procedure can coordinate several clients without taking over the
  viewer or forcing the user to close their notebook

The power of the architecture is that the visual/live tooling and the scripted
control tooling can run at the same time. A user can watch what is happening
through viewers and widgets, then control the same instrument from a notebook or
script as if the instrument were a local Python object.

## Typical Instrument Layers

Most instrument families should follow this shape where practical:

```text
InstrumentObject.py   # Direct hardware wrapper; owns the vendor API/SDK calls
Instrument_Server.py  # Long-running process that owns one or more objects
Instrument_Client.py  # Lightweight API used by notebooks, scripts, procedures
Instrument_Viewer.py  # Optional live visual feed or monitor
Instrument_Widget.py  # Optional notebook/control widget
BridgeServer.py       # Optional bridge for cross-machine/cross-process setups
```

Not every instrument needs every layer. A small serial device may only need a
direct object and a client/server pair. A camera or SLM often benefits from a
viewer. A device that must run on a specific machine or operating system may
also need a bridge.

## Bridge Systems And Network Access

Some instruments are attached to a specific lab machine because of vendor
drivers, PCIe/USB connections, operating-system constraints, or local display
requirements. JazLabs should support bridge systems for those cases. A bridge
lets the instrument stay physically connected to the machine that can run it,
while controls and data are made available to another computer on the same
network.

The goal is that a user should not need to SSH into the hardware computer or
remote desktop into the lab setup just to control an instrument or read its
data. Instead, the hardware-side server or bridge process can run near the
instrument, and a client, notebook, script, viewer, or widget can connect from a
normal workstation on the lab network.

Bridge systems are useful when:

- the instrument SDK only works on one operating system or one configured PC
- the hardware computer should stay connected to the instrument but not be the
  main user interface
- multiple users or processes need access to live data streams
- a clean notebook/script workflow is preferred over remote-desktop control
- the lab setup should expose instrument controls without exposing the whole
  machine

The bridge layer should preserve the same general feel as local clients:
controls should look like method calls, and streamed data should arrive in a
form that is easy to use from Python. Network latency and bandwidth are still
real constraints, especially for high-rate camera streams, but the user-facing
workflow should feel like operating a virtual instrument from their own machine.

## Direct Object Use Is Still Supported

The server/client approach is recommended for normal lab operation, but it is
not mandatory. Users can directly import and instantiate the instrument object
they need when that is clearer:

```python
from JazLabs.hardware.Cameras.NiT.NiTCameraObj import NiTCameraObject

camera = NiTCameraObject()
frame = camera.GetFrame()
```

Direct object use removes some overhead and can be useful for debugging,
one-off scripts, or new driver development. The overhead of the server/client
path is usually modest, but it is real: process communication, ZeroMQ messages,
and shared-memory handoff all have natural costs. For many instruments that
cost is small compared with acquisition time, hardware latency, or user
interaction, but high-rate workflows should choose the layer that matches the
measurement.

## When To Prefer Each Mode

Use the server/client pattern when:

- more than one process needs to observe or control the instrument
- a viewer should stay open while scripts or notebooks run
- the hardware should remain initialized across multiple experiments
- the instrument must run on a different machine, OS, or Python environment
- procedures need a stable interface to several instruments at once

Use the direct object when:

- developing or debugging a driver
- writing a very small one-off script
- measuring the absolute minimum software overhead
- the instrument is only needed by one Python process

## Examples And Notebooks

The repository contains matching minimal client scripts and notebooks under
`examples/instrument_clients/` and `notebooks/instrument_clients/`. Earlier lab
examples are preserved in the corresponding `legacy/` folders and should be
treated as working references rather than polished tutorials.

Examples should continue to show both supported usage styles:

- direct object examples for simple hardware access and driver debugging
- server/client examples for normal virtual-lab operation
- notebooks that demonstrate interactive workflows
- scripts that demonstrate repeatable automated measurements

## Dependency Philosophy

JazLabs should keep common, pip-installable dependencies easy to install while
keeping instrument-specific dependencies optional. Core scientific and
communication packages belong in the project dependencies. Vendor SDKs,
proprietary DLLs, and packages needed for only one device family should be
documented as optional instrument requirements instead of being forced on every
user.

The goal is that a new user can install the common stack, run the package,
inspect examples, and only worry about specialised SDKs when they actually want
to use the matching instrument.
