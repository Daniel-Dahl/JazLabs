"""Expose a remote motor server through a separately launched local bridge."""
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Run a local bridge for a remote JazLabs motor server.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--motor", dest="name", required=True)
    parser.add_argument("--remote-host", default=None)
    parser.add_argument("--remote-command-port", type=int, default=None)
    parser.add_argument("--local-host", default=None)
    parser.add_argument("--local-command-port", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=500)
    parser.add_argument("--poll-timeout-ms", type=int, default=50)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    motor = get_named_config(load_config(args.config), "MOTOR_SERVERS", args.name)
    remote_host = args.remote_host or motor.get("remote_host")
    if not remote_host:
        parser.error("Set remote_host in the motor config or supply --remote-host")
    remote_port = args.remote_command_port if args.remote_command_port is not None else motor["command_port"]
    local_host = args.local_host or motor.get("local_host", "127.0.0.1")
    local_port = args.local_command_port if args.local_command_port is not None else motor["local_command_port"]
    mp.freeze_support()
    from JazLabs.hardware.MotorisedStages.MotorisedStage_BridgeServer import MotorisedStageZMQBridgeServer
    bridge = MotorisedStageZMQBridgeServer(
        remote_host=remote_host, remote_command_port=remote_port, local_host=local_host,
        local_command_port=local_port, timeout_ms=args.timeout_ms, poll_timeout_ms=args.poll_timeout_ms,
    )
    print(f"Launching motor bridge for {motor['name']!r}.")
    try:
        bridge.run_forever()
    except KeyboardInterrupt:
        print("Motor bridge stopped.")


if __name__ == "__main__":
    main()
