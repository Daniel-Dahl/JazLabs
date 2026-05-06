
# import ctypes
# import os
# import numpy as np

# DEFAULT_FC2_DLL_PATH = r"C:\Program Files\Point Grey Research\FlyCapture2\bin64\FlyCapture2_C_v100.dll"
# MAX_STRING_LENGTH = 512
import ctypes
import os
import sys
import platform
import ctypes.util
import numpy as np

MAX_STRING_LENGTH = 512

if platform.system() == "Windows":
    DEFAULT_FC2_DLL_CANDIDATES = [
        os.environ.get("FLYCAPTURE2_DLL_PATH"),
        r"C:\Program Files\Point Grey Research\FlyCapture2\bin64\FlyCapture2_C_v100.dll",
        r"C:\Program Files\FLIR Systems\FlyCapture2\bin64\FlyCapture2_C_v100.dll",
        "FlyCapture2_C_v100.dll",
    ]
else:
    DEFAULT_FC2_DLL_CANDIDATES = [
        os.environ.get("FLYCAPTURE2_DLL_PATH"),
        "/lib/libflycapture-c.so",
        "/usr/lib/libflycapture-c.so",
        "/usr/lib64/libflycapture-c.so",
        "/usr/lib/x86_64-linux-gnu/libflycapture-c.so",
        "libflycapture-c.so",
        ctypes.util.find_library("flycapture-c"),
        ctypes.util.find_library("flycapture"),
    ]
def _load_flycapture_library(user_path=None):
    """
    Load FlyCapture2 shared library on Windows or Linux.

    Accepts either:
    - explicit full path
    - library filename / soname
    - auto-detected fallback paths
    """
    candidates = []

    if user_path:
        candidates.append(user_path)

    for candidate in DEFAULT_FC2_DLL_CANDIDATES:
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
        "Could not load FlyCapture2 library.\n"
        "Tried these candidates:\n"
        f"{joined}\n\n"
        "Set FLYCAPTURE2_DLL_PATH explicitly if needed."
    )

class FlyCapture2Error(RuntimeError):
    def __init__(self, code: int, func: str):
        super().__init__(f"{func} failed with FlyCapture2 error code {code}")
        self.code = int(code)
        self.func = func
    


def _check_error(code: int, func: str):
    if int(code) != 0:
        raise FlyCapture2Error(int(code), func)


class fc2Mode(ctypes.c_uint):
    FC2_MODE_0 = 0
    FC2_MODE_1 = 1
    FC2_MODE_2 = 2
    FC2_MODE_3 = 3
    FC2_MODE_4 = 4
    FC2_MODE_5 = 5
    FC2_MODE_6 = 6
    FC2_MODE_7 = 7


class fc2PixelFormat(ctypes.c_uint):
    # FC2_PIXEL_FORMAT_MONO8 = 0x80000000
    # FC2_PIXEL_FORMAT_MONO16 = 0x04000000
    # FC2_PIXEL_FORMAT_RAW8 = 0x00400000
    # FC2_PIXEL_FORMAT_RAW16 = 0x00200000
    # FC2_PIXEL_FORMAT_MONO12 = 0x00100000
    # FC2_PIXEL_FORMAT_RAW12 = 0x00080000
    # FC2_UNSPECIFIED_PIXEL_FORMAT = 0
    FC2_PIXEL_FORMAT_MONO8 = 0x80000000
    FC2_PIXEL_FORMAT_MONO10 = 0x02000000
    FC2_PIXEL_FORMAT_411YUV8 = 0x40000000
    FC2_PIXEL_FORMAT_422YUV8 = 0x20000000
    FC2_PIXEL_FORMAT_444YUV8 = 0x10000000
    FC2_PIXEL_FORMAT_RGB8 = 0x08000000
    FC2_PIXEL_FORMAT_MONO16 = 0x04000000
    FC2_PIXEL_FORMAT_RGB16 = 0x02000000
    FC2_PIXEL_FORMAT_S_MONO16 = 0x01000000
    FC2_PIXEL_FORMAT_S_RGB16 = 0x00800000
    FC2_PIXEL_FORMAT_RAW8 = 0x00400000
    FC2_PIXEL_FORMAT_RAW16 = 0x00200000
    FC2_PIXEL_FORMAT_MONO12 = 0x00100000
    FC2_PIXEL_FORMAT_RAW12 = 0x00080000
    FC2_PIXEL_FORMAT_BGR = 0x80000008
    FC2_PIXEL_FORMAT_BGRU = 0x40000008
    FC2_PIXEL_FORMAT_RGB = 0x08000000  # Same value as FC2_PIXEL_FORMAT_RGB8
    FC2_PIXEL_FORMAT_RGBU = 0x40000002
    FC2_PIXEL_FORMAT_BGR16 = 0x02000001
    FC2_PIXEL_FORMAT_BGRU16 = 0x02000002
    FC2_PIXEL_FORMAT_422YUV8_JPEG = 0x40000001
    FC2_NUM_PIXEL_FORMATS = 20
    FC2_UNSPECIFIED_PIXEL_FORMAT = 0


