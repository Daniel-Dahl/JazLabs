"""Small ctypes wrapper around the Xeneth C API."""

import ctypes
import os


I_OK = 0
E_NOT_SUPPORTED = 10005
E_NOT_FOUND = 10006
E_NO_FRAME = 10008

FT_NATIVE = 0
FT_8_BPP_GRAY = 1
FT_16_BPP_GRAY = 2
FT_32_BPP_GRAY = 3

XGF_BLOCKING = 1
XGF_NO_CONVERSION = 2
XLC_START_SOFTWARE_CORRECTION = 1

XEF_ENABLE_ALL = 0x0000FFFF
XEF_USE_CACHED = 0x01000000

XDS_AVAILABLE = 0
XDS_BUSY = 1
XDS_UNREACHABLE = 2


class XDeviceInformation(ctypes.Structure):
    """Packed layout from the SDK's XCamera.h header."""

    _pack_ = 1
    _fields_ = (
        ("size", ctypes.c_int),
        ("name", ctypes.c_char * 64),
        ("transport", ctypes.c_char * 64),
        ("url", ctypes.c_char * 256),
        ("address", ctypes.c_char * 64),
        ("serial", ctypes.c_uint),
        ("pid", ctypes.c_uint),
        ("state", ctypes.c_uint),
    )


class XenethError(RuntimeError):
    def __init__(self, code, function_name, message=None):
        self.code = int(code)
        self.function_name = str(function_name)
        detail = message or f"Xeneth error code {self.code}"
        super().__init__(f"{self.function_name} failed: {detail} ({self.code})")


