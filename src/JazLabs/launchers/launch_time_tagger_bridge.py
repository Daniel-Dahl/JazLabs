#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run a local bridge for a remote JazLabs Time Tagger server."
    )
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--time-tagger", dest="name", required=True)
    parser.add_argument("--remote-host", required=True)
    parser.add_argument("--local-host", default="127.0.0.1")
    parser.add_argument("--local-command-port", type=int, default=None)
    parser.add_argument("--remote-command-port", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=120000)
    parser.add_argument("--poll-timeout-ms", type=int, default=100)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    server_config = get_named_config(config, "TIME_TAGGER_SERVERS", args.name)
    local_command_port = args.local_command_port or server_config["command_port"]
    remote_command_port = args.remote_command_port or server_config["command_port"]

    mp.freeze_support()
    from JazLabs.hardware.TimeTagger.TimeTagger_BridgeServer import (
        TimeTaggerZMQBridgeServer,
    )

    bridge = TimeTaggerZMQBridgeServer(
        local_host=args.local_host,
        local_command_port=local_command_port,
        remote_host=args.remote_host,
        remote_command_port=remote_command_port,
        timeout_ms=args.timeout_ms,
        poll_timeout_ms=args.poll_timeout_ms,
    )

    print(f"Launching Time Tagger bridge for {server_config['name']!r}.")
    print(f"Local endpoint: tcp://{args.local_host}:{local_command_port}")
    print(f"Remote endpoint: tcp://{args.remote_host}:{remote_command_port}")
    bridge.run_forever()


if __name__ == "__main__":
    main()