class fc2BayerTileFormat(ctypes.c_uint):
    FC2_BT_NONE = 0
    FC2_BT_RGGB = 1
    FC2_BT_GRBG = 2
    FC2_BT_GBRG = 3
    FC2_BT_BGGR = 4


class fc2Image(ctypes.Structure):
    _fields_ = [
        ("rows", ctypes.c_uint),
        ("cols", ctypes.c_uint),
        ("stride", ctypes.c_uint),
        ("pData", ctypes.POINTER(ctypes.c_ubyte)),
        ("dataSize", ctypes.c_uint),
        ("receivedDataSize", ctypes.c_uint),
        ("format", fc2PixelFormat),
        ("bayerFormat", fc2BayerTileFormat),
        ("imageImpl", ctypes.c_void_p),
    ]
    
class fc2EmbeddedImageInfoProperty(ctypes.Structure):
    _fields_ = [
        ("available", ctypes.c_int),
        ("onOff", ctypes.c_int),
    ]


class fc2EmbeddedImageInfo(ctypes.Structure):
    _fields_ = [
        ("timestamp", fc2EmbeddedImageInfoProperty),
        ("gain", fc2EmbeddedImageInfoProperty),
        ("shutter", fc2EmbeddedImageInfoProperty),
        ("brightness", fc2EmbeddedImageInfoProperty),
        ("exposure", fc2EmbeddedImageInfoProperty),
        ("whiteBalance", fc2EmbeddedImageInfoProperty),
        ("frameCounter", fc2EmbeddedImageInfoProperty),
        ("ROIPosition", fc2EmbeddedImageInfoProperty),
        ("GPIOPinState", fc2EmbeddedImageInfoProperty),
        ("strobePattern", fc2EmbeddedImageInfoProperty),
        ("reserved", ctypes.c_uint * 8),
    ]


class fc2ImageMetadata(ctypes.Structure):
    _fields_ = [
        ("embeddedTimeStamp", ctypes.c_uint),
        ("embeddedGain", ctypes.c_uint),
        ("embeddedShutter", ctypes.c_uint),
        ("embeddedBrightness", ctypes.c_uint),
        ("embeddedExposure", ctypes.c_uint),
        ("embeddedWhiteBalance", ctypes.c_uint),
        ("embeddedFrameCounter", ctypes.c_uint),
        ("embeddedStrobePattern", ctypes.c_uint),
        ("embeddedGPIOPinState", ctypes.c_uint),
        ("embeddedROIPosition", ctypes.c_uint),
        ("reserved", ctypes.c_uint * 31),
    ]


class fc2PGRGuid(ctypes.Structure):
    _fields_ = [("value", ctypes.c_uint * 4)]


class fc2PropertyType(ctypes.c_uint):
    FC2_BRIGHTNESS = 0
    FC2_AUTO_EXPOSURE = 1
    FC2_SHARPNESS = 2
    FC2_WHITE_BALANCE = 3
    FC2_HUE = 4
    FC2_SATURATION = 5
    FC2_GAMMA = 6
    FC2_IRIS = 7
    FC2_FOCUS = 8
    FC2_ZOOM = 9
    FC2_PAN = 10
    FC2_TILT = 11
    FC2_SHUTTER = 12
    FC2_GAIN = 13
    FC2_TRIGGER_MODE = 14
    FC2_TRIGGER_DELAY = 15
    FC2_FRAME_RATE = 16
    FC2_TEMPERATURE = 17


