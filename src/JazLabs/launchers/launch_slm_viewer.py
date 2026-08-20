#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

from JazLabs.launchers.config import load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Open the JazLabs SLM viewer.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--display-pub-port", type=int, default=None)
    parser.add_argument("--window-name", default=None)
    parser.add_argument("--zoom", type=float, default=None)
    parser.add_argument("--fps", type=int, default=None)
    parser.add_argument("--timeout-ms", type=int, default=None)
    return parser


def start_slm_viewer(
    config_name="default_lab",
    host=None,
    command_port=None,
    display_pub_port=None,
    window_name=None,
    zoom=None,
    fps=None,
    timeout_ms=None,
):
    config = load_config(config_name)
    server = config.get("SLM_SERVER", {})
    viewer = merge_overrides(
        config.get("SLM_VIEWER", {}),
        {
            "host": host,
            "command_port": command_port,
            "display_pub_port": display_pub_port,
            "window_name": window_name,
            "zoom": zoom,
            "fps": fps,
            "timeout_ms": timeout_ms,
        },
    )
    viewer.setdefault("host", server.get("viewer_host", "127.0.0.1"))
    viewer.setdefault("command_port", server.get("command_port", 5555))
    viewer.setdefault("display_pub_port", server.get("display_pub_port", 5556))
    viewer.setdefault("window_name", "SLM viewer")
    viewer.setdefault("zoom", 0.2)
    viewer.setdefault("fps", 30)
    viewer.setdefault("timeout_ms", server.get("timeout_ms", 5000))

    from JazLabs.hardware.SLM.SLMStack.SLM_Client import SLMClient
    from JazLabs.hardware.SLM.SLMStack.SLM_Viewer import SLMOutputViewer

    client = SLMClient(
        host=viewer["host"],
        command_port=viewer["command_port"],
        display_pub_port=viewer["display_pub_port"],
        timeout_ms=viewer["timeout_ms"],
        attach_viewer_shared_memory=False,
    )
    try:
        props = client.GetProperties()
    finally:
        client.close()

    process = SLMOutputViewer(
        shm_name=props["viewer_shared_memory_name"],
        shape=props["viewer_shape"],
        dtype=props["viewer_dtype"],
        window_name=viewer["window_name"],
        zoom=viewer["zoom"],
        fps=viewer["fps"],
    )
    process.startProcess()
    return [("slm viewer", process)]


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
    processes = start_slm_viewer(
        config_name=args.config,
        host=args.host,
        command_port=args.command_port,
        display_pub_port=args.display_pub_port,
        window_name=args.window_name,
        zoom=args.zoom,
        fps=args.fps,
        timeout_ms=args.timeout_ms,
    )
    wait_for_processes(processes)


if __name__ == "__main__":
    main()
