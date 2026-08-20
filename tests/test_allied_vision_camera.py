import threading
import unittest

import numpy as np

from JazLabs.hardware.Cameras.AlliedVision.AlliedVisionCameraObj import CameraObject


class FakeEnumEntry:
    def __init__(self, name):
        self.name = name

    def as_tuple(self):
        return self.name, 0


class FakeFeature:
    def __init__(self, value, value_range=None, increment=1, writeable=True):
        self.value = value
        self.value_range = value_range
        self.increment = increment
        self.writeable = writeable
        self.run_count = 0

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def get_range(self):
        return self.value_range

    def get_increment(self):
        return self.increment

    def is_writeable(self):
        return self.writeable

    def run(self):
        self.run_count += 1

    def is_done(self):
        return True


class FakeFrame:
    def __init__(self, frame_id, image):
        self.frame_id = frame_id
        self.image = image

    def get_status(self):
        return FakeEnumEntry("Complete")

    def get_id(self):
        return self.frame_id

    def as_numpy_ndarray(self):
        return self.image


class FakeStreamingCamera:
    def __init__(self):
        self.handler = None
        self.start_count = 0
        self.stop_count = 0
        self.start_buffer_counts = []
        self.queued_frames = []

    def start_streaming(self, handler, buffer_count):
        self.handler = handler
        self.start_count += 1
        self.start_buffer_counts.append(buffer_count)

    def stop_streaming(self):
        self.handler = None
        self.stop_count += 1

    def is_streaming(self):
        return self.handler is not None

    def queue_frame(self, frame):
        self.queued_frames.append(frame)


class FakeTriggerSelectorFeature:
    def __init__(self, camera, selector_names):
        self.camera = camera
        self.selector_names = selector_names

    def get_available_entries(self):
        return tuple(FakeEnumEntry(name) for name in self.selector_names)

    def set(self, selector_name):
        self.camera.selected_trigger = selector_name


class FakeTriggerModeFeature:
    def __init__(self, camera):
        self.camera = camera

    def get(self):
        return FakeEnumEntry(self.camera.trigger_modes[self.camera.selected_trigger])

    def is_writeable(self):
        writeable_by_selector = getattr(self.camera, "trigger_writeable", {})
        return writeable_by_selector.get(self.camera.selected_trigger, True)

    def set(self, mode):
        if not self.is_writeable():
            raise RuntimeError("TriggerMode is read-only")
        self.camera.trigger_modes[self.camera.selected_trigger] = mode


class FakeStreamingLockedTriggerMode(FakeFeature):
    def __init__(self, camera, value):
        super().__init__(value=value)
        self.camera = camera

    def is_writeable(self):
        exposure_is_timed = self.camera.ExposureMode.get() == "Timed"
        activation_is_rising_edge = self.camera.TriggerActivation.get() == "RisingEdge"
        fixed_frame_rate_is_disabled = not self.camera.AcquisitionFrameRateEnable.get()
        return (
            not self.camera.is_streaming()
            and exposure_is_timed
            and activation_is_rising_edge
            and fixed_frame_rate_is_disabled
        )

    def set(self, value):
        if not self.is_writeable():
            raise RuntimeError("TriggerMode is read-only while streaming")
        self.value = value


class FakeDynamicROIFeature:
    def __init__(self, camera, name):
        self.camera = camera
        self.name = name

    def get(self):
        return self.camera.roi_values[self.name]

    def set(self, value):
        self.camera.roi_values[self.name] = int(value)

    def get_increment(self):
        return 2

    def get_range(self):
        if self.name == "Width":
            return 2, self.camera.sensor_width - self.camera.roi_values["OffsetX"]
        if self.name == "Height":
            return 2, self.camera.sensor_height - self.camera.roi_values["OffsetY"]
        if self.name == "OffsetX":
            return 0, self.camera.sensor_width - self.camera.roi_values["Width"]
        return 0, self.camera.sensor_height - self.camera.roi_values["Height"]


def make_camera_object():
    camera_object = object.__new__(CameraObject)
    camera_object._closed = False
    camera_object._capturing = False
    camera_object._stream_buffer_count = 5
    camera_object._frame_condition = threading.Condition()
    camera_object._latest_frame = None
    camera_object._frame_error = None
    camera_object._frame_sequence = 0
    camera_object._last_delivered_sequence = 0
    camera_object.frame_id = None
    camera_object.grab_timeout_ms = 100
    camera_object.verbose = False
    camera_object.VmbFeatureError = RuntimeError
    camera_object._frame_rate_enable_before_software_trigger = None
    return camera_object


