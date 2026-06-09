import atexit
import time
import weakref

from .spinnaker_ctypes import SpinnakerError, SpinnakerLibrary


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

    if snapped < minimum:
        snapped = minimum
    return int(snapped)


def _shutdown_camera_ref(camera_ref):
    camera = camera_ref()
    if camera is not None:
        camera.shutdown()


class CameraObject:
    """
    FLIR camera object using the Spinnaker C API through ctypes.

    The public method names intentionally match PointGrey.py because the camera
    server and upstream clients call those names directly.
    """

    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=6.9e-6, dll_path=None, verbose=False):
        self.CameraIdx = int(CameraIdx)
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.grab_timeout_ms = 1000

        self.spin = SpinnakerLibrary(dll_path=dll_path)
        self.system = self.spin.get_system_instance()
        self.camera_list = self.spin.create_camera_list()
        self.camera = None
        self.node_map = None

        self.spin.get_cameras(self.system, self.camera_list)
        self.num_cameras = self.spin.get_camera_list_size(self.camera_list)

        print(f"{self.num_cameras} cameras detected:")
        for k in range(self.num_cameras):
            print(f"{k}: FLIR Spinnaker camera {k}")
        print(f"Using camera {self.CameraIdx}")

        if self.num_cameras <= 0:
            self.shutdown()
            raise RuntimeError("No FLIR Spinnaker cameras detected")
        if self.CameraIdx < 0 or self.CameraIdx >= self.num_cameras:
            self.shutdown()
            raise IndexError(f"CameraIdx {self.CameraIdx} out of range for {self.num_cameras} cameras")

        self.camera = self.spin.get_camera_from_index(self.camera_list, self.CameraIdx)
        self.spin.init_camera(self.camera)
        self.node_map = self.spin.get_node_map(self.camera)

        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.trigger_selector = "FrameStart"
        self.acquisition_mode = "Continuous"
        self.trigger_polarity = 1
        self.trigger_source_raw = None
        self.trigger_mode_raw = None
        self.trigger_parameter = 0

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
        self.frame_counter_available = True

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
            if getattr(self, "camera", None) is not None:
                try:
                    self.spin.deinit_camera(self.camera)
                except Exception:
                    pass
                try:
                    self.spin.release_camera(self.camera)
                except Exception:
                    pass
                self.camera = None

            if getattr(self, "camera_list", None) is not None:
                try:
                    self.spin.destroy_camera_list(self.camera_list)
                except Exception:
                    pass
                self.camera_list = None

            if getattr(self, "system", None) is not None:
                try:
                    self.spin.release_system_instance(self.system)
                except Exception:
                    pass
                self.system = None

    def StartAcquisition(self):
        if not self._capturing:
            self.spin.begin_acquisition(self.camera)
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            self.spin.end_acquisition(self.camera)
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

        old_timeout = self.GetGrabTimeout()
        drained = 0
        try:
            self.SetGrabTimeout(timeout_ms)
            for _ in range(int(max_frames)):
                image = None
                try:
                    image = self.spin.get_next_image(self.camera, self.grab_timeout_ms)
                    drained += 1
                except SpinnakerError:
                    break
                finally:
                    if image is not None:
                        try:
                            self.spin.release_image(image)
                        except Exception:
                            pass
        finally:
            self.SetGrabTimeout(old_timeout)

        self.frame_id = None
        return drained

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError("Spinnaker stream buffer sizing is not implemented in this wrapper.")

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
            return bool(self.spin.get_boolean(self.node_map, "SoftwareTriggerIsBusy") is False)
        except Exception:
            return True

    def WaitForSoftwareTriggerReady(self, timeout_ms=1000, poll_interval_s=0.001):
        deadline = time.perf_counter() + (float(timeout_ms) * 1e-3)
        while True:
            if self.IsSoftwareTriggerReady():
                return True
            if timeout_ms is not None and time.perf_counter() >= deadline:
                raise TimeoutError(f"Timed out waiting {timeout_ms} ms for FLIR software trigger ready")
            time.sleep(poll_interval_s)

    def GetTriggerMode(self):
        trigger_mode_symbol = self.spin.get_enumeration_symbol(self.node_map, "TriggerMode")
        self.trigger_mode = "On" if trigger_mode_symbol == "On" else "Off"

        if self.trigger_mode == "Off":
            self.trigger_source = "FreeRun"
        else:
            trigger_source_symbol = self.spin.get_enumeration_symbol(self.node_map, "TriggerSource")
            if trigger_source_symbol == "Software":
                self.trigger_source = "Software"
            elif trigger_source_symbol.startswith("Line"):
                self.trigger_source = "line " + trigger_source_symbol[4:]
            else:
                self.trigger_source = trigger_source_symbol

        try:
            self.trigger_selector = self.spin.get_enumeration_symbol(self.node_map, "TriggerSelector")
        except Exception:
            self.trigger_selector = "FrameStart"

        try:
            self.acquisition_mode = self.spin.get_enumeration_symbol(self.node_map, "AcquisitionMode")
        except Exception:
            self.acquisition_mode = "Continuous"

        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.spin.set_enumeration_symbol(self.node_map, "TriggerMode", "Off")
            self.spin.set_enumeration_symbol(self.node_map, "AcquisitionMode", "Continuous")
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
            self.spin.set_enumeration_symbol(self.node_map, "TriggerSelector", "FrameStart")
            self.spin.set_enumeration_symbol(self.node_map, "TriggerMode", "On")
            self.spin.set_enumeration_symbol(self.node_map, "TriggerSource", "Software")
            self.spin.set_enumeration_symbol(self.node_map, "AcquisitionMode", "Continuous")
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

        self.spin.execute_command(self.node_map, "TriggerSoftware")
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.spin.set_enumeration_symbol(self.node_map, "TriggerSelector", "FrameStart")
            self.spin.set_enumeration_symbol(self.node_map, "TriggerMode", "On")
            self.spin.set_enumeration_symbol(self.node_map, "TriggerSource", f"Line{int(lineNumber)}")
            trigger_activation = "RisingEdge" if RiseEdgeOrFallEdge == 1 else "FallingEdge"
            self.spin.set_enumeration_symbol(self.node_map, "TriggerActivation", trigger_activation)
            self.spin.set_enumeration_symbol(self.node_map, "AcquisitionMode", "Continuous")
            self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
        finally:
            if was_capturing:
                self.StartAcquisition()

        self.ResetBuffer()
        return self.GetTriggerMode()

    def _get_property_info(self, prop_type):
        raise NotImplementedError("FlyCapture2 property info is not available through the Spinnaker wrapper.")

    def _get_property_abs(self, prop_type):
        raise NotImplementedError("FlyCapture2 property access is not available through the Spinnaker wrapper.")

    def _set_property_abs(self, prop_type, value):
        raise NotImplementedError("FlyCapture2 property access is not available through the Spinnaker wrapper.")

    def SetExposureTime(self, exposure_time):
        self.GetMaxMinFPS_ExposureTime()

        if exposure_time < self.ExposureTimeMin:
            print("Exposure time too low, setting to minimum:", self.ExposureTimeMin)
            exposure_time = self.ExposureTimeMin
        if exposure_time > self.ExposureTimeMax:
            print("Exposure time too high, setting to maximum:", self.ExposureTimeMax)
            exposure_time = self.ExposureTimeMax

        try:
            self.spin.set_enumeration_symbol(self.node_map, "ExposureAuto", "Off")
        except Exception:
            pass
        self.spin.set_float(self.node_map, "ExposureTime", float(exposure_time))
        self.ExposureTime = self.GetExposureTime()
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = self.spin.get_float(self.node_map, "ExposureTime")
        return self.ExposureTime

    def SetGain(self, gain):
        gain_min, gain_max = self.spin.get_float_limits(self.node_map, "Gain")

        if gain < gain_min:
            print("Gain too low, setting to minimum:", gain_min)
            gain = gain_min
        if gain > gain_max:
            print("Gain too high, setting to maximum:", gain_max)
            gain = gain_max

        try:
            self.spin.set_enumeration_symbol(self.node_map, "GainAuto", "Off")
        except Exception:
            pass
        self.spin.set_float(self.node_map, "Gain", float(gain))
        self.gain = self.GetGain()
        return self.gain

    def GetGain(self):
        self.gain = self.spin.get_float(self.node_map, "Gain")
        return self.gain

    def SetFPS(self, fps):
        self.GetMaxMinFPS_ExposureTime()

        if fps < self.FPSMin:
            print("FPS too low, setting to minimum:", self.FPSMin)
            fps = self.FPSMin
        if fps > self.FPSMax:
            print("FPS too high, setting to maximum:", self.FPSMax)
            fps = self.FPSMax

        try:
            self.spin.set_boolean(self.node_map, "AcquisitionFrameRateEnable", True)
        except Exception:
            pass
        self.spin.set_float(self.node_map, "AcquisitionFrameRate", float(fps))
        self.fps = self.GetFPS()
        return self.fps

    def GetFPS(self):
        self.fps = self.spin.get_float(self.node_map, "AcquisitionFrameRate")
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin, self.ExposureTimeMax = self.spin.get_float_limits(self.node_map, "ExposureTime")
        self.FPSMin, self.FPSMax = self.spin.get_float_limits(self.node_map, "AcquisitionFrameRate")
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def _get_current_fc2_pixel_format(self):
        return self.GetPixelFormat()

    def SetPixelFormat(self, pixel_format):
        if isinstance(pixel_format, str):
            pixel_format_key = pixel_format.strip().lower()
            if pixel_format_key == "mono8":
                pixel_format_symbol = "Mono8"
            elif pixel_format_key == "mono10":
                pixel_format_symbol = "Mono10"
            elif pixel_format_key == "mono12":
                pixel_format_symbol = "Mono12"
            elif pixel_format_key == "mono16":
                pixel_format_symbol = "Mono16"
            else:
                raise ValueError("pixel_format must be one of: mono8, mono10, mono12, mono16")
        else:
            raise TypeError("Spinnaker pixel_format must be a string")

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.spin.set_enumeration_symbol(self.node_map, "PixelFormat", pixel_format_symbol)
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetPixelFormat()

    def GetPixelFormat(self):
        pixel_format_symbol = self.spin.get_enumeration_symbol(self.node_map, "PixelFormat")
        self.pixel_format_fc2 = pixel_format_symbol
        self.pixel_format = pixel_format_symbol.lower()
        return self.pixel_format

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode="nearest"):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()

        try:
            width_min, width_max, width_step = self.spin.get_integer_limits(self.node_map, "Width")
            height_min, height_max, height_step = self.spin.get_integer_limits(self.node_map, "Height")
            offset_x_min, offset_x_max, offset_x_step = self.spin.get_integer_limits(self.node_map, "OffsetX")
            offset_y_min, offset_y_max, offset_y_step = self.spin.get_integer_limits(self.node_map, "OffsetY")

            if not enable:
                offset_x = 0
                offset_y = 0
                width = width_max
                height = height_max
            else:
                if offset_x is None:
                    offset_x = self.spin.get_integer(self.node_map, "OffsetX")
                if offset_y is None:
                    offset_y = self.spin.get_integer(self.node_map, "OffsetY")
                if width is None:
                    width = self.spin.get_integer(self.node_map, "Width")
                if height is None:
                    height = self.spin.get_integer(self.node_map, "Height")

            if snap_values:
                width = snap_to_value(width, width_step, mode, minimum=width_min)
                height = snap_to_value(height, height_step, mode, minimum=height_min)
                width = min(width, width_max)
                height = min(height, height_max)

                max_offset_x = max(offset_x_min, width_max - width)
                max_offset_y = max(offset_y_min, height_max - height)
                offset_x = snap_to_value(offset_x, offset_x_step, mode, minimum=offset_x_min)
                offset_y = snap_to_value(offset_y, offset_y_step, mode, minimum=offset_y_min)
                offset_x = min(offset_x, snap_to_value(max_offset_x, offset_x_step, "floor", minimum=offset_x_min))
                offset_y = min(offset_y, snap_to_value(max_offset_y, offset_y_step, "floor", minimum=offset_y_min))

            self.spin.set_integer(self.node_map, "OffsetX", 0)
            self.spin.set_integer(self.node_map, "OffsetY", 0)
            self.spin.set_integer(self.node_map, "Width", int(width))
            self.spin.set_integer(self.node_map, "Height", int(height))
            self.spin.set_integer(self.node_map, "OffsetX", int(offset_x))
            self.spin.set_integer(self.node_map, "OffsetY", int(offset_y))
        finally:
            if was_capturing:
                self.StartAcquisition()

        return self.GetROI()

    def GetROI(self):
        self.offset_x = self.spin.get_integer(self.node_map, "OffsetX")
        self.offset_y = self.spin.get_integer(self.node_map, "OffsetY")
        self.width = self.spin.get_integer(self.node_map, "Width")
        self.height = self.spin.get_integer(self.node_map, "Height")
        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def GetFrameID(self):
        return self.frame_id

    def GetFrame(self, timeout_ms=None):
        image = None
        if timeout_ms is None:
            timeout_ms = self.grab_timeout_ms

        try:
            image = self.spin.get_next_image(self.camera, int(timeout_ms))
            self.frame_id = self.spin.get_image_frame_id(image)
            frame = self.spin.image_to_numpy(image)
            return frame
        finally:
            if image is not None:
                self.spin.release_image(image)
