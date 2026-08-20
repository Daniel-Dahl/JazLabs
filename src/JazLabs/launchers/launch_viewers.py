#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

from JazLabs.launchers.launch_camera_viewer import start_camera_viewers
from JazLabs.launchers.config import load_config
from JazLabs.launchers.launch_slm_milk_viewer import start_slm_milk_viewer
from JazLabs.launchers.launch_slm_viewer import start_slm_viewer


def build_parser():
    parser = argparse.ArgumentParser(description="Open configured JazLabs viewers.")
    parser.add_argument("target", choices=("all", "camera", "slm", "slm-milk"))
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--camera", dest="name", default=None)
    parser.add_argument("--viewer", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--widget", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--initial-scale", type=float, default=1.0)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    parser.add_argument("--refresh-ms", type=int, default=500)
    parser.add_argument("--slm-zoom", type=float, default=0.2)
    parser.add_argument("--slm-fps", type=int, default=30)
    return parser


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
    config = load_config(args.config)

    processes = []
    if args.target in ("all", "camera"):
        processes.extend(
            start_camera_viewers(
                config_name=args.config,
                name=args.name,
                include_all=args.name is None,
                open_viewer=args.viewer,
                open_widget=args.widget,
                initial_scale=args.initial_scale,
                timeout_ms=args.timeout_ms,
                refresh_ms=args.refresh_ms,
            )
        )

    if args.target == "slm" or (
        args.target == "all"
        and (
            config.get("SLM_BRIDGE", {}).get("enabled", False)
            or config.get("SLM_SERVER", {}).get("enabled", False)
        )
    ):
        processes.extend(
            start_slm_viewer(
                config_name=args.config,
                zoom=args.slm_zoom,
                fps=args.slm_fps,
            )
        )

    if args.target == "slm-milk" or (
        args.target == "all"
        and config.get("SLM_MILK_BRIDGE", {}).get("enabled", False)
    ):
        processes.extend(
            start_slm_milk_viewer(
                config_name=args.config,
                zoom=args.slm_zoom,
                fps=args.slm_fps,
            )
        )

    if not processes:
        raise SystemExit("No viewers matched the request.")

    wait_for_processes(processes)


if __name__ == "__main__":
    main()
