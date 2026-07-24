#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run one configured JazLabs laser server.")
    parser.add_argument("--config", default="HDStokes")
    parser.add_argument("--name", "--laser", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--laser-type", default=None)
    parser.add_argument("--serial-port", default=None)
    parser.add_argument("--laser-id", default=None)
    parser.add_argument("--poll-timeout-ms", type=int, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    laser = get_named_config(config, "LASER_SERVERS", args.name)
    laser = merge_overrides(
        laser,
        {
            "host": args.host,
            "command_port": args.command_port,
            "laser_type": args.laser_type,
            "poll_timeout_ms": args.poll_timeout_ms,
        },
    )
    laser.setdefault("host", config.get("LASER_HOST", "127.0.0.1"))
    laser.setdefault("poll_timeout_ms", 100)
    laser_kwargs = dict(laser.get("laser_kwargs", {}))
    if args.serial_port is not None:
        laser_kwargs["port"] = args.serial_port
    if args.laser_id is not None:
        laser_kwargs["LaserID"] = args.laser_id

    mp.freeze_support()
    from JazLabs.hardware.Lasers.Laser_Server import LaserZMQServer

    server = LaserZMQServer(
        host=laser["host"],
        command_port=laser["command_port"],
        LaserType=laser["laser_type"],
        LaserKwargs=laser_kwargs,
        PollTimeoutMS=laser["poll_timeout_ms"],
    )
    print(f"Launching laser server {laser['name']!r}.")
    print(f"Host: {laser['host']}")
    print(f"Command port: {laser['command_port']}")
    print(f"Laser type: {laser['laser_type']}")
    server.run_forever()


if __name__ == "__main__":
    main()
