import atexit
import time
import weakref

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


class CameraObject:
    """
    Simple Allied Vision camera object using Vimba X / VmbPy.

    The method names follow the FLIR, PointGrey, Lucid, and QImag wrappers.
    """

    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=3.45e-6, verbose=False):
        self.CameraIdx = int(CameraIdx)
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.grab_timeout_ms = 1000

        from vmbpy import PixelFormat, VmbSystem

        self.PixelFormat = PixelFormat
        self.vmb_context = VmbSystem.get_instance()
        self.vmb = self.vmb_context.__enter__()

        self.cameras = self.vmb.get_all_cameras()
        self.num_cameras = len(self.cameras)

        print(f"{self.num_cameras} cameras detected:")
        for k, camera in enumerate(self.cameras):
            print(f"{k}: Allied Vision camera {camera}")
        print(f"Using camera {self.CameraIdx}")

        if self.num_cameras <= 0:
            self.shutdown()
            raise RuntimeError("No Allied Vision cameras detected")
        if self.CameraIdx < 0 or self.CameraIdx >= self.num_cameras:
            self.shutdown()
            raise IndexError(f"CameraIdx {self.CameraIdx} out of range for {self.num_cameras} cameras")

        self.camera = self.cameras[self.CameraIdx]
        self.camera.__enter__()

        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.trigger_selector = "FrameStart"
        self.acquisition_mode = "Continuous"
        self.trigger_polarity = 1

        self.offset_x = 0
        self.offset_y = 0
        self.width = 0
        self.height = 0
        self.Nx = 0
        self.Ny = 0

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

        self.SetContinuousMode()
        self.GetROI()
        self.GetExposureTime()
        self.GetGain()
        self.GetFPS()
        self.GetPixelFormat()
        self.GetMaxMinFPS_ExposureTime()

        try:
            self.SetPixelFormat("mono16")
        except Exception:
            if self.verbose:
                print("Mono16 is not available on this Allied Vision camera; keeping current pixel format")

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
            if getattr(self, "camera", None) is not None:
                try:
                    self.camera.__exit__(None, None, None)
                except Exception:
                    pass
                self.camera = None

            if getattr(self, "vmb_context", None) is not None:
                try:
                    self.vmb_context.__exit__(None, None, None)
                except Exception:
                    pass
                self.vmb_context = None

    def _feature(self, name):
        return getattr(self.camera, name)

    def _get(self, name):
        return self._feature(name).get()

    def _set(self, name, value):
        self._feature(name).set(value)

    def _run(self, name):
        self._feature(name).run()

    def _limits(self, name):
        feature = self._feature(name)
        minimum = feature.get_min() if hasattr(feature, "get_min") else feature.get()
        maximum = feature.get_max() if hasattr(feature, "get_max") else feature.get()
        increment = feature.get_increment() if hasattr(feature, "get_increment") else 1
        if increment in (None, 0):
            increment = 1
        return minimum, maximum, increment

    def StartAcquisition(self):
        self._capturing = True

    def StopAcquisition(self):
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
        raise NotImplementedError("VmbPy stream buffer sizing is not implemented in this simple wrapper.")

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
        self.trigger_mode = self._get("TriggerMode")
        try:
            self.trigger_selector = self._get("TriggerSelector")
        except Exception:
            self.trigger_selector = "FrameStart"

        try:
            self.acquisition_mode = self._get("AcquisitionMode")
        except Exception:
            self.acquisition_mode = "Continuous"

        if self.trigger_mode == "Off":
            self.trigger_source = "FreeRun"
        else:
            source = self._get("TriggerSource")
            self.trigger_source = "line " + source[4:] if source.startswith("Line") else source

        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        self._set("AcquisitionMode", "Continuous")
        try:
            self._set("TriggerSelector", "FrameStart")
        except Exception:
            pass
        self._set("TriggerMode", "Off")
        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        self._set("AcquisitionMode", "Continuous")
        self._set("TriggerSelector", "FrameStart")
        self._set("TriggerSource", "Software")
        self._set("TriggerMode", "On")
        self.ResetBuffer()
        return self.GetTriggerMode()

    def FireSoftwareTrigger(self, wait_ready=True, ready_timeout_ms=1000, drain_stale_frames=True):
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            self.GetTriggerMode()
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            raise RuntimeError("Camera is not in software trigger mode")

        if wait_ready:
            self.WaitForSoftwareTriggerReady(timeout_ms=ready_timeout_ms)
        self._run("TriggerSoftware")
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        self._set("AcquisitionMode", "Continuous")
        self._set("TriggerSelector", "FrameStart")
        self._set("TriggerSource", f"Line{int(lineNumber)}")
        self._set("TriggerActivation", "RisingEdge" if RiseEdgeOrFallEdge == 1 else "FallingEdge")
        self._set("TriggerMode", "On")
        self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetExposureTime(self, exposure_time):
        self.GetMaxMinFPS_ExposureTime()
        exposure_time = max(self.ExposureTimeMin, min(float(exposure_time), self.ExposureTimeMax))

        try:
            self._set("ExposureAuto", "Off")
        except Exception:
            pass
        self._set("ExposureTime", exposure_time)
        self.ExposureTime = self.GetExposureTime()
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = float(self._get("ExposureTime"))
        return self.ExposureTime

    def SetGain(self, gain):
        gain_min, gain_max, _ = self._limits("Gain")
        gain = max(float(gain_min), min(float(gain), float(gain_max)))

        try:
            self._set("GainAuto", "Off")
        except Exception:
            pass
        self._set("Gain", gain)
        self.gain = self.GetGain()
        return self.gain

    def GetGain(self):
        self.gain = float(self._get("Gain"))
        return self.gain

    def SetFPS(self, fps):
        self.GetMaxMinFPS_ExposureTime()
        fps = max(self.FPSMin, min(float(fps), self.FPSMax))

        try:
            self._set("AcquisitionFrameRateEnable", True)
        except Exception:
            pass
        self._set("AcquisitionFrameRate", fps)
        self.fps = self.GetFPS()
        return self.fps

    def GetFPS(self):
        self.fps = float(self._get("AcquisitionFrameRate"))
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin, self.ExposureTimeMax, _ = self._limits("ExposureTime")
        self.FPSMin, self.FPSMax, _ = self._limits("AcquisitionFrameRate")
        self.ExposureTimeMin = float(self.ExposureTimeMin)
        self.ExposureTimeMax = float(self.ExposureTimeMax)
        self.FPSMin = float(self.FPSMin)
        self.FPSMax = float(self.FPSMax)
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def SetPixelFormat(self, pixel_format):
        if isinstance(pixel_format, str):
            key = pixel_format.strip().lower()
            mapping = {
                "mono8": self.PixelFormat.Mono8,
                "mono10": self.PixelFormat.Mono10,
                "mono12": self.PixelFormat.Mono12,
                "mono16": self.PixelFormat.Mono16,
            }
            if key not in mapping:
                raise ValueError("pixel_format must be one of: mono8, mono10, mono12, mono16")
            pixel_format_value = mapping[key]
        else:
            pixel_format_value = pixel_format

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.camera.set_pixel_format(pixel_format_value)
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetPixelFormat()

    def GetPixelFormat(self):
        self.pixel_format_fc2 = self.camera.get_pixel_format()
        self.pixel_format = self._pixel_format_name(self.pixel_format_fc2).lower()
        return self.pixel_format

    def _pixel_format_name(self, pixel_format):
        name = getattr(pixel_format, "name", None)
        if name:
            return name
        text = str(pixel_format)
        return text.split(".")[-1]

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode="nearest"):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()

        try:
            width_min, width_max, width_step = self._limits("Width")
            height_min, height_max, height_step = self._limits("Height")
            offset_x_min, offset_x_max, offset_x_step = self._limits("OffsetX")
            offset_y_min, offset_y_max, offset_y_step = self._limits("OffsetY")

            width_min = int(width_min)
            width_max = int(width_max)
            width_step = int(width_step)
            height_min = int(height_min)
            height_max = int(height_max)
            height_step = int(height_step)
            offset_x_min = int(offset_x_min)
            offset_x_max = int(offset_x_max)
            offset_x_step = int(offset_x_step)
            offset_y_min = int(offset_y_min)
            offset_y_max = int(offset_y_max)
            offset_y_step = int(offset_y_step)

            if not enable:
                offset_x = offset_x_min
                offset_y = offset_y_min
                width = width_max
                height = height_max
            else:
                offset_x = self._get("OffsetX") if offset_x is None else offset_x
                offset_y = self._get("OffsetY") if offset_y is None else offset_y
                width = self._get("Width") if width is None else width
                height = self._get("Height") if height is None else height

            if snap_values:
                width = snap_to_value(width, width_step, mode, minimum=width_min)
                height = snap_to_value(height, height_step, mode, minimum=height_min)
                width = min(width, width_max)
                height = min(height, height_max)

                max_offset_x = min(offset_x_max, width_max - width)
                max_offset_y = min(offset_y_max, height_max - height)
                offset_x = snap_to_value(offset_x, offset_x_step, mode, minimum=offset_x_min)
                offset_y = snap_to_value(offset_y, offset_y_step, mode, minimum=offset_y_min)
                offset_x = min(offset_x, snap_to_value(max_offset_x, offset_x_step, "floor", minimum=offset_x_min))
                offset_y = min(offset_y, snap_to_value(max_offset_y, offset_y_step, "floor", minimum=offset_y_min))

            self._set("OffsetX", offset_x_min)
            self._set("OffsetY", offset_y_min)
            self._set("Width", int(width))
            self._set("Height", int(height))
            self._set("OffsetX", int(offset_x))
            self._set("OffsetY", int(offset_y))
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetROI()

    def GetROI(self):
        self.offset_x = int(self._get("OffsetX"))
        self.offset_y = int(self._get("OffsetY"))
        self.width = int(self._get("Width"))
        self.height = int(self._get("Height"))
        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def GetFrameID(self):
        return self.frame_id

    def GetFrame(self, timeout_ms=None):
        if timeout_ms is None:
            timeout_ms = self.grab_timeout_ms

        try:
            frame = self.camera.get_frame(timeout_ms=int(timeout_ms))
        except TypeError:
            frame = self.camera.get_frame()

        self.frame_id = getattr(frame, "get_id", lambda: None)()

        if hasattr(frame, "as_numpy_ndarray"):
            return np.array(frame.as_numpy_ndarray(), copy=True)
        if hasattr(frame, "as_opencv_image"):
            return np.array(frame.as_opencv_image(), copy=True)

        raise RuntimeError("VmbPy Frame does not provide NumPy/OpenCV export. Install VmbPy with the numpy extra.")


AlliedVisionCameraObject = CameraObject
