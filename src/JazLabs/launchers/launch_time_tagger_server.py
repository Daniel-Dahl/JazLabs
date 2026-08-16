#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run one configured JazLabs Time Tagger server."
    )
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--time-tagger", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--serial", default=None)
    parser.add_argument("--poll-timeout-ms", type=int, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    configured_server = get_named_config(config, "TIME_TAGGER_SERVERS", args.name)
    server_config = merge_overrides(
        configured_server,
        {
            "host": args.host,
            "command_port": args.command_port,
            "serial": args.serial,
            "poll_timeout_ms": args.poll_timeout_ms,
        },
    )

    mp.freeze_support()
    from JazLabs.hardware.TimeTagger.TimeTagger_Server import TimeTaggerZMQServer

    server = TimeTaggerZMQServer(
        host=server_config["host"],
        command_port=server_config["command_port"],
        serial=server_config.get("serial"),
        create_kwargs=server_config.get("create_kwargs", {}),
        poll_timeout_ms=server_config.get("poll_timeout_ms", 100),
    )

    print(f"Launching Time Tagger server {server_config['name']!r}.")
    print(f"Host: {server_config['host']}")
    print(f"Command port: {server_config['command_port']}")
    print(f"Serial: {server_config.get('serial')}")
    server.run_forever()


if __name__ == "__main__":
    main()
