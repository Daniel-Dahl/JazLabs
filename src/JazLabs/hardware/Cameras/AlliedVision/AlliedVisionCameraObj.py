import atexit
import threading
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

    def __init__(self, CameraSerialNumber, CalibrationFile=None, PixelSize=3.45e-6, verbose=False):
        if CameraSerialNumber is None:
            raise ValueError("CameraSerialNumber must not be None")
        requested_serial_number = str(CameraSerialNumber).strip()
        if not requested_serial_number:
            raise ValueError("CameraSerialNumber must not be empty")

        self.CameraSerialNumber = requested_serial_number
        self.CameraType = "Allied Vision"
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self._stream_buffer_count = 5
        self._frame_condition = threading.Condition()
        self._latest_frame = None
        self._frame_error = None
        self._frame_sequence = 0
        self._last_delivered_sequence = 0
        self.frame_id_updates_asynchronously = True
        self.grab_timeout_ms = 1000

        from vmbpy import PixelFormat, VmbSystem

        self.PixelFormat = PixelFormat
        self.vmb_context = VmbSystem.get_instance()
        self.vmb = self.vmb_context.__enter__()

        self.cameras = self.vmb.get_all_cameras()
        self.num_cameras = len(self.cameras)

        print(f"{self.num_cameras} cameras detected:")
        selected_camera = None
        discovered_serial_numbers = []
        for k, camera in enumerate(self.cameras):
            serial_number = str(camera.get_serial()).strip()
            discovered_serial_numbers.append(serial_number)
            print(f"{k}: Allied Vision camera serial number {serial_number}")
            if serial_number.casefold() == requested_serial_number.casefold():
                selected_camera = camera

        if self.num_cameras <= 0:
            self.shutdown()
            raise RuntimeError("No Allied Vision cameras detected")
        if selected_camera is None:
            self.shutdown()
            raise ValueError(
                "Allied Vision camera with serial number "
                f"{requested_serial_number!r} was not found. Discovered serial "
                f"numbers: {', '.join(discovered_serial_numbers)}"
            )

        self.camera = selected_camera
        self.camera.__enter__()
        self.CameraSerialNumber = str(self.camera.get_serial()).strip()
        print(f"Using Allied Vision camera serial number {self.CameraSerialNumber}")

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

    def GetSerialNumber(self):
        self.CameraSerialNumber = str(self.camera.get_serial()).strip()
        return self.CameraSerialNumber

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
        if hasattr(feature, "get_range"):
            minimum, maximum = feature.get_range()
        else:
            minimum = feature.get_min() if hasattr(feature, "get_min") else feature.get()
            maximum = feature.get_max() if hasattr(feature, "get_max") else feature.get()
        increment = feature.get_increment() if hasattr(feature, "get_increment") else 1
        if increment in (None, 0):
            increment = 1
        return minimum, maximum, increment

    def _enum_name(self, value):
        if isinstance(value, str):
            return value
        if hasattr(value, "as_tuple"):
            return value.as_tuple()[0]
        name = getattr(value, "name", None)
        return name if name is not None else str(value)

    def _disable_all_trigger_modes(self):
        trigger_selector = self._feature("TriggerSelector")
        trigger_mode = self._feature("TriggerMode")

        if hasattr(trigger_selector, "get_available_entries"):
            available_selectors = trigger_selector.get_available_entries()
        else:
            available_selectors = ("FrameStart",)

        selector_names = [self._enum_name(selector) for selector in available_selectors]
        if not selector_names:
            selector_names = ["FrameStart"]

        for selector_name in selector_names:
            trigger_selector.set(selector_name)
            trigger_mode.set("Off")

        if "FrameStart" in selector_names:
            trigger_selector.set("FrameStart")

        return tuple(selector_names)

    def _frame_handler(self, camera, stream, frame):
        try:
            status = frame.get_status()
            status_name = self._enum_name(status)
            if status_name != "Complete" and status != 0:
                raise RuntimeError(f"Received an incomplete VmbPy frame ({status_name})")

            if hasattr(frame, "as_numpy_ndarray"):
                image = np.array(frame.as_numpy_ndarray(), copy=True)
            elif hasattr(frame, "as_opencv_image"):
                image = np.array(frame.as_opencv_image(), copy=True)
            else:
                raise RuntimeError(
                    "VmbPy Frame does not provide NumPy/OpenCV export. "
                    "Install VmbPy with the numpy extra."
                )

            frame_id = frame.get_id()
            with self._frame_condition:
                self._latest_frame = image
                self.frame_id = frame_id
                self._frame_error = None
                self._frame_sequence += 1
                self._frame_condition.notify_all()
        except Exception as error:
            with self._frame_condition:
                self._frame_error = error
                self._frame_condition.notify_all()
        finally:
            camera.queue_frame(frame)

    def StartAcquisition(self):
        if self._capturing:
            return
        self.ResetBuffer()
        self.camera.start_streaming(
            handler=self._frame_handler,
            buffer_count=self._stream_buffer_count,
        )
        self._capturing = True

    def StopAcquisition(self):
        if not getattr(self, "_capturing", False):
            return
        camera = getattr(self, "camera", None)
        if camera is not None:
            camera.stop_streaming()
        self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        with self._frame_condition:
            self._latest_frame = None
            self._frame_error = None
            self.frame_id = None
            self._last_delivered_sequence = self._frame_sequence

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        with self._frame_condition:
            discarded_frames = min(
                int(max_frames),
                max(0, self._frame_sequence - self._last_delivered_sequence),
            )
        self.ResetBuffer()
        return discarded_frames

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
        if not self._capturing:
            return False
        trigger_command = self._feature("TriggerSoftware")
        if hasattr(trigger_command, "is_writeable"):
            return bool(trigger_command.is_writeable())
        if hasattr(trigger_command, "get_access_mode"):
            return bool(trigger_command.get_access_mode()[1])
        return True

    def WaitForSoftwareTriggerReady(self, timeout_ms=1000, poll_interval_s=0.001):
        deadline = time.monotonic() + float(timeout_ms) / 1000.0
        while time.monotonic() < deadline:
            if self.IsSoftwareTriggerReady():
                return True
            time.sleep(poll_interval_s)
        raise TimeoutError(f"Software trigger was not ready within {int(timeout_ms)} ms")

    def GetTriggerMode(self):
        self.trigger_mode = self._enum_name(self._get("TriggerMode"))
        try:
            self.trigger_selector = self._enum_name(self._get("TriggerSelector"))
        except Exception:
            self.trigger_selector = "FrameStart"

        try:
            self.acquisition_mode = self._enum_name(self._get("AcquisitionMode"))
        except Exception:
            self.acquisition_mode = "Continuous"

        if self.trigger_mode == "Off":
            self.trigger_source = "FreeRun"
        else:
            self.trigger_source = self._enum_name(self._get("TriggerSource"))

        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set("AcquisitionMode", "Continuous")
            disabled_trigger_selectors = self._disable_all_trigger_modes()
            self.ResetBuffer()
        finally:
            if was_capturing:
                self.StartAcquisition()
        trigger_state = self.GetTriggerMode()
        if self.verbose:
            print(
                "Allied Vision continuous mode: "
                f"AcquisitionMode={self.acquisition_mode}, "
                f"TriggerMode={self.trigger_mode}, "
                f"disabled selectors={disabled_trigger_selectors}"
            )
        return trigger_state

    def SetSoftwareTriggerMode(self):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set("AcquisitionMode", "Continuous")
            self._disable_all_trigger_modes()
            self._set("TriggerSelector", "FrameStart")
            self._set("TriggerSource", "Software")
            self._set("TriggerMode", "On")
            self.ResetBuffer()
        finally:
            if was_capturing:
                self.StartAcquisition()
        return self.GetTriggerMode()

    def FireSoftwareTrigger(self, wait_ready=True, ready_timeout_ms=1000, drain_stale_frames=True):
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            self.GetTriggerMode()
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            raise RuntimeError("Camera is not in software trigger mode")

        if wait_ready:
            self.WaitForSoftwareTriggerReady(timeout_ms=ready_timeout_ms)
        if drain_stale_frames:
            self.ResetBuffer()
        self._run("TriggerSoftware")
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self._set("AcquisitionMode", "Continuous")
            self._disable_all_trigger_modes()
            self._set("TriggerSelector", "FrameStart")
            self._set("TriggerSource", f"Line{int(lineNumber)}")
            self._set("TriggerActivation", "RisingEdge" if RiseEdgeOrFallEdge == 1 else "FallingEdge")
            self._set("TriggerMode", "On")
            self.ResetBuffer()
        finally:
            if was_capturing:
                self.StartAcquisition()
        self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
        return self.GetTriggerMode()

    def SetExposureTime(self, exposure_time):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.GetMaxMinFPS_ExposureTime()
            exposure_time = max(self.ExposureTimeMin, min(float(exposure_time), self.ExposureTimeMax))
            try:
                self._set("ExposureAuto", "Off")
            except Exception:
                pass
            self._set("ExposureTime", exposure_time)
        finally:
            if was_capturing:
                self.StartAcquisition()
        self.ExposureTime = self.GetExposureTime()
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = float(self._get("ExposureTime"))
        return self.ExposureTime

    def SetGain(self, gain):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            gain_min, gain_max, _ = self._limits("Gain")
            gain = max(float(gain_min), min(float(gain), float(gain_max)))
            try:
                self._set("GainAuto", "Off")
            except Exception:
                pass
            self._set("Gain", gain)
        finally:
            if was_capturing:
                self.StartAcquisition()
        self.gain = self.GetGain()
        return self.gain

    def GetGain(self):
        self.gain = float(self._get("Gain"))
        return self.gain

    def SetFPS(self, fps):
        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.GetMaxMinFPS_ExposureTime()
            fps = max(self.FPSMin, min(float(fps), self.FPSMax))
            try:
                self._set("AcquisitionFrameRateEnable", True)
            except Exception:
                pass
            self._set("AcquisitionFrameRate", fps)
        finally:
            if was_capturing:
                self.StartAcquisition()
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
        if not self._capturing:
            self.StartAcquisition()

        deadline = time.monotonic() + float(timeout_ms) / 1000.0
        with self._frame_condition:
            while self._frame_sequence <= self._last_delivered_sequence:
                if self._frame_error is not None:
                    error = self._frame_error
                    self._frame_error = None
                    raise RuntimeError("VmbPy failed while receiving a frame") from error

                remaining_seconds = deadline - time.monotonic()
                if remaining_seconds <= 0:
                    try:
                        trigger_mode, trigger_source = self.GetTriggerMode()
                        acquisition_mode = self.acquisition_mode
                    except Exception as state_error:
                        trigger_mode = f"unavailable ({state_error})"
                        trigger_source = "unavailable"
                        acquisition_mode = "unavailable"

                    is_streaming = "unavailable"
                    if hasattr(self.camera, "is_streaming"):
                        try:
                            is_streaming = bool(self.camera.is_streaming())
                        except Exception:
                            pass

                    raise TimeoutError(
                        f"No new camera frame arrived within {int(timeout_ms)} ms. "
                        f"Streaming={is_streaming}, AcquisitionMode={acquisition_mode}, "
                        f"TriggerMode={trigger_mode}, TriggerSource={trigger_source}"
                    )
                self._frame_condition.wait(remaining_seconds)

            image = self._latest_frame
            self._last_delivered_sequence = self._frame_sequence
            return np.array(image, copy=True)


AlliedVisionCameraObject = CameraObject
