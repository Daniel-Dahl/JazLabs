
import atexit
import time
import weakref
import numpy as np

from .flir_flycapture2_ctypes import (
    FlyCapture2Library,
    FlyCapture2Error,
    fc2PropertyType,
    fc2Mode,
    fc2PixelFormat,
)


def snap_to_value(value, step, mode='nearest', minimum=0):
    value = int(value)
    step = int(step)
    minimum = int(minimum)

    if step <= 0:
        raise ValueError("step must be > 0")

    rel = value - minimum

    if mode == 'nearest':
        snapped = minimum + round(rel / step) * step
    elif mode == 'floor':
        snapped = minimum + (rel // step) * step
    elif mode == 'ceil':
        snapped = minimum + ((rel + step - 1) // step) * step
    else:
        raise ValueError("mode must be 'nearest', 'floor', or 'ceil'")

    if snapped < minimum:
        snapped = minimum

    return int(snapped)

def _debug_file_dump(message):
    lines = []
    lines.append(message)
    # Print to terminal
    for line in lines:
        print(line)
    # Dump to file
    with open("camera_log.txt", "a") as f:
        for line in lines:
            f.write(line + "\n")


def _shutdown_camera_ref(camera_ref):
    camera = camera_ref()
    if camera is not None:
        camera.shutdown()


class CameraObject:
    """
    FLIR / Point Grey camera object with the same public API style as the
    FirstLight camera objects.

    Notes
    -----
    - No multiprocessing / shared memory / OpenCV code.
    - ROI uses FlyCapture2 Format7 mode 0.
    - Frame data is returned as a NumPy array.
    """


    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=6.9e-6, dll_path=None,verbose=False):
        self.CameraIdx = int(CameraIdx)
        self.CalibrationFile = CalibrationFile
        self.PixelSize = PixelSize

        self._closed = False
        self._capturing = False

        self.fc2 = FlyCapture2Library(dll_path=dll_path)
        self.context = self.fc2.create_context()

        self.num_cameras = self.fc2.get_num_cameras(self.context)
        print(f"{self.num_cameras} cameras detected:")
        for k in range(self.num_cameras):
            print(f"{k}: FLIR camera {k}")
        print(f"Using camera {self.CameraIdx}")
        
        if self.num_cameras <= 0:
            self.shutdown()
            raise RuntimeError("No FLIR cameras detected")
        if self.CameraIdx < 0 or self.CameraIdx >= self.num_cameras:
            self.shutdown()
            raise IndexError(f"CameraIdx {self.CameraIdx} out of range for {self.num_cameras} cameras")

        self.guid = self.fc2.get_camera_from_index(self.context, self.CameraIdx)
        
        self.fc2.connect(self.context, self.guid)
        
        self.StartAcquisition() 
        
         # turn on embedded frame counter if available, which can be used for diagnostics and dropped frame detection
        try:
            self.frame_counter_available = self.fc2.enable_embedded_frame_counter(self.context, True)
            if not self.frame_counter_available:
                print("Embedded frame counter is not available on this FLIR camera")
        except Exception as e:
            self.frame_counter_available = False
            print(f"Could not enable embedded frame counter: {e}")
        self.image = self.fc2.create_image()
        

        self.trigger_mode = "Off"
        self.trigger_source = "FreeRun"
        self.trigger_selector = "FrameStart"
        self.acquisition_mode = "Continuous"
        self.trigger_polarity = 1
        self.trigger_source_raw = 7
        self.trigger_mode_raw = 0
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

        self.GetTriggerMode()
        self.GetROI()
        self.GetExposureTime()
        self.GetGain()
        self.GetFPS()
        self.GetPixelFormat()
        self.GetMaxMinFPS_ExposureTime()
        self.SetPixelFormat("mono16")
       
            

        atexit.register(_shutdown_camera_ref, weakref.ref(self))

    def __del__(self):
        self.shutdown()

    def shutdown(self):
        if getattr(self, "_closed", True):
            return
        self._closed = True

        try:
            if hasattr(self, "image") and self.image is not None:
                try:
                    self.fc2.destroy_image(self.image)
                except Exception:
                    pass
                self.image = None

            self.StopAcquisition()
        finally:
            try:
                self.fc2.disconnect(self.context)
            except Exception:
                pass
            try:
                self.fc2.destroy_context(self.context)
            except Exception:
                pass

    def StartAcquisition(self):
        if not self._capturing:
            # _debug_file_dump("StartAcquisition: calling fc2StartCapture")
            self.fc2.start_capture(self.context)
            self._capturing = True
            # _debug_file_dump("StartAcquisition: fc2StartCapture returned")

    def StopAcquisition(self):
        if self._capturing:
            self.fc2.stop_capture(self.context)
            self._capturing = False

    def ResetCamera(self):
        self.StopAcquisition()
        time.sleep(0.05)
        self.StartAcquisition()
        self.ResetBuffer()

    def ResetBuffer(self):
        if hasattr(self, "image") and self.image is not None:
            try:
                self.fc2.destroy_image(self.image)
            except Exception:
                pass

        time.sleep(0.05)
        self.image = self.fc2.create_image()
        self.frame_id = None

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        raise NotImplementedError("FlyCapture2 buffer sizing is not implemented in this wrapper.")

    def GetBufferSizeInNumberOfFrames(self):
        return -1

    def GetNumberOfFramesInBuffer(self):
        return -1

    def GetTriggerMode(self):
        trig = self.fc2.get_trigger_mode(self.context)

        self.trigger_mode = "On" if int(trig.onOff) else "Off"
        if self.trigger_mode == "Off":
            self.trigger_source = "FreeRun"
        else:
            self.trigger_source = "Software" if int(trig.source) == 7 else f"line {int(trig.source)}"

        self.trigger_selector = "FrameStart"
        self.acquisition_mode = "Continuous"
        self.trigger_polarity = 1 if int(trig.polarity) else -1
        self.trigger_source_raw = int(trig.source)
        self.trigger_mode_raw = int(trig.mode)
        self.trigger_parameter = int(trig.parameter)

        return self.trigger_mode, self.trigger_source

    def SetContinuousMode(self):
        trig = self.fc2.get_trigger_mode(self.context)
        trig.onOff = 0
        self.fc2.set_trigger_mode(self.context, trig)
        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        trig = self.fc2.get_trigger_mode(self.context)
        trig.onOff = 1
        trig.source = 7
        trig.mode = 0
        trig.parameter = 0
        self.fc2.set_trigger_mode(self.context, trig)
        self.ResetBuffer()
        return self.GetTriggerMode()

    def SetHardwareTriggerMode(self, RiseEdgeOrFallEdge=1, lineNumber=0):
        trig = self.fc2.get_trigger_mode(self.context)
        trig.onOff = 1
        trig.source = int(lineNumber)
        trig.mode = 0
        trig.parameter = 0
        trig.polarity = 1 if RiseEdgeOrFallEdge == 1 else 0
        self.fc2.set_trigger_mode(self.context, trig)
        self.ResetBuffer()
        return self.GetTriggerMode()

    def _get_property_info(self, prop_type):
        return self.fc2.get_property_info(self.context, int(prop_type))

    def _get_property_abs(self, prop_type):
        prop = self.fc2.get_property(self.context, int(prop_type))
        return float(prop.absValue)

    def _set_property_abs(self, prop_type, value):
        prop = self.fc2.get_property(self.context, int(prop_type))
        prop.absControl = 1
        prop.autoManualMode = 0
        prop.onePush = 0
        prop.onOff = 1
        prop.absValue = float(value)
        self.fc2.set_property(self.context, prop)

    def SetExposureTime(self, exposure_time):
        self.GetMaxMinFPS_ExposureTime()

        if exposure_time < self.ExposureTimeMin:
            print("Exposure time too low, setting to minimum:", self.ExposureTimeMin)
            exposure_time = self.ExposureTimeMin

        if exposure_time > self.ExposureTimeMax:
            print("Exposure time too high, setting to maximum:", self.ExposureTimeMax)
            exposure_time = self.ExposureTimeMax

        self._set_property_abs(fc2PropertyType.FC2_SHUTTER, exposure_time)
        self.ExposureTime = self.GetExposureTime()
        return self.ExposureTime

    def GetExposureTime(self):
        self.ExposureTime = self._get_property_abs(fc2PropertyType.FC2_SHUTTER)
        return self.ExposureTime

    def SetGain(self, gain):
        info = self._get_property_info(fc2PropertyType.FC2_GAIN)
        gain_min = float(info.absMin)
        gain_max = float(info.absMax)

        if gain < gain_min:
            print("Gain too low, setting to minimum:", gain_min)
            gain = gain_min
        if gain > gain_max:
            print("Gain too high, setting to maximum:", gain_max)
            gain = gain_max

        self._set_property_abs(fc2PropertyType.FC2_GAIN, gain)
        self.gain = self.GetGain()
        return self.gain

    def GetGain(self):
        self.gain = self._get_property_abs(fc2PropertyType.FC2_GAIN)
        return self.gain

    def SetFPS(self, fps):
        self.GetMaxMinFPS_ExposureTime()

        if fps < self.FPSMin:
            print("FPS too low, setting to minimum:", self.FPSMin)
            fps = self.FPSMin
        if fps > self.FPSMax:
            print("FPS too high, setting to maximum:", self.FPSMax)
            fps = self.FPSMax

        self._set_property_abs(fc2PropertyType.FC2_FRAME_RATE, fps)
        self.fps = self.GetFPS()
        return self.fps

    def GetFPS(self):
        self.fps = self._get_property_abs(fc2PropertyType.FC2_FRAME_RATE)
        return self.fps

    def GetMaxMinFPS_ExposureTime(self):
        exp_info = self._get_property_info(fc2PropertyType.FC2_SHUTTER)
        fps_info = self._get_property_info(fc2PropertyType.FC2_FRAME_RATE)

        self.ExposureTimeMin = float(exp_info.absMin)
        self.ExposureTimeMax = float(exp_info.absMax)
        self.FPSMin = float(fps_info.absMin)
        self.FPSMax = float(fps_info.absMax)

        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax

    def _get_current_fc2_pixel_format(self):
        settings, _, _ = self.fc2.get_format7_configuration(self.context)
        return int(settings.pixelFormat)

    def SetPixelFormat(self, pixel_format):
        if isinstance(pixel_format, str):
            pixel_format_key = pixel_format.strip().lower()
            if pixel_format_key == "mono8":
                fc2_pixel_format = int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO8)
            elif pixel_format_key == "mono10":
                # FlyCapture2 does not expose a clean separate mono10 path here,
                # so keep this mapped onto the common 16-bit mono container.
                fc2_pixel_format = int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO16)
            elif pixel_format_key == "mono12":
                fc2_pixel_format = int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO12)
            elif pixel_format_key == "mono16":
                fc2_pixel_format = int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO16)
            else:
                raise ValueError("pixel_format must be one of: mono8, mono10, mono12, mono16")
        elif isinstance(pixel_format, int):
            fc2_pixel_format = int(pixel_format)
        else:
            raise TypeError("pixel_format must be a string or integer")

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.pixel_format_fc2 = self.fc2.set_pixel_format(self.context, fc2_pixel_format)

            if self.pixel_format_fc2 == int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO8):
                self.pixel_format = "mono8"
            elif self.pixel_format_fc2 == int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO12):
                self.pixel_format = "mono12"
            elif self.pixel_format_fc2 == int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO16):
                self.pixel_format = "mono16"
            else:
                self.pixel_format = f"fc2:{self.pixel_format_fc2}"
        finally:
            if was_capturing:
                self.StartAcquisition()
        return self.pixel_format

    def GetPixelFormat(self):
        self.pixel_format_fc2 = self.fc2.get_pixel_format(self.context)

        if self.pixel_format_fc2 == int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO8):
            self.pixel_format = "mono8"
        elif self.pixel_format_fc2 == int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO12):
            self.pixel_format = "mono12"
        elif self.pixel_format_fc2 == int(fc2PixelFormat.FC2_PIXEL_FORMAT_MONO16):
            self.pixel_format = "mono16"
        else:
            self.pixel_format = f"fc2:{self.pixel_format_fc2}"

        return self.pixel_format

    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None,snap_values=True, enable=True, mode='nearest'):
        """
        Set or disable ROI.

        enable=True  → apply ROI
        enable=False → full frame
        """
        format7_mode = int(fc2Mode.FC2_MODE_0)

        info, supported = self.fc2.get_format7_info(self.context, mode=format7_mode)
        if not supported:
            raise RuntimeError("Format7 mode 0 is not supported by this camera")

        if not enable:
            offset_x = 0
            offset_y = 0
            width = int(info.maxWidth)
            height = int(info.maxHeight)
        else:
            current_settings, _, _ = self.fc2.get_format7_configuration(self.context)
            if offset_x is None:
                offset_x = int(current_settings.offsetX)
            if offset_y is None:
                offset_y = int(current_settings.offsetY)
            if width is None:
                width = int(current_settings.width)
            if height is None:
                height = int(current_settings.height)
        
        info, supported = self.fc2.get_format7_info(self.context, mode=int(fc2Mode.FC2_MODE_0))
        if not supported:
            raise RuntimeError("Format7 mode 0 is not supported by this camera")
        if snap_values:
            offset_x = snap_to_value(offset_x, info.offsetHStepSize, mode, minimum=0)
            offset_y = snap_to_value(offset_y, info.offsetVStepSize, mode, minimum=0)
            width = snap_to_value(width, info.imageHStepSize, mode, minimum=info.imageHStepSize)
            height = snap_to_value(height, info.imageVStepSize, mode, minimum=info.imageVStepSize)

            width = min(width, int(info.maxWidth))
            height = min(height, int(info.maxHeight))

            max_offset_x = max(0, int(info.maxWidth) - width)
            max_offset_y = max(0, int(info.maxHeight) - height)

            offset_x = min(offset_x, snap_to_value(max_offset_x, info.offsetHStepSize, 'floor', minimum=0))
            offset_y = min(offset_y, snap_to_value(max_offset_y, info.offsetVStepSize, 'floor', minimum=0))



        current_settings, current_packet_size, _ = self.fc2.get_format7_configuration(self.context)

        new_settings = self.fc2.make_format7_settings(
            mode=format7_mode,
            offsetX=offset_x,
            offsetY=offset_y,
            width=width,
            height=height,
            pixelFormat=int(current_settings.pixelFormat.value),
        )

        settings_are_valid, packet_info = self.fc2.validate_format7_settings(self.context, new_settings)
        if not settings_are_valid:
            raise RuntimeError("Requested ROI is not valid for this FLIR camera")

        packet_size = int(packet_info.recommendedBytesPerPacket)
        print(packet_size)
        if packet_size <= 0:
            packet_size = int(current_packet_size)
        if packet_size <= 0:
            packet_size = int(info.packetSize)
        if packet_size <= 0:
            packet_size = int(info.maxPacketSize)

        was_capturing = self._capturing
        if was_capturing:
            self.StopAcquisition()
        try:
            self.fc2.set_format7_configuration_packet(self.context, new_settings, packet_size)
        finally:
            if was_capturing:
                self.StartAcquisition()

        self.offset_x = offset_x
        self.offset_y = offset_y
        self.width = width
        self.height = height
        self.Nx = width
        self.Ny = height

        return self.GetROI()

    def GetROI(self):
        settings, packet_size, percentage = self.fc2.get_format7_configuration(self.context)

        self.offset_x = int(settings.offsetX)
        self.offset_y = int(settings.offsetY)
        self.width = int(settings.width)
        self.height = int(settings.height)
        self.packet_size = int(packet_size)
        self.packet_percentage = float(percentage)
        self.Nx = self.width
        self.Ny = self.height

        return self.offset_x, self.offset_y, self.width, self.height
    
    def GetFrameID(self):
        try:
            metadata = self.fc2.get_image_metadata(self.image)
            self.frame_id = int(metadata.embeddedFrameCounter)
        except Exception:
            self.frame_id = -1
        return self.frame_id
    
    def GetFrame(self):
        """
        In continuous mode: return latest frame.
        In software trigger mode: send one software trigger, then return latest frame.
        """
        if self.trigger_mode == "On" and self.trigger_source == "Software":
            self.fc2.fire_software_trigger(self.context)

        self.fc2.retrieve_buffer(self.context, self.image)

        if self.frame_counter_available:
            self.frame_id = self.GetFrameID()

        frame = self.fc2.image_to_numpy(self.image)
        return frame
    
    
    
    
