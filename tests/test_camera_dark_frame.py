import json
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import numpy as np

from JazLabs.procedures.Camera.run_camera_dark_frame import (
    acquire_dark_frame,
    save_dark_frame,
)


class FakeCameraClient:
    def __init__(self, frames, trigger_mode=("Off", "")):
        self.frames = iter(frames)
        self.trigger_mode = trigger_mode
        self.software_mode_calls = 0
        self.continuous_mode_calls = 0

    def GetTriggerMode(self):
        return self.trigger_mode

    def SetSoftwareTriggerMode(self):
        self.software_mode_calls += 1

    def GetSoftwareTriggeredFrame(self):
        return next(self.frames)

    def SetContinuousMode(self):
        self.continuous_mode_calls += 1


class CameraDarkFrameTests(unittest.TestCase):
    def test_acquisition_averages_frames_and_restores_continuous_mode(self):
        camera = FakeCameraClient(
            [
                np.array([[0, 2], [4, 6]], dtype=np.uint16),
                np.array([[2, 4], [6, 8]], dtype=np.uint16),
                np.array([[4, 6], [8, 10]], dtype=np.uint16),
            ]
        )

        dark_frame = acquire_dark_frame(camera, num_frames=3)

        np.testing.assert_array_equal(
            dark_frame,
            np.array([[2, 4], [6, 8]], dtype=np.float64),
        )
        self.assertEqual(camera.software_mode_calls, 1)
        self.assertEqual(camera.continuous_mode_calls, 1)

    def test_hardware_trigger_mode_is_not_modified(self):
        camera = FakeCameraClient([], trigger_mode=("On", "Line0"))

        with self.assertRaisesRegex(RuntimeError, "hardware trigger"):
            acquire_dark_frame(camera, num_frames=1)

        self.assertEqual(camera.software_mode_calls, 0)
        self.assertEqual(camera.continuous_mode_calls, 0)

    def test_save_writes_array_and_metadata_with_descriptive_name(self):
        captured_at = datetime(2026, 8, 10, 14, 30, 5, tzinfo=timezone.utc)
        dark_frame = np.array([[1.0, 2.0], [3.0, 4.0]])

        with tempfile.TemporaryDirectory() as temporary_directory:
            dark_frame_path, metadata_path, preview_path = save_dark_frame(
                dark_frame=dark_frame,
                output_directory=temporary_directory,
                camera_name="cam_slm",
                exposure_time_us=100.5,
                camera_fps=30.0,
                description="Dark lab; lights OFF",
                num_frames=4,
                captured_at=captured_at,
                camera_connection={
                    "host": "127.0.0.1",
                    "command_port": 50731,
                    "frame_pub_port": 50732,
                },
                save_preview=True,
            )

            self.assertEqual(
                dark_frame_path.name,
                "darkframe_20260810_143005_cam_slm_exp-100p5us_"
                "fps-30_dark-lab-lights-off.npy",
            )
            np.testing.assert_array_equal(np.load(dark_frame_path), dark_frame)
            metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
            self.assertEqual(metadata["exposure_time_us"], 100.5)
            self.assertEqual(metadata["camera_fps"], 30.0)
            self.assertEqual(metadata["description"], "Dark lab; lights OFF")
            self.assertEqual(metadata["captured_at"], "2026-08-10T14:30:05+00:00")
            self.assertEqual(
                preview_path.name,
                "darkframe_20260810_143005_cam_slm_exp-100p5us_"
                "fps-30_dark-lab-lights-off.png",
            )
            self.assertTrue(preview_path.is_file())


if __name__ == "__main__":
    unittest.main()
