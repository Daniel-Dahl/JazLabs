#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Open a JazLabs laser control GUI.")
    parser.add_argument("--config", default="HDStokes")
    parser.add_argument("--name", "--laser", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--refresh-ms", type=int, default=1000)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    laser = get_named_config(config, "LASER_SERVERS", args.name)
    host = args.host or laser.get("host", config.get("LASER_HOST", "127.0.0.1"))
    command_port = args.command_port or laser["command_port"]

    mp.freeze_support()
    from JazLabs.hardware.Lasers.Laser_Widget import LaserControlWindow

    window = LaserControlWindow(
        host=host,
        command_port=command_port,
        timeout_ms=args.timeout_ms,
        refresh_ms=args.refresh_ms,
        window_name=f"Laser Control - {laser['name']}",
    )
    window.run()


if __name__ == "__main__":
    main()
