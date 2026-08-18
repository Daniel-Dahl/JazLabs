import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from JazLabs.utils import camera_tools
from JazLabs.hardware.Cameras.Camera_Client import CameraClient


class FakeCamera:
    def __init__(self):
        self.frame_number = 0
        self.continuous_mode_restored = False

    def GetFrame(self):
        self.frame_number += 1
        return np.full((2, 3), self.frame_number, dtype=np.uint16)

    def SetSoftwareTriggerMode(self):
        pass

    def FireSoftwareTrigger(self):
        pass

    def SetContinuousMode(self):
        self.continuous_mode_restored = True

    def GetProperties(self):
        return {"camera_type": "FLIR"}

    def GetSerialNumber(self):
        return "SN-12345"

    def GetExposureTime(self):
        return 125.0

    def GetFPS(self):
        return 20.0

    def GetGain(self):
        return 4.5


class CameraToolsTests(unittest.TestCase):
    def test_camera_client_requests_serial_number_from_server(self):
        camera_client = object.__new__(CameraClient)
        camera_client.SendCommand = mock.Mock(return_value="SN-12345")

        self.assertEqual(camera_client.GetSerialNumber(), "SN-12345")
        camera_client.SendCommand.assert_called_once_with(
            {"cmd": "get_serial_number"}
        )

    def test_default_output_contains_camera_identity_metadata(self):
        camera = FakeCamera()

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            pretend_module_path = (
                temporary_root / "src" / "JazLabs" / "utils" / "camera_tools.py"
            )

            with mock.patch.object(camera_tools, "__file__", str(pretend_module_path)):
                dark_frame = camera_tools.take_darkframe(camera, num_frames=2)

            output_directory = temporary_root / "calibrations" / "Camera"
            dark_frame_paths = sorted(output_directory.glob("darkframe_*.npy"))
            metadata_paths = sorted(output_directory.glob("darkframe_meta_*.npy"))

            self.assertEqual(len(dark_frame_paths), 2)
            self.assertEqual(len(metadata_paths), 1)
            metadata = np.load(metadata_paths[0], allow_pickle=True).item()

            self.assertEqual(metadata["camera_type"], "FLIR")
            self.assertEqual(metadata["camera_serial_number"], "SN-12345")
            self.assertEqual(metadata["exposure_time"], 125.0)
            self.assertEqual(metadata["fps"], 20.0)
            self.assertEqual(metadata["gain"], 4.5)
            self.assertEqual(metadata["frame_shape"], (2, 3))
            self.assertEqual(dark_frame.dtype, np.float64)
            self.assertTrue(camera.continuous_mode_restored)


if __name__ == "__main__":
    unittest.main()
