import ctypes
import threading

import FliSdk_V2


NewImageCallback = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p)


class FirstLightSdkExtras:
    """
    Small ctypes layer for First Light SDK functions that are missing or
    incomplete in the vendor Python wrapper.

    The C++ SDK has a ring-buffer last-image index, but the public C/Python
    wrapper installed with this SDK version does not export it. For trigger
    synchronization we use the official new-image callback as a monotonic
    image-arrival counter instead of polling buffer occupancy.
    """

    def __init__(self):
        self.lib = FliSdk_V2.LibLoader.lib
        self._set_prototypes()

    def _set_prototypes(self):
        self.lib.FliSdk_addCallbackNewImage_V2.argtypes = [
            ctypes.c_void_p,
            NewImageCallback,
            ctypes.c_uint16,
            ctypes.c_bool,
            ctypes.c_void_p,
        ]
        self.lib.FliSdk_addCallbackNewImage_V2.restype = ctypes.c_void_p

        self.lib.FliSdk_removeCallbackNewImage_V2.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        self.lib.FliSdk_removeCallbackNewImage_V2.restype = None

    def add_new_image_callback(self, context, callback, fps=0, before_copy=False, user_context=None):
        return self.lib.FliSdk_addCallbackNewImage_V2(
            ctypes.c_void_p(context),
            callback,
            ctypes.c_uint16(fps),
            ctypes.c_bool(before_copy),
            ctypes.c_void_p(0 if user_context is None else user_context),
        )

    def remove_new_image_callback(self, context, callback_handler):
        if callback_handler:
            self.lib.FliSdk_removeCallbackNewImage_V2(
                ctypes.c_void_p(context),
                ctypes.c_void_p(callback_handler),
            )


class FirstLightNewImageCounter:
    def __init__(self, context, fps=0, before_copy=False):
        self.context = context
        self.sdk = FirstLightSdkExtras()
        self._lock = threading.Lock()
        self._count = 0
        self._closed = False

        self._callback = NewImageCallback(self._on_new_image)
        self._callback_handler = self.sdk.add_new_image_callback(
            context,
            self._callback,
            fps=fps,
            before_copy=before_copy,
            user_context=None,
        )
        if not self._callback_handler:
            raise RuntimeError("Failed to register First Light new-image callback")

    def _on_new_image(self, image, user_context):
        with self._lock:
            self._count += 1

    def get_count(self):
        with self._lock:
            return int(self._count)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.sdk.remove_new_image_callback(self.context, self._callback_handler)
        self._callback_handler = None
