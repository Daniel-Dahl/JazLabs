import atexit
import ctypes
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
    Simple Lucid Vision camera object using the Arena Python API.

    This follows the public API style used by the FLIR and PointGrey wrappers:
    direct camera control, NumPy frames, and no multiprocessing/display code.
    """

    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=5e-6, verbose=False):
        self.CameraIdx = int(CameraIdx)
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.grab_timeout_ms = 1000

        from arena_api.system import system

        self.system = system
        self.devices = self.system.create_device()
        self.num_cameras = len(self.devices)

        print(f"{self.num_cameras} cameras detected:")
        for k, device in enumerate(self.devices):
            print(f"{k}: Lucid Vision camera {k}")
        print(f"Using camera {self.CameraIdx}")

        if self.num_cameras <= 0:
            self.shutdown()
            raise RuntimeError("No Lucid Vision cameras detected")
        if self.CameraIdx < 0 or self.CameraIdx >= self.num_cameras:
            self.shutdown()
            raise IndexError(f"CameraIdx {self.CameraIdx} out of range for {self.num_cameras} cameras")

        self.device = self.devices[self.CameraIdx]
        self.node_map = self.device.nodemap

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
        self.SetPixelFormat("mono16")
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
            try:
                self.system.destroy_device(self.device)
            except TypeError:
                self.system.destroy_device()
            except Exception:
                pass

    def _node(self, name):
        return self.node_map[name]

    def _get_value(self, name):
        return self._node(name).value

    def _set_value(self, name, value):
        self._node(name).value = value

    def _execute(self, name):
        self._node(name).execute()

    def _limits(self, name, default_step=1):
        node = self._node(name)
        minimum = int(getattr(node, "min", 0))
        maximum = int(getattr(node, "max", node.value))
        step = int(getattr(node, "inc", default_step) or default_step)
        return minimum, maximum, step

    def StartAcquisition(self):
        if not self._capturing:
            self.device.start_stream()
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            self.device.stop_stream()
            self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        self.frame_id = None

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        if not self._capturing:
            return 0

        drained = 0
        for _ in range(int(max_frames)):
            image_buffer = None
            try:
                image_buffer = self.device.get_buffer(timeout=timeout_ms)
                drained += 1
            except TypeError:
                try:
                    image_buffer = self.device.get_buffer()
                    drained += 1
                except Exception:
                    break
            except Exception:
                break
            finally:
                if image_buffer is not None:
                    self.device.requeue_buffer(image_buffer)

        self.frame_id = None
        return drained

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError("Arena stream buffer sizing is not implemented in this wrapper.")

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
        try:
            return bool(self._get_value("SoftwareTriggerIsBusy") is False)
        except Exception:
            return True

    def WaitForSoftwareTriggerReady(self, timeout_ms=1000, poll_interval_s=0.001):
        deadline = time.perf_counter() + (float(timeout_ms) * 1e-3)
        while True:
            if self.IsSoftwareTriggerReady():
                return True
            if timeout_ms is not None and time.perf_counter() >= deadline:
                raise TimeoutError(f"Timed out waiting {timeout_ms} ms for Lucid software trigger ready")
            time.sleep(poll_interval_s)

    def GetTriggerMode(self):
        self.trigger_mode = self._get_value("TriggerMode")
        self.trigger_selector = self._get_value("TriggerSelector")
        self.acquisition_mode = self._get_value("AcquisitionMode")

        if self.trigger_mode == "Off":
            self.trigger_source = "FreeRun"
        else:
            source = self._get_value("TriggerSource")
            self.trigger_source = "line " + source[4:] if source.startswith("Line") else source

        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set_value("AcquisitionMode", "Continuous")
            self._set_value("TriggerSelector", "FrameStart")
            self._set_value("TriggerMode", "Off")
        finally:
            if was_capturing:
                self.StartAcquisition()

        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set_value("AcquisitionMode", "Continuous")
            self._set_value("TriggerSelector", "FrameStart")
            self._set_value("TriggerSource", "Software")
            self._set_value("TriggerMode", "On")
        finally:
            if was_capturing:
                self.StartAcquisition()

        self.ResetBuffer()
        self.DrainImageBuffer()
        return self.GetTriggerMode()

    def FireSoftwareTrigger(self, wait_ready=True, ready_timeout_ms=1000, drain_stale_frames=True):
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            self.GetTriggerMode()
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            raise RuntimeError("Camera is not in software trigger mode")

        if drain_stale_frames:
            self.DrainImageBuffer()
        if wait_ready:
            self.WaitForSoftwareTriggerReady(timeout_ms=ready_timeout_ms)

        self._execute("TriggerSoftware")
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set_value("AcquisitionMode", "Continuous")
            self._set_value("TriggerSelector", "FrameStart")
            self._set_value("TriggerSource", f"Line{int(lineNumber)}")
            self._set_value("TriggerMode", "On")
            self._set_value("TriggerActivation", "RisingEdge" if RiseEdgeOrFallEdge == 1 else "FallingEdge")
            self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
        finally:
            if was_capturing:
                self.StartAcquisition()

        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetExposureTime(self, exposure_time):
        self.GetMaxMinFPS_ExposureTime()
        exposure_time = max(self.ExposureTimeMin, min(float(exposure_time), self.ExposureTimeMax))

        try:
            self._set_value("ExposureAuto", "Off")
        except Exception:
            pass
        self._set_value("ExposureTime", exposure_time)
        self.ExposureTime = self.GetExposureTime()
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = float(self._get_value("ExposureTime"))
        return self.ExposureTime

    def SetGain(self, gain):
        gain_min = float(getattr(self._node("Gain"), "min", gain))
        gain_max = float(getattr(self._node("Gain"), "max", gain))
        gain = max(gain_min, min(float(gain), gain_max))

        try:
            self._set_value("GainAuto", "Off")
        except Exception:
            pass
        self._set_value("Gain", gain)
        self.gain = self.GetGain()
        return self.gain

    def GetGain(self):
        self.gain = float(self._get_value("Gain"))
        return self.gain

    def SetFPS(self, fps):
        self.GetMaxMinFPS_ExposureTime()
        fps = max(self.FPSMin, min(float(fps), self.FPSMax))

        try:
            self._set_value("AcquisitionFrameRateEnable", True)
        except Exception:
            pass
        self._set_value("AcquisitionFrameRate", fps)
        self.fps = self.GetFPS()
        return self.fps

    def GetFPS(self):
        self.fps = float(self._get_value("AcquisitionFrameRate"))
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        exp_node = self._node("ExposureTime")
        fps_node = self._node("AcquisitionFrameRate")
        self.ExposureTimeMin = float(getattr(exp_node, "min", 0.0))
        self.ExposureTimeMax = float(getattr(exp_node, "max", self.ExposureTimeMin))
        self.FPSMin = float(getattr(fps_node, "min", 0.0))
        self.FPSMax = float(getattr(fps_node, "max", self.FPSMin))
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def SetPixelFormat(self, pixel_format):
        if isinstance(pixel_format, str):
            pixel_format_key = pixel_format.strip().lower()
            formats = {
                "mono8": "Mono8",
                "mono10": "Mono10",
                "mono12": "Mono12",
                "mono16": "Mono16",
            }
            if pixel_format_key not in formats:
                raise ValueError("pixel_format must be one of: mono8, mono10, mono12, mono16")
            pixel_format_symbol = formats[pixel_format_key]
        else:
            raise TypeError("pixel_format must be a string")

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set_value("PixelFormat", pixel_format_symbol)
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetPixelFormat()

    def GetPixelFormat(self):
        self.pixel_format_fc2 = self._get_value("PixelFormat")
        self.pixel_format = str(self.pixel_format_fc2).lower()
        return self.pixel_format

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode="nearest"):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()

        try:
            width_min, width_max, width_step = self._limits("Width")
            height_min, height_max, height_step = self._limits("Height")
            offset_x_min, offset_x_max, offset_x_step = self._limits("OffsetX")
            offset_y_min, offset_y_max, offset_y_step = self._limits("OffsetY")

            if not enable:
                offset_x = offset_x_min
                offset_y = offset_y_min
                width = width_max
                height = height_max
            else:
                offset_x = self._get_value("OffsetX") if offset_x is None else offset_x
                offset_y = self._get_value("OffsetY") if offset_y is None else offset_y
                width = self._get_value("Width") if width is None else width
                height = self._get_value("Height") if height is None else height

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

            self._set_value("OffsetX", offset_x_min)
            self._set_value("OffsetY", offset_y_min)
            self._set_value("Width", int(width))
            self._set_value("Height", int(height))
            self._set_value("OffsetX", int(offset_x))
            self._set_value("OffsetY", int(offset_y))
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetROI()

    def GetROI(self):
        self.offset_x = int(self._get_value("OffsetX"))
        self.offset_y = int(self._get_value("OffsetY"))
        self.width = int(self._get_value("Width"))
        self.height = int(self._get_value("Height"))
        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def GetFrameID(self):
        return self.frame_id

    def GetFrame(self, timeout_ms=None):
        image_buffer = None
        if timeout_ms is None:
            timeout_ms = self.grab_timeout_ms

        try:
            try:
                image_buffer = self.device.get_buffer(timeout=int(timeout_ms))
            except TypeError:
                image_buffer = self.device.get_buffer()

            self.frame_id = getattr(image_buffer, "frame_id", None)
            pixel_format = self.GetPixelFormat()
            c_type = ctypes.c_ubyte if pixel_format == "mono8" else ctypes.c_ushort
            frame_ptr = ctypes.cast(image_buffer.pdata, ctypes.POINTER(c_type))
            frame = np.ctypeslib.as_array(frame_ptr, (image_buffer.height, image_buffer.width)).copy()
            return frame
        finally:
            if image_buffer is not None:
                self.device.requeue_buffer(image_buffer)


LucidVisCameraObject = CameraObject
