# JazLabs

JazLabs is a Python lab-control playground for bringing cameras, SLMs, lasers,
motorised mounts, DAQs, switches, and analysis tools together into one optics
experiment stack.

The central idea is simple: a long-running server owns each physical instrument,
while scripts, notebooks, viewers, and control GUIs connect as clients. This
keeps the hardware alive and visible while experiment code controls it through
small Python objects. Bridges extend the same model to instruments attached to
another computer on the lab network.

For example, once a camera server is running:

```python
from JazLabs.hardware.Cameras.Camera_Client import CameraClient

camera = CameraClient()
frame = camera.GetFrame(WaitForNewFrame=True)
camera.close()
```

Direct hardware objects are also available for driver development and small
single-process experiments. The server/client path is the usual choice when an
instrument should remain available to multiple tools.

## Start Here

- [Launch servers, viewers, and control GUIs](docs/guides/launch-servers-viewers-and-guis.md)
- [Use the small instrument client examples](docs/guides/instrument-client-examples.md)
- [Understand the main JazLabs concepts](docs/core_concepts.md)
- [Browse the repository structure](docs/repo_structure.md)

The current runnable scripts are in [`examples/instrument_clients`](examples/instrument_clients),
with matching notebooks in [`notebooks/instrument_clients`](notebooks/instrument_clients).
Older examples and notebooks are preserved in the respective `legacy` folders.

## Installation

JazLabs requires Python 3.10 or newer. For an editable development install:

```bash
python -m pip install -e .
```

Install only the optional dependencies needed by the hardware or workflow in
use, for example:

```bash
python -m pip install -e ".[notebooks,serial,visa]"
```

Other extras are listed in `pyproject.toml`. Some instruments also require
vendor SDKs, drivers, DLLs, or proprietary packages that pip cannot install.

## Repository Map

- `src/JazLabs/hardware/`: drivers, clients, servers, bridges, viewers, and GUIs
- `src/JazLabs/launchers/`: command-line launchers and lab configurations
- `src/JazLabs/procedures/`: reusable multi-instrument procedures
- `src/JazLabs/utils/`: shared array, camera, plotting, mask, and alignment tools
- `src/JazLabs/Simulator/`: optical simulation and analysis
- `examples/` and `notebooks/`: runnable client examples and preserved older work
- `docs/`: concepts, architecture, and task-based operating guides
- `data/` and `calibrations/`: local data and calibration locations

JazLabs is deliberately an evolving shared workspace: instrument interfaces and
repeatable experiment patterns can accumulate without forcing every lab task
into one closed application.
