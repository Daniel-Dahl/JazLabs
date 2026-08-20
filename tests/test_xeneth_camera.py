import numpy as np

from JazLabs.hardware.Cameras.Xenic import Xeneth as xeneth_camera


class FakeXenethLibrary:
    instances = []

    def __init__(self, dll_path=None):
        self.dll_path = dll_path
        self.closed = False
        self.capturing = False
        self.float_properties = {
            "IntegrationTime": 1250.0,
            "FrameRate": 50.0,
        }
        self.long_properties = {
            "WoiSX(0)": 0,
            "WoiEX(0)": 3,
            "WoiSY(0)": 0,
            "WoiEY(0)": 2,
            "TriggerInEnable": 0,
            "TriggerInMode": 0,
        }
        self.string_properties = {
            "LowGain": "False",
            "Fan": "False",
        }
        self.instances.append(self)

    def open_camera(self, camera_name):
        self.camera_name = camera_name
        return 17

    def close_camera(self, handle):
        assert handle == 17
        self.closed = True

    def start_capture(self, handle):
        assert handle == 17
        self.capturing = True

    def stop_capture(self, handle):
        assert handle == 17
        self.capturing = False

    def get_width(self, handle):
        return 4

    def get_height(self, handle):
        return 3

    def get_frame_size(self, handle):
        return 4 * 3 * np.dtype(np.uint16).itemsize

    def get_frame_type(self, handle):
        return xeneth_camera.FT_16_BPP_GRAY

    def get_bit_size(self, handle):
        return 12

    def get_frame(self, handle, frame_buffer):
        frame = np.arange(12, dtype=np.uint16)
        frame_buffer[:] = frame.view(np.uint8)

    def get_frame_count(self, handle):
        return 42

    def get_frame_rate(self, handle):
        return self.float_properties["FrameRate"]

    def get_property(self, handle, property_name):
        return self.string_properties[property_name]

    def set_property(self, handle, property_name, value, unit=""):
        self.string_properties[property_name] = str(value)
        return self.string_properties[property_name]

    def get_property_long(self, handle, property_name):
        return self.long_properties[property_name]

    def set_property_long(self, handle, property_name, value, unit=""):
        self.long_properties[property_name] = int(value)
        return self.long_properties[property_name]

    def get_property_float(self, handle, property_name):
        return self.float_properties[property_name]

    def set_property_float(self, handle, property_name, value, unit=""):
        self.float_properties[property_name] = float(value)
        return self.float_properties[property_name]

    def get_property_range_float(self, handle, property_name):
        if property_name == "IntegrationTime":
            return 1.0, 1_000_000.0
        return 1.0, 100.0

    def load_settings(self, handle, settings_path):
        self.settings_path = settings_path

    def load_calibration(self, handle, calibration_path):
        self.calibration_path = calibration_path


def make_camera(monkeypatch, **camera_kwargs):
    FakeXenethLibrary.instances.clear()
    monkeypatch.setattr(xeneth_camera, "XenethLibrary", FakeXenethLibrary)
    camera = xeneth_camera.CameraObject(**camera_kwargs)
    return camera, FakeXenethLibrary.instances[-1]


def test_camera_returns_native_frame_and_closes_cleanly(monkeypatch):
    camera, library = make_camera(monkeypatch, CameraName="cam://2")

    frame = camera.GetFrame()

    assert camera.CameraType == "Xeneth"
    assert camera.GetSerialNumber() == "cam://2"
    assert frame.shape == (3, 4)
    assert frame.dtype == np.uint16
    np.testing.assert_array_equal(frame, np.arange(12).reshape(3, 4))
    assert camera.GetFrameID() == 42
    assert library.capturing is True

    camera.shutdown()

    assert library.capturing is False
    assert library.closed is True
    assert camera.handle == 0


def test_camera_controls_use_one_explicit_xeneth_property_set(monkeypatch):
    camera, library = make_camera(monkeypatch)

    assert camera.SetExposureTime(2500) == 2500.0
    assert library.float_properties["IntegrationTime"] == 2500.0
    assert camera.SetGain(1) == 1
    assert library.string_properties["LowGain"] == "True"
    assert camera.SetFanState(1) == 1
    assert library.string_properties["Fan"] == "True"

    assert camera.SetROI(offset_x=1, offset_y=1, width=2, height=2) == (
        1,
        1,
        2,
        2,
    )
    assert library.long_properties["WoiSX(0)"] == 1
    assert library.long_properties["WoiEX(0)"] == 2
    assert library.long_properties["WoiSY(0)"] == 1
    assert library.long_properties["WoiEY(0)"] == 2

    assert camera.SetSoftwareTriggerMode() == ("On", "Software")
    camera.FireSoftwareTrigger()
    assert library.long_properties["SoftwareTrigger"] == 1

    camera.shutdown()
