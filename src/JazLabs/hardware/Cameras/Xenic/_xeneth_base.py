import atexit
import ctypes
import time
import weakref

import numpy as np

from .xeneth_ctypes import (
    E_NOT_FOUND,
    E_NOT_SUPPORTED,
    FT_16_BPP_GRAY,
    FT_32_BPP_GRAY,
    FT_8_BPP_GRAY,
    FT_NATIVE,
    I_OK,
    XGF_BLOCKING,
    XGF_NO_CONVERSION,
    XLC_START_SOFTWARE_CORRECTION,
    XenethError,
    XenethLibrary,
)


def snap_to_value(value, step, mode="nearest", minimum=0):
    value = int(value)
    step = int(step)
    minimum = int(minimum)

    if step <= 0:
        return value

    rel = value - minimum
    if mode == "nearest":
        snapped = minimum + round(rel / step) * step
    elif mode == "floor":
        snapped = minimum + (rel // step) * step
    elif mode == "ceil":
        snapped = minimum + ((rel + step - 1) // step) * step
    else:
        raise ValueError("mode must be 'nearest', 'floor', or 'ceil'")

    return int(max(snapped, minimum))


def _shutdown_camera_ref(camera_ref):
    camera = camera_ref()
    if camera is not None:
        camera.shutdown()


class XenethCameraBase:
    CAMERA_NAME = "cam://0"
    MODEL_NAME = "Xenics"
    PIXEL_SIZE = 30e-6
    EXPOSURE_PROPERTIES = ("IntegrationTime", "ExposureTime", "ExposureTimeAbs")
    GAIN_PROPERTIES = ("LowGain", "Gain", "AnalogGain")
    FPS_PROPERTIES = ("FrameRate", "AcquisitionFrameRate")
    ROI_STYLE = "woi"
    TRIGGER_STYLE = "trigger_in"
    SOFTWARE_TRIGGER_MODE = 5
    HARDWARE_TRIGGER_MODE = 1

    def __init__(self, CameraName=None, CameraIdx=0, CalibrationFile=None, PixelSize=None, dll_path=None, verbose=False):
        self.CameraIdx = int(CameraIdx)
        self.CameraName = CameraName or self.CAMERA_NAME
        if self.CameraName == "cam://0" and self.CameraIdx != 0:
            self.CameraName = f"cam://{self.CameraIdx}"
        self.CalibrationFile = CalibrationFile
        self.PixelSize = self.PIXEL_SIZE if PixelSize is None else PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.grab_timeout_ms = None

        self.xeneth = XenethLibrary(dll_path=dll_path)
        self.dll = self.xeneth.lib
        self.handle = self.dll.XC_OpenCamera(self.CameraName.encode("utf-8"), None, None)
        if not self.handle or not self.dll.XC_IsInitialised(self.handle):
            self.shutdown()
            raise RuntimeError(f"Could not initialise {self.MODEL_NAME} camera at {self.CameraName}")

        self._load_optional_files()

        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.trigger_selector = "FrameStart"
        self.acquisition_mode = "Continuous"
        self.trigger_polarity = 1

        self.offset_x = 0
        self.offset_y = 0
        self.width = int(self.dll.XC_GetWidth(self.handle))
        self.height = int(self.dll.XC_GetHeight(self.handle))
        self.Nx = self.width
        self.Ny = self.height

        self.ExposureTime = None
        self.ExposureTimeMin = None
        self.ExposureTimeMax = None
        self.FPSMin = None
        self.FPSMax = None
        self.fps = None
        self.gain = None
        self.pixel_format = None
        self.pixel_format_fc2 = None
        self.frame_id = None

        self.GetROI()
        self.GetExposureTime()
        self.GetGain()
        self.GetFPS()
        self.GetPixelFormat()
        self.GetMaxMinFPS_ExposureTime()
        self.SetContinuousMode()
        self.StartAcquisition()

        atexit.register(_shutdown_camera_ref, weakref.ref(self))

    def __del__(self):
        self.shutdown()

    def shutdown(self):
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            self.StopAcquisition()
        finally:
            if getattr(self, "handle", 0):
                try:
                    self.dll.XC_CloseCamera(self.handle)
                except Exception:
                    pass
                self.handle = 0

    def _check(self, err_code, message, allow_unsupported=False):
        if err_code == I_OK:
            return
        if allow_unsupported and err_code in (E_NOT_FOUND, E_NOT_SUPPORTED):
            raise KeyError(message)
        raise XenethError(err_code, message, self.xeneth.error_to_string(err_code))

    def _load_optional_files(self):
        if not self.CalibrationFile:
            return
        path = os.fspath(self.CalibrationFile)
        lower = path.lower()
        if lower.endswith(".xcf"):
            self._check(self.dll.XC_LoadSettings(self.handle, path.encode("utf-8")), f"Load settings {path}")
        else:
            self._check(
                self.dll.XC_LoadCalibration(self.handle, path.encode("utf-8"), XLC_START_SOFTWARE_CORRECTION),
                f"Load calibration {path}",
            )
            try:
                self.dll.XC_FLT_Queue(self.handle, b"SoftwareCorrection", b"0")
            except Exception:
                pass

    def _try_get_float(self, names):
        for name in names:
            value = ctypes.c_double()
            err = self.dll.XC_GetPropertyValueF(self.handle, name.encode("utf-8"), ctypes.byref(value))
            if err == I_OK:
                return name, float(value.value)
        return None, None

    def _try_set_float(self, names, value, unit=""):
        last_error = None
        for name in names:
            err = self.dll.XC_SetPropertyValueF(self.handle, name.encode("utf-8"), float(value), unit.encode("utf-8"))
            if err == I_OK:
                return self._try_get_float((name,))[1]
            last_error = err
        raise XenethError(last_error, f"SetPropertyValueF({names})", self.xeneth.error_to_string(last_error))

    def _try_get_long(self, names):
        for name in names:
            value = ctypes.c_long()
            err = self.dll.XC_GetPropertyValueL(self.handle, name.encode("utf-8"), ctypes.byref(value))
            if err == I_OK:
                return name, int(value.value)
        return None, None

    def _try_set_long(self, names, value, unit=""):
        last_error = None
        for name in names:
            err = self.dll.XC_SetPropertyValueL(self.handle, name.encode("utf-8"), int(value), unit.encode("utf-8"))
            if err == I_OK:
                return self._try_get_long((name,))[1]
            last_error = err
        raise XenethError(last_error, f"SetPropertyValueL({names})", self.xeneth.error_to_string(last_error))

    def _set_long_if_supported(self, name, value):
        err = self.dll.XC_SetPropertyValueL(self.handle, name.encode("utf-8"), int(value), b"")
        return err == I_OK

    def _get_long_if_supported(self, name):
        value = ctypes.c_long()
        err = self.dll.XC_GetPropertyValueL(self.handle, name.encode("utf-8"), ctypes.byref(value))
        if err == I_OK:
            return int(value.value)
        return None

    def StartAcquisition(self):
        if not self._capturing:
            self._check(self.dll.XC_StartCapture(self.handle), "XC_StartCapture")
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            try:
                self.dll.XC_StopCapture(self.handle)
            finally:
                self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        self.frame_id = None

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        self.frame_id = None
        return 0

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError("Xeneth stream buffer sizing is not implemented in this simple wrapper.")

    def GetBufferSizeInNumberOfFrames(self):
        return None

    def GetNumberOfFramesInBuffer(self):
        return None

    def GetGrabTimeout(self):
        return self.grab_timeout_ms

    def SetGrabTimeout(self, timeout_ms):
        self.grab_timeout_ms = None if timeout_ms is None else int(timeout_ms)
        return self.GetGrabTimeout()

    def IsSoftwareTriggerReady(self):
        return True

    def WaitForSoftwareTriggerReady(self, timeout_ms=1000, poll_interval_s=0.001):
        return True

    def GetTriggerMode(self):
        if self.TRIGGER_STYLE == "trigger_mode":
            mode = self._get_long_if_supported("TriggerMode")
            if mode in (self.SOFTWARE_TRIGGER_MODE,):
                self.trigger_mode = "On"
                self.trigger_source = "Software"
            elif mode not in (None, 0):
                self.trigger_mode = "On"
                self.trigger_source = "line 0"
            else:
                self.trigger_mode = "Off"
                self.trigger_source = "FreeRun"
            return self.trigger_mode, self.trigger_source

        mode = self._get_long_if_supported("TriggerInMode")
        if mode == 1:
            self.trigger_mode = "On"
            self.trigger_source = "Software" if self._get_long_if_supported("TriggerInEnable") == 0 else "line 0"
        else:
            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        if self.TRIGGER_STYLE == "trigger_mode":
            self._set_long_if_supported("TriggerMode", 0)
            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
            self.acquisition_mode = "Continuous"
            return self.GetTriggerMode()

        self._set_long_if_supported("TriggerInEnable", 0)
        self._set_long_if_supported("TriggerInMode", 0)
        self._set_long_if_supported("TriggerOutEnable", 0)
        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.acquisition_mode = "Continuous"
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        if self.TRIGGER_STYLE == "trigger_mode":
            self._set_long_if_supported("TriggerMode", self.SOFTWARE_TRIGGER_MODE)
            self.trigger_mode = "On"
            self.trigger_source = "Software"
            return self.GetTriggerMode()

        self._set_long_if_supported("TriggerInEnable", 0)
        self._set_long_if_supported("TriggerOutEnable", 0)
        self._set_long_if_supported("TriggerInMode", 1)
        self._set_long_if_supported("TriggerInTiming", 0)
        self.trigger_mode = "On"
        self.trigger_source = "Software"
        return self.GetTriggerMode()

    def FireSoftwareTrigger(self, wait_ready=True, ready_timeout_ms=1000, drain_stale_frames=True):
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            self.GetTriggerMode()
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            raise RuntimeError("Camera is not in software trigger mode")
        if self.TRIGGER_STYLE == "trigger_mode":
            self._set_long_if_supported("TriggerMode", 0)
            self._set_long_if_supported("TriggerMode", self.SOFTWARE_TRIGGER_MODE)
        else:
            self._try_set_long(("SoftwareTrigger",), 1)
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        if self.TRIGGER_STYLE == "trigger_mode":
            self._set_long_if_supported("TriggerMode", self.HARDWARE_TRIGGER_MODE)
            self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
            return self.GetTriggerMode()

        self._set_long_if_supported("TriggerOutEnable", 0)
        self._set_long_if_supported("TriggerDirection", 0)
        self._set_long_if_supported("TriggerInMode", 1)
        self._set_long_if_supported("TriggerInSensitivity", 1)
        self._set_long_if_supported("TriggerInPolarity", 1 if RiseEdgeOrFallEdge == 1 else 0)
        self._set_long_if_supported("TriggerInDelay", 0)
        self._set_long_if_supported("TriggerInSkip", 0)
        self._set_long_if_supported("TriggerInTiming", 0)
        self._set_long_if_supported("TriggerInEnable", 1)
        self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
        return self.GetTriggerMode()

    def SetExposureTime(self, exposure_time):
        self.ExposureTime = self._try_set_float(self.EXPOSURE_PROPERTIES, exposure_time)
        return self.ExposureTime

    def GetExposureTime(self):
        _, self.ExposureTime = self._try_get_float(self.EXPOSURE_PROPERTIES)
        return self.ExposureTime

    def SetGain(self, gain):
        try:
            self.gain = self._try_set_float(self.GAIN_PROPERTIES, gain)
        except XenethError:
            self.gain = self._try_set_long(self.GAIN_PROPERTIES, gain)
        return self.gain

    def GetGain(self):
        _, self.gain = self._try_get_float(self.GAIN_PROPERTIES)
        if self.gain is None:
            _, self.gain = self._try_get_long(self.GAIN_PROPERTIES)
        return self.gain

    def SetFPS(self, fps):
        self.fps = self._try_set_float(self.FPS_PROPERTIES, fps)
        return self.fps

    def GetFPS(self):
        self.fps = float(self.dll.XC_GetFrameRate(self.handle))
        if self.fps <= 0:
            _, self.fps = self._try_get_float(self.FPS_PROPERTIES)
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin = None
        self.ExposureTimeMax = None
        for name in self.EXPOSURE_PROPERTIES:
            low = ctypes.c_double()
            high = ctypes.c_double()
            err = self.dll.XC_GetPropertyRangeF(self.handle, name.encode("utf-8"), ctypes.byref(low), ctypes.byref(high))
            if err == I_OK:
                self.ExposureTimeMin = float(low.value)
                self.ExposureTimeMax = float(high.value)
                break

        self.FPSMin = None
        self.FPSMax = None
        for name in self.FPS_PROPERTIES:
            low = ctypes.c_double()
            high = ctypes.c_double()
            err = self.dll.XC_GetPropertyRangeF(self.handle, name.encode("utf-8"), ctypes.byref(low), ctypes.byref(high))
            if err == I_OK:
                self.FPSMin = float(low.value)
                self.FPSMax = float(high.value)
                break
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def SetPixelFormat(self, pixel_format):
        key = str(pixel_format).strip().lower()
        if key in ("mono8", "8", "8bit"):
            self.pixel_format_fc2 = FT_8_BPP_GRAY
            self.pixel_format = "mono8"
        elif key in ("mono16", "16", "16bit"):
            self.pixel_format_fc2 = FT_16_BPP_GRAY
            self.pixel_format = "mono16"
        elif key in ("mono32", "float32", "32", "32bit"):
            self.pixel_format_fc2 = FT_32_BPP_GRAY
            self.pixel_format = "mono32"
        elif key == "native":
            self.pixel_format_fc2 = FT_NATIVE
            self.pixel_format = self.GetPixelFormat()
        else:
            raise ValueError("pixel_format must be one of: mono8, mono16, mono32, native")
        return self.pixel_format

    def GetPixelFormat(self):
        bit_size = int(self.dll.XC_GetBitSize(self.handle))
        frame_type = int(self.dll.XC_GetFrameType(self.handle))
        self.pixel_format_fc2 = frame_type
        if bit_size <= 8 or frame_type == FT_8_BPP_GRAY:
            self.pixel_format = "mono8"
        elif bit_size <= 16 or frame_type == FT_16_BPP_GRAY:
            self.pixel_format = "mono16"
        elif frame_type == FT_32_BPP_GRAY:
            self.pixel_format = "mono32"
        else:
            self.pixel_format = f"xeneth:{frame_type}:{bit_size}"
        return self.pixel_format

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode="nearest"):
        sensor_width = int(self.dll.XC_GetWidth(self.handle))
        sensor_height = int(self.dll.XC_GetHeight(self.handle))

        if not enable:
            offset_x = 0
            offset_y = 0
            width = sensor_width
            height = sensor_height
        else:
            offset_x = self.offset_x if offset_x is None else offset_x
            offset_y = self.offset_y if offset_y is None else offset_y
            width = self.width if width is None else width
            height = self.height if height is None else height

        if snap_values:
            offset_x = snap_to_value(offset_x, 1, mode, minimum=0)
            offset_y = snap_to_value(offset_y, 1, mode, minimum=0)
            width = snap_to_value(width, 1, mode, minimum=1)
            height = snap_to_value(height, 1, mode, minimum=1)

        width = min(int(width), sensor_width)
        height = min(int(height), sensor_height)
        offset_x = min(max(int(offset_x), 0), sensor_width - width)
        offset_y = min(max(int(offset_y), 0), sensor_height - height)

        sx = offset_x
        sy = offset_y
        ex = offset_x + width - 1
        ey = offset_y + height - 1

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            if self.ROI_STYLE == "width_height":
                self._try_set_long(("Width",), width)
                self._try_set_long(("Height",), height)
                self._set_long_if_supported("OffsetX", offset_x)
                self._set_long_if_supported("OffsetY", offset_y)
            else:
                supported = self._get_long_if_supported("CapWoiCount")
                if supported is None:
                    raise NotImplementedError("This Xenics camera does not report WOI support")
                self._try_set_long(("WoiSX(0)",), sx)
                self._try_set_long(("WoiEX(0)",), ex)
                self._try_set_long(("WoiSY(0)",), sy)
                self._try_set_long(("WoiEY(0)",), ey)
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetROI()

    def GetROI(self):
        if self.ROI_STYLE == "width_height":
            width = self._get_long_if_supported("Width")
            height = self._get_long_if_supported("Height")
            offset_x = self._get_long_if_supported("OffsetX")
            offset_y = self._get_long_if_supported("OffsetY")

            self.width = int(width if width is not None else self.dll.XC_GetWidth(self.handle))
            self.height = int(height if height is not None else self.dll.XC_GetHeight(self.handle))
            self.offset_x = int(offset_x or 0)
            self.offset_y = int(offset_y or 0)
            self.Nx = self.width
            self.Ny = self.height
            return self.offset_x, self.offset_y, self.width, self.height

        sx = self._get_long_if_supported("WoiSX(0)")
        ex = self._get_long_if_supported("WoiEX(0)")
        sy = self._get_long_if_supported("WoiSY(0)")
        ey = self._get_long_if_supported("WoiEY(0)")
        if None not in (sx, ex, sy, ey):
            self.offset_x = int(sx)
            self.offset_y = int(sy)
            self.width = int(ex - sx + 1)
            self.height = int(ey - sy + 1)
        else:
            self.width = int(self.dll.XC_GetWidth(self.handle))
            self.height = int(self.dll.XC_GetHeight(self.handle))
            self.offset_x = 0
            self.offset_y = 0
        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def GetFrameID(self):
        try:
            self.frame_id = int(self.dll.XC_GetFrameCount(self.handle))
        except Exception:
            pass
        return self.frame_id

    def _frame_dtype_and_type(self):
        if self.pixel_format_fc2 in (FT_8_BPP_GRAY, FT_16_BPP_GRAY, FT_32_BPP_GRAY):
            frame_type = self.pixel_format_fc2
        else:
            frame_type = FT_NATIVE

        frame_type_native = int(self.dll.XC_GetFrameType(self.handle))
        bit_size = int(self.dll.XC_GetBitSize(self.handle))
        effective_type = frame_type_native if frame_type == FT_NATIVE else frame_type

        if effective_type == FT_8_BPP_GRAY or bit_size <= 8:
            return np.uint8, frame_type
        if effective_type == FT_32_BPP_GRAY:
            return np.uint32, frame_type
        return np.uint16, frame_type

    def GetFrame(self, timeout_ms=None):
        if not self._capturing:
            self.StartAcquisition()

        self.GetROI()
        frame_size = int(self.dll.XC_GetFrameSize(self.handle))
        dtype, frame_type = self._frame_dtype_and_type()
        frame = np.zeros((self.height, self.width), dtype=dtype)

        flags = XGF_BLOCKING | XGF_NO_CONVERSION
        err = self.dll.XC_GetFrame(
            self.handle,
            frame_type,
            flags,
            frame.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_uint(frame_size),
        )
        self._check(err, "XC_GetFrame")
        self.GetFrameID()
        return frame.copy()
