import atexit
import importlib
import os
import sys
import time
import weakref
from pathlib import Path

import numpy as np


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


def _load_nit_library(sdk_dir=None):
    """
    Load the NIT Python module matching the active Python version.

    The SDK ships version-tagged modules such as
    NITLibrary_x64_360_py310.pyd. Keep this lazy so importing this wrapper does
    not fail on machines without the camera SDK installed.
    """
    if sdk_dir is None:
        sdk_dir = Path(__file__).resolve().parent
    else:
        sdk_dir = Path(sdk_dir).resolve()

    python_tag = f"py{sys.version_info.major}{sys.version_info.minor}"
    candidates = sorted(sdk_dir.glob(f"NITLibrary_*_{python_tag}.pyd"))

    if not candidates:
        repo_sdk_dir = Path.cwd() / "NiTcamera"
        candidates = sorted(repo_sdk_dir.glob(f"NITLibrary_*_{python_tag}.pyd"))
        if candidates:
            sdk_dir = repo_sdk_dir

    if not candidates:
        raise ImportError(
            f"No NITLibrary module for Python {sys.version_info.major}.{sys.version_info.minor}. "
            f"Expected a file like NITLibrary_x64_360_{python_tag}.pyd in {sdk_dir}"
        )

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(str(sdk_dir))
    if str(sdk_dir) not in sys.path:
        sys.path.insert(0, str(sdk_dir))

    return importlib.import_module(candidates[0].stem)


class _FrameObserver:
    def __init__(self, nit_library):
        self.NITLibrary = nit_library
        self._observer = None
        self.frame = None
        self.frame_id = None

        class FrameObserver(nit_library.NITUserObserver):
            def __init__(inner_self, owner):
                nit_library.NITUserObserver.__init__(inner_self)
                inner_self.owner = owner

            def onNewFrame(inner_self, frame):
                inner_self.owner.frame = np.array(frame.data(), copy=True)
                inner_self.owner.frame_id = frame.id()

        self._observer = FrameObserver(self)

    @property
    def observer(self):
        return self._observer


