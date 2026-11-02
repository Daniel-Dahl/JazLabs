"""Launch the process that owns uhubctl access."""
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run a configured USB hub server.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--uhubctl", default=None, help="Path to the installed uhubctl executable")
    parser.add_argument("--command-timeout", type=float, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    hub = merge_overrides(get_named_config(load_config(args.config), "USB_HUB_SERVERS", args.name),
        {"host": args.host, "command_port": args.command_port, "binary": args.uhubctl,
         "command_timeout": args.command_timeout})
    mp.freeze_support()
    from JazLabs.hardware.USBHub.USBHub_Server import USBHubZMQServer
    server = USBHubZMQServer(host=hub.get("host", "127.0.0.1"), command_port=hub["command_port"],
        binary=hub.get("binary"), command_timeout=hub.get("command_timeout", 25.0))
    server.run_forever()


if __name__ == "__main__":
    main()
