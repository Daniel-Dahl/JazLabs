#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run the local SLMStack ZMQ server.")
    parser.add_argument("--config", default="HDStokes")
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--display-pub-port", type=int, default=None)
    parser.add_argument("--display-topic", default=None)
    parser.add_argument("--slm-type", default=None)
    parser.add_argument("--board-number", type=int, default=None)
    parser.add_argument("--monitor-index", type=int, default=None)
    parser.add_argument("--refresh-rate", type=float, default=None)
    parser.add_argument("--lut-file", default=None)
    parser.add_argument("--timeout-ms", type=int, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    slm = merge_overrides(
        config.get("SLM_STACK_SERVER", {}),
        {
            "host": args.host,
            "command_port": args.command_port,
            "display_pub_port": args.display_pub_port,
            "display_topic": args.display_topic,
            "slm_type": args.slm_type,
            "board_number": args.board_number,
            "monitor_index": args.monitor_index,
            "refresh_rate": args.refresh_rate,
            "lut_file": args.lut_file,
            "timeout_ms": args.timeout_ms,
        },
    )
    slm.setdefault("name", "slm_stack")
    slm.setdefault("host", "0.0.0.0")
    slm.setdefault("command_port", 5555)
    slm.setdefault("display_pub_port", 5556)
    slm.setdefault("display_topic", "slm.display")
    slm.setdefault("slm_type", "Blink OverDrive Plus")
    slm.setdefault("board_number", 1)
    slm.setdefault("monitor_index", 1)
    slm.setdefault("refresh_rate", 0)
    slm.setdefault("lut_file", None)
    slm.setdefault("timeout_ms", 5000)

    mp.freeze_support()

    from JazLabs.hardware.SLM.SLMStack.SLM_Server import SLMZMQServer

    server = SLMZMQServer(
        host=slm["host"],
        command_port=slm["command_port"],
        display_pub_port=slm["display_pub_port"],
        display_topic=slm["display_topic"],
        SLMType=slm["slm_type"],
        BoardNumber=slm["board_number"],
        MonitorIndex=slm["monitor_index"],
        RefreshRate=slm["refresh_rate"],
        LutFile=slm["lut_file"],
        timeout_ms=slm["timeout_ms"],
    )

    print(f"Launching SLMStack server {slm['name']!r}.")
    print(f"Host: {slm['host']}")
    print(f"Command port: {slm['command_port']}")
    print(f"Display PUB port: {slm['display_pub_port']}")
    print(f"Display topic: {slm['display_topic']}")
    print(f"SLM type: {slm['slm_type']}")
    if slm["slm_type"] == "HDMI SLM":
        print(f"Monitor index: {slm['monitor_index']}")
    else:
        print(f"Board number: {slm['board_number']}")
    print(f"Refresh rate: {slm['refresh_rate']}")
    if slm.get("lut_file") is not None:
        print(f"LUT file: {slm['lut_file']}")
    server.run_forever()


if __name__ == "__main__":
    main()
