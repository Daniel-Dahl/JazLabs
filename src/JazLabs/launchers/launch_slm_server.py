#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run the hardware-facing SLM server.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--image-sub-port", type=int, default=None)
    parser.add_argument("--ack-pub-port", type=int, default=None)
    parser.add_argument("--image-topic", default=None)
    parser.add_argument("--ack-topic", default=None)
    parser.add_argument("--slm-type", default=None)
    parser.add_argument("--refresh-rate", type=float, default=None)
    parser.add_argument("--lut-file", default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    slm = merge_overrides(
        config.get("SLM_SERVER", {}),
        {
            "host": args.host,
            "command_port": args.command_port,
            "image_sub_port": args.image_sub_port,
            "ack_pub_port": args.ack_pub_port,
            "image_topic": args.image_topic,
            "ack_topic": args.ack_topic,
            "slm_type": args.slm_type,
            "refresh_rate": args.refresh_rate,
            "lut_file": args.lut_file,
        },
    )

    mp.freeze_support()

    from JazLabs.hardware.SLM.SLMStackMilk.SLM_Server import SLMZMQServer

    server = SLMZMQServer(
        host=slm["host"],
        command_port=slm["command_port"],
        image_sub_port=slm["image_sub_port"],
        ack_pub_port=slm["ack_pub_port"],
        image_topic=slm["image_topic"],
        ack_topic=slm["ack_topic"],
        SLMType=slm["slm_type"],
        RefreshRate=slm["refresh_rate"],
        LutFile=slm["lut_file"],
    )

    print("Launching SLM server.")
    print(f"Host: {slm['host']}")
    print(
        "Ports: "
        f"{slm['command_port']}/"
        f"{slm['image_sub_port']}/"
        f"{slm['ack_pub_port']}"
    )
    print(f"SLM type: {slm['slm_type']}")
    print(f"Refresh rate: {slm['refresh_rate']}")
    if slm.get("lut_file") is not None:
        print(f"LUT file: {slm['lut_file']}")
    server.run_forever()


if __name__ == "__main__":
    main()
