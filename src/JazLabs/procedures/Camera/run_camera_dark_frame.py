"""Acquire and save an averaged dark frame from a configured camera server."""

import argparse
from datetime import datetime
import json
from pathlib import Path
import re

import numpy as np

from JazLabs.launchers.config import get_named_config, load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(
        description="Acquire an averaged dark frame from a configured camera client."
    )
    parser.add_argument(
        "--config",
        default="default_lab",
        help="Config module name or path to a Python config file.",
    )
    parser.add_argument(
        "--name",
        "--camera",
        dest="camera_name",
        default=None,
        help="Camera name from CAMERA_SERVERS (defaults to DARK_FRAME_CONFIG).",
    )
    parser.add_argument(
        "--num-frames",
        type=int,
        default=None,
        help="Number of software-triggered frames to average.",
    )
    parser.add_argument(
        "--description",
        default=None,
        help='Optional acquisition description, for example "dark lab, lights off".',
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="Directory for the NPY dark frame, JSON metadata, and PNG preview.",
    )
    parser.add_argument(
        "--save-preview",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Save a PNG preview (enabled by default).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the prompt asking the operator to confirm that the camera is dark.",
    )
    return parser


def _filename_number(value):
    return format(float(value), ".9g").replace("-", "m").replace(".", "p")


def _description_slug(description):
    slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")
    return slug[:48].rstrip("-")


def _camera_name_slug(camera_name):
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", camera_name).strip("-_")
    return slug[:48].rstrip("-_")


def acquire_dark_frame(camera_client, num_frames):
    """Acquire software-triggered frames and return their float64 mean."""
    if num_frames < 1:
        raise ValueError("num_frames must be at least 1")

    trigger_mode, trigger_source = camera_client.GetTriggerMode()
    trigger_mode_text = str(trigger_mode).lower()
    trigger_source_text = str(trigger_source).lower()
    if trigger_mode_text == "on" and trigger_source_text != "software":
        raise RuntimeError(
            "The camera is using a hardware trigger. Its trigger line cannot be "
            "restored through CameraClient, so dark-frame acquisition was not started."
        )

    restore_continuous_mode = trigger_mode_text == "off"
    dark_frame = None

    try:
        camera_client.SetSoftwareTriggerMode()
        for frame_index in range(num_frames):
            frame = np.asarray(camera_client.GetSoftwareTriggeredFrame())
            if frame.ndim != 2:
                raise ValueError(
                    f"Dark-frame acquisition requires 2-D frames; received {frame.shape}"
                )

            frame_float = frame.astype(np.float64, copy=False)
            if dark_frame is None:
                dark_frame = frame_float.copy()
            else:
                if frame.shape != dark_frame.shape:
                    raise ValueError(
                        "Camera frame shape changed during acquisition: "
                        f"expected {dark_frame.shape}, received {frame.shape}"
                    )
                dark_frame += (frame_float - dark_frame) / (frame_index + 1)

            completed_count = frame_index + 1
            if completed_count % 10 == 0 or completed_count == num_frames:
                print(f"  Frame {completed_count}/{num_frames}")
    finally:
        if restore_continuous_mode:
            camera_client.SetContinuousMode()

    return dark_frame


