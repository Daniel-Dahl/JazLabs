# Time Tagger Server, Bridge Server, and Client

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

## Configure the Time Tagger

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

## 1. Start the hardware server

On the computer physically connected to the Time Tagger, run:

```bash
jazlabs-server-time-tagger \
    --config default_lab \
    --name time_tagger
```

The server creates the vendor device object and listens on the configured
command port. Leave it running while measurements are being performed.

## 2. Start the bridge server

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

## 3. Connect a client

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

## Stopping the stack

Close client objects first. Then stop the bridge and hardware server with
`Ctrl+C` in their terminals. `TimeTaggerClient.ShutdownServer()` is available
for controlled shutdown from Python, but should only be used by code that owns
the server lifecycle.

## Troubleshooting

- If the hardware server cannot import `TimeTagger`, install the Swabian
  Instruments software and its Python package on that computer.
- If the bridge times out, confirm the remote host, command port, firewall,
  and hardware-server terminal.
- If a client times out during a measurement, make sure the bridge timeout is
  longer than the requested counting time.
- If the wrong device opens, set its serial number in `TIME_TAGGER_SERVERS` or
  pass `--serial` to the hardware-server command.