class XenethLibrary:
    """Load Xeneth and expose its C functions as ordinary Python methods."""

    DEFAULT_DLL_PATHS = (
        r"C:\Program Files\Common Files\XenICs\Runtime\xeneth64.dll",
        r"C:\Program Files\Xeneth\Runtime\xeneth64.dll",
        r"C:\Program Files\Xeneth\Sdk\Bin\xeneth64.dll",
        "xeneth64.dll",
    )

    def __init__(self, dll_path=None):
        self.lib, self.dll_path = self._load_library(dll_path)
        self._set_function_signatures()

    def _load_library(self, dll_path):
        candidates = []
        for candidate in (
            dll_path,
            os.environ.get("XENETH_DLL_PATH"),
            *self.DEFAULT_DLL_PATHS,
        ):
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        load_errors = []
        for candidate in candidates:
            try:
                if hasattr(os, "add_dll_directory"):
                    dll_directory = os.path.dirname(candidate)
                    if dll_directory and os.path.isdir(dll_directory):
                        os.add_dll_directory(dll_directory)
                return ctypes.cdll.LoadLibrary(candidate), candidate
            except OSError as error:
                load_errors.append(f"{candidate}: {error}")

        attempted_paths = "\n".join(load_errors)
        raise FileNotFoundError(
            "Could not load the Xeneth library.\n"
            f"Tried:\n{attempted_paths}\n\n"
            "Pass dll_path or set XENETH_DLL_PATH."
        )

    def _set_function_signatures(self):
        self.lib.XC_OpenCamera.restype = ctypes.c_int32
        self.lib.XC_OpenCamera.argtypes = (
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        )
        self.lib.XC_CloseCamera.restype = None
        self.lib.XC_CloseCamera.argtypes = (ctypes.c_int32,)

        self.lib.XC_ErrorToString.restype = ctypes.c_int32
        self.lib.XC_ErrorToString.argtypes = (
            ctypes.c_ulong,
            ctypes.c_char_p,
            ctypes.c_int32,
        )

        self.lib.XC_IsInitialised.restype = ctypes.c_ubyte
        self.lib.XC_IsInitialised.argtypes = (ctypes.c_int32,)
        self.lib.XC_StartCapture.restype = ctypes.c_ulong
        self.lib.XC_StartCapture.argtypes = (ctypes.c_int32,)
        self.lib.XC_StopCapture.restype = ctypes.c_ulong
        self.lib.XC_StopCapture.argtypes = (ctypes.c_int32,)
        self.lib.XC_IsCapturing.restype = ctypes.c_ubyte
        self.lib.XC_IsCapturing.argtypes = (ctypes.c_int32,)

        self.lib.XC_GetWidth.restype = ctypes.c_ulong
        self.lib.XC_GetWidth.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetHeight.restype = ctypes.c_ulong
        self.lib.XC_GetHeight.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetMaxWidth.restype = ctypes.c_ulong
        self.lib.XC_GetMaxWidth.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetMaxHeight.restype = ctypes.c_ulong
        self.lib.XC_GetMaxHeight.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetFrameSize.restype = ctypes.c_ulong
        self.lib.XC_GetFrameSize.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetFrameType.restype = ctypes.c_int
        self.lib.XC_GetFrameType.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetBitSize.restype = ctypes.c_ubyte
        self.lib.XC_GetBitSize.argtypes = (ctypes.c_int32,)

        self.lib.XC_GetFrame.restype = ctypes.c_ulong
        self.lib.XC_GetFrame.argtypes = (
            ctypes.c_int32,
            ctypes.c_int,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_uint,
        )
        self.lib.XC_GetFrameCount.restype = ctypes.c_ulong
        self.lib.XC_GetFrameCount.argtypes = (ctypes.c_int32,)
        self.lib.XC_GetFrameRate.restype = ctypes.c_double
        self.lib.XC_GetFrameRate.argtypes = (ctypes.c_int32,)

        self.lib.XC_LoadSettings.restype = ctypes.c_ulong
        self.lib.XC_LoadSettings.argtypes = (ctypes.c_int32, ctypes.c_char_p)
        self.lib.XC_LoadCalibration.restype = ctypes.c_ulong
        self.lib.XC_LoadCalibration.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.c_ulong,
        )

        self.lib.XC_SetPropertyValue.restype = ctypes.c_ulong
        self.lib.XC_SetPropertyValue.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_char_p,
        )
        self.lib.XC_GetPropertyValue.restype = ctypes.c_ulong
        self.lib.XC_GetPropertyValue.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.c_int32,
        )

        self.lib.XC_SetPropertyValueL.restype = ctypes.c_ulong
        self.lib.XC_SetPropertyValueL.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.c_long,
            ctypes.c_char_p,
        )
        self.lib.XC_GetPropertyValueL.restype = ctypes.c_ulong
        self.lib.XC_GetPropertyValueL.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_long),
        )
        self.lib.XC_GetPropertyRangeL.restype = ctypes.c_ulong
        self.lib.XC_GetPropertyRangeL.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_long),
            ctypes.POINTER(ctypes.c_long),
        )

        self.lib.XC_SetPropertyValueF.restype = ctypes.c_ulong
        self.lib.XC_SetPropertyValueF.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.c_double,
            ctypes.c_char_p,
        )
        self.lib.XC_GetPropertyValueF.restype = ctypes.c_ulong
        self.lib.XC_GetPropertyValueF.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_double),
        )
        self.lib.XC_GetPropertyRangeF.restype = ctypes.c_ulong
        self.lib.XC_GetPropertyRangeF.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
        )

        self.lib.XCD_EnumerateDevices.restype = ctypes.c_ulong
        self.lib.XCD_EnumerateDevices.argtypes = (
            ctypes.POINTER(XDeviceInformation),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.c_uint,
        )

    def error_to_string(self, code):
        message_buffer = ctypes.create_string_buffer(512)
        self.lib.XC_ErrorToString(int(code), message_buffer, len(message_buffer))
        message = message_buffer.value.decode(errors="replace")
        return message or f"Xeneth error code {int(code)}"

    def check_error(self, code, function_name):
        if int(code) != I_OK:
            raise XenethError(code, function_name, self.error_to_string(code))

    def open_camera(self, camera_name):
        handle = self.lib.XC_OpenCamera(camera_name.encode("utf-8"), None, None)
        if not handle or not self.lib.XC_IsInitialised(handle):
            if handle:
                self.lib.XC_CloseCamera(handle)
            raise RuntimeError(f"Could not initialise Xeneth camera {camera_name!r}")
        return handle

    def enumerate_devices(self):
        device_count = ctypes.c_uint(0)
        error = self.lib.XCD_EnumerateDevices(
            None,
            ctypes.byref(device_count),
            XEF_ENABLE_ALL,
        )
        self.check_error(error, "XCD_EnumerateDevices(discover)")

        if device_count.value == 0:
            return []

        device_array = (XDeviceInformation * device_count.value)()
        for device_information in device_array:
            device_information.size = ctypes.sizeof(XDeviceInformation)

        cached_device_count = ctypes.c_uint(device_count.value)
        error = self.lib.XCD_EnumerateDevices(
            device_array,
            ctypes.byref(cached_device_count),
            XEF_USE_CACHED,
        )
        self.check_error(error, "XCD_EnumerateDevices(cached)")

        devices = []
        for index in range(cached_device_count.value):
            device_information = device_array[index]
            devices.append(
                {
                    "name": device_information.name.decode(errors="replace"),
                    "transport": device_information.transport.decode(
                        errors="replace"
                    ),
                    "url": device_information.url.decode(errors="replace"),
                    "address": device_information.address.decode(
                        errors="replace"
                    ),
                    "serial": int(device_information.serial),
                    "pid": int(device_information.pid),
                    "state": int(device_information.state),
                }
            )
        return devices

    def close_camera(self, handle):
        self.lib.XC_CloseCamera(handle)

    def start_capture(self, handle):
        self.check_error(self.lib.XC_StartCapture(handle), "XC_StartCapture")

    def stop_capture(self, handle):
        self.check_error(self.lib.XC_StopCapture(handle), "XC_StopCapture")

    def get_width(self, handle):
        return int(self.lib.XC_GetWidth(handle))

    def get_height(self, handle):
        return int(self.lib.XC_GetHeight(handle))

    def get_max_width(self, handle):
        return int(self.lib.XC_GetMaxWidth(handle))

    def get_max_height(self, handle):
        return int(self.lib.XC_GetMaxHeight(handle))

    def get_frame_size(self, handle):
        return int(self.lib.XC_GetFrameSize(handle))

    def get_frame_type(self, handle):
        return int(self.lib.XC_GetFrameType(handle))

    def get_bit_size(self, handle):
        return int(self.lib.XC_GetBitSize(handle))

    def get_frame(self, handle, frame_buffer):
        error = self.lib.XC_GetFrame(
            handle,
            FT_NATIVE,
            XGF_BLOCKING | XGF_NO_CONVERSION,
            frame_buffer.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_uint(frame_buffer.nbytes),
        )
        self.check_error(error, "XC_GetFrame")

    def try_get_frame(self, handle, frame_buffer):
        error = self.lib.XC_GetFrame(
            handle,
            FT_NATIVE,
            XGF_NO_CONVERSION,
            frame_buffer.ctypes.data_as(ctypes.c_void_p),
            ctypes.c_uint(frame_buffer.nbytes),
        )
        if int(error) == E_NO_FRAME:
            return False
        self.check_error(error, "XC_GetFrame(nonblocking)")
        return True

    def drain_frames(self, handle, max_frames=64):
        frame_size = self.get_frame_size(handle)
        frame_buffer = ctypes.create_string_buffer(frame_size)
        drained_frame_count = 0

        while drained_frame_count < int(max_frames):
            error = self.lib.XC_GetFrame(
                handle,
                FT_NATIVE,
                0,
                frame_buffer,
                ctypes.c_uint(frame_size),
            )
            if int(error) == E_NO_FRAME:
                break
            self.check_error(error, "XC_GetFrame(drain)")
            drained_frame_count += 1

        return drained_frame_count

    def get_frame_count(self, handle):
        return int(self.lib.XC_GetFrameCount(handle))

    def get_frame_rate(self, handle):
        return float(self.lib.XC_GetFrameRate(handle))

    def get_property(self, handle, property_name):
        value_buffer = ctypes.create_string_buffer(256)
        error = self.lib.XC_GetPropertyValue(
            handle,
            property_name.encode("utf-8"),
            value_buffer,
            len(value_buffer),
        )
        self.check_error(error, f"XC_GetPropertyValue({property_name})")
        return value_buffer.value.decode(errors="replace")

    def set_property(self, handle, property_name, value, unit=""):
        error = self.lib.XC_SetPropertyValue(
            handle,
            property_name.encode("utf-8"),
            str(value).encode("utf-8"),
            unit.encode("utf-8"),
        )
        self.check_error(error, f"XC_SetPropertyValue({property_name})")
        return self.get_property(handle, property_name)

    def get_property_long(self, handle, property_name):
        value = ctypes.c_long()
        error = self.lib.XC_GetPropertyValueL(
            handle,
            property_name.encode("utf-8"),
            ctypes.byref(value),
        )
        self.check_error(error, f"XC_GetPropertyValueL({property_name})")
        return int(value.value)

    def set_property_long(self, handle, property_name, value, unit=""):
        error = self.lib.XC_SetPropertyValueL(
            handle,
            property_name.encode("utf-8"),
            int(value),
            unit.encode("utf-8"),
        )
        self.check_error(error, f"XC_SetPropertyValueL({property_name})")
        return int(value)

    def get_property_range_long(self, handle, property_name):
        minimum = ctypes.c_long()
        maximum = ctypes.c_long()
        error = self.lib.XC_GetPropertyRangeL(
            handle,
            property_name.encode("utf-8"),
            ctypes.byref(minimum),
            ctypes.byref(maximum),
        )
        self.check_error(error, f"XC_GetPropertyRangeL({property_name})")
        return int(minimum.value), int(maximum.value)

    def get_property_float(self, handle, property_name):
        value = ctypes.c_double()
        error = self.lib.XC_GetPropertyValueF(
            handle,
            property_name.encode("utf-8"),
            ctypes.byref(value),
        )
        self.check_error(error, f"XC_GetPropertyValueF({property_name})")
        return float(value.value)

    def set_property_float(self, handle, property_name, value, unit=""):
        error = self.lib.XC_SetPropertyValueF(
            handle,
            property_name.encode("utf-8"),
            float(value),
            unit.encode("utf-8"),
        )
        self.check_error(error, f"XC_SetPropertyValueF({property_name})")
        return self.get_property_float(handle, property_name)

    def get_property_range_float(self, handle, property_name):
        minimum = ctypes.c_double()
        maximum = ctypes.c_double()
        error = self.lib.XC_GetPropertyRangeF(
            handle,
            property_name.encode("utf-8"),
            ctypes.byref(minimum),
            ctypes.byref(maximum),
        )
        self.check_error(error, f"XC_GetPropertyRangeF({property_name})")
        return float(minimum.value), float(maximum.value)

    def load_settings(self, handle, settings_path):
        error = self.lib.XC_LoadSettings(
            handle,
            os.fspath(settings_path).encode("utf-8"),
        )
        self.check_error(error, "XC_LoadSettings")

    def load_calibration(self, handle, calibration_path):
        error = self.lib.XC_LoadCalibration(
            handle,
            os.fspath(calibration_path).encode("utf-8"),
            XLC_START_SOFTWARE_CORRECTION,
        )
        self.check_error(error, "XC_LoadCalibration")
