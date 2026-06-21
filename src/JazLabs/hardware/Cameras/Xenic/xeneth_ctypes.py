import ctypes
import os


I_OK = 0
I_DIRTY = 1
E_BUG = 10000
E_NOINIT = 10001
E_LOGICLOADFAILED = 10002
E_INTERFACE_ERROR = 10003
E_OUT_OF_RANGE = 10004
E_NOT_SUPPORTED = 10005
E_NOT_FOUND = 10006
E_FILTER_DONE = 10007
E_NO_FRAME = 10008
E_SAVE_ERROR = 10009
E_MISMATCHED = 10010
E_BUSY = 10011
E_INVALID_HANDLE = 10012
E_TIMEOUT = 10013
E_FRAMEGRABBER = 10014
E_NO_CONVERSION = 10015
E_FILTER_SKIP_FRAME = 10016
E_WRONG_VERSION = 10017
E_PACKET_ERROR = 10018
E_WRONG_FORMAT = 10019
E_WRONG_SIZE = 10020
E_CAPSTOP = 10021
E_OUT_OF_MEMORY = 10022


class FrameType:
    FT_UNKNOWN = -1
    FT_NATIVE = 0
    FT_8_BPP_GRAY = 1
    FT_16_BPP_GRAY = 2
    FT_32_BPP_GRAY = 3
    FT_32_BPP_RGBA = 4
    FT_32_BPP_RGB = 5
    FT_32_BPP_BGRA = 6
    FT_32_BPP_BGR = 7


class XGetFrameFlags:
    XGF_BLOCKING = 1
    XGF_NO_CONVERSION = 2
    XGF_FETCH_PFF = 4


class XLoadCalibrationFlags:
    XLC_START_SOFTWARE_CORRECTION = 1


FT_NATIVE = FrameType.FT_NATIVE
FT_8_BPP_GRAY = FrameType.FT_8_BPP_GRAY
FT_16_BPP_GRAY = FrameType.FT_16_BPP_GRAY
FT_32_BPP_GRAY = FrameType.FT_32_BPP_GRAY

XGF_BLOCKING = XGetFrameFlags.XGF_BLOCKING
XGF_NO_CONVERSION = XGetFrameFlags.XGF_NO_CONVERSION
XLC_START_SOFTWARE_CORRECTION = XLoadCalibrationFlags.XLC_START_SOFTWARE_CORRECTION


def _default_dll_path():
    candidates = [
        os.environ.get("XENETH_DLL_PATH"),
        r"C:\Program Files\Common Files\XenICs\Runtime\xeneth64.dll",
        r"C:\Program Files\Xeneth\Runtime\xeneth64.dll",
        r"C:\Program Files\Xeneth\Sdk\Bin\xeneth64.dll",
        "xeneth64.dll",
    ]
    for path in candidates:
        if path and (os.path.exists(path) or path == "xeneth64.dll"):
            return path
    return "xeneth64.dll"


def _load_xeneth_library(user_path=None):
    candidates = []
    if user_path:
        candidates.append(user_path)

    default_path = _default_dll_path()
    if default_path not in candidates:
        candidates.append(default_path)

    load_errors = []
    for candidate in candidates:
        try:
            if hasattr(os, "add_dll_directory"):
                dll_dir = os.path.dirname(candidate)
                if dll_dir and os.path.isdir(dll_dir):
                    os.add_dll_directory(dll_dir)
            return ctypes.cdll.LoadLibrary(candidate), candidate
        except OSError as exc:
            load_errors.append(f"{candidate}: {exc}")

    joined = "\n".join(load_errors)
    raise FileNotFoundError(
        "Could not load Xeneth library.\n"
        "Tried these candidates:\n"
        f"{joined}\n\n"
        "Set XENETH_DLL_PATH explicitly if needed."
    )


class XenethError(RuntimeError):
    def __init__(self, code, func, message=None):
        self.code = int(code)
        self.func = str(func)
        detail = message or f"Xeneth error code {self.code}"
        super().__init__(f"{self.func} failed: {detail} ({self.code})")


