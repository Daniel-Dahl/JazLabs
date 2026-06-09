#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

from JazLabs.launchers.config import load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Open the configured JazLabs SLM viewer.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--shm-name", default=None)
    parser.add_argument("--window-name", default="SLM viewer")
    parser.add_argument("--zoom", type=float, default=0.2)
    parser.add_argument("--fps", type=int, default=30)
    return parser


def start_slm_viewer(
    config_name="default_lab",
    shm_name=None,
    window_name="SLM viewer",
    zoom=0.2,
    fps=30,
):
    config = load_config(config_name)
    if shm_name is None:
        shm_name = config.get("SLM_SHM_NAME")
    if shm_name is None:
        shm_name = config.get("SLM_LINUX_SERVER", {}).get("shm_name")
    if shm_name is None:
        raise ValueError("No SLM SHM name was provided and config has no SLM_SHM_NAME.")

    from JazLabs.hardware.SLM.SLMStackMilk.SLM_ViewerLinux import SLMLinuxViewer

    viewer = SLMLinuxViewer(
        stream_name=shm_name,
        window_name=window_name,
        zoom=zoom,
        fps=fps,
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
    processes = start_slm_viewer(
        config_name=args.config,
        shm_name=args.shm_name,
        window_name=args.window_name,
        zoom=args.zoom,
        fps=args.fps,
    )
    wait_for_processes(processes)


if __name__ == "__main__":
    main()