class fc2Property(ctypes.Structure):
    _fields_ = [
        ("type", fc2PropertyType),
        ("present", ctypes.c_int),
        ("absControl", ctypes.c_int),
        ("onePush", ctypes.c_int),
        ("onOff", ctypes.c_int),
        ("autoManualMode", ctypes.c_int),
        ("valueA", ctypes.c_uint),
        ("valueB", ctypes.c_uint),
        ("absValue", ctypes.c_float),
        ("reserved", ctypes.c_uint * 8),
    ]


class fc2PropertyInfo(ctypes.Structure):
    _fields_ = [
        ("type", fc2PropertyType),
        ("present", ctypes.c_int),
        ("autoSupported", ctypes.c_int),
        ("manualSupported", ctypes.c_int),
        ("onOffSupported", ctypes.c_int),
        ("onePushSupported", ctypes.c_int),
        ("absValSupported", ctypes.c_int),
        ("readOutSupported", ctypes.c_int),
        ("min", ctypes.c_uint),
        ("max", ctypes.c_uint),
        ("absMin", ctypes.c_float),
        ("absMax", ctypes.c_float),
        ("pUnits", ctypes.c_char * MAX_STRING_LENGTH),
        ("pUnitAbbr", ctypes.c_char * MAX_STRING_LENGTH),
        ("reserved", ctypes.c_uint * 8),
    ]


class fc2TriggerMode(ctypes.Structure):
    _fields_ = [
        ("onOff", ctypes.c_int),
        ("polarity", ctypes.c_uint),
        ("source", ctypes.c_uint),
        ("mode", ctypes.c_uint),
        ("parameter", ctypes.c_uint),
        ("reserved", ctypes.c_uint * 8),
    ]


class fc2Format7ImageSettings(ctypes.Structure):
    _fields_ = [
        ("mode", fc2Mode),
        ("offsetX", ctypes.c_uint),
        ("offsetY", ctypes.c_uint),
        ("width", ctypes.c_uint),
        ("height", ctypes.c_uint),
        ("pixelFormat", fc2PixelFormat),
        ("reserved", ctypes.c_uint * 8),
    ]


class fc2Format7Info(ctypes.Structure):
    _fields_ = [
        ("mode", fc2Mode),
        ("maxWidth", ctypes.c_uint),
        ("maxHeight", ctypes.c_uint),
        ("offsetHStepSize", ctypes.c_uint),
        ("offsetVStepSize", ctypes.c_uint),
        ("imageHStepSize", ctypes.c_uint),
        ("imageVStepSize", ctypes.c_uint),
        ("pixelFormatBitField", ctypes.c_uint),
        ("vendorPixelFormatBitField", ctypes.c_uint),
        ("packetSize", ctypes.c_uint),
        ("minPacketSize", ctypes.c_uint),
        ("maxPacketSize", ctypes.c_uint),
        ("percentage", ctypes.c_float),
        ("reserved", ctypes.c_uint * 16),
    ]


class fc2Format7PacketInfo(ctypes.Structure):
    _fields_ = [
        ("recommendedBytesPerPacket", ctypes.c_uint),
        ("maxBytesPerPacket", ctypes.c_uint),
        ("unitBytesPerPacket", ctypes.c_uint),
        ("reserved", ctypes.c_uint * 8),
    ]


