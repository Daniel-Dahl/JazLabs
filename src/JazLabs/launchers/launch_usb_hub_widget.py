"""Open the USB hub GUI through a client, without starting hardware processes."""
import argparse

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Open a USB hub control widget.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--bridge", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    hub = get_named_config(load_config(args.config), "USB_HUB_SERVERS", args.name)
    if args.bridge:
        host = args.host or hub.get("local_host", "127.0.0.1")
        port = args.command_port if args.command_port is not None else hub["local_command_port"]
    else:
        host = args.host or hub.get("client_host", "127.0.0.1")
        port = args.command_port if args.command_port is not None else hub["command_port"]
    from JazLabs.hardware.USBHub.USBHub_Client import USBHubClient
    from JazLabs.hardware.USBHub.USBHub_Widget import USBHubWidget
    import tkinter as tk
    client = USBHubClient(host, port, timeout_ms=args.timeout_ms if args.timeout_ms is not None else hub.get("timeout_ms", 100000))
    root = tk.Tk()
    try:
        USBHubWidget(root, client)
        root.mainloop()
    finally:
        client.close()


if __name__ == "__main__":
    main()