class AlliedVisionCameraTests(unittest.TestCase):
    def test_limits_use_vmbpy_get_range(self):
        camera_object = make_camera_object()
        camera_object.camera = type("FeatureCamera", (), {})()
        camera_object.camera.ExposureTime = FakeFeature(
            value=500.0,
            value_range=(10.0, 20000.0),
            increment=1.0,
        )

        self.assertEqual(
            camera_object._limits("ExposureTime"),
            (10.0, 20000.0, 1.0),
        )

    def test_trigger_mode_preserves_software_source(self):
        camera_object = make_camera_object()
        camera_object.camera = type("FeatureCamera", (), {})()
        camera_object.camera.TriggerMode = FakeFeature(FakeEnumEntry("On"))
        camera_object.camera.TriggerSelector = FakeFeature(FakeEnumEntry("FrameStart"))
        camera_object.camera.TriggerSource = FakeFeature(FakeEnumEntry("Software"))
        camera_object.camera.AcquisitionMode = FakeFeature(FakeEnumEntry("Continuous"))

        self.assertEqual(camera_object.GetTriggerMode(), ("On", "Software"))

    def test_continuous_setup_disables_every_trigger_selector(self):
        camera_object = make_camera_object()
        fake_camera = type("TriggerCamera", (), {})()
        fake_camera.selected_trigger = "ExposureStart"
        fake_camera.trigger_modes = {
            "FrameStart": "On",
            "ExposureStart": "On",
        }
        fake_camera.TriggerSelector = FakeTriggerSelectorFeature(
            fake_camera,
            ("FrameStart", "ExposureStart"),
        )
        fake_camera.TriggerMode = FakeTriggerModeFeature(fake_camera)
        camera_object.camera = fake_camera

        disabled_selectors = camera_object._disable_all_trigger_modes()

        self.assertEqual(disabled_selectors, ("FrameStart", "ExposureStart"))
        self.assertEqual(
            fake_camera.trigger_modes,
            {"FrameStart": "Off", "ExposureStart": "Off"},
        )
        self.assertEqual(fake_camera.selected_trigger, "FrameStart")

    def test_continuous_setup_does_not_write_read_only_trigger_mode(self):
        camera_object = make_camera_object()
        fake_camera = type("TriggerCamera", (), {})()
        fake_camera.selected_trigger = "ExposureStart"
        fake_camera.trigger_modes = {
            "FrameStart": "On",
            "ExposureStart": "Off",
        }
        fake_camera.trigger_writeable = {
            "FrameStart": True,
            "ExposureStart": False,
        }
        fake_camera.TriggerSelector = FakeTriggerSelectorFeature(
            fake_camera,
            ("FrameStart", "ExposureStart"),
        )
        fake_camera.TriggerMode = FakeTriggerModeFeature(fake_camera)
        camera_object.camera = fake_camera

        disabled_selectors = camera_object._disable_all_trigger_modes()

        self.assertEqual(disabled_selectors, ("FrameStart",))
        self.assertEqual(
            fake_camera.trigger_modes,
            {"FrameStart": "Off", "ExposureStart": "Off"},
        )

    def test_stream_callback_delivers_a_fresh_copied_frame(self):
        camera_object = make_camera_object()
        camera_object.camera = FakeStreamingCamera()
        source_image = np.arange(6, dtype=np.uint16).reshape(2, 3)

        camera_object.StartAcquisition()
        frame = FakeFrame(17, source_image)
        camera_object.camera.handler(camera_object.camera, None, frame)
        returned_image = camera_object.GetFrame()
        source_image[:] = 0

        np.testing.assert_array_equal(
            returned_image,
            np.arange(6, dtype=np.uint16).reshape(2, 3),
        )
        self.assertEqual(camera_object.GetFrameID(), 17)
        self.assertEqual(camera_object.camera.queued_frames, [frame])
        self.assertEqual(camera_object.camera.start_count, 1)

        camera_object.StopAcquisition()
        self.assertEqual(camera_object.camera.stop_count, 1)

    def test_stream_buffer_size_restarts_acquisition_with_new_count(self):
        camera_object = make_camera_object()
        camera_object.camera = FakeStreamingCamera()

        camera_object.StartAcquisition()
        result = camera_object.SetBufferSizeInNumberOfFrames(9)

        self.assertEqual(result, 9)
        self.assertEqual(camera_object.camera.start_buffer_counts, [5, 9])
        self.assertEqual(camera_object.camera.stop_count, 1)
        camera_object.StopAcquisition()

    def test_stop_acquisition_uses_vmbpy_stream_state_when_flag_is_stale(self):
        camera_object = make_camera_object()
        camera_object.camera = FakeStreamingCamera()
        camera_object.camera.handler = camera_object._frame_handler
        camera_object._capturing = False

        camera_object.StopAcquisition()

        self.assertFalse(camera_object.camera.is_streaming())
        self.assertEqual(camera_object.camera.stop_count, 1)

    def test_software_trigger_stops_real_stream_before_enabling_trigger_mode(self):
        camera_object = make_camera_object()
        fake_camera = FakeStreamingCamera()
        fake_camera.handler = camera_object._frame_handler
        fake_camera.TriggerSelector = FakeFeature(FakeEnumEntry("FrameStart"))
        fake_camera.TriggerMode = FakeStreamingLockedTriggerMode(
            fake_camera,
            FakeEnumEntry("Off"),
        )
        fake_camera.TriggerSource = FakeFeature(FakeEnumEntry("Freerun"))
        fake_camera.AcquisitionMode = FakeFeature(FakeEnumEntry("Continuous"))
        fake_camera.AcquisitionFrameRateEnable = FakeFeature(True)
        fake_camera.ExposureMode = FakeFeature(FakeEnumEntry("TriggerWidth"))
        fake_camera.TriggerActivation = FakeFeature(FakeEnumEntry("FallingEdge"))
        fake_camera.TriggerSoftware = FakeFeature(value=None, writeable=True)
        camera_object.camera = fake_camera
        camera_object._capturing = False

        result = camera_object.SetSoftwareTriggerMode()

        self.assertEqual(result, ("On", "Software"))
        self.assertEqual(fake_camera.stop_count, 1)
        self.assertEqual(fake_camera.start_count, 1)
        self.assertTrue(fake_camera.is_streaming())
        self.assertFalse(fake_camera.AcquisitionFrameRateEnable.get())
        self.assertEqual(fake_camera.ExposureMode.get(), "Timed")
        self.assertEqual(fake_camera.TriggerActivation.get(), "RisingEdge")

        continuous_result = camera_object.SetContinuousMode()

        self.assertEqual(continuous_result, ("Off", "FreeRun"))
        self.assertTrue(fake_camera.AcquisitionFrameRateEnable.get())

    def test_gige_packet_size_adjustment_matches_vmbpy_example(self):
        camera_object = make_camera_object()
        packet_size_command = FakeFeature(value=None)
        stream = type("FakeStream", (), {})()
        stream.GVSPAdjustPacketSize = packet_size_command
        camera_object.camera = type("TransportCamera", (), {})()
        camera_object.camera.get_streams = lambda: (stream,)

        camera_object._configure_stream_transport()

        self.assertEqual(packet_size_command.run_count, 1)

    def test_full_sensor_roi_queries_size_after_resetting_offsets(self):
        camera_object = make_camera_object()
        fake_camera = type("ROICamera", (), {})()
        fake_camera.sensor_width = 100
        fake_camera.sensor_height = 80
        fake_camera.roi_values = {
            "OffsetX": 20,
            "OffsetY": 10,
            "Width": 80,
            "Height": 70,
        }
        for feature_name in ("OffsetX", "OffsetY", "Width", "Height"):
            setattr(
                fake_camera,
                feature_name,
                FakeDynamicROIFeature(fake_camera, feature_name),
            )
        camera_object.camera = fake_camera

        roi = camera_object.SetROI(enable=False)

        self.assertEqual(roi, (0, 0, 100, 80))

    def test_software_trigger_runs_when_stream_is_armed(self):
        camera_object = make_camera_object()
        camera_object._capturing = True
        camera_object.trigger_mode = "On"
        camera_object.trigger_source = "Software"
        camera_object.camera = FakeStreamingCamera()
        camera_object.camera.handler = camera_object._frame_handler
        camera_object.camera.TriggerSoftware = FakeFeature(
            value=None,
            writeable=True,
        )

        result = camera_object.FireSoftwareTrigger()

        self.assertEqual(result, 0)
        self.assertEqual(camera_object.camera.TriggerSoftware.run_count, 1)


if __name__ == "__main__":
    unittest.main()
