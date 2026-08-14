#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run the SLM bridge server.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--client-id", default=None)
    parser.add_argument("--shm-name", default=None)
    parser.add_argument("--bind-host", default=None)
    parser.add_argument("--local-command-port", type=int, default=None)
    parser.add_argument("--server-host", default=None)
    parser.add_argument("--server-command-port", type=int, default=None)
    parser.add_argument("--server-image-port", type=int, default=None)
    parser.add_argument("--server-ack-port", type=int, default=None)
    parser.add_argument("--image-topic", default=None)
    parser.add_argument("--ack-topic", default=None)
    parser.add_argument("--timeout-ms", type=int, default=None)
    parser.add_argument("--create-shm", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--acquire-control", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--poll-timeout-s", type=float, default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    slm = merge_overrides(
        config.get("SLM_BRIDGE", {}),
        {
            "client_id": args.client_id,
            "shm_name": args.shm_name,
            "bind_host": args.bind_host,
            "local_command_port": args.local_command_port,
            "server_host": args.server_host,
            "server_command_port": args.server_command_port,
            "server_image_port": args.server_image_port,
            "server_ack_port": args.server_ack_port,
            "image_topic": args.image_topic,
            "ack_topic": args.ack_topic,
            "timeout_ms": args.timeout_ms,
            "create_shm": args.create_shm,
            "acquire_control": args.acquire_control,
            "poll_timeout_s": args.poll_timeout_s,
        },
    )

    mp.freeze_support()

    from JazLabs.hardware.SLM.SLMStackMilk.SLM_BridgeServer import SLMZMQBridgeServer

    server = SLMZMQBridgeServer(
        client_id=slm["client_id"],
        shm_name=slm["shm_name"],
        bind_host=slm["bind_host"],
        local_command_port=slm["local_command_port"],
        server_host=slm["server_host"],
        server_command_port=slm["server_command_port"],
        server_image_port=slm["server_image_port"],
        server_ack_port=slm["server_ack_port"],
        image_topic=slm["image_topic"],
        ack_topic=slm["ack_topic"],
        timeout_ms=slm["timeout_ms"],
        create_shm=slm["create_shm"],
        acquire_control=slm["acquire_control"],
        poll_timeout_s=slm["poll_timeout_s"],
    )

    print("Launching SLM bridge server.")
    print(f"SHM name: {slm['shm_name']}")
    print(f"Local command: {slm['bind_host']}:{slm['local_command_port']}")
    print(f"SLM server host: {slm['server_host']}")
    print(
        "SLM server ports: "
        f"{slm['server_command_port']}/"
        f"{slm['server_image_port']}/"
        f"{slm['server_ack_port']}"
    )
    server.run_forever()


if __name__ == "__main__":
    main()