def save_dark_frame(
    dark_frame,
    output_directory,
    camera_name,
    exposure_time_us,
    camera_fps,
    description,
    num_frames,
    captured_at,
    camera_connection,
    save_preview=True,
):
    output_directory = Path(output_directory).expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)

    timestamp = captured_at.strftime("%Y%m%d_%H%M%S")
    filename_parts = [
        "darkframe",
        timestamp,
        _camera_name_slug(camera_name) or "camera",
        f"exp-{_filename_number(exposure_time_us)}us",
        f"fps-{_filename_number(camera_fps)}",
    ]
    description_slug = _description_slug(description)
    if description_slug:
        filename_parts.append(description_slug)
    filename_stem = "_".join(filename_parts)

    dark_frame_path = output_directory / f"{filename_stem}.npy"
    metadata_path = output_directory / f"{filename_stem}.json"
    preview_path = output_directory / f"{filename_stem}.png" if save_preview else None

    np.save(dark_frame_path, dark_frame, allow_pickle=False)

    metadata = {
        "captured_at": captured_at.isoformat(),
        "camera_name": camera_name,
        "exposure_time_us": float(exposure_time_us),
        "camera_fps": float(camera_fps),
        "description": description,
        "number_of_frames_averaged": int(num_frames),
        "dark_frame_shape": list(dark_frame.shape),
        "dark_frame_dtype": str(dark_frame.dtype),
        "dark_frame_minimum": float(np.min(dark_frame)),
        "dark_frame_maximum": float(np.max(dark_frame)),
        "dark_frame_mean": float(np.mean(dark_frame)),
        "dark_frame_standard_deviation": float(np.std(dark_frame)),
        "camera_connection": camera_connection,
        "dark_frame_file": dark_frame_path.name,
        "preview_file": preview_path.name if preview_path is not None else None,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    if preview_path is not None:
        import matplotlib.pyplot as plt

        figure, axis = plt.subplots(figsize=(8, 6))
        image = axis.imshow(dark_frame, cmap="gray")
        axis.set_title(
            f"{camera_name} dark frame\n"
            f"{exposure_time_us:g} us, {camera_fps:g} FPS, {num_frames} frames"
        )
        axis.set_xlabel("Camera X pixel")
        axis.set_ylabel("Camera Y pixel")
        figure.colorbar(image, ax=axis, label="Mean camera counts")
        if description:
            figure.text(0.5, 0.01, description, ha="center")
        figure.savefig(preview_path, dpi=150, bbox_inches="tight")
        plt.close(figure)

    return dark_frame_path, metadata_path, preview_path


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    procedure_config = merge_overrides(
        config.get("DARK_FRAME_CONFIG", {}),
        {
            "camera_name": args.camera_name,
            "num_frames": args.num_frames,
            "description": args.description,
            "output_directory": args.output_directory,
            "save_preview": args.save_preview,
        },
    )

    required_settings = ("camera_name", "num_frames", "output_directory")
    missing_settings = [
        setting for setting in required_settings if setting not in procedure_config
    ]
    if missing_settings:
        raise ValueError(
            "DARK_FRAME_CONFIG is missing required settings: "
            + ", ".join(missing_settings)
        )

    camera_name = procedure_config["camera_name"]
    camera_config = get_named_config(config, "CAMERA_SERVERS", camera_name)
    camera_host = camera_config.get("host", config.get("CAMERA_HOST", "127.0.0.1"))
    description = str(procedure_config.get("description") or "")
    num_frames = int(procedure_config["num_frames"])
    if num_frames < 1:
        raise ValueError("num_frames must be at least 1")

    if not args.yes:
        print("Ready to acquire a dark frame. Make sure the camera is dark.")
        input("Press Enter to continue, or Ctrl+C to cancel...")

    from JazLabs.hardware.Cameras.Camera_Client import CameraClient

    camera_client = None
    try:
        camera_client = CameraClient(
            host=camera_host,
            command_port=camera_config["command_port"],
            frame_pub_port=camera_config["frame_pub_port"],
            timeout_ms=procedure_config.get("camera_timeout_ms", 60000),
            client_id=procedure_config.get("camera_client_id", "camera_dark_frame"),
        )
        exposure_time_us = float(camera_client.GetExposureTime())
        camera_fps = float(camera_client.GetFPS())
        captured_at = datetime.now().astimezone()

        print(
            f"Acquiring {num_frames} frames from {camera_name!r} at "
            f"{exposure_time_us:g} us and {camera_fps:g} FPS."
        )
        dark_frame = acquire_dark_frame(camera_client, num_frames)
        dark_frame_path, metadata_path, preview_path = save_dark_frame(
            dark_frame=dark_frame,
            output_directory=procedure_config["output_directory"],
            camera_name=camera_name,
            exposure_time_us=exposure_time_us,
            camera_fps=camera_fps,
            description=description,
            num_frames=num_frames,
            captured_at=captured_at,
            camera_connection={
                "host": camera_host,
                "command_port": int(camera_config["command_port"]),
                "frame_pub_port": int(camera_config["frame_pub_port"]),
            },
            save_preview=procedure_config.get("save_preview", True),
        )
    finally:
        if camera_client is not None:
            camera_client.close()

    print(f"Dark frame saved: {dark_frame_path}")
    print(f"Metadata saved: {metadata_path}")
    if preview_path is not None:
        print(f"Preview saved: {preview_path}")


if __name__ == "__main__":
    main()
