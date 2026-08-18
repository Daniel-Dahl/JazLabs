import numpy as np
from datetime import datetime
from pathlib import Path
import time


def take_darkframe(camera_object, num_frames=10, save_path=None, wait_time=None):
    """Take a dark frame using the provided camera object.

    Args:
        camera_object: The camera object to use for taking the dark frame.
        num_frames: The number of dark frames to take (default is 10).
        save_path: Directory for the dark frame and metadata files. Defaults to
            the repository's calibrations/Camera directory.
        wait_time: Time to wait between frames in seconds (None for no wait).
    """
    dumbframe=camera_object.GetFrame()
    darkframe_accum = np.zeros((dumbframe.shape[0], dumbframe.shape[1]),
        dtype=np.float64)

    frames = []
    camera_object.SetSoftwareTriggerMode()
    for i in range(num_frames):
        frame = camera_object.FireSoftwareTrigger()
        frame = camera_object.GetFrame()
        frames.append(frame)
        darkframe_accum += frame.astype(np.float64)
        if (i + 1) % 10 == 0:
            print(f"  Frame {i + 1}/{num_frames}")
        if wait_time is not None:
            time.sleep(wait_time)

    # Check all frames are unique
    for i in range(len(frames)):
        for j in range(i + 1, len(frames)):
            if np.array_equal(frames[i], frames[j]):
                raise ValueError(f"Frames {i} and {j} are identical — camera may be returning cached data.")

    # Average (keep as float64)
    darkframe = darkframe_accum / num_frames
    print(camera_object.GetExposureTime())

    if save_path is None:
        save_path = Path(__file__).resolve().parents[3] / "calibrations" / "Camera"

    save_directory = Path(save_path).expanduser()
    save_directory.mkdir(parents=True, exist_ok=True)

    camera_type = None
    get_properties = getattr(camera_object, "GetProperties", None)
    if callable(get_properties):
        camera_properties = get_properties()
        if isinstance(camera_properties, dict):
            camera_type = camera_properties.get("camera_type")
    if camera_type is None:
        camera_type = getattr(camera_object, "CameraType", None)
    if camera_type is None:
        camera_type = getattr(camera_object, "camera_type", None)
    if camera_type is None:
        camera_type = getattr(camera_object, "camModel", None)
    if camera_type is None:
        camera_class = type(camera_object)
        camera_type = f"{camera_class.__module__}.{camera_class.__qualname__}"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    darkframe_path = save_directory / f"darkframe_{timestamp}.npy"
    darkframe_path_meta = save_directory / f"darkframe_meta_{timestamp}.npy"

    np.save(darkframe_path, darkframe)
    np.save(darkframe_path_meta, {
        "num_frames": num_frames,
        "wait_time": wait_time,
        "timestamp": timestamp,
        "camera_type": str(camera_type),
        "camera_serial_number": str(camera_object.GetSerialNumber()),
        "exposure_time": camera_object.GetExposureTime(),
        "fps": camera_object.GetFPS(),
        "gain": camera_object.GetGain(),
        "frame_shape": darkframe.shape,
    })
    print(f"Dark frame saved to: {darkframe_path}")
    camera_object.SetContinuousMode()

    return darkframe
