"""Test-only uhubctl replacement; never installed or imported by production code."""
import sys
from pathlib import Path


def create_uhubctl_stub(directory):
    """Exercise subprocess and spawned servers without accessing a USB device."""
    executable = Path(directory) / "uhubctl-stub"
    executable.write_text(f"#!{sys.executable}\n" + '''import json
import sys
from pathlib import Path

state_file = Path(__file__).with_suffix(".json")
states = json.loads(state_file.read_text()) if state_file.exists() else {}
arguments = sys.argv[1:]
if arguments:
    location = arguments[arguments.index("-l") + 1]
    port = arguments[arguments.index("-p") + 1]
    states[location + "/" + port] = arguments[arguments.index("-a") + 1] == "on"
    state_file.write_text(json.dumps(states))

for suffix in ("", ".3", ".4"):
    location = "20-1" + suffix
    print(f"Current status for hub {location} [0bda:0411 Generic Hub, 4 ports, ppps]")
    for port in range(1, 5):
        if not suffix and port > 2:
            details = "power connect [0bda:0411 Internal Hub, ppps]"
        else:
            on = states.get(location + "/" + str(port), True)
            details = ("power " if on else "off ") + "connect [1234:5678 Test device]"
        print(f"  Port {port}: 0200 {details}")
''')
    executable.chmod(0o755)
    return str(executable)