class CameraObject:
    """
    Simple New Imaging Technologies camera object using the local NIT SDK.

    This intentionally avoids the older multiprocessing/display path. Frames are
    returned directly as NumPy arrays.
    """

    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=15e-6, sdk_dir=None, verbose=False):
        self.CameraIdx = int(CameraIdx)
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.grab_timeout_ms = 2000
        self._software_frame_ready = False

        self.NITLibrary = _load_nit_library(sdk_dir=sdk_dir)
        self.nm = self.NITLibrary.NITManager.getInstance()

        devices = self.nm.listDevices()
        print("NIT devices:", devices)

        if self.CameraIdx == 0:
            self.dev = self.nm.openOneDevice()
        else:
            self.dev = self.nm.openDevice(self.CameraIdx)

        if self.dev is None:
            self.shutdown()
            raise RuntimeError("No NIT camera detected")

        self.observer = _FrameObserver(self.NITLibrary)
        self.dev << self.observer.observer

        self.sensor_width = int(self.dev.sensorWidth())
        self.sensor_height = int(self.dev.sensorHeight())
        self.offset_x = 0
        self.offset_y = 0
        self.width = self.sensor_width
        self.height = self.sensor_height
        self.Nx = self.width
        self.Ny = self.height

        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.trigger_selector = "FrameStart"
        self.acquisition_mode = "Continuous"
        self.trigger_polarity = 1

        self.ExposureTime = None
        self.ExposureTimeMin = 0.0
        self.ExposureTimeMax = 1e9
        self.FPSMin = None
        self.FPSMax = None
        self.fps = None
        self.gain = None
        self.capture_mode = None
        self.pixel_format = None
        self.pixel_format_fc2 = None
        self.frame_id = None

        self._configure_defaults()
        self.GetROI()
        self.GetExposureTime()
        self.GetGain()
        self.GetFPS()
        self.GetPixelFormat()
        self.GetMaxMinFPS_ExposureTime()
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
            if getattr(self, "nm", None) is not None:
                time.sleep(0.05)
                try:
                    self.nm.reset()
                except Exception:
                    pass
                self.nm = None

    def _configure_defaults(self):
        if self.CalibrationFile:
            try:
                self.dev.setNucDirectory(self.CalibrationFile)
                self.dev.activateNuc(True)
            except Exception:
                if self.verbose:
                    print(f"Could not load NIT calibration/NUC path: {self.CalibrationFile}")

        try:
            self.dev.activateBpr(True)
        except Exception:
            pass

        try:
            if self.dev.connectorType() == self.NITLibrary.GIGE:
                self.dev.setParamValueOf("OutputType", "RAW")
        except Exception:
            pass

        try:
            self.dev.updateConfig()
        except Exception:
            pass

    def _set_param(self, name, value):
        self.dev.setParamValueOf(name, value)
        self.dev.updateConfig()
        return self._get_param(name)

    def _get_param(self, name, default=None):
        try:
            return self.dev.paramValueOf(name)
        except Exception:
            if default is not None:
                return default
            raise

    def _get_param_str(self, name, default=None):
        try:
            return self.dev.paramStrValueOf(name)
        except Exception:
            return default

    def StartAcquisition(self):
        if not self._capturing:
            self.dev.start()
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            try:
                self.dev.stop()
            finally:
                self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        self.frame_id = None
        self._software_frame_ready = False

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        self.ResetBuffer()
        return 0

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError("NIT frame buffer sizing is not implemented in this simple wrapper.")

    def GetBufferSizeInNumberOfFrames(self):
        return None

    def GetNumberOfFramesInBuffer(self):
        return None

    def GetGrabTimeout(self):
        return int(self.grab_timeout_ms)

    def SetGrabTimeout(self, timeout_ms):
        self.grab_timeout_ms = int(timeout_ms)
        return self.GetGrabTimeout()

    def IsSoftwareTriggerReady(self):
        return True

    def WaitForSoftwareTriggerReady(self, timeout_ms=1000, poll_interval_s=0.001):
        return True

    def GetTriggerMode(self):
        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.acquisition_mode = "Continuous"
        self.StartAcquisition()
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        self.StopAcquisition()
        self.trigger_mode = "On"
        self.trigger_source = "Software"
        self.acquisition_mode = "SingleFrame"
        self.ResetBuffer()
        return self.GetTriggerMode()

    def FireSoftwareTrigger(self, wait_ready=True, ready_timeout_ms=1000, drain_stale_frames=True):
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            self.GetTriggerMode()
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            raise RuntimeError("Camera is not in software trigger mode")

        self._capture_one_frame()
        self._software_frame_ready = True
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        raise NotImplementedError("Hardware trigger mode is not implemented for the NIT SDK wrapper.")

    def SetExposureTime(self, exposure_time):
        self.ExposureTime = self._set_param("Exposure Time", exposure_time)
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = self._get_param("Exposure Time")
        return self.ExposureTime

    def SetGain(self, gain):
        self.gain = self._set_param("Analog Gain", int(gain))
        return self.gain

    def GetGain(self):
        self.gain = self._get_param("Analog Gain", default=None)
        return self.gain

    def SetCaptureMode(self, capture_mode):
        self.capture_mode = self._set_param("Mode", int(capture_mode))
        return self.capture_mode

    def GetCaptureMode(self):
        self.capture_mode = self._get_param("Mode", default=None)
        return self.capture_mode

    def SetFPS(self, fps):
        self.dev.setFps(float(fps))
        self.dev.updateConfig()
        self.fps = self.GetFPS()
        return self.fps

    def GetFPS(self):
        self.fps = float(self.dev.fps())
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin = 0.0
        self.ExposureTimeMax = 1e9
        try:
            self.FPSMin = float(self.dev.minFps())
            self.FPSMax = float(self.dev.maxFps())
        except Exception:
            self.FPSMin = None
            self.FPSMax = None
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def SetPixelFormat(self, pixel_format):
        pixel_format_key = str(pixel_format).strip().lower()
        if pixel_format_key not in ("mono8", "mono16", "float32", "float64"):
            raise ValueError("NIT pixel_format is inferred from frame dtype; accepted labels are mono8, mono16, float32, float64")
        self.pixel_format = pixel_format_key
        return self.GetPixelFormat()

    def GetPixelFormat(self):
        if self.observer.frame is not None:
            dtype = self.observer.frame.dtype
            if dtype == np.uint8:
                self.pixel_format = "mono8"
            elif dtype == np.uint16:
                self.pixel_format = "mono16"
            elif dtype == np.float32:
                self.pixel_format = "float32"
            elif dtype == np.float64:
                self.pixel_format = "float64"
            else:
                self.pixel_format = str(dtype)
        elif self.pixel_format is None:
            self.pixel_format = "float64"

        self.pixel_format_fc2 = self.pixel_format
        return self.pixel_format

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode="nearest"):
        if not enable:
            offset_x = 0
            offset_y = 0
            width = self.sensor_width
            height = self.sensor_height
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

        width = min(int(width), self.sensor_width)
        height = min(int(height), self.sensor_height)
        offset_x = min(max(int(offset_x), 0), self.sensor_width - width)
        offset_y = min(max(int(offset_y), 0), self.sensor_height - height)

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()

        try:
            self.dev.setRoi(int(width), int(height), int(offset_x), int(offset_y))
            self.dev.updateConfig()
        finally:
            if was_capturing:
                self.StartAcquisition()

        self.offset_x = offset_x
        self.offset_y = offset_y
        self.width = width
        self.height = height
        self.Nx = width
        self.Ny = height
        return self.GetROI()

    def GetROI(self):
        return self.offset_x, self.offset_y, self.width, self.height

    def GetFrameID(self):
        return self.frame_id

    def _capture_one_frame(self, n_frames=1):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()

        try:
            self.dev.captureNFrames(int(n_frames))
            self.dev.waitEndCapture()
        finally:
            if was_capturing and self.trigger_mode == "Off":
                self.StartAcquisition()

        if self.observer.frame is None:
            raise RuntimeError("NIT camera did not deliver a frame")

        self.frame_id = self.observer.frame_id
        return np.array(self.observer.frame, copy=True)

    def _wait_for_stream_frame(self, timeout_ms):
        deadline = time.perf_counter() + (float(timeout_ms) * 1e-3)
        start_id = self.observer.frame_id

        while self.observer.frame is None or self.observer.frame_id == start_id:
            if time.perf_counter() >= deadline:
                if self.observer.frame is not None:
                    break
                raise TimeoutError(f"Timed out waiting {timeout_ms} ms for a NIT frame")
            time.sleep(0.001)

        self.frame_id = self.observer.frame_id
        return np.array(self.observer.frame, copy=True)

    def GetFrame(self, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = self.grab_timeout_ms

        if self._software_frame_ready and self.observer.frame is not None:
            self._software_frame_ready = False
            self.frame_id = self.observer.frame_id
            return np.array(self.observer.frame, copy=True)

        if self.trigger_mode == "On" and self.trigger_source == "Software":
            return self._capture_one_frame()

        if self._capturing:
            return self._wait_for_stream_frame(timeout_ms)

        return self._capture_one_frame()


NiTCamraObject = CameraObject
NiTCameraObject = CameraObject
