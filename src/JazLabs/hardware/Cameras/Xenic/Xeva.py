"""JazLabs camera object for Xenics XEVA cameras controlled by Xeneth."""

import atexit
import os
import time
import weakref

import numpy as np

from .xeneth_ctypes import (
    FT_16_BPP_GRAY,
    FT_32_BPP_GRAY,
    FT_8_BPP_GRAY,
    XDS_AVAILABLE,
    XDS_BUSY,
    XDS_UNREACHABLE,
    XenethError,
    XenethLibrary,
)


def _shutdown_camera(camera_reference):
    camera = camera_reference()
    if camera is not None:
        camera.shutdown()


class CameraObject:
    """Camera object for the XEVA USB and Camera Link camera variants."""

    XEVA_USB_PRODUCT_ID = 0x810A
    XEVA_CAMERA_LINK_PRODUCT_ID = 0x8110

    def __init__(
        self,
        CameraSerialNumber=None,
        CalibrationFile=None,
        PixelSize=30e-6,
        dll_path=None,
        verbose=False,
    ):
        self.CameraType = "Xeva"
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize
        self.verbose = bool(verbose)

        self._closed = False
        self._capturing = False
        self.xeneth = XenethLibrary(dll_path=dll_path)
        self.handle = 0

        discovered_devices = [
            device
            for device in self.xeneth.enumerate_devices()
            if device["name"].strip().upper().startswith("XEVA")
            or device["pid"]
            in (self.XEVA_USB_PRODUCT_ID, self.XEVA_CAMERA_LINK_PRODUCT_ID)
        ]
        requested_serial_number = (
            "" if CameraSerialNumber is None else str(CameraSerialNumber).strip()
        )

        if not requested_serial_number:
            print("Available XEVA cameras:")
            if not discovered_devices:
                print("  none detected")
            for device_index, device in enumerate(discovered_devices):
                state_name = {
                    XDS_AVAILABLE: "available",
                    XDS_BUSY: "busy",
                    XDS_UNREACHABLE: "unreachable",
                }.get(device["state"], f"unknown ({device['state']})")
                print(
                    f"  {device_index}: {device['name']} | serial "
                    f"{device['serial']} | PID 0x{device['pid']:04X} | "
                    f"{device['url']} | {state_name}"
                )
            raise ValueError(
                "CameraSerialNumber must be provided; choose one of the "
                "serial numbers listed above"
            )

        try:
            if requested_serial_number.casefold().startswith("0x"):
                numeric_serial_number = int(requested_serial_number, 16)
            else:
                numeric_serial_number = int(requested_serial_number, 10)
        except ValueError as error:
            raise ValueError(
                "XEVA camera serial numbers must be decimal integers or "
                "hexadecimal integers beginning with 0x"
            ) from error

        if not discovered_devices:
            raise RuntimeError("No XEVA cameras detected")

        selected_device = None
        for device_index, device in enumerate(discovered_devices):
            if self.verbose:
                state_name = {
                    XDS_AVAILABLE: "available",
                    XDS_BUSY: "busy",
                    XDS_UNREACHABLE: "unreachable",
                }.get(device["state"], f"unknown ({device['state']})")
                print(
                    f"{device_index}: {device['name']} serial "
                    f"{device['serial']} at {device['url']} ({state_name})"
                )
            if device["serial"] == numeric_serial_number:
                selected_device = device

        if selected_device is None:
            discovered_serial_numbers = ", ".join(
                str(device["serial"]) for device in discovered_devices
            )
            raise ValueError(
                "XEVA camera with serial number "
                f"{requested_serial_number!r} was not found. Discovered "
                f"serial numbers: {discovered_serial_numbers}"
            )

        if selected_device["state"] != XDS_AVAILABLE:
            state_name = {
                XDS_BUSY: "busy",
                XDS_UNREACHABLE: "unreachable",
            }.get(
                selected_device["state"],
                f"in unknown state {selected_device['state']}",
            )
            raise RuntimeError(
                f"XEVA camera {selected_device['serial']} is {state_name}"
            )

        self.CameraSerialNumber = str(selected_device["serial"])
        self.CameraName = selected_device["url"]
        self.CameraModel = selected_device["name"]
        self.CameraTransport = selected_device["transport"]
        self.CameraAddress = selected_device["address"]
        self.CameraProductID = selected_device["pid"]
        self.handle = self.xeneth.open_camera(self.CameraName)

        try:
            connected_serial_number = self.GetSerialNumber()
            if connected_serial_number != str(numeric_serial_number):
                raise RuntimeError(
                    "Xeneth opened a different XEVA camera than the selected "
                    f"device: requested {numeric_serial_number}, connected "
                    f"{connected_serial_number}"
                )
            self.CameraProductID = self.xeneth.get_property_long(
                self.handle,
                "_CAM_PID",
            )
            if self.CameraProductID not in (
                self.XEVA_USB_PRODUCT_ID,
                self.XEVA_CAMERA_LINK_PRODUCT_ID,
            ):
                raise ValueError(
                    f"{self.CameraModel!r} with PID "
                    f"0x{self.CameraProductID:04X} is not a supported XEVA "
                    "USB or XEVA Camera Link camera"
                )
            if not self.CameraModel.strip().upper().startswith("XEVA"):
                raise ValueError(
                    f"Discovered camera {self.CameraModel!r} is not a XEVA"
                )

            if self.CameraProductID == self.XEVA_USB_PRODUCT_ID:
                self.XevaInterface = "USB"
            else:
                self.XevaInterface = "CameraLink"

            if self.verbose:
                print(
                    f"Using XEVA-{self.XevaInterface} camera serial number "
                    f"{self.CameraSerialNumber} at {self.CameraName}"
                )

            self._load_calibration_file()

            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
            self.trigger_selector = "FrameStart"
            self.acquisition_mode = "Continuous"
            self.trigger_polarity = 1

            self.offset_x = 0
            self.offset_y = 0
            self.width = self.xeneth.get_width(self.handle)
            self.height = self.xeneth.get_height(self.handle)
            self.Nx = self.width
            self.Ny = self.height

            self.frame_id = None
            self.grab_timeout_ms = None
            self.frame_id_updates_asynchronously = False
            self.software_trigger_is_emulated = True
            self._pseudo_software_trigger_enabled = False
            self._pending_software_trigger_frame = None
            self._pending_software_trigger_frame_id = None
            self.ExposureTime = self.GetExposureTime()
            self.ExposureTimeMin, self.ExposureTimeMax = (
                self.xeneth.get_property_range_float(
                    self.handle,
                    "IntegrationTime",
                )
            )
            self.fps = self.GetFPS()
            self.FPSMin = None
            self.FPSMax = None
            self.gain = self.GetGain()
            self.pixel_format = self.GetPixelFormat()

            self.SetContinuousMode()
            self.StartAcquisition()
        except Exception:
            self.shutdown()
            raise

        atexit.register(_shutdown_camera, weakref.ref(self))

    def __del__(self):
        self.shutdown()

    def _load_calibration_file(self):
        if self.CalibrationFile is None:
            return

        calibration_path = os.fspath(self.CalibrationFile)
        if calibration_path.lower().endswith(".xcf"):
            self.xeneth.load_settings(self.handle, calibration_path)
        else:
            self.xeneth.load_calibration(self.handle, calibration_path)

    def shutdown(self):
        if getattr(self, "_closed", True):
            return

        self._closed = True
        if getattr(self, "_capturing", False):
            try:
                self.xeneth.stop_capture(self.handle)
            except Exception:
                pass
            self._capturing = False

        if getattr(self, "handle", 0):
            try:
                self.xeneth.close_camera(self.handle)
            finally:
                self.handle = 0

    def GetSerialNumber(self):
        self.CameraSerialNumber = str(
            self.xeneth.get_property_long(self.handle, "_CAM_SER")
        )
        return self.CameraSerialNumber

    def StartAcquisition(self):
        if not self._capturing:
            self.xeneth.start_capture(self.handle)
            self._capturing = True

    def StopAcquisition(self):
        if self._capturing:
            self.xeneth.stop_capture(self.handle)
            self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        self.frame_id = None
        self._pending_software_trigger_frame = None
        self._pending_software_trigger_frame_id = None

    def DrainImageBuffer(self, max_frames=64, timeout_ms=1):
        self.ResetBuffer()
        return self.xeneth.drain_frames(self.handle, max_frames=max_frames)

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError(
            "Xeneth does not expose stream buffer sizing through this wrapper"
        )

    def GetBufferSizeInNumberOfFrames(self):
        return None

    def GetNumberOfFramesInBuffer(self):
        return None

    def GetGrabTimeout(self):
        return self.grab_timeout_ms

    def SetGrabTimeout(self, timeout_ms):
        self.grab_timeout_ms = None if timeout_ms is None else int(timeout_ms)
        return self.grab_timeout_ms

    def GetFrameID(self):
        self.frame_id = self.xeneth.get_frame_count(self.handle)
        return self.frame_id

    def GetFrame(self, timeout_ms=None):
        """Return a continuous frame or consume the pending pseudo-triggered frame."""
        if self._pseudo_software_trigger_enabled:
            if self._pending_software_trigger_frame is None:
                raise RuntimeError(
                    "No pseudo-software-triggered XEVA frame is pending; "
                    "call FireSoftwareTrigger() before GetFrame()"
                )

            triggered_frame = self._pending_software_trigger_frame
            self.frame_id = self._pending_software_trigger_frame_id
            self._pending_software_trigger_frame = None
            self._pending_software_trigger_frame_id = None
            return triggered_frame.copy()

        return self._capture_frame_from_camera()

    def _capture_frame_from_camera(self):
        if not self._capturing:
            self.StartAcquisition()

        self.GetROI()
        frame_byte_count = self.xeneth.get_frame_size(self.handle)
        frame_buffer = np.empty(frame_byte_count, dtype=np.uint8)
        self.xeneth.get_frame(self.handle, frame_buffer)

        if self.pixel_format == "mono8":
            frame_dtype = np.uint8
        elif self.pixel_format == "mono32":
            frame_dtype = np.uint32
        else:
            frame_dtype = np.uint16

        required_pixel_count = self.width * self.height
        frame_values = frame_buffer.view(frame_dtype)
        if frame_values.size < required_pixel_count:
            raise RuntimeError(
                "Xeneth returned a frame buffer smaller than the reported "
                f"image dimensions ({frame_values.size} values for "
                f"{self.width} x {self.height})"
            )

        self.GetFrameID()
        return frame_values[:required_pixel_count].reshape(
            self.height,
            self.width,
        ).copy()

    def GetExposureTime(self):
        self.ExposureTime = self.xeneth.get_property_float(
            self.handle,
            "IntegrationTime",
        )
        return self.ExposureTime

    def SetExposureTime(self, exposure_time):
        self.ExposureTime = self.xeneth.set_property_float(
            self.handle,
            "IntegrationTime",
            exposure_time,
            "us",
        )
        return self.ExposureTime

    def GetGain(self):
        gain_value = self.xeneth.get_property(self.handle, "LowGain")
        self.gain = int(gain_value.strip().casefold() in ("1", "true", "on"))
        return self.gain

    def SetGain(self, gain):
        gain = int(gain)
        if gain not in (0, 1):
            raise ValueError("Xeneth LowGain must be 0 or 1")

        self.xeneth.set_property(
            self.handle,
            "LowGain",
            "True" if gain else "False",
            "bool",
        )
        return self.GetGain()

    def GetFanState(self):
        fan_value = self.xeneth.get_property(self.handle, "Fan")
        return int(fan_value.strip().casefold() in ("1", "true", "on"))

    def SetFanState(self, fan_state):
        fan_state = int(fan_state)
        if fan_state not in (0, 1):
            raise ValueError("Xeneth fan state must be 0 or 1")

        self.xeneth.set_property(
            self.handle,
            "Fan",
            "True" if fan_state else "False",
            "bool",
        )
        return self.GetFanState()

    def GetFPS(self):
        self.fps = self.xeneth.get_frame_rate(self.handle)
        return self.fps

    def SetFPS(self, fps):
        raise NotImplementedError(
            "XEVA cameras expose Framerate as a camera-specific enumeration; "
            "use IntegrationTime to control the acquisition rate"
        )

    def GetMaxMinFPS_ExposureTime(self):
        self.ExposureTimeMin, self.ExposureTimeMax = (
            self.xeneth.get_property_range_float(
                self.handle,
                "IntegrationTime",
            )
        )
        self.FPSMin = None
        self.FPSMax = None
        return (
            self.ExposureTimeMin,
            self.ExposureTimeMax,
            self.FPSMin,
            self.FPSMax,
        )

    def GetPixelFormat(self):
        frame_type = self.xeneth.get_frame_type(self.handle)
        bit_size = self.xeneth.get_bit_size(self.handle)

        if frame_type == FT_8_BPP_GRAY or bit_size <= 8:
            self.pixel_format = "mono8"
        elif frame_type == FT_32_BPP_GRAY:
            self.pixel_format = "mono32"
        elif frame_type == FT_16_BPP_GRAY or bit_size <= 16:
            self.pixel_format = "mono16"
        else:
            raise RuntimeError(
                f"Unsupported Xeneth frame type {frame_type}, {bit_size} bits"
            )
        return self.pixel_format

    def SetPixelFormat(self, pixel_format):
        requested_format = str(pixel_format).strip().casefold()
        accepted_names = {
            "native",
            self.pixel_format,
            self.pixel_format.replace("mono", ""),
            self.pixel_format.replace("mono", "") + "bit",
        }
        if requested_format not in accepted_names:
            raise NotImplementedError(
                "This simple Xeneth wrapper returns the camera's native pixel "
                f"format ({self.pixel_format})"
            )
        return self.pixel_format

    def GetROI(self):
        try:
            start_x = self.xeneth.get_property_long(self.handle, "WoiSX(0)")
            end_x = self.xeneth.get_property_long(self.handle, "WoiEX(0)")
            start_y = self.xeneth.get_property_long(self.handle, "WoiSY(0)")
            end_y = self.xeneth.get_property_long(self.handle, "WoiEY(0)")
        except XenethError:
            self.offset_x = 0
            self.offset_y = 0
            self.width = self.xeneth.get_width(self.handle)
            self.height = self.xeneth.get_height(self.handle)
        else:
            self.offset_x = start_x
            self.offset_y = start_y
            self.width = end_x - start_x + 1
            self.height = end_y - start_y + 1

        self.Nx = self.width
        self.Ny = self.height
        return self.offset_x, self.offset_y, self.width, self.height

    def SetROI(
        self,
        offset_x=None,
        offset_y=None,
        width=None,
        height=None,
        snap_values=True,
        enable=True,
        mode="nearest",
    ):
        sensor_width = self.xeneth.get_width(self.handle)
        sensor_height = self.xeneth.get_height(self.handle)

        if not enable:
            offset_x = 0
            offset_y = 0
            width = sensor_width
            height = sensor_height
        else:
            offset_x = self.offset_x if offset_x is None else int(offset_x)
            offset_y = self.offset_y if offset_y is None else int(offset_y)
            width = self.width if width is None else int(width)
            height = self.height if height is None else int(height)

        width = min(max(int(width), 1), sensor_width)
        height = min(max(int(height), 1), sensor_height)
        offset_x = min(max(int(offset_x), 0), sensor_width - width)
        offset_y = min(max(int(offset_y), 0), sensor_height - height)

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.xeneth.set_property_long(self.handle, "WoiSX(0)", offset_x)
            self.xeneth.set_property_long(
                self.handle,
                "WoiEX(0)",
                offset_x + width - 1,
            )
            self.xeneth.set_property_long(self.handle, "WoiSY(0)", offset_y)
            self.xeneth.set_property_long(
                self.handle,
                "WoiEY(0)",
                offset_y + height - 1,
            )
        finally:
            if was_capturing:
                self.StartAcquisition()
        return self.GetROI()

    def GetTriggerMode(self):
        if self._pseudo_software_trigger_enabled:
            self.trigger_mode = "On"
            self.trigger_source = "Software"
            return self.trigger_mode, self.trigger_source

        if self.CameraProductID == self.XEVA_USB_PRODUCT_ID:
            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
            return self.trigger_mode, self.trigger_source

        trigger_mode = self.xeneth.get_property_long(
            self.handle,
            "TriggerMode",
        )
        if trigger_mode == 0:
            self.trigger_mode = "Off"
            self.trigger_source = "FreeRun"
        else:
            self.trigger_mode = "On"
            self.trigger_source = "Hardware"
        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        self._pseudo_software_trigger_enabled = False
        self._pending_software_trigger_frame = None
        self._pending_software_trigger_frame_id = None

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            if self.CameraProductID == self.XEVA_CAMERA_LINK_PRODUCT_ID:
                self.xeneth.set_property_long(
                    self.handle,
                    "TriggerMode",
                    0,
                )
        finally:
            if was_capturing:
                self.StartAcquisition()
        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.acquisition_mode = "Continuous"
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        """Arm host-side pseudo triggering while the XEVA remains free-running."""
        self.SetContinuousMode()
        self.DrainImageBuffer(max_frames=4096)
        self._pseudo_software_trigger_enabled = True
        self.trigger_mode = "On"
        self.trigger_source = "Software"
        self.acquisition_mode = "Continuous"
        return self.GetTriggerMode()

    def IsSoftwareTriggerReady(self):
        return self._pseudo_software_trigger_enabled and self._capturing

    def WaitForSoftwareTriggerReady(
        self,
        timeout_ms=1000,
        poll_interval_s=0.001,
    ):
        if self.IsSoftwareTriggerReady():
            return True
        raise RuntimeError(
            "XEVA pseudo software-trigger mode is not armed; call "
            "SetSoftwareTriggerMode() first"
        )

    def FireSoftwareTrigger(
        self,
        wait_ready=True,
        ready_timeout_ms=1000,
        drain_stale_frames=True,
    ):
        """Drain stale frames, capture the next new frame, and hold it for GetFrame."""
        if wait_ready:
            self.WaitForSoftwareTriggerReady(timeout_ms=ready_timeout_ms)
        elif not self.IsSoftwareTriggerReady():
            raise RuntimeError(
                "XEVA pseudo software-trigger mode is not armed; call "
                "SetSoftwareTriggerMode() first"
            )

        if drain_stale_frames:
            self.DrainImageBuffer(max_frames=4096)

        triggered_frame = self._capture_frame_from_camera()
        self._pending_software_trigger_frame = triggered_frame
        self._pending_software_trigger_frame_id = self.frame_id
        return 0

    def SetHardwareTriggerMode(self, RiseEdgeOrFallEdge=1, lineNumber=0):
        self._pseudo_software_trigger_enabled = False
        self._pending_software_trigger_frame = None
        self._pending_software_trigger_frame_id = None

        if self.CameraProductID == self.XEVA_USB_PRODUCT_ID:
            raise NotImplementedError(
                f"XEVA-USB serial {self.CameraSerialNumber} does not expose "
                "hardware-trigger controls through Xeneth"
            )
        if RiseEdgeOrFallEdge != 1:
            raise NotImplementedError(
                "XEVA Camera Link does not expose trigger-edge polarity in "
                "the supplied Xeneth property set"
            )
        if int(lineNumber) != 0:
            raise ValueError("Xeneth exposes hardware trigger input line 0")

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.xeneth.set_property_long(self.handle, "TriggerMode", 1)
        finally:
            if was_capturing:
                self.StartAcquisition()
        self.trigger_polarity = RiseEdgeOrFallEdge
        return self.GetTriggerMode()


XevaCameraObject = CameraObject
