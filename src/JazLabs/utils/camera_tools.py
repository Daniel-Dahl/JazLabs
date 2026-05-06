import numpy as np
from datetime import datetime
from pathlib import Path
import time


def take_darkframe(camera_object, num_frames=10, save_path=None, wait_time=None):
    """Take a dark frame using the provided camera object.

    Args:
        camera_object: The camera object to use for taking the dark frame.
        num_frames: The number of dark frames to take (default is 10).
        save_path: Path to save the dark frame as a npy file (None to not save).
        wait_time: Time to wait between frames in seconds (None for no wait).
    """
    darkframe_accum = np.zeros((camera_object.Ny, camera_object.Nx),
        dtype=np.float64)

    frames = []
    for i in range(num_frames):
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

    if save_path is not None:
        # Save with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        darkframe_path = Path(save_path) / f"darkframe_{timestamp}.npy"
        # darkframe_path.parent.mkdir(parents=True, exist_ok=True)
        np.save(darkframe_path, darkframe)
        print(f"Dark frame saved to: {darkframe_path}")

    return darkframe