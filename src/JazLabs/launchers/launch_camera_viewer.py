#!/usr/bin/env python3
import argparse
import multiprocessing as mp
import time

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(description="Open configured JazLabs camera viewers.")
    parser.add_argument("--config", default="default_lab")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--name", "--camera", dest="name")
    group.add_argument("--all", action="store_true")
    parser.add_argument("--viewer", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--widget", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--initial-scale", type=float, default=1.0)
    parser.add_argument("--timeout-ms", type=int, default=60000)
    parser.add_argument("--refresh-ms", type=int, default=500)
    return parser


def selected_cameras(config, name=None, include_all=False):
    if include_all:
        return [
            dict(camera)
            for camera in config.get("CAMERA_SERVERS", [])
            if camera.get("enabled", True)
        ]
    return [get_named_config(config, "CAMERA_SERVERS", name)]


def start_camera_viewers(
    config_name="default_lab",
    name=None,
    include_all=False,
    open_viewer=True,
    open_widget=True,
    initial_scale=1.0,
    timeout_ms=5000,
    refresh_ms=500,
):
    config = load_config(config_name)
    host = config.get("CAMERA_HOST", "127.0.0.1")
    cameras = selected_cameras(config, name=name, include_all=include_all)
    processes = []

    from JazLabs.hardware.Cameras.Camera_Viewer import CameraViewer
    from JazLabs.hardware.Cameras.Camera_Widget import CameraWidget

    for camera in cameras:
        camera_host = camera.get("host", host)
        camera_name = camera["name"]

        if open_viewer:
            viewer = CameraViewer(
                host=camera_host,
                command_port=camera["command_port"],
                frame_pub_port=camera["frame_pub_port"],
                window_name=f"{camera_name} viewer",
                initial_scale=initial_scale,
            )
            viewer.startProcess()
            processes.append((f"{camera_name} viewer", viewer))

        if open_widget:
            widget = CameraWidget(
                host=camera_host,
                command_port=camera["command_port"],
                frame_pub_port=camera["frame_pub_port"],
                timeout_ms=timeout_ms,
                refresh_ms=refresh_ms,
            )
            widget.startProcess()
            processes.append((f"{camera_name} widget", widget))

    return processes


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
    if not args.viewer and not args.widget:
        raise SystemExit("Nothing to open: --no-viewer and --no-widget were both set.")

    mp.freeze_support()
    processes = start_camera_viewers(
        config_name=args.config,
        name=args.name,
        include_all=args.all,
        open_viewer=args.viewer,
        open_widget=args.widget,
        initial_scale=args.initial_scale,
        timeout_ms=args.timeout_ms,
        refresh_ms=args.refresh_ms,
    )
    if not processes:
        raise SystemExit("No enabled camera viewers matched the request.")
    wait_for_processes(processes)


if __name__ == "__main__":
    main()