class XenethLibrary:
    def __init__(self, dll_path=None):
        self.lib, self.dll_path = _load_xeneth_library(dll_path)
        self._set_prototypes()

    def _set_prototypes(self):
        lib = self.lib

        lib.XC_OpenCamera.restype = ctypes.c_int32
        lib.XC_OpenCamera.argtypes = (ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p)

        lib.XC_CloseCamera.argtypes = (ctypes.c_int32,)

        lib.XC_ErrorToString.restype = ctypes.c_int32
        lib.XC_ErrorToString.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_int32)

        lib.XC_IsInitialised.restype = ctypes.c_int32
        lib.XC_IsInitialised.argtypes = (ctypes.c_int32,)

        lib.XC_StartCapture.restype = ctypes.c_ulong
        lib.XC_StartCapture.argtypes = (ctypes.c_int32,)

        lib.XC_StopCapture.restype = ctypes.c_ulong
        lib.XC_StopCapture.argtypes = (ctypes.c_int32,)

        lib.XC_IsCapturing.restype = ctypes.c_bool
        lib.XC_IsCapturing.argtypes = (ctypes.c_int32,)

        lib.XC_GetWidth.restype = ctypes.c_ulong
        lib.XC_GetWidth.argtypes = (ctypes.c_int32,)

        lib.XC_GetHeight.restype = ctypes.c_ulong
        lib.XC_GetHeight.argtypes = (ctypes.c_int32,)

        lib.XC_GetFrameSize.restype = ctypes.c_ulong
        lib.XC_GetFrameSize.argtypes = (ctypes.c_int32,)

        lib.XC_GetFrameType.restype = ctypes.c_ulong
        lib.XC_GetFrameType.argtypes = (ctypes.c_int32,)

        lib.XC_GetBitSize.restype = ctypes.c_ubyte
        lib.XC_GetBitSize.argtypes = (ctypes.c_int32,)

        lib.XC_GetFrame.restype = ctypes.c_ulong
        lib.XC_GetFrame.argtypes = (ctypes.c_int32, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_uint)

        lib.XC_GetFrameCount.restype = ctypes.c_ulong
        lib.XC_GetFrameCount.argtypes = (ctypes.c_int32,)

        lib.XC_GetFrameRate.restype = ctypes.c_double
        lib.XC_GetFrameRate.argtypes = (ctypes.c_int32,)

        lib.XC_LoadSettings.restype = ctypes.c_ulong
        lib.XC_LoadSettings.argtypes = (ctypes.c_int32, ctypes.c_char_p)

        lib.XC_LoadCalibration.restype = ctypes.c_ulong
        lib.XC_LoadCalibration.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_ulong)

        lib.XC_SetPropertyValue.restype = ctypes.c_ulong
        lib.XC_SetPropertyValue.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p)

        lib.XC_SetPropertyValueL.restype = ctypes.c_ulong
        lib.XC_SetPropertyValueL.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_long, ctypes.c_char_p)

        lib.XC_SetPropertyValueF.restype = ctypes.c_ulong
        lib.XC_SetPropertyValueF.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_double, ctypes.c_char_p)

        lib.XC_SetPropertyValueE.restype = ctypes.c_ulong
        lib.XC_SetPropertyValueE.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p)

        lib.XC_GetPropertyValue.restype = ctypes.c_ulong
        lib.XC_GetPropertyValue.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32)

        lib.XC_GetPropertyValueL.restype = ctypes.c_ulong
        lib.XC_GetPropertyValueL.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_long))

        lib.XC_GetPropertyValueF.restype = ctypes.c_ulong
        lib.XC_GetPropertyValueF.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double))

        lib.XC_GetPropertyValueE.restype = ctypes.c_ulong
        lib.XC_GetPropertyValueE.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int32)

        lib.XC_GetPropertyRangeF.restype = ctypes.c_ulong
        lib.XC_GetPropertyRangeF.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_double),
            ctypes.POINTER(ctypes.c_double),
        )

        lib.XC_GetPropertyRangeL.restype = ctypes.c_ulong
        lib.XC_GetPropertyRangeL.argtypes = (
            ctypes.c_int32,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_long),
            ctypes.POINTER(ctypes.c_long),
        )

        lib.XC_FLT_Queue.restype = ctypes.c_ulong
        lib.XC_FLT_Queue.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p)

    def error_to_string(self, code):
        buf = ctypes.create_string_buffer(512)
        try:
            self.lib.XC_ErrorToString(int(code), buf, len(buf))
            msg = buf.value.decode(errors="replace")
        except Exception:
            msg = ""
        return msg or f"Xeneth error code {int(code)}"

    def check_error(self, code, func):
        if int(code) != I_OK:
            raise XenethError(code, func, self.error_to_string(code))

