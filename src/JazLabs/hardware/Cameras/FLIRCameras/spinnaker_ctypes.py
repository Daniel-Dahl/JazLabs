import ctypes
import ctypes.util
import os
import platform

import numpy as np


MAX_STRING_LENGTH = 512
SPINNAKER_ERR_SUCCESS = 0


if platform.system() == "Windows":
    DEFAULT_SPINNAKER_LIBRARY_CANDIDATES = [
        os.environ.get("SPINNAKER_C_DLL_PATH"),
        r"C:\Program Files\FLIR Systems\Spinnaker\bin64\Spinnaker_C_v140.dll",
        r"C:\Program Files\Teledyne\Spinnaker\bin64\Spinnaker_C_v140.dll",
        "Spinnaker_C_v140.dll",
    ]
else:
    DEFAULT_SPINNAKER_LIBRARY_CANDIDATES = [
        os.environ.get("SPINNAKER_C_DLL_PATH"),
        "/usr/lib/libSpinnaker_C.so",
        "/usr/lib64/libSpinnaker_C.so",
        "/usr/lib/x86_64-linux-gnu/libSpinnaker_C.so",
        "/opt/spinnaker/lib/libSpinnaker_C.so",
        "libSpinnaker_C.so",
        ctypes.util.find_library("Spinnaker_C"),
    ]


def _load_spinnaker_library(user_path=None):
    candidates = []
    if user_path:
        candidates.append(user_path)

    for candidate in DEFAULT_SPINNAKER_LIBRARY_CANDIDATES:
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    load_errors = []
    for candidate in candidates:
        try:
            lib = ctypes.cdll.LoadLibrary(candidate)
            return lib, candidate
        except OSError as e:
            load_errors.append(f"{candidate}: {e}")

    joined = "\n".join(load_errors)
    raise FileNotFoundError(
        "Could not load the Spinnaker C library.\n"
        "Tried these candidates:\n"
        f"{joined}\n\n"
        "Set SPINNAKER_C_DLL_PATH explicitly if needed."
    )


class SpinnakerError(RuntimeError):
    def __init__(self, code, func):
        super().__init__(f"{func} failed with Spinnaker error code {int(code)}")
        self.code = int(code)
        self.func = func


def _check_error(code, func):
    if int(code) != SPINNAKER_ERR_SUCCESS:
        raise SpinnakerError(code, func)


class spinLibraryVersion(ctypes.Structure):
    _fields_ = [
        ("major", ctypes.c_uint),
        ("minor", ctypes.c_uint),
        ("type", ctypes.c_uint),
        ("build", ctypes.c_uint),
    ]


