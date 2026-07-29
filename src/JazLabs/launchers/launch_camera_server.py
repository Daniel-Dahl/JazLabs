#!/usr/bin/env python3
import argparse
import multiprocessing as mp

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(description="Run one configured JazLabs camera server.")
    parser.add_argument("--config", default="default_lab")
    parser.add_argument("--name", "--camera", dest="name", required=True)
    parser.add_argument("--host", default=None)
    parser.add_argument("--command-port", type=int, default=None)
    parser.add_argument("--frame-pub-port", type=int, default=None)
    parser.add_argument("--frame-topic", default=None)
    parser.add_argument("--camera-type", default=None)
    parser.add_argument("--camera_serial_number", type=any, default=None)
    parser.add_argument("--poll-sleep", type=float, default=None)
    parser.add_argument("--verbose", action="store_true", default=None)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    camera = get_named_config(config, "CAMERA_SERVERS", args.name)
    camera = merge_overrides(
        camera,
        {
            "host": args.host,
            "command_port": args.command_port,
            "frame_pub_port": args.frame_pub_port,
            "frame_topic": args.frame_topic,
            "camera_type": args.camera_type,
            "camera_serial_number": args.camera_serial_number,
            "poll_sleep": args.poll_sleep,
            "verbose": args.verbose,
        },
    )
    camera.setdefault("host", config.get("CAMERA_HOST", "127.0.0.1"))
    camera.setdefault("frame_topic", "camera.frame")
    camera.setdefault("poll_sleep", 0.0001)
    camera.setdefault("verbose", False)

    mp.freeze_support()

    from JazLabs.hardware.Cameras.Camera_Server import CameraZMQServer

    server = CameraZMQServer(
        host=camera["host"],
        command_port=camera["command_port"],
        frame_pub_port=camera["frame_pub_port"],
        CameraType=camera["camera_type"],
        CameraKwargs={
            "CameraSerialNumber": camera["camera_serial_number"],
            "verbose": camera["verbose"],
        },
        PollSleep=camera["poll_sleep"],
        PublishFramesOverZMQ=False,
        frame_topic=camera["frame_topic"],
    )

    print(f"Launching camera server {camera['name']!r}.")
    print(f"Host: {camera['host']}")
    print(f"Command port: {camera['command_port']}")
    print(f"Frame PUB port: {camera['frame_pub_port']}")
    print(f"Frame topic: {camera['frame_topic']}")
    print(f"Camera type: {camera['camera_type']}")
    print(f"Camera serial number: {camera['camera_serial_number']}")
    server.run_forever()


if __name__ == "__main__":
    main()