class FlyCapture2Library:
    def __init__(self, dll_path=None):
        self.lib, self.dll_path = _load_flycapture_library(dll_path)
        self._set_prototypes()
    # def __init__(self, dll_path=None):
    #     self.dll_path = dll_path or os.environ.get("FLYCAPTURE2_DLL_PATH", DEFAULT_FC2_DLL_PATH)
    #     if not os.path.isfile(self.dll_path):
    #         raise FileNotFoundError(
    #             f"FlyCapture2 DLL not found: {self.dll_path}. "
    #             "Set FLYCAPTURE2_DLL_PATH or pass dll_path explicitly."
    #         )
        
    #     self.lib = ctypes.cdll.LoadLibrary(self.dll_path)
    #     self._set_prototypes()

    def _set_prototypes(self):
        lib = self.lib

        lib.fc2CreateContext.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        lib.fc2CreateContext.restype = ctypes.c_int

        lib.fc2DestroyContext.argtypes = [ctypes.c_void_p]
        lib.fc2DestroyContext.restype = ctypes.c_int

        lib.fc2GetNumOfCameras.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        lib.fc2GetNumOfCameras.restype = ctypes.c_int

        lib.fc2GetCameraFromIndex.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(fc2PGRGuid)]
        lib.fc2GetCameraFromIndex.restype = ctypes.c_int

        lib.fc2Connect.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2PGRGuid)]
        lib.fc2Connect.restype = ctypes.c_int

        lib.fc2Disconnect.argtypes = [ctypes.c_void_p]
        lib.fc2Disconnect.restype = ctypes.c_int

        lib.fc2StartCapture.argtypes = [ctypes.c_void_p]
        lib.fc2StartCapture.restype = ctypes.c_int

        lib.fc2StopCapture.argtypes = [ctypes.c_void_p]
        lib.fc2StopCapture.restype = ctypes.c_int

        lib.fc2CreateImage.argtypes = [ctypes.POINTER(fc2Image)]
        lib.fc2CreateImage.restype = ctypes.c_int

        lib.fc2DestroyImage.argtypes = [ctypes.POINTER(fc2Image)]
        lib.fc2DestroyImage.restype = ctypes.c_int

        lib.fc2RetrieveBuffer.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2Image)]
        lib.fc2RetrieveBuffer.restype = ctypes.c_int

        lib.fc2GetProperty.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2Property)]
        lib.fc2GetProperty.restype = ctypes.c_int

        lib.fc2SetProperty.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2Property)]
        lib.fc2SetProperty.restype = ctypes.c_int

        lib.fc2GetPropertyInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2PropertyInfo)]
        lib.fc2GetPropertyInfo.restype = ctypes.c_int

        lib.fc2GetTriggerMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2TriggerMode)]
        lib.fc2GetTriggerMode.restype = ctypes.c_int

        lib.fc2SetTriggerMode.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2TriggerMode)]
        lib.fc2SetTriggerMode.restype = ctypes.c_int

        lib.fc2FireSoftwareTrigger.argtypes = [ctypes.c_void_p]
        lib.fc2FireSoftwareTrigger.restype = ctypes.c_int
        
        lib.fc2GetEmbeddedImageInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2EmbeddedImageInfo)]
        lib.fc2GetEmbeddedImageInfo.restype = ctypes.c_int

        lib.fc2SetEmbeddedImageInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(fc2EmbeddedImageInfo)]
        lib.fc2SetEmbeddedImageInfo.restype = ctypes.c_int

        lib.fc2GetImageMetadata.argtypes = [ctypes.POINTER(fc2Image), ctypes.POINTER(fc2ImageMetadata)]
        lib.fc2GetImageMetadata.restype = ctypes.c_int

        lib.fc2GetFormat7Info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(fc2Format7Info),
            ctypes.POINTER(ctypes.c_int),
        ]
        lib.fc2GetFormat7Info.restype = ctypes.c_int

        lib.fc2ValidateFormat7Settings.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(fc2Format7ImageSettings),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(fc2Format7PacketInfo),
        ]
        lib.fc2ValidateFormat7Settings.restype = ctypes.c_int

        lib.fc2GetFormat7Configuration.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(fc2Format7ImageSettings),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_float),
        ]
        lib.fc2GetFormat7Configuration.restype = ctypes.c_int

        lib.fc2SetFormat7ConfigurationPacket.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(fc2Format7ImageSettings),
            ctypes.c_uint,
        ]
        lib.fc2SetFormat7ConfigurationPacket.restype = ctypes.c_int

    def create_context(self):
        ctx = ctypes.c_void_p()
        _check_error(self.lib.fc2CreateContext(ctypes.byref(ctx)), "fc2CreateContext")
        return ctx

    def destroy_context(self, ctx):
        _check_error(self.lib.fc2DestroyContext(ctx), "fc2DestroyContext")

    def get_num_cameras(self, ctx):
        n = ctypes.c_uint()
        _check_error(self.lib.fc2GetNumOfCameras(ctx, ctypes.byref(n)), "fc2GetNumOfCameras")
        return int(n.value)

    def get_camera_guid(self, ctx, index):
        guid = fc2PGRGuid()
        _check_error(self.lib.fc2GetCameraFromIndex(ctx, int(index), ctypes.byref(guid)), "fc2GetCameraFromIndex")
        return guid

    def get_camera_from_index(self, ctx, index):
        return self.get_camera_guid(ctx, index)

    def connect(self, ctx, guid):
        _check_error(self.lib.fc2Connect(ctx, ctypes.byref(guid)), "fc2Connect")

    def disconnect(self, ctx):
        _check_error(self.lib.fc2Disconnect(ctx), "fc2Disconnect")

    def start_capture(self, ctx):
        _check_error(self.lib.fc2StartCapture(ctx), "fc2StartCapture")

    def stop_capture(self, ctx):
        _check_error(self.lib.fc2StopCapture(ctx), "fc2StopCapture")

    def create_image(self):
        image = fc2Image()
        _check_error(self.lib.fc2CreateImage(ctypes.byref(image)), "fc2CreateImage")
        return image

    def destroy_image(self, image):
        _check_error(self.lib.fc2DestroyImage(ctypes.byref(image)), "fc2DestroyImage")

    def retrieve_buffer(self, ctx, image):
        _check_error(self.lib.fc2RetrieveBuffer(ctx, ctypes.byref(image)), "fc2RetrieveBuffer")

    def get_property(self, ctx, prop_type):
        prop = fc2Property()
        prop.type = int(prop_type)
        _check_error(self.lib.fc2GetProperty(ctx, ctypes.byref(prop)), "fc2GetProperty")
        return prop

    def set_property(self, ctx, prop):
        _check_error(self.lib.fc2SetProperty(ctx, ctypes.byref(prop)), "fc2SetProperty")

    def get_property_info(self, ctx, prop_type):
        info = fc2PropertyInfo()
        info.type = int(prop_type)
        _check_error(self.lib.fc2GetPropertyInfo(ctx, ctypes.byref(info)), "fc2GetPropertyInfo")
        return info

    def get_trigger_mode(self, ctx):
        trig = fc2TriggerMode()
        _check_error(self.lib.fc2GetTriggerMode(ctx, ctypes.byref(trig)), "fc2GetTriggerMode")
        return trig

    def set_trigger_mode(self, ctx, trig):
        _check_error(self.lib.fc2SetTriggerMode(ctx, ctypes.byref(trig)), "fc2SetTriggerMode")

    def fire_software_trigger(self, ctx):
        _check_error(self.lib.fc2FireSoftwareTrigger(ctx), "fc2FireSoftwareTrigger")
        
    def get_embedded_image_info(self, ctx):
        info = fc2EmbeddedImageInfo()
        _check_error(
            self.lib.fc2GetEmbeddedImageInfo(ctx, ctypes.byref(info)),
            "fc2GetEmbeddedImageInfo",
        )
        return info


    def set_embedded_image_info(self, ctx, info):
        _check_error(
            self.lib.fc2SetEmbeddedImageInfo(ctx, ctypes.byref(info)),
            "fc2SetEmbeddedImageInfo",
        )


    def enable_embedded_frame_counter(self, ctx, enable=True):
        info = self.get_embedded_image_info(ctx)
        if int(info.frameCounter.available):
            info.frameCounter.onOff = 1 if enable else 0
            self.set_embedded_image_info(ctx, info)
            return True
        return False


    def get_image_metadata(self, image):
        metadata = fc2ImageMetadata()
        _check_error(
            self.lib.fc2GetImageMetadata(ctypes.byref(image), ctypes.byref(metadata)),
            "fc2GetImageMetadata",
        )
        return metadata
    
    def get_format7_info(self, ctx, mode=0):
        info = fc2Format7Info()
        info.mode = int(mode)
        supported = ctypes.c_int()
        _check_error(
            self.lib.fc2GetFormat7Info(ctx, ctypes.byref(info), ctypes.byref(supported)),
            "fc2GetFormat7Info",
        )
        return info, bool(supported.value)

    def validate_format7_settings(self, ctx, settings):
        valid = ctypes.c_int()
        packet_info = fc2Format7PacketInfo()
        _check_error(
            self.lib.fc2ValidateFormat7Settings(
                ctx,
                ctypes.byref(settings),
                ctypes.byref(valid),
                ctypes.byref(packet_info),
            ),
            "fc2ValidateFormat7Settings",
        )
        return bool(valid.value), packet_info

    def get_format7_configuration(self, ctx):
        settings = fc2Format7ImageSettings()
        packet_size = ctypes.c_uint()
        percentage = ctypes.c_float()
        _check_error(
            self.lib.fc2GetFormat7Configuration(
                ctx,
                ctypes.byref(settings),
                ctypes.byref(packet_size),
                ctypes.byref(percentage),
            ),
            "fc2GetFormat7Configuration",
        )
        return settings, int(packet_size.value), float(percentage.value)

    def get_pixel_format(self, ctx):
        settings, _, _ = self.get_format7_configuration(ctx)
        return int(settings.pixelFormat.value)

    def set_pixel_format(self, ctx, pixel_format):
        current_settings, current_packet_size, _ = self.get_format7_configuration(ctx)

        new_settings = self.make_format7_settings(
            mode=int(current_settings.mode.value),
            offsetX=int(current_settings.offsetX),
            offsetY=int(current_settings.offsetY),
            width=int(current_settings.width),
            height=int(current_settings.height),
            pixelFormat=int(pixel_format),
        )

        settings_are_valid, packet_info = self.validate_format7_settings(ctx, new_settings)
        if not settings_are_valid:
            raise RuntimeError("Requested pixel format is not valid for this FLIR camera")

        packet_size = int(packet_info.recommendedBytesPerPacket)
        if packet_size <= 0:
            packet_size = int(current_packet_size)

        self.set_format7_configuration_packet(ctx, new_settings, packet_size)
        return self.get_pixel_format(ctx)

    def set_format7_configuration_packet(self, ctx, settings, packet_size):
        _check_error(
            self.lib.fc2SetFormat7ConfigurationPacket(
                ctx,
                ctypes.byref(settings),
                int(packet_size),
            ),
            "fc2SetFormat7ConfigurationPacket",
        )

    def make_format7_settings(self, mode=0, offsetX=0, offsetY=0, width=0, height=0, pixelFormat=None):
        settings = fc2Format7ImageSettings()
        settings.mode = int(mode)
        settings.offsetX = int(offsetX)
        settings.offsetY = int(offsetY)
        settings.width = int(width)
        settings.height = int(height)
        if pixelFormat is None:
            pixelFormat = int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO16)
        settings.pixelFormat = int(pixelFormat)
        return settings

    def image_to_numpy(self, image):
        rows = int(image.rows)
        cols = int(image.cols)
        stride = int(image.stride)
        data_size = int(image.receivedDataSize if image.receivedDataSize else image.dataSize)

        if rows <= 0 or cols <= 0 or data_size <= 0:
            raise RuntimeError("Invalid FlyCapture2 image dimensions")

        buffer = ctypes.string_at(image.pData, data_size)
        fmt = int(image.format.value)
        if fmt in (
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO16),
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO10),
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_RAW16),
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO12),
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_RAW12),
        ):
            
            row_words = stride // 2
            arr = np.frombuffer(buffer, dtype=np.uint16).reshape(rows, row_words)
            # frame = np.ctypeslib.as_array(frameBufferPtr,shape=(FrameHeight,FrameWidth))
            
            return np.ascontiguousarray(arr[:, :cols])

        if fmt in (
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO8),
            int(fc2PixelFormat.FC2_PIXEL_FORMAT_RAW8),
        ):
            arr = np.frombuffer(buffer, dtype=np.uint8).reshape(rows, stride)
            return np.ascontiguousarray(arr[:, :cols])

        raise NotImplementedError(f"Unsupported FlyCapture2 pixel format: {fmt}")