class SpinnakerLibrary:
    def __init__(self, dll_path=None):
        self.lib, self.dll_path = _load_spinnaker_library(dll_path)
        self._set_prototypes()

    def _set_prototypes(self):
        lib = self.lib

        lib.spinSystemGetInstance.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.spinSystemGetInstance.restype = ctypes.c_int
        lib.spinSystemReleaseInstance.argtypes = [ctypes.c_void_p]
        lib.spinSystemReleaseInstance.restype = ctypes.c_int
        lib.spinSystemGetCameras.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.spinSystemGetCameras.restype = ctypes.c_int
        lib.spinSystemGetLibraryVersion.argtypes = [ctypes.c_void_p, ctypes.POINTER(spinLibraryVersion)]
        lib.spinSystemGetLibraryVersion.restype = ctypes.c_int

        lib.spinCameraListCreateEmpty.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.spinCameraListCreateEmpty.restype = ctypes.c_int
        lib.spinCameraListDestroy.argtypes = [ctypes.c_void_p]
        lib.spinCameraListDestroy.restype = ctypes.c_int
        lib.spinCameraListClear.argtypes = [ctypes.c_void_p]
        lib.spinCameraListClear.restype = ctypes.c_int
        lib.spinCameraListGetSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.spinCameraListGetSize.restype = ctypes.c_int
        lib.spinCameraListGet.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        lib.spinCameraListGet.restype = ctypes.c_int

        lib.spinCameraInit.argtypes = [ctypes.c_void_p]
        lib.spinCameraInit.restype = ctypes.c_int
        lib.spinCameraDeInit.argtypes = [ctypes.c_void_p]
        lib.spinCameraDeInit.restype = ctypes.c_int
        lib.spinCameraRelease.argtypes = [ctypes.c_void_p]
        lib.spinCameraRelease.restype = ctypes.c_int
        lib.spinCameraGetNodeMap.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.spinCameraGetNodeMap.restype = ctypes.c_int
        lib.spinCameraGetTLDeviceNodeMap.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.spinCameraGetTLDeviceNodeMap.restype = ctypes.c_int
        lib.spinCameraBeginAcquisition.argtypes = [ctypes.c_void_p]
        lib.spinCameraBeginAcquisition.restype = ctypes.c_int
        lib.spinCameraEndAcquisition.argtypes = [ctypes.c_void_p]
        lib.spinCameraEndAcquisition.restype = ctypes.c_int
        lib.spinCameraGetNextImageEx.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint64,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.spinCameraGetNextImageEx.restype = ctypes.c_int

        lib.spinNodeMapGetNode.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.spinNodeMapGetNode.restype = ctypes.c_int
        lib.spinNodeIsImplemented.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]
        lib.spinNodeIsImplemented.restype = ctypes.c_int
        lib.spinNodeIsAvailable.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]
        lib.spinNodeIsAvailable.restype = ctypes.c_int
        lib.spinNodeIsReadable.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]
        lib.spinNodeIsReadable.restype = ctypes.c_int
        lib.spinNodeIsWritable.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]
        lib.spinNodeIsWritable.restype = ctypes.c_int

        lib.spinIntegerGetValue.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
        lib.spinIntegerGetValue.restype = ctypes.c_int
        lib.spinIntegerSetValue.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.spinIntegerSetValue.restype = ctypes.c_int
        lib.spinIntegerGetMin.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
        lib.spinIntegerGetMin.restype = ctypes.c_int
        lib.spinIntegerGetMax.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
        lib.spinIntegerGetMax.restype = ctypes.c_int
        lib.spinIntegerGetInc.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
        lib.spinIntegerGetInc.restype = ctypes.c_int

        lib.spinFloatGetValue.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
        lib.spinFloatGetValue.restype = ctypes.c_int
        lib.spinFloatSetValue.argtypes = [ctypes.c_void_p, ctypes.c_double]
        lib.spinFloatSetValue.restype = ctypes.c_int
        lib.spinFloatGetMin.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
        lib.spinFloatGetMin.restype = ctypes.c_int
        lib.spinFloatGetMax.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_double)]
        lib.spinFloatGetMax.restype = ctypes.c_int

        lib.spinBooleanGetValue.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint8)]
        lib.spinBooleanGetValue.restype = ctypes.c_int
        lib.spinBooleanSetValue.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
        lib.spinBooleanSetValue.restype = ctypes.c_int

        lib.spinEnumerationGetEntryByName.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        lib.spinEnumerationGetEntryByName.restype = ctypes.c_int
        lib.spinEnumerationGetCurrentEntry.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.spinEnumerationGetCurrentEntry.restype = ctypes.c_int
        lib.spinEnumerationSetIntValue.argtypes = [ctypes.c_void_p, ctypes.c_int64]
        lib.spinEnumerationSetIntValue.restype = ctypes.c_int
        lib.spinEnumerationEntryGetIntValue.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
        lib.spinEnumerationEntryGetIntValue.restype = ctypes.c_int
        lib.spinEnumerationEntryGetSymbolic.argtypes = [
            ctypes.c_void_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_size_t),
        ]
        lib.spinEnumerationEntryGetSymbolic.restype = ctypes.c_int

        lib.spinCommandExecute.argtypes = [ctypes.c_void_p]
        lib.spinCommandExecute.restype = ctypes.c_int

        lib.spinImageRelease.argtypes = [ctypes.c_void_p]
        lib.spinImageRelease.restype = ctypes.c_int
        lib.spinImageGetStatus.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        lib.spinImageGetStatus.restype = ctypes.c_int
        lib.spinImageGetWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.spinImageGetWidth.restype = ctypes.c_int
        lib.spinImageGetHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.spinImageGetHeight.restype = ctypes.c_int
        lib.spinImageGetStride.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.spinImageGetStride.restype = ctypes.c_int
        lib.spinImageGetBufferSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.spinImageGetBufferSize.restype = ctypes.c_int
        lib.spinImageGetData.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.spinImageGetData.restype = ctypes.c_int
        lib.spinImageGetBitsPerPixel.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        lib.spinImageGetBitsPerPixel.restype = ctypes.c_int
        lib.spinImageGetFrameID.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        lib.spinImageGetFrameID.restype = ctypes.c_int

    def get_system_instance(self):
        system = ctypes.c_void_p()
        _check_error(self.lib.spinSystemGetInstance(ctypes.byref(system)), "spinSystemGetInstance")
        return system

    def release_system_instance(self, system):
        _check_error(self.lib.spinSystemReleaseInstance(system), "spinSystemReleaseInstance")

    def create_camera_list(self):
        camera_list = ctypes.c_void_p()
        _check_error(
            self.lib.spinCameraListCreateEmpty(ctypes.byref(camera_list)),
            "spinCameraListCreateEmpty",
        )
        return camera_list

    def destroy_camera_list(self, camera_list):
        _check_error(self.lib.spinCameraListDestroy(camera_list), "spinCameraListDestroy")

    def get_cameras(self, system, camera_list):
        _check_error(self.lib.spinSystemGetCameras(system, camera_list), "spinSystemGetCameras")

    def get_camera_list_size(self, camera_list):
        size = ctypes.c_size_t()
        _check_error(
            self.lib.spinCameraListGetSize(camera_list, ctypes.byref(size)),
            "spinCameraListGetSize",
        )
        return int(size.value)

    def get_camera_from_index(self, camera_list, index):
        camera = ctypes.c_void_p()
        _check_error(
            self.lib.spinCameraListGet(camera_list, ctypes.c_size_t(index), ctypes.byref(camera)),
            "spinCameraListGet",
        )
        return camera

    def init_camera(self, camera):
        _check_error(self.lib.spinCameraInit(camera), "spinCameraInit")

    def deinit_camera(self, camera):
        _check_error(self.lib.spinCameraDeInit(camera), "spinCameraDeInit")

    def release_camera(self, camera):
        _check_error(self.lib.spinCameraRelease(camera), "spinCameraRelease")

    def get_node_map(self, camera):
        node_map = ctypes.c_void_p()
        _check_error(self.lib.spinCameraGetNodeMap(camera, ctypes.byref(node_map)), "spinCameraGetNodeMap")
        return node_map

    def begin_acquisition(self, camera):
        _check_error(self.lib.spinCameraBeginAcquisition(camera), "spinCameraBeginAcquisition")

    def end_acquisition(self, camera):
        _check_error(self.lib.spinCameraEndAcquisition(camera), "spinCameraEndAcquisition")

    def get_next_image(self, camera, timeout_ms):
        image = ctypes.c_void_p()
        _check_error(
            self.lib.spinCameraGetNextImageEx(camera, ctypes.c_uint64(timeout_ms), ctypes.byref(image)),
            "spinCameraGetNextImageEx",
        )
        return image

    def release_image(self, image):
        _check_error(self.lib.spinImageRelease(image), "spinImageRelease")

    def get_node(self, node_map, name):
        node = ctypes.c_void_p()
        _check_error(
            self.lib.spinNodeMapGetNode(node_map, name.encode("ascii"), ctypes.byref(node)),
            f"spinNodeMapGetNode({name})",
        )
        return node

    def node_is_readable(self, node):
        result = ctypes.c_uint8()
        _check_error(self.lib.spinNodeIsReadable(node, ctypes.byref(result)), "spinNodeIsReadable")
        return bool(result.value)

    def node_is_writable(self, node):
        result = ctypes.c_uint8()
        _check_error(self.lib.spinNodeIsWritable(node, ctypes.byref(result)), "spinNodeIsWritable")
        return bool(result.value)

    def node_is_available(self, node):
        result = ctypes.c_uint8()
        _check_error(self.lib.spinNodeIsAvailable(node, ctypes.byref(result)), "spinNodeIsAvailable")
        return bool(result.value)

    def get_integer(self, node_map, name):
        node = self.get_node(node_map, name)
        value = ctypes.c_int64()
        _check_error(self.lib.spinIntegerGetValue(node, ctypes.byref(value)), f"spinIntegerGetValue({name})")
        return int(value.value)

    def set_integer(self, node_map, name, value):
        node = self.get_node(node_map, name)
        _check_error(self.lib.spinIntegerSetValue(node, ctypes.c_int64(value)), f"spinIntegerSetValue({name})")

    def get_integer_limits(self, node_map, name):
        node = self.get_node(node_map, name)
        minimum = ctypes.c_int64()
        maximum = ctypes.c_int64()
        increment = ctypes.c_int64()
        _check_error(self.lib.spinIntegerGetMin(node, ctypes.byref(minimum)), f"spinIntegerGetMin({name})")
        _check_error(self.lib.spinIntegerGetMax(node, ctypes.byref(maximum)), f"spinIntegerGetMax({name})")
        _check_error(self.lib.spinIntegerGetInc(node, ctypes.byref(increment)), f"spinIntegerGetInc({name})")
        return int(minimum.value), int(maximum.value), int(increment.value)

    def get_float(self, node_map, name):
        node = self.get_node(node_map, name)
        value = ctypes.c_double()
        _check_error(self.lib.spinFloatGetValue(node, ctypes.byref(value)), f"spinFloatGetValue({name})")
        return float(value.value)

    def set_float(self, node_map, name, value):
        node = self.get_node(node_map, name)
        _check_error(self.lib.spinFloatSetValue(node, ctypes.c_double(value)), f"spinFloatSetValue({name})")

    def get_float_limits(self, node_map, name):
        node = self.get_node(node_map, name)
        minimum = ctypes.c_double()
        maximum = ctypes.c_double()
        _check_error(self.lib.spinFloatGetMin(node, ctypes.byref(minimum)), f"spinFloatGetMin({name})")
        _check_error(self.lib.spinFloatGetMax(node, ctypes.byref(maximum)), f"spinFloatGetMax({name})")
        return float(minimum.value), float(maximum.value)

    def get_boolean(self, node_map, name):
        node = self.get_node(node_map, name)
        value = ctypes.c_uint8()
        _check_error(self.lib.spinBooleanGetValue(node, ctypes.byref(value)), f"spinBooleanGetValue({name})")
        return bool(value.value)

    def set_boolean(self, node_map, name, value):
        node = self.get_node(node_map, name)
        _check_error(
            self.lib.spinBooleanSetValue(node, ctypes.c_uint8(1 if value else 0)),
            f"spinBooleanSetValue({name})",
        )

    def get_enumeration_symbol(self, node_map, name):
        enum_node = self.get_node(node_map, name)
        entry = ctypes.c_void_p()
        _check_error(
            self.lib.spinEnumerationGetCurrentEntry(enum_node, ctypes.byref(entry)),
            f"spinEnumerationGetCurrentEntry({name})",
        )
        return self.get_enumeration_entry_symbol(entry)

    def set_enumeration_symbol(self, node_map, name, symbol):
        enum_node = self.get_node(node_map, name)
        entry = ctypes.c_void_p()
        _check_error(
            self.lib.spinEnumerationGetEntryByName(enum_node, symbol.encode("ascii"), ctypes.byref(entry)),
            f"spinEnumerationGetEntryByName({name}, {symbol})",
        )
        int_value = ctypes.c_int64()
        _check_error(
            self.lib.spinEnumerationEntryGetIntValue(entry, ctypes.byref(int_value)),
            f"spinEnumerationEntryGetIntValue({symbol})",
        )
        _check_error(
            self.lib.spinEnumerationSetIntValue(enum_node, int_value),
            f"spinEnumerationSetIntValue({name}, {symbol})",
        )

    def get_enumeration_entry_symbol(self, entry):
        length = ctypes.c_size_t(MAX_STRING_LENGTH)
        buffer = ctypes.create_string_buffer(MAX_STRING_LENGTH)
        _check_error(
            self.lib.spinEnumerationEntryGetSymbolic(entry, buffer, ctypes.byref(length)),
            "spinEnumerationEntryGetSymbolic",
        )
        return buffer.value.decode("ascii", errors="replace")

    def execute_command(self, node_map, name):
        node = self.get_node(node_map, name)
        _check_error(self.lib.spinCommandExecute(node), f"spinCommandExecute({name})")

    def get_image_frame_id(self, image):
        frame_id = ctypes.c_uint64()
        _check_error(self.lib.spinImageGetFrameID(image, ctypes.byref(frame_id)), "spinImageGetFrameID")
        return int(frame_id.value)

    def image_to_numpy(self, image):
        status = ctypes.c_uint()
        _check_error(self.lib.spinImageGetStatus(image, ctypes.byref(status)), "spinImageGetStatus")
        if int(status.value) != 0:
            raise RuntimeError(f"Spinnaker returned incomplete image status {int(status.value)}")

        width = ctypes.c_size_t()
        height = ctypes.c_size_t()
        stride = ctypes.c_size_t()
        buffer_size = ctypes.c_size_t()
        bits_per_pixel = ctypes.c_size_t()
        data_ptr = ctypes.c_void_p()

        _check_error(self.lib.spinImageGetWidth(image, ctypes.byref(width)), "spinImageGetWidth")
        _check_error(self.lib.spinImageGetHeight(image, ctypes.byref(height)), "spinImageGetHeight")
        _check_error(self.lib.spinImageGetStride(image, ctypes.byref(stride)), "spinImageGetStride")
        _check_error(self.lib.spinImageGetBufferSize(image, ctypes.byref(buffer_size)), "spinImageGetBufferSize")
        _check_error(self.lib.spinImageGetBitsPerPixel(image, ctypes.byref(bits_per_pixel)), "spinImageGetBitsPerPixel")
        _check_error(self.lib.spinImageGetData(image, ctypes.byref(data_ptr)), "spinImageGetData")

        rows = int(height.value)
        cols = int(width.value)
        row_stride = int(stride.value)
        data_size = int(buffer_size.value)
        bit_depth = int(bits_per_pixel.value)

        if rows <= 0 or cols <= 0 or row_stride <= 0 or data_size <= 0 or not data_ptr.value:
            raise RuntimeError("Invalid Spinnaker image dimensions")

        buffer = ctypes.string_at(data_ptr, data_size)
        if bit_depth <= 8:
            arr = np.frombuffer(buffer, dtype=np.uint8).reshape(rows, row_stride)
            return np.ascontiguousarray(arr[:, :cols])

        row_words = row_stride // 2
        arr = np.frombuffer(buffer, dtype=np.uint16).reshape(rows, row_words)
        return np.ascontiguousarray(arr[:, :cols])
