import ctypes

import numpy as np
import pytest

from JazLabs.hardware.Cameras.Xenic import Xeneth as xeneth_camera
from JazLabs.hardware.Cameras.Xenic import xeneth_ctypes


class FakeXenethLibrary:
    instances = []

    def __init__(self, dll_path=None):
        self.dll_path = dll_path
        self.closed = False
        self.capturing = False
        self.capture_events = []
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
            "TriggerOutEnable": 0,
            "TriggerInTiming": 0,
        }
        self.string_properties = {
            "LowGain": "False",
            "Fan": "False",
        }
        self.instances.append(self)

    def enumerate_devices(self):
        return [
            {
                "name": "Xeva-1.7-320",
                "transport": "USB",
                "url": "cam://0",
                "address": "USB0",
                "serial": 8755,
                "pid": 0xF027,
                "state": xeneth_camera.XDS_AVAILABLE,
            },
            {
                "name": "Xeva-1.7-320",
                "transport": "USB",
                "url": "cam://1",
                "address": "USB1",
                "serial": 5920,
                "pid": 0xF027,
                "state": xeneth_camera.XDS_AVAILABLE,
            },
        ]

    def open_camera(self, camera_name):
        self.camera_name = camera_name
        self.long_properties["_CAM_SER"] = {
            "cam://0": 8755,
            "cam://1": 5920,
        }[camera_name]
        self.long_properties["_CAM_PID"] = 0xF027
        return 17

    def close_camera(self, handle):
        assert handle == 17
        self.closed = True

    def start_capture(self, handle):
        assert handle == 17
        self.capturing = True
        self.capture_events.append("start")

    def stop_capture(self, handle):
        assert handle == 17
        self.capturing = False
        self.capture_events.append("stop")

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

    def drain_frames(self, handle, max_frames=64):
        self.drained_frames = True
        return 0

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
    camera, library = make_camera(monkeypatch, CameraSerialNumber="5920")

    frame = camera.GetFrame()

    assert camera.CameraType == "Xeneth"
    assert camera.GetSerialNumber() == "5920"
    assert camera.CameraName == "cam://1"
    assert library.camera_name == "cam://1"
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
    camera, library = make_camera(monkeypatch, CameraSerialNumber=8755)

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
    assert library.long_properties["TriggerInEnable"] == 0
    assert library.long_properties["TriggerOutEnable"] == 0
    assert library.long_properties["TriggerInMode"] == 1
    assert library.long_properties["TriggerInTiming"] == 0
    assert library.capture_events[-2:] == ["stop", "start"]
    assert camera.FireSoftwareTrigger() == 0
    assert library.long_properties["SoftwareTrigger"] == 1
    assert library.drained_frames is True

    camera.shutdown()


def test_camera_rejects_a_serial_number_that_was_not_discovered(monkeypatch):
    FakeXenethLibrary.instances.clear()
    monkeypatch.setattr(xeneth_camera, "XenethLibrary", FakeXenethLibrary)

    with pytest.raises(ValueError, match="8755, 5920"):
        xeneth_camera.CameraObject(CameraSerialNumber="1234")


def test_camera_accepts_a_hexadecimal_serial_number(monkeypatch):
    camera, library = make_camera(
        monkeypatch,
        CameraSerialNumber=hex(8755),
    )

    assert camera.GetSerialNumber() == "8755"
    assert library.camera_name == "cam://0"

    camera.shutdown()


def test_camera_lists_available_devices_when_serial_is_omitted(
    monkeypatch,
    capsys,
):
    FakeXenethLibrary.instances.clear()
    monkeypatch.setattr(xeneth_camera, "XenethLibrary", FakeXenethLibrary)

    with pytest.raises(ValueError, match="choose one"):
        xeneth_camera.CameraObject()

    output = capsys.readouterr().out
    assert "Available Xeneth cameras:" in output
    assert "Xeva-1.7-320 | serial 8755 | cam://0 | available" in output
    assert "Xeva-1.7-320 | serial 5920 | cam://1 | available" in output


def test_device_information_layout_matches_xcamera_header():
    assert xeneth_ctypes.XDeviceInformation._pack_ == 1
    assert ctypes.sizeof(xeneth_ctypes.XDeviceInformation) == 464


def test_ctypes_wrapper_discovers_devices_using_the_sdk_cache():
    calls = []

    class FakeEnumerateDevices:
        def __call__(self, device_array, device_count_pointer, flags):
            device_count = ctypes.cast(
                device_count_pointer,
                ctypes.POINTER(ctypes.c_uint),
            )
            calls.append(int(flags))

            if not device_array:
                device_count.contents.value = 1
                return xeneth_ctypes.I_OK

            assert device_array[0].size == 464
            device_array[0].name = b"Xeva-1.7-320"
            device_array[0].transport = b"USB"
            device_array[0].url = b"cam://3"
            device_array[0].address = b"USB3"
            device_array[0].serial = 8755
            device_array[0].pid = 0xF027
            device_array[0].state = xeneth_ctypes.XDS_AVAILABLE
            device_count.contents.value = 1
            return xeneth_ctypes.I_OK

    library = xeneth_ctypes.XenethLibrary.__new__(
        xeneth_ctypes.XenethLibrary
    )
    library.lib = type(
        "FakeLibrary",
        (),
        {"XCD_EnumerateDevices": FakeEnumerateDevices()},
    )()

    devices = library.enumerate_devices()

    assert calls == [
        xeneth_ctypes.XEF_ENABLE_ALL,
        xeneth_ctypes.XEF_USE_CACHED,
    ]
    assert devices == [
        {
            "name": "Xeva-1.7-320",
            "transport": "USB",
            "url": "cam://3",
            "address": "USB3",
            "serial": 8755,
            "pid": 0xF027,
            "state": xeneth_ctypes.XDS_AVAILABLE,
        }
    ]
