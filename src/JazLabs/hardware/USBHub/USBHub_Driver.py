"""USB-facing layer: wrap the installed uhubctl executable, not its C API.

No GUI or network imports. Construction does not access hardware.
"""
import os
import platform
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field, asdict


@dataclass
class Hub:
    location: str
    identity: str
    description: str
    individual: bool
    ports: dict = field(default_factory=dict)


def parse_status(output):
    hubs = {}
    current = None
    for line in output.splitlines():
        header = re.match(r'Current status for hub ([\d.-]+) \[([0-9a-fA-F]{4}:[0-9a-fA-F]{4}) (.*)\]$', line.strip())
        if header:
            location, identity, description = header.groups()
            current = Hub(location, identity.lower(), description, bool(re.search(r'\bppps\b', description)))
            hubs[location] = current
            continue
        port = re.match(r'\s*Port (\d+): ([0-9a-fA-F]{4,8})\s*(.*)', line)
        if port and current:
            number, bits, details = port.groups()
            current.ports[int(number)] = {'on': bool(re.search(r'\bpower\b', details.split('[', 1)[0])), 'details': details, 'bits': bits}
    return hubs


def discover_trees(hubs):
    """Recognize only the documented RSH-A10 three-chip shape; never guess numbering."""
    trees = {}
    for location, root in hubs.items():
        if root.identity not in ('0bda:0411', '0bda:5411'):
            continue
        members = [hubs.get(location + suffix) for suffix in ('', '.3', '.4')]
        if not all(hub and hub.individual and hub.identity == root.identity and set(hub.ports) == {1, 2, 3, 4} for hub in members):
            continue
        endpoints = [(location, 1), (location, 2)]
        endpoints += [(location + suffix, port) for suffix in ('.3', '.4') for port in range(1, 5)]
        # A downstream hub is never offered as a switchable device endpoint.
        if any(re.search(r'\bhub\b|, \d+ ports[,\]]', hubs[loc].ports[port]['details'], re.IGNORECASE) or loc + '.' + str(port) in hubs for loc, port in endpoints):
            continue
        trees[location] = endpoints
    return trees


class USBHubDriver:
    def __init__(self, binary=None, command_timeout=25.0):
        if command_timeout <= 0:
            raise ValueError("command_timeout must be positive")
        self.command_timeout = float(command_timeout)
        self.session_id = uuid.uuid4().hex
        self.binary = binary or shutil.which('uhubctl')
        if not self.binary:
            for path in ('/opt/homebrew/bin/uhubctl', '/usr/local/bin/uhubctl', '/usr/sbin/uhubctl'):
                if os.path.isfile(path):
                    self.binary = path
                    break

    def _run_uhubctl(self, arguments):
        if not self.binary:
            raise RuntimeError('uhubctl is missing. Install uhubctl on the hardware computer; see docs/guides/usb-hub.md.')
        try:
            # Equivalent to running `uhubctl <arguments>` in a terminal:
            # wait for it to finish and capture its output for parsing below.
            # Pass arguments directly to the executable, without a shell.
            result = subprocess.run([self.binary, *arguments], capture_output=True, text=True, timeout=self.command_timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise RuntimeError('uhubctl timed out. Power state is unknown; refresh before trying again.') from None
        if result.returncode:
            raise RuntimeError((result.stderr + '\n' + result.stdout).strip()[:3000] or 'uhubctl failed. Check USB access and the hub connection.')
        return result.stdout

    def _scan(self):
        output = self._run_uhubctl([])
        # Older uhubctl omits "ppps" in headers. Its default discovery (no
        # force option) lists only hubs supporting individual power switching.
        # Normalize only this trusted discovery output, not arbitrary parser input.
        lines = []
        for line in output.splitlines():
            if line.startswith('Current status for hub ') and line.endswith(']'):
                if not re.search(r'\b(ppps|ganged)\b', line):
                    line = line[:-1] + ', ppps]'
            lines.append(line)
        return '\n'.join(lines)

    def GetStatus(self):
        """Read the current topology and reported port power; no cached feedback."""
        status = snapshot_from_output(self._scan())
        status['session_id'] = self.session_id
        return status

    def SetPower(self, endpoint, on, expected_identity, session_id=None):
        """Switch one verified leaf endpoint and return confirmed status.

        endpoint is (uhubctl location, port), not a physical socket number.
        Use the identity and optional session_id from a recent GetStatus().
        """
        if session_id is not None and session_id != self.session_id:
            raise ValueError('USB hub owner restarted. Refresh and verify mappings again.')
        if not isinstance(endpoint, (tuple, list)) or len(endpoint) != 2:
            raise ValueError('endpoint must be a (location, port) pair')
        location, port = endpoint
        if not isinstance(location, str) or not location:
            raise ValueError('location must be a nonempty string')
        if type(port) is not int or not 1 <= port <= 4:
            raise ValueError('port must be an integer from 1 to 4')
        if type(on) is not bool:
            raise ValueError('on must be a boolean')
        if not isinstance(expected_identity, str):
            raise ValueError('expected_identity must be a VID:PID string')
        endpoint = (location, port)
        # Re-discover immediately before every write, including topology and identity.
        hubs = parse_status(self._scan())
        trees = discover_trees(hubs)
        if not any(endpoint in ports for ports in trees.values()):
            raise RuntimeError('Hub topology changed or support is unverified. Reconnect and map the hub again.')
        location, port = endpoint
        if hubs[location].identity != expected_identity:
            raise RuntimeError('Hub identity changed. No command was sent.')
        # Keep uhubctl automatic USB2/USB3 companion handling. Never force support.
        arguments = ['-l', location, '-p', str(port), '-a', 'on' if on else 'off']
        # Linux 5.x drivers can immediately restore power. Upstream advises
        # repeated off requests on these kernels to suppress that behavior.
        kernel_version = re.match(r'(\d+)\.', platform.release())
        if not on and platform.system() == 'Linux' and kernel_version and int(kernel_version[1]) < 6:
            arguments += ['-r', '100']
        command_output = self._run_uhubctl(arguments)
        output = self._scan()
        observed = parse_status(output).get(location)
        if not observed or port not in observed.ports or observed.ports[port]['on'] != on:
            requested = 'on' if on else 'off'
            reported = 'unknown'
            if observed and port in observed.ports:
                reported = 'on' if observed.ports[port]['on'] else 'off'
            raise RuntimeError(
                f'Requested power state was not confirmed for {location} / {port}: '
                f'requested {requested}, reported {reported}.\n'
                'Electrical power is not measured by this app.\n\n'
                f'Command output:\n{command_output or "(no command output)"}\n\n'
                f'Follow-up discovery:\n{output}'
            )
        status = snapshot_from_output(output)
        status['session_id'] = self.session_id
        return status


def snapshot_from_output(output):
    """Convert discovery/readback into JSON-safe data for both server commands."""
    hubs = parse_status(output)
    return {
        "raw": output,
        "hubs": {location: asdict(hub) for location, hub in hubs.items()},
        "trees": discover_trees(hubs),
    }
