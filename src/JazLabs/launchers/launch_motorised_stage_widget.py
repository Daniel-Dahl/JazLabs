"""Open a motor widget using its client; never start a server or open a driver."""
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Open a configured JazLabs motor control GUI.")
    parser.add_argument("--config", default="motorised_mounts")
    parser.add_argument("--name", "--motor", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--bridge", action="store_true", help="Use the configured local bridge endpoint")
    parser.add_argument("--timeout-ms", type=int, default=500)
    parser.add_argument("--layout", choices=("alignment", "console"), default="alignment")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    motor = get_named_config(load_config(args.config), "MOTOR_SERVERS", args.name)
    if args.bridge:
        host = args.host or motor.get("local_host", "127.0.0.1")
        port = args.command_port if args.command_port is not None else motor["local_command_port"]
    else:
        host = args.host or motor.get("client_host", "127.0.0.1")
        port = args.command_port if args.command_port is not None else motor["command_port"]
    if host in ("0.0.0.0", "::"):
        raise ValueError("A widget must connect to a reachable host, not a wildcard bind address")
    mp.freeze_support()
    from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
    from JazLabs.hardware.MotorisedStages.MotorisedStage_Widget import MotorisedStageControlWindow
    client = MotorisedStageClient(host=host, command_port=port, timeout_ms=args.timeout_ms)
    print(f"Opening motor widget {motor['name']!r}: tcp://{host}:{port}")
    try:
        MotorisedStageControlWindow(client, args.layout).run()
    finally:
        client.close()
        if client.thread.is_alive():
            client.thread.join(timeout=3)


if __name__ == "__main__":
    main()
