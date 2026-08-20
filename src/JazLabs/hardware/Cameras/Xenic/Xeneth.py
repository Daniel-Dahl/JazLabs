"""JazLabs camera object for a camera controlled by Xeneth."""

import atexit
import os
import time
import weakref

import numpy as np

from .xeneth_ctypes import (
    FT_16_BPP_GRAY,
    FT_32_BPP_GRAY,
    FT_8_BPP_GRAY,
    XenethLibrary,
)


def _shutdown_camera(camera_reference):
    camera = camera_reference()
    if camera is not None:
        camera.shutdown()


class CameraObject:
    """A direct, single-camera wrapper with the common JazLabs camera API."""

    def __init__(
        self,
        CameraName="cam://0",
        CalibrationFile=None,
        PixelSize=30e-6,
        dll_path=None,
        verbose=False,
    ):
        self.CameraName = str(CameraName)
        self.CameraSerialNumber = self.CameraName
        self.CameraType = "Xeneth"
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.xeneth = XenethLibrary(dll_path=dll_path)
        self.handle = self.xeneth.open_camera(self.CameraName)

        try:
            self._load_calibration_file()

            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
            self.trigger_selector = "FrameStart"
            self.acquisition_mode = "Continuous"
            self.trigger_polarity = 1

            self.offset_x = 0
            self.offset_y = 0
            self.width = self.xeneth.get_width(self.handle)
            self.height = self.xeneth.get_height(self.handle)
            self.Nx = self.width
            self.Ny = self.height

            self.frame_id = None
            self.ExposureTime = self.GetExposureTime()
            self.ExposureTimeMin, self.ExposureTimeMax = (
                self.xeneth.get_property_range_float(
                    self.handle,
                    "IntegrationTime",
                )
            )
            self.fps = self.GetFPS()
            self.FPSMin = None
            self.FPSMax = None
            self.gain = self.GetGain()
            self.pixel_format = self.GetPixelFormat()

            self.SetContinuousMode()
            self.StartAcquisition()
        except Exception:
            self.shutdown()
            raise

        atexit.register(_shutdown_camera, weakref.ref(self))

    def __del__(self):
        self.shutdown()

    def _load_calibration_file(self):
        if self.CalibrationFile is None:
            return

        calibration_path = os.fspath(self.CalibrationFile)
        if calibration_path.lower().endswith(".xcf"):
            self.xeneth.load_settings(self.handle, calibration_path)
        else:
            self.xeneth.load_calibration(self.handle, calibration_path)

    def shutdown(self):
        if getattr(self, "_closed", True):
            return

        self._closed = True
        if getattr(self, "_capturing", False):
            try:
                self.xeneth.stop_capture(self.handle)
            except Exception:
                pass
            self._capturing = False

        if getattr(self, "handle", 0):
            try:
                self.xeneth.close_camera(self.handle)
            finally:
                self.handle = 0

    def GetSerialNumber(self):
        return self.CameraSerialNumber

    def StartAcquisition(self):
        if not self._capturing:
            self.xeneth.start_capture(self.handle)
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            self.xeneth.stop_capture(self.handle)
            self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        self.frame_id = None

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        self.ResetBuffer()
        return 0

    def GetFrameID(self):
        self.frame_id = self.xeneth.get_frame_count(self.handle)
        return self.frame_id

    def GetFrame(self, timeout_ms=None):
        if not self._capturing:
            self.StartAcquisition()

        self.GetROI()
        frame_byte_count = self.xeneth.get_frame_size(self.handle)
        frame_buffer = np.empty(frame_byte_count, dtype=np.uint8)
        self.xeneth.get_frame(self.handle, frame_buffer)

        if self.pixel_format == "mono8":
            frame_dtype = np.uint8
        elif self.pixel_format == "mono32":
            frame_dtype = np.uint32
        else:
            frame_dtype = np.uint16

        required_pixel_count = self.width * self.height
        frame_values = frame_buffer.view(frame_dtype)
        if frame_values.size < required_pixel_count:
            raise RuntimeError(
                "Xeneth returned a frame buffer smaller than the reported "
                f"image dimensions ({frame_values.size} values for "
                f"{self.width} x {self.height})"
            )

        self.GetFrameID()
        return frame_values[:required_pixel_count].reshape(
            self.height,
            self.width,
        ).copy()

    def GetExposureTime(self):
        self.ExposureTime = self.xeneth.get_property_float(
            self.handle,
            "IntegrationTime",
        )
        return self.ExposureTime

    def SetExposureTime(self, exposure_time):
        self.ExposureTime = self.xeneth.set_property_float(
            self.handle,
            "IntegrationTime",
            exposure_time,
            "us",
        )
        return self.ExposureTime

    def GetGain(self):
        gain_value = self.xeneth.get_property(self.handle, "LowGain")
        self.gain = int(gain_value.strip().casefold() in ("1", "true", "on"))
        return self.gain

    def SetGain(self, gain):
        gain = int(gain)
        if gain not in (0, 1):
            raise ValueError("Xeneth LowGain must be 0 or 1")

        self.xeneth.set_property(
            self.handle,
            "LowGain",
            "True" if gain else "False",
            "bool",
        )
        return self.GetGain()

    def GetFanState(self):
        fan_value = self.xeneth.get_property(self.handle, "Fan")
        return int(fan_value.strip().casefold() in ("1", "true", "on"))

    def SetFanState(self, fan_state):
        fan_state = int(fan_state)
        if fan_state not in (0, 1):
            raise ValueError("Xeneth fan state must be 0 or 1")

        self.xeneth.set_property(
            self.handle,
            "Fan",
            "True" if fan_state else "False",
            "bool",
        )
        return self.GetFanState()

    def GetFPS(self):
        self.fps = self.xeneth.get_frame_rate(self.handle)
        return self.fps

    def SetFPS(self, fps):
        self.fps = self.xeneth.set_property_float(
            self.handle,
            "FrameRate",
            fps,
            "Hz",
        )
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin, self.ExposureTimeMax = (
            self.xeneth.get_property_range_float(
                self.handle,
                "IntegrationTime",
            )
        )
        try:
            self.FPSMin, self.FPSMax = (
                self.xeneth.get_property_range_float(
                    self.handle,
                    "FrameRate",
                )
            )
        except Exception:
            self.FPSMin = None
            self.FPSMax = None
        return (
            self.ExposureTimeMin,
            self.ExposureTimeMax,
            self.FPSMin,
            self.FPSMax,
        )

    def GetPixelFormat(self):
        frame_type = self.xeneth.get_frame_type(self.handle)
        bit_size = self.xeneth.get_bit_size(self.handle)

        if frame_type == FT_8_BPP_GRAY or bit_size <= 8:
            self.pixel_format = "mono8"
        elif frame_type == FT_32_BPP_GRAY:
            self.pixel_format = "mono32"
        elif frame_type == FT_16_BPP_GRAY or bit_size <= 16:
            self.pixel_format = "mono16"
        else:
            raise RuntimeError(
                f"Unsupported Xeneth frame type {frame_type}, {bit_size} bits"
            )
        return self.pixel_format

    def GetROI(self):
        try:
            start_x = self.xeneth.get_property_long(self.handle, "WoiSX(0)")
            end_x = self.xeneth.get_property_long(self.handle, "WoiEX(0)")
            start_y = self.xeneth.get_property_long(self.handle, "WoiSY(0)")
            end_y = self.xeneth.get_property_long(self.handle, "WoiEY(0)")
        except Exception:
            self.offset_x = 0
            self.offset_y = 0
            self.width = self.xeneth.get_width(self.handle)
            self.height = self.xeneth.get_height(self.handle)
        else:
            self.offset_x = start_x
            self.offset_y = start_y
            self.width = end_x - start_x + 1
            self.height = end_y - start_y + 1

        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def SetROI(
        self,
        offset_x=None,
        offset_y=None,
        width=None,
        height=None,
        snap_values=True,
        enable=True,
        mode="nearest",
    ):
        sensor_width = self.xeneth.get_width(self.handle)
        sensor_height = self.xeneth.get_height(self.handle)

        if not enable:
            offset_x = 0
            offset_y = 0
            width = sensor_width
            height = sensor_height
        else:
            offset_x = self.offset_x if offset_x is None else int(offset_x)
            offset_y = self.offset_y if offset_y is None else int(offset_y)
            width = self.width if width is None else int(width)
            height = self.height if height is None else int(height)

        width = min(max(int(width), 1), sensor_width)
        height = min(max(int(height), 1), sensor_height)
        offset_x = min(max(int(offset_x), 0), sensor_width - width)
        offset_y = min(max(int(offset_y), 0), sensor_height - height)

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.xeneth.set_property_long(self.handle, "WoiSX(0)", offset_x)
            self.xeneth.set_property_long(
                self.handle,
                "WoiEX(0)",
                offset_x + width - 1,
            )
            self.xeneth.set_property_long(self.handle, "WoiSY(0)", offset_y)
            self.xeneth.set_property_long(
                self.handle,
                "WoiEY(0)",
                offset_y + height - 1,
            )
        finally:
            if was_capturing:
                self.StartAcquisition()
        return self.GetROI()

    def GetTriggerMode(self):
        trigger_enabled = self.xeneth.get_property_long(
            self.handle,
            "TriggerInEnable",
        )
        trigger_mode = self.xeneth.get_property_long(
            self.handle,
            "TriggerInMode",
        )

        if trigger_mode == 0:
            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
        elif trigger_enabled:
            self.trigger_mode = "On"
            self.trigger_source = "line 0"
        else:
            self.trigger_mode = "On"
            self.trigger_source = "Software"
        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        self.xeneth.set_property_long(self.handle, "TriggerInEnable", 0)
        self.xeneth.set_property_long(self.handle, "TriggerInMode", 0)
        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.acquisition_mode = "Continuous"
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        self.xeneth.set_property_long(self.handle, "TriggerInEnable", 0)
        self.xeneth.set_property_long(self.handle, "TriggerInMode", 1)
        self.trigger_mode = "On"
        self.trigger_source = "Software"
        return self.GetTriggerMode()

    def FireSoftwareTrigger(
        self,
        wait_ready=True,
        ready_timeout_ms=1000,
        drain_stale_frames=True,
    ):
        if self.GetTriggerMode() != ("On", "Software"):
            raise RuntimeError("Camera is not in software trigger mode")
        return self.xeneth.set_property_long(
            self.handle,
            "SoftwareTrigger",
            1,
        )

    def SetHardwareTriggerMode(self, RiseEdgeOrFallEdge=1, lineNumber=0):
        if RiseEdgeOrFallEdge not in (-1, 1):
            raise ValueError("RiseEdgeOrFallEdge must be 1 or -1")
        if int(lineNumber) != 0:
            raise ValueError("Xeneth exposes hardware trigger input line 0")

        trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else 0
        self.xeneth.set_property_long(
            self.handle,
            "TriggerInPolarity",
            trigger_polarity,
        )
        self.xeneth.set_property_long(self.handle, "TriggerInMode", 1)
        self.xeneth.set_property_long(self.handle, "TriggerInEnable", 1)
        self.trigger_polarity = RiseEdgeOrFallEdge
        return self.GetTriggerMode()


XenethCameraObject = CameraObject
