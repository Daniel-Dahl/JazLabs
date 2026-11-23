"""Launch a local command bridge to a remote USB hub server."""
import argparse

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Run a USB hub bridge.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", required=True)
    parser.add_argument("--remote-host", default=None)
    parser.add_argument("--remote-command-port", type=int, default=None)
    parser.add_argument("--local-host", default=None)
    parser.add_argument("--local-command-port", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=None)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    hub = get_named_config(load_config(args.config), "USB_HUB_SERVERS", args.name)
    remote_host = args.remote_host or hub.get("remote_host")
    if not remote_host:
        parser.error("Set remote_host in the USB hub config or supply --remote-host")
    from JazLabs.hardware.USBHub.USBHub_BridgeServer import USBHubZMQBridgeServer
    bridge = USBHubZMQBridgeServer(remote_host=remote_host,
        remote_command_port=args.remote_command_port if args.remote_command_port is not None else hub["command_port"],
        local_host=args.local_host or hub.get("local_host", "127.0.0.1"),
        local_command_port=args.local_command_port if args.local_command_port is not None else hub["local_command_port"],
        timeout_ms=args.timeout_ms if args.timeout_ms is not None else hub.get("bridge_timeout_ms", 90000))
    bridge.run_forever()


if __name__ == "__main__":
    main()
