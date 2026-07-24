#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config


def build_parser():
    parser = argparse.ArgumentParser(
        description="Open a live spot-power viewer for a configured camera server."
    )
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--camera", dest="name", required=True)
    parser.add_argument(
        "--centres",
        help="Optional .npy, .npz, .csv, or text file containing (y, x) centres.",
    )
    parser.add_argument("--radius-y", type=float)
    parser.add_argument("--radius-x", type=float)
    parser.add_argument("--dark-frame")
    parser.add_argument("--refresh-ms", type=int)
    return parser


def get_spot_power_config(config, name):
    for viewer_config in config.get("SPOT_POWER_VIEWERS", []):
        if viewer_config.get("name") == name:
            return dict(viewer_config)
    return {}


def main(argv=None):
    args = build_parser().parse_args(argv)

    from JazLabs.hardware.SpotPower.SpotPower_Viewer import (
        SpotPowerViewer,
        load_spot_centres_file,
    )

    config = load_config(args.config)
    spot_power_config = get_spot_power_config(config, args.name)
    camera_name = spot_power_config.get("camera_name", args.name)
    camera = get_named_config(config, "CAMERA_SERVERS", camera_name)
    default_host = config.get("CAMERA_HOST", "127.0.0.1")

    centres_filename = (
        args.centres
        if args.centres is not None
        else spot_power_config.get("centres")
    )
    dark_frame_filename = (
        args.dark_frame
        if args.dark_frame is not None
        else spot_power_config.get("dark_frame")
    )
    radius_y = (
        args.radius_y
        if args.radius_y is not None
        else spot_power_config.get("radius_y", 3.0)
    )
    radius_x = (
        args.radius_x
        if args.radius_x is not None
        else spot_power_config.get("radius_x", 3.0)
    )
    refresh_ms = (
        args.refresh_ms
        if args.refresh_ms is not None
        else spot_power_config.get("refresh_ms", 100)
    )

    spot_centres = None
    if centres_filename:
        spot_centres = load_spot_centres_file(centres_filename)

    mp.freeze_support()
    viewer = SpotPowerViewer(
        host=camera.get("host", default_host),
        command_port=camera["command_port"],
        frame_pub_port=camera["frame_pub_port"],
        spot_centres=spot_centres,
        aperture_radii=(radius_y, radius_x),
        dark_frame_filename=dark_frame_filename,
        refresh_ms=refresh_ms,
        window_name=spot_power_config.get(
            "window_name",
            f"{camera['name']} spot power",
        ),
    )
    viewer.startProcess()

    try:
        viewer.Process.join()
    except KeyboardInterrupt:
        viewer.stopProcess()


if __name__ == "__main__":
    main()
