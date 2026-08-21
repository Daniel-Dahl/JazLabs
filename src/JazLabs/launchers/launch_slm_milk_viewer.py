#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

import zmq

from JazLabs.launchers.config import load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Open the configured pyMilk SLM viewer.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--shm-name", default=None)
    parser.add_argument("--window-name", default="SLM viewer")
    parser.add_argument("--zoom", type=float, default=0.2)
    parser.add_argument("--fps", type=int, default=30)
    return parser


def start_slm_milk_viewer(
    config_name="default_lab",
    shm_name=None,
    window_name="SLM viewer",
    zoom=0.2,
    fps=30,
):
    config = load_config(config_name)
    if "SLM_MILK_BRIDGE" not in config:
        raise ValueError(
            f"Config {config_name!r} does not define SLM_MILK_BRIDGE."
        )

    if shm_name is None:
        shm_name = config.get("SLM_MILK_SHM_NAME")
    if shm_name is None:
        shm_name = config.get("SLM_MILK_BRIDGE", {}).get("shm_name")
    if shm_name is None:
        raise ValueError(
            "No SLM SHM name was provided and config has no SLM_MILK_SHM_NAME."
        )

    bridge = config["SLM_MILK_BRIDGE"]
    bridge_host = bridge.get("bind_host", "127.0.0.1")
    bridge_command_port = int(bridge.get("local_command_port", 5565))
    timeout_ms = int(bridge.get("timeout_ms", 5000))

    context = zmq.Context()
    command_socket = context.socket(zmq.REQ)
    command_socket.setsockopt(zmq.LINGER, 0)
    command_socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
    command_socket.setsockopt(zmq.SNDTIMEO, timeout_ms)
    command_socket.connect(f"tcp://{bridge_host}:{bridge_command_port}")
    try:
        command_socket.send_json(
            {"cmd": "get_properties", "client_id": "slm_milk_viewer_startup"}
        )
        reply = command_socket.recv_json()
    finally:
        command_socket.close(0)
        context.term()

    if not reply.get("ok", False):
        raise RuntimeError(reply.get("error", "Unable to query SLM Milk bridge"))
    properties = reply["result"]

    from JazLabs.hardware.SLM.SLMStackMilk.SLM_Viewer import SLMViewer

    viewer = SLMViewer(
        stream_name=properties.get(
            "confirmed_shm_name",
            f"{shm_name}_confirmed",
        ),
        window_name=window_name,
        zoom=zoom,
        fps=fps,
        number_of_channels=properties["number_of_channels"],
        bridge_host=bridge_host,
        bridge_command_port=bridge_command_port,
        timeout_ms=timeout_ms,
    )
    viewer.startProcess()
    return [("slm viewer", viewer)]


def wait_for_processes(processes):
    try:
        while any(process_obj.Process is not None and process_obj.Process.is_alive() for _, process_obj in processes):
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping viewers.")
    finally:
        for _, process_obj in processes:
            process_obj.stopProcess()


def main(argv=None):
    args = build_parser().parse_args(argv)
    mp.freeze_support()
    processes = start_slm_milk_viewer(
        config_name=args.config,
        shm_name=args.shm_name,
        window_name=args.window_name,
        zoom=args.zoom,
        fps=args.fps,
    )
    wait_for_processes(processes)


if __name__ == "__main__":
    main()
