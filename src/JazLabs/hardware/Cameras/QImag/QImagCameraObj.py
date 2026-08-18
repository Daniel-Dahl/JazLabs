import atexit
import ctypes
import time
import weakref

import numpy as np

from .oldversion.qcam import Camera as QCamCamera
from .oldversion.qcam import QCam_CamListItem


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
    Simple QImaging camera object using the local QCam ctypes wrapper.

    Exposure is in microseconds, matching the QCam qprmExposure parameter.
    """

    TRIGGER_FREERUN = 0
    TRIGGER_EDGE_HIGH = 1
    TRIGGER_EDGE_LOW = 2
    TRIGGER_SOFTWARE = 5

    def __init__(self, CameraSerialNumber, CalibrationFile=None, PixelSize=6.45e-6, verbose=False):
        if CameraSerialNumber is None:
            raise ValueError("CameraSerialNumber must not be None")
        requested_serial_number = str(CameraSerialNumber).strip()
        if not requested_serial_number:
            raise ValueError("CameraSerialNumber must not be empty")

        self.CameraSerialNumber = requested_serial_number
        self.CameraType = "QImaging"
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.grab_timeout_ms = None

        self.cam = QCamCamera()
        self.cam.PARAM_KEYS.setdefault("Trigger Type", 7)
        self._connect_to_camera(requested_serial_number)
        self.cam.setup_camera()

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
        self.offset = None
        self.pixel_format = None
        self.pixel_format_fc2 = None
        self.frame_id = None

        self.SetContinuousMode()
        self.GetROI()
        self.GetExposureTime()
        self.GetGain()
        self.GetPixelFormat()
        self.GetMaxMinFPS_ExposureTime()
        self.StartAcquisition()

        atexit.register(_shutdown_camera_ref, weakref.ref(self))

    def __del__(self):
        self.shutdown()

    def _check(self, result, message):
        if result != 0:
            raise RuntimeError(f"{message} failed with QCam error {result}")

    def _connect_to_camera(self, requested_serial_number):
        self._check(self.cam.load_driver(), "QCam_LoadDriver")

        max_cameras = 10
        camera_items = (QCam_CamListItem * max_cameras)()
        camera_count = ctypes.c_uint32(max_cameras)
        self._check(self.cam.list_cameras(ctypes.byref(camera_items[0]), ctypes.byref(camera_count)), "QCam_ListCameras")

        self.num_cameras = int(camera_count.value)
        print(f"{self.num_cameras} cameras detected:")
        selected_camera_item = None
        discovered_serial_numbers = []
        for k in range(self.num_cameras):
            item = camera_items[k]
            serial_number = str(item.uniqueId)
            discovered_serial_numbers.append(serial_number)
            print(f"{k}: QImaging camera serial number {serial_number}")
            if serial_number.casefold() == requested_serial_number.casefold():
                selected_camera_item = item

        if self.num_cameras <= 0:
            self.cam.release_driver()
            raise RuntimeError("No QImaging cameras detected")
        if selected_camera_item is None:
            self.cam.release_driver()
            raise ValueError(
                "QImaging camera with serial number "
                f"{requested_serial_number!r} was not found. Discovered serial "
                f"numbers: {', '.join(discovered_serial_numbers)}"
            )

        self.CameraSerialNumber = str(selected_camera_item.uniqueId)
        self._check(
            self.cam.open_camera(selected_camera_item.cameraId),
            "QCam_OpenCamera",
        )
        print(f"Using QImaging camera serial number {self.CameraSerialNumber}")

    def GetSerialNumber(self):
        return self.CameraSerialNumber

    def shutdown(self):
        if getattr(self, "_closed", True):
            return
        self._closed = True

        try:
            self.StopAcquisition()
            try:
                self.cam.QCam_Abort(self.cam.camera_handle)
            except Exception:
                pass
            try:
                self.cam.close_camera()
            except Exception:
                pass
        finally:
            try:
                self.cam.release_driver()
            except Exception:
                pass

    def _read_settings(self):
        result, _ = self.cam.QCam_ReadSettingsFromCam()
        self._check(result, "QCam_ReadSettingsFromCam")

    def _get_param(self, name):
        self._read_settings()
        result, value = self.cam.QCam_GetParam(self.cam.PARAM_KEYS[name])
        self._check(result, f"QCam_GetParam({name})")
        return int(value)

    def _set_param(self, name, value, clamp=True):
        value = int(value)
        if clamp:
            min_value, max_value = self._param_limits(name)
            value = max(min_value, min(value, max_value))

        result = self.cam.QCam_SetParam(self.cam.PARAM_KEYS[name], value)
        self._check(result, f"QCam_SetParam({name})")
        result = self.cam.QCam_SendSettingsToCam(self.cam.camera_handle)
        self._check(result, "QCam_SendSettingsToCam")
        return self._get_param(name)

    def _param_limits(self, name):
        param = self.cam.parameters.get(name)
        if param is not None and param.min_value is not None and param.max_value is not None:
            return int(param.min_value), int(param.max_value)

        key = self.cam.PARAM_KEYS[name]
        result, min_value = self.cam.QCam_GetParamMin(key)
        self._check(result, f"QCam_GetParamMin({name})")
        result, max_value = self.cam.QCam_GetParamMax(key)
        self._check(result, f"QCam_GetParamMax({name})")
        return int(min_value), int(max_value)

    def _get_info(self, name):
        result, value = self.cam.QCam_GetInfo(self.cam.INFO_KEYS[name])
        self._check(result, f"QCam_GetInfo({name})")
        return int(value)

    def StartAcquisition(self):
        if not self._capturing:
            try:
                self.cam.dll.QCam_SetStreaming.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                self.cam.dll.QCam_SetStreaming.restype = ctypes.c_uint32
                self._check(self.cam.dll.QCam_SetStreaming(self.cam.camera_handle, 1), "QCam_SetStreaming(1)")
            except AttributeError:
                pass
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            try:
                self.cam.dll.QCam_SetStreaming.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
                self.cam.dll.QCam_SetStreaming.restype = ctypes.c_uint32
                self.cam.dll.QCam_SetStreaming(self.cam.camera_handle, 0)
            except Exception:
                pass
            self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        try:
            self.cam.QCam_Abort(self.cam.camera_handle)
        except Exception:
            pass
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        self.frame_id = None

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        try:
            self.cam.QCam_Abort(self.cam.camera_handle)
        except Exception:
            return 0
        self.frame_id = None
        return 0

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError("QCam frame buffer sizing is not implemented in this wrapper.")

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
        trigger_type = self._get_param("Trigger Type")
        if trigger_type == self.TRIGGER_SOFTWARE:
            self.trigger_mode = "On"
            self.trigger_source = "Software"
        elif trigger_type == self.TRIGGER_EDGE_HIGH:
            self.trigger_mode = "On"
            self.trigger_source = "line 0"
            self.trigger_polarity = 1
        elif trigger_type == self.TRIGGER_EDGE_LOW:
            self.trigger_mode = "On"
            self.trigger_source = "line 0"
            self.trigger_polarity = -1
        else:
            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        self._set_param("Trigger Type", self.TRIGGER_FREERUN, clamp=False)
        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        self._set_param("Trigger Type", self.TRIGGER_SOFTWARE, clamp=False)
        self.ResetBuffer()
        return self.GetTriggerMode()

    def FireSoftwareTrigger(self, wait_ready=True, ready_timeout_ms=1000, drain_stale_frames=True):
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            self.GetTriggerMode()
        if self.trigger_mode != "On" or self.trigger_source != "Software":
            raise RuntimeError("Camera is not in software trigger mode")
        self._check(self.cam.QCam_Trigger(self.cam.camera_handle), "QCam_Trigger")
        return 0

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        trigger_type = self.TRIGGER_EDGE_HIGH if RiseEdgeOrFallEdge == 1 else self.TRIGGER_EDGE_LOW
        self._set_param("Trigger Type", trigger_type, clamp=False)
        self.trigger_polarity = 1 if RiseEdgeOrFallEdge == 1 else -1
        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetExposureTime(self, exposure_time):
        self.ExposureTime = self._set_param("Exposure", exposure_time)
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = self._get_param("Exposure")
        return self.ExposureTime

    def SetGain(self, gain):
        self.gain = self._set_param("Gain", gain)
        return self.gain

    def GetGain(self):
        self.gain = self._get_param("Gain")
        return self.gain

    def SetOffset(self, offset):
        self.offset = self._set_param("Offset", offset)
        return self.offset

    def GetOffset(self):
        self.offset = self._get_param("Offset")
        return self.offset

    def SetFPS(self, fps):
        raise NotImplementedError("QCam does not expose frame-rate control through this simple wrapper.")

    def GetFPS(self):
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin, self.ExposureTimeMax = self._param_limits("Exposure")
        self.FPSMin = None
        self.FPSMax = None
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def SetPixelFormat(self, pixel_format):
        if isinstance(pixel_format, str):
            pixel_format_key = pixel_format.strip().lower()
            if pixel_format_key == "mono8":
                image_format = 2
            elif pixel_format_key == "mono16":
                image_format = 3
            else:
                raise ValueError("pixel_format must be one of: mono8, mono16")
        else:
            image_format = int(pixel_format)

        self.pixel_format_fc2 = self._set_param("Image Format", image_format, clamp=False)
        return self.GetPixelFormat()

    def GetPixelFormat(self):
        self.pixel_format_fc2 = self._get_param("Image Format")
        bit_depth = self._get_info("Bit Depth")
        self.pixel_format = "mono8" if bit_depth <= 8 else "mono16"
        return self.pixel_format

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode="nearest"):
        ccd_width = self._get_info("CCD Width")
        ccd_height = self._get_info("CCD Height")

        if not enable:
            offset_x = 0
            offset_y = 0
            width = ccd_width
            height = ccd_height
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

        width = min(int(width), ccd_width)
        height = min(int(height), ccd_height)
        offset_x = min(max(int(offset_x), 0), ccd_width - width)
        offset_y = min(max(int(offset_y), 0), ccd_height - height)

        self._set_param("ROI X", offset_x, clamp=False)
        self._set_param("ROI Y", offset_y, clamp=False)
        self._set_param("ROI Width", width, clamp=False)
        self._set_param("ROI Height", height, clamp=False)
        self.cam.setup_camera()
        return self.GetROI()

    def GetROI(self):
        self.offset_x = self._get_param("ROI X")
        self.offset_y = self._get_param("ROI Y")
        self.width = self._get_info("Image Width")
        self.height = self._get_info("Image Height")
        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def GetFrameID(self):
        return self.frame_id

    def GetFrame(self, timeout_ms=None):
        raw_frame = self.cam.grab_frame()
        if raw_frame is None:
            raise RuntimeError("QCam_GrabFrame returned no frame")

        self.frame_id = int(raw_frame.frameNumber)
        byte_count = int(raw_frame.size or raw_frame.bufferSize)
        pixel_count = int(raw_frame.width * raw_frame.height)
        bytes_per_pixel = max(1, byte_count // max(1, pixel_count))
        dtype = np.uint16 if int(raw_frame.bits) > 8 or bytes_per_pixel > 1 else np.uint8

        p_buffer = ctypes.cast(raw_frame.pBuffer, ctypes.POINTER(ctypes.c_char * byte_count))
        frame = np.frombuffer(p_buffer.contents, dtype=dtype, count=pixel_count)
        return frame.reshape(int(raw_frame.height), int(raw_frame.width)).copy()


QImagCamraObject = CameraObject
QImagCameraObject = CameraObject
