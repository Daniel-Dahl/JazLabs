# USB hub setup and physical socket mapping

JazLabs controls the RSH-A10 hub through a wrapper around the installed
[`uhubctl` executable](https://github.com/mvp/uhubctl). It is a command-line
program, not a Python package. Python runs it with an argument list through
`subprocess.run`; uhubctl handles USB communication. Only the hardware computer
needs uhubctl and permission to access the hub.

## Install

Install JazLabs with `pip install -e .` to register the launchers. PyZMQ is
already a project dependency; there is no separate hub requirements file.
The GUI also needs Tk (`python -m tkinter` checks the active environment).

On Ubuntu/Debian:

```bash
sudo apt install uhubctl python3-tk
```

On macOS:

```bash
brew install uhubctl
```

For macOS 26+, upstream requires libusb 1.0.30 or later. On Linux, follow the
[upstream USB permission instructions](https://github.com/mvp/uhubctl#linux-usb-permissions)
for the actual hub IDs and kernel. The wrapper does not invoke sudo or install
udev rules. The old HubDesk setup/launch scripts are not part of JazLabs.

Run `uhubctl` without arguments to inspect discovery before starting the live
server. Upstream currently does not support power switching on Windows; a
Windows client/GUI can connect to a server on Linux or macOS instead. See the
[upstream installation notes](https://github.com/mvp/uhubctl#installing).

## Code and process layout

| File under `hardware/USBHub` | Responsibility |
|---|---|
| `USBHub_Driver.py` | Run uhubctl, parse discovery, validate topology and identity, switch one endpoint, verify readback |
| `USBHub_Server.py` | Own one driver and handle explicit requests in one loop |
| `USBHub_BridgeServer.py` | Relay requests to a remote owner; no driver imports |
| `USBHub_Client.py` | Synchronous Python calls through ZMQ |
| `USBHub_Widget.py` | Ten socket controls, manual mapping, freshness and error display |

The command path is widget → client → optional bridge → server → driver →
uhubctl. The CLI server is its own process and runs `run_forever()` directly.
For Python applications, `USBHubZMQServer.start()` launches that same loop using
`multiprocessing`; `stop()` requests shutdown. Use a `__main__` guard when
starting child processes from a script. A notebook can simply connect a client
or instantiate the driver directly.

There are no Python worker threads, event queues, or background polling loops
in the client or widget. Tk schedules refresh/control callbacks with `after`.
Calls wait for replies, so the window can pause during a slow query until its
configured timeout. The server handles one request at a time; another client
waits while uhubctl is running. No shared memory is needed for these small
status dictionaries. Run only one live owner for a given hub; independent
uhubctl programs are not locked out by this server.

## Launch

`USB_HUB_SERVERS` in `default_lab.py` supplies the server endpoint, local bridge
endpoint, executable path, and timeouts. The example is disabled for
automatic tmux launch. Explicit named commands still work.

Start the server and widget on the configured hub computer:

```bash
jazlabs-server-usb-hub --config default_lab --name usb_hub
jazlabs-view-usb-hub --config default_lab --name usb_hub
```

Run the commands in separate terminals. `--uhubctl /absolute/path/to/uhubctl`
overrides executable discovery. Opening/closing the GUI or stopping the server
leaves port power states unchanged.

For another computer, start the hardware server with `--host 0.0.0.0`, then
on the control computer:

```bash
jazlabs-bridge-usb-hub --config default_lab --name usb_hub --remote-host 192.168.1.25
jazlabs-view-usb-hub --config default_lab --name usb_hub --bridge
```

Replace the IP with the hardware computer's reachable address. The example
bridge exposes local port 51951 and forwards to server port 50951. The protocol
has no authentication: use a trusted lab network or an SSH tunnel. A loopback
server can remain on `127.0.0.1` when reached through an SSH tunnel.

Once configured, setting `enabled=True` allows
`jazlabs-tmux usb-hub --config default_lab --name usb_hub` to start the server.
It does not start the GUI or bridge. The direct module forms are
`python -m JazLabs.launchers.launch_usb_hub_server`,
`launch_usb_hub_bridge`, and `launch_usb_hub_widget`, with the same flags.

## Map software endpoints to physical sockets

The wrapper recognizes the documented RSH-A10 three-chip topology: a root and
children at `.3` and `.4`, each with four ports, using `0bda:0411` or
`0bda:5411` and individual port switching. It exposes ten leaf endpoints and
excludes the root's two internal hub links. Other layouts, ganged switching,
and detected downstream hubs remain unavailable. This recognition is not
proof of the model or of electrical power removal.

1. Connect the power adapter and upstream cable. Press the physical port
   buttons into their on position. Keep essential input devices off this hub.
2. Open the widget and click **Refresh**. Choose a detected root. USB2 and
   USB3 sides may appear separately; choose one side rather than mapping both
   as different sockets. uhubctl retains its default companion handling.
3. Label the physical sockets 1–10 from the cable end as your own convention.
   The program does not infer physical socket order from logical port numbers.
4. Insert one spare USB device into the first physical socket. Refresh and
   open **Discovery & error details**. Identify the location/port whose device
   description changes. Select that endpoint in the socket's dropdown.
5. Repeat for every socket. Each endpoint can be assigned only once. Remove
   any downstream external hub during mapping. Never map an internal hub link.
6. Check the mapping acknowledgement. Use a spare USB light or fan to switch
   one socket off/on, verify that it actually loses power, and check that its
   neighbors stay powered. Eject storage before any off request.
7. Verify again after reconnecting or moving the upstream cable. Mappings are
   session-only; changing roots or restarting the owner clears them. Bus
   locations are not persistent hardware serial numbers.

The [RSH-A10 hardware report](https://github.com/octoprobe/usbhubctl/blob/main/usb_hubs/README_RSHTECH_RSH-A10.md)
documents the topology and physical button requirement. Successful status
readback reports the hub's power flag; it is not a voltage measurement. If the
light/fan stays powered, leave control disarmed.

## Python client or direct driver

```python
from JazLabs.hardware.USBHub.USBHub_Client import USBHubClient

hub = USBHubClient(host="127.0.0.1", command_port=50951)
try:
    status = hub.GetStatus()
    print(status["trees"])
    print(status["hubs"])
    # After mapping this endpoint to a real physical socket:
    # endpoint = ("actual-location", 1)
    # hub.SetPower(endpoint, False, status["hubs"][endpoint[0]]["identity"],
    #              session_id=status["session_id"])
finally:
    hub.close()
```

Use the bridge's local port 51951 when connecting through it. `GetStatus()`
returns `raw`, `hubs`, `trees`, and `session_id`. Port keys are integers
for both client and driver. `SetPower()` takes an explicit boolean on/off value
and expected VID:PID, checks topology/identity before writing, and returns
confirmed status. Passing the session ID protects a mapping against a restarted
owner. Without it, the client first requests the current owner's session.

For direct notebook use on the hardware computer:

```python
from JazLabs.hardware.USBHub.USBHub_Driver import USBHubDriver

hub = USBHubDriver()
status = hub.GetStatus()
print(status["trees"])
# hub.SetPower(mapped_endpoint, True, expected_identity, status["session_id"])
```

Construction does not access USB. Driver calls use no network or persistent
connection and need one caller at a time. Client `close()` disconnects only;
`ShutdownServer()` explicitly stops the hardware owner. A bridge's
`request("shutdown_bridge")` stops just that bridge.

Minimal matching examples are in `examples/instrument_clients/usb_hub_client.py`
and `notebooks/instrument_clients/usb_hub_client.ipynb`.

## Timeouts and failures

Each uhubctl subprocess defaults to 25 seconds. A power request can run three:
discovery, switching, and readback. The default bridge timeout is 90 seconds
and client timeout is 100 seconds. Keep the latter larger than the former;
allow extra time if multiple clients queue commands. The wrapper retains
repeated off requests for older Linux kernels and automatic USB2/USB3 handling.
It never forces unsupported hardware or targets every port at once.

After a failed request or feedback older than 30 seconds, the GUI marks states
unknown and disables switching until a successful refresh. It does not retry
power requests automatically. A timeout does not prove a command failed;
refresh before deciding what to do next. If discovery is empty, inspect power,
cabling, physical buttons, USB permissions, and uhubctl's terminal output.
