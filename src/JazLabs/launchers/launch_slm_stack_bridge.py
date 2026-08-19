#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run the SLMStack bridge server.")
    parser.add_argument("--config", default="HDStokes")
    parser.add_argument("--local-host", default=None)
    parser.add_argument("--local-command-port", type=int, default=None)
    parser.add_argument("--local-display-pub-port", type=int, default=None)
    parser.add_argument("--remote-host", default=None)
    parser.add_argument("--remote-command-port", type=int, default=None)
    parser.add_argument("--remote-display-pub-port", type=int, default=None)
    parser.add_argument("--display-topic", default=None)
    parser.add_argument("--timeout-ms", type=int, default=None)
    parser.add_argument("--poll-sleep", type=float, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    bridge = merge_overrides(
        config.get("SLM_STACK_BRIDGE", {}),
        {
            "local_host": args.local_host,
            "local_command_port": args.local_command_port,
            "local_display_pub_port": args.local_display_pub_port,
            "remote_host": args.remote_host,
            "remote_command_port": args.remote_command_port,
            "remote_display_pub_port": args.remote_display_pub_port,
            "display_topic": args.display_topic,
            "timeout_ms": args.timeout_ms,
            "poll_sleep": args.poll_sleep,
        },
    )
    bridge.setdefault("name", "slm_stack_bridge")
    bridge.setdefault("local_host", "127.0.0.1")
    bridge.setdefault("local_command_port", 5565)
    bridge.setdefault("local_display_pub_port", 5566)
    bridge.setdefault("remote_host", "127.0.0.1")
    bridge.setdefault("remote_command_port", 5555)
    bridge.setdefault("remote_display_pub_port", 5556)
    bridge.setdefault("display_topic", "slm.display")
    bridge.setdefault("timeout_ms", 5000)
    bridge.setdefault("poll_sleep", 0.0)

    mp.freeze_support()

    from JazLabs.hardware.SLM.SLMStack.SLM_BridgeServer import SLMZMQBridgeServer

    server = SLMZMQBridgeServer(
        local_host=bridge["local_host"],
        local_command_port=bridge["local_command_port"],
        local_display_pub_port=bridge["local_display_pub_port"],
        remote_host=bridge["remote_host"],
        remote_command_port=bridge["remote_command_port"],
        remote_display_pub_port=bridge["remote_display_pub_port"],
        display_topic=bridge["display_topic"],
        timeout_ms=bridge["timeout_ms"],
        PollSleep=bridge["poll_sleep"],
    )

    print(f"Launching SLMStack bridge {bridge['name']!r}.")
    print(
        f"Local endpoint: {bridge['local_host']}:"
        f"{bridge['local_command_port']}/{bridge['local_display_pub_port']}"
    )
    print(
        f"Remote endpoint: {bridge['remote_host']}:"
        f"{bridge['remote_command_port']}/{bridge['remote_display_pub_port']}"
    )
    server.run_forever()


if __name__ == "__main__":
    main()
