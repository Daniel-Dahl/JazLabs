# from Lab_Equipment.Config import config
import numpy as np
import os
import sys
import atexit
import time 
# Detect OS and set SDK path
if sys.platform.startswith("win"):
    FliSdk_V2lib = r"C:\Program Files\FirstLightImaging\FliSdk\Python\lib"
elif sys.platform.startswith("linux"):
    FliSdk_V2lib = "/opt/FirstLightImaging/FliSdk/Python/lib"
else:
    raise RuntimeError(f"Unsupported OS: {sys.platform}")

if not os.path.isdir(FliSdk_V2lib):
    raise FileNotFoundError(f"FLI SDK path not found: {FliSdk_V2lib}")

if FliSdk_V2lib not in sys.path:
    sys.path.append(FliSdk_V2lib)

import FliSdk_V2

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

class CameraObject:
    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=15.0e-6, verbose=False):
        self.cam_context = FliSdk_V2.Init()
        self._closed = False
        self.verbose = verbose

        self.grabber_list = FliSdk_V2.DetectGrabbers(self.cam_context)
        self.camera_list = FliSdk_V2.DetectCameras(self.cam_context)

        self.num_cameras = len(self.camera_list)
        if self.verbose:
            print(f"{self.num_cameras} cameras detected:")
            for k, name in enumerate(self.camera_list):
                print(f"{k}: {name}")
            print(f"Using camera {CameraIdx}")

        ok = FliSdk_V2.SetCamera(self.cam_context, self.camera_list[CameraIdx])
        if not ok:
            raise RuntimeError("Failed to set camera")

        FliSdk_V2.SetMode(self.cam_context, FliSdk_V2.Mode.Full)

        ok = FliSdk_V2.Update(self.cam_context)
        if not ok:
            raise RuntimeError("Failed to update SDK after setting camera")

        self.Nx, self.Ny = FliSdk_V2.GetCurrentImageDimension(self.cam_context)
        
        self.pixelFormat = "mono14"
        self.pixelFormatRaw = "Mono14"
        self.GetExposureTime()
       
        # Start SDK/grabber first
        FliSdk_V2.Start(self.cam_context)
        self.SetContinuousMode()
        

        atexit.register(self.shutdown)

    def __del__(self):
        self.shutdown()

    # ----------------------------
    # shutdown
    # ----------------------------
    def shutdown(self):
        if getattr(self, "_closed", True):
            return
        self._closed = True
        try:
            self.StopAcquisition()
            FliSdk_V2.Stop(self.cam_context)
        finally:
            try:
                FliSdk_V2.Exit(self.cam_context)
            except Exception:
                pass
    
    def StartAcquisition(self):
        ok = FliSdk_V2.Start(self.cam_context)
        if not ok:
            raise RuntimeError("Failed to start acquisition")
    def StopAcquisition(self):
        ok = FliSdk_V2.Stop(self.cam_context)
        if not ok:
            raise RuntimeError("Failed to stop acquisition")
        
    def ResetCamera(self):
        self.StopAcquisition()
        self.StartAcquisition()

    def ResetBuffer(self):
        FliSdk_V2.ResetBuffer(self.cam_context)

    # ----------------------------
    # buffer
    # ----------------------------
    def SetBufferSizeInNumberOfFrames(self, n_frames):
        self.StopAcquisition()
        FliSdk_V2.SetBufferSizeInImages(self.cam_context, int(n_frames))
        self.StartAcquisition()

    def GetBufferSizeInNumberOfFrames(self):
        buffsize_mb = FliSdk_V2.GetBufferSize(self.cam_context)
        buffsize_bytes = buffsize_mb * 1024 * 1024

        width, height = FliSdk_V2.GetCurrentImageDimension(self.cam_context)
        bytes_per_pixel = 1 if FliSdk_V2.IsMono8Pixel(self.cam_context) else 2
        bytes_per_frame = width * height * bytes_per_pixel

        return int(buffsize_bytes // bytes_per_frame)
    def GetNumberOfFramesInBuffer(self):
        return FliSdk_V2.GetBufferFilling(self.cam_context)

    # ----------------------------
    # trigger / mode configuration
    # ----------------------------
    def GetTriggerMode(self):
        commandstr='swsynchro source raw'
        errorval, trigger_source_raw = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        
        commandstr='swsynchro raw'
        errorval, trigger_mode_raw = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        
        commandstr='extsynchro raw'
        errorval, self.acquisition_mode = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        
        trigger_mode_norm = str(trigger_mode_raw).strip().lower()
        trigger_source_norm = str(trigger_source_raw).strip().lower()
        self.trigger_mode = "On" if trigger_mode_norm == "on" else "Off"
        if self.trigger_mode == "Off":
            self.trigger_source = "FreeRun"
        elif trigger_source_norm == "swtrig":
            self.trigger_source = "Software"
        elif trigger_source_norm == "external":
            self.trigger_source = "line 0"
        else:
            self.trigger_source = str(trigger_source_raw)
        
        

        if self.verbose:
            print(
                "AcquisitionMode:", self.acquisition_mode,
                "| TriggerMode:", self.trigger_mode,
                "| TriggerSource:", self.trigger_source,
            )
        return  self.trigger_mode, self.trigger_source,


    def SetContinuousMode(self):
        """
        Free-running continuous acquisition.
        """
        
        commandstr='set swsynchro off'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        commandstr='set extsynchro off'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        """
        One trigger starts one frame.
        """
        # set software trigger
        
        commandstr='set swsynchro source swtrig'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        commandstr='set swsynchro on'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        commandstr='set extsynchro off'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
    
        self.GetTriggerMode()
        
    def SetHardwareTriggerMode(self, RiseEdgeOrFallEdge=-1, lineNumber=0):
        commandstr='set swsynchro off'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        commandstr='set swsynchro source external'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        commandstr='set extsynchro on'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
    
        if RiseEdgeOrFallEdge == 1:
            commandstr='set extsynchro polarity Custom'
            errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        elif RiseEdgeOrFallEdge == -1:
            commandstr='set extsynchro polarity inverted'
            errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)    
        else:
            commandstr='set extsynchro polarity inverted'
            errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
            if self.verbose:
                print("RiseEdgeOrFallEdge need to be 1(custom) or -1(FallingEdge)")
                print("Set to default FallingEdge")
        
        self.ResetBuffer()
        # Arm acquisition; frames only come when TriggerSoftware is executed
        self.GetTriggerMode()
        
    def SetTriggerDelay(self, delay_ms):
        commandstr="set syncdelay "+ str(delay_ms)
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        commandstr="syncdelay raw"
        self.GetTriggerDelay()
        return self.TriggerDelay
    
    def GetTriggerDelay(self):
        commandstr="syncdelay raw"
        _, delay = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        self.TriggerDelay = float(delay)
        return self.TriggerDelay
    # ----------------------------
    # exposure
    # ----------------------------
    def SetExposureTime(self, exposure_time):
        self.GetMaxMinFPS_ExposureTime()
        
        if exposure_time < self.ExposureTimeMin:
            if self.verbose:
                print("Exposure time too low, setting to minimum:", self.ExposureTimeMin)
            exposure_time = self.ExposureTimeMin

        if exposure_time > self.ExposureTimeMax:
            if self.verbose:
                print("Exposure time too high, setting to maximum:", self.ExposureTimeMax)
            exposure_time = self.ExposureTimeMax
        commandstr='set tint ' + str(exposure_time*1e-6)
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
                
        self.GetExposureTime()
        return self.ExposureTime

    def GetExposureTime(self):
        commandstr='tint raw' 
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        self.ExposureTime=(float(response)*1e6)
        return self.ExposureTime
    def SetFPS(self, fps):
        self.GetMaxMinFPS_ExposureTime()
        if fps < self.FPSMin:
            if self.verbose:
                print("FPS too low, setting to minimum:", self.FPSMin)
            fps = self.FPSMin
        if fps > self.FPSMax:
            if self.verbose:
                print("FPS too high, setting to maximum:", self.FPSMax)
            fps = self.FPSMax
        commandstr='set fps ' + str(fps)
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        self.GetFPS()
        self.GetMaxMinFPS_ExposureTime()
        return self.fps
    def GetFPS(self):
        commandstr='fps raw'
        errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        self.fps=(float(response))
        return self.fps
    
    def GetMaxMinFPS_ExposureTime(self):
        commandstr='maxtint raw'
        ok, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        self.ExposureTimeMax=(float(response)*1e6)
        commandstr='mintint raw'
        ok, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        self.ExposureTimeMin = float(response)*1e6
        commandstr='maxfps raw'
        ok, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        self.FPSMax = float(response)
        commandstr='minfps raw'
        ok, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        self.FPSMin = float(response)

        # print(f"ExposureTime range: {self.ExposureTimeMin} - {self.ExposureTimeMax} us")
        # print(f"FPS range: {self.FPSMin} - {self.FPSMax} fps")
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax
    
    def SetGain(self, gain):
        if gain==0:
            commandstr="set sensibility low"
            errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        elif gain==1:
            commandstr="set sensibility medium"
            errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        elif gain==2:
            commandstr="set sensibility high"
            errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr) 
        else:
            if self.verbose:
                print("Gain value need to be 0(low), 1(medium) or 2(high)")
        self.GetGain()
        return self.gain
    
    def GetGain(self):
        commandstr="sensibility raw"
        _,gain = FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context, commandstr)
        if gain=="low":
            self.gain=0
        elif gain=="medium":
            self.gain=1
        elif gain=="high":
            self.gain=2
            
        return self.gain

    def SetPixelFormat(self, pixel_format):
        """
        Keep a consistent camera API across vendors.

        The CRED3-2Lite wrapper does not support changing pixel format through
        this interface, so this method only accepts the already-active Mono14
        format and raises for anything else.
        """
        if not isinstance(pixel_format, str):
            raise TypeError("pixel_format must be a string")

        pixel_format_key = pixel_format.strip().lower()
        if pixel_format_key not in ("mono14",):
            raise NotImplementedError(
                "FirstLight CRED3-2Lite pixel format cannot be changed in this wrapper. "
                "Current fixed format is mono14."
            )

        self.pixelFormat = "mono14"
        self.pixelFormatRaw = "Mono14"
        return self.pixelFormat

    def GetPixelFormat(self):
        self.pixelFormat = "mono14"
        self.pixelFormatRaw = "Mono14"
        return self.pixelFormat
    
    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, enable=True,
               snap_values=True, mode='nearest'):
        """
        Set or disable ROI.

        enable=True  → apply ROI
        enable=False → full frame
        """
        # these are hard coded as I dont think there is a function in the camera to get the max 
        # frame size values.
        height_max=512
        width_max=640
        
        if not enable:
            offset_x = 0
            offset_y = 0
            width = width_max
            height = height_max
            
        if snap_values:
            offset_x = snap_to_value(offset_x, 32, mode=mode, minimum=0)
            offset_y = snap_to_value(offset_y, 4,  mode=mode, minimum=0)
            width    = snap_to_value(width,    4,  mode=mode, minimum=4)
            height   = snap_to_value(height,   32, mode=mode, minimum=32)
            width = min(width, width_max)
            height = min(height, height_max)

            offset_x = min(offset_x, width_max - width)
            offset_y = min(offset_y, height_max - height)

            # Snap offsets again (keep inside bounds)
            offset_x = snap_to_value(offset_x, 32, mode='floor', minimum=0)
            offset_y = snap_to_value(offset_y, 4,  mode='floor', minimum=0)
            
        # even if the user has set enable=False, we still need to send the cropping commands to reset to full frame
        # this is so that the GetROI method can report the correct full-frame geometry, 
        # and so that the camera is actually set to full frame (disabling cropping)
        commandstr="set cropping columns "+ str(offset_x)+"-"+str((offset_x+width)-1)
        FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context,commandstr)

        commandstr="set cropping rows "+ str(offset_y)+"-"+str((offset_y+height)-1)
        FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context,commandstr)

        if not enable:
            # Disable ROI → full frame
            if self.verbose:
                print("ROI disabled full frame")
            FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context,'set cropping off')


        else:    
            FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context,'set cropping on')
        
        self.Nx, self.Ny = FliSdk_V2.GetCurrentImageDimension(self.cam_context)

        if self.verbose:
            print(
                f"ROI: x={offset_x}, y={offset_y}, "
                f"width={width}, height={height}"
            )
        # Update dims
        if self.verbose:
            print(f"Current image size: {self.Nx} x {self.Ny}")
        self.GetROI()
        
    def GetROI(self):
        commandstr="cropping rows raw" 
        errorval,respone=FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context,commandstr)
        self.offset_y, temp = map(int, respone.split('-'))
        self.height = temp - self.offset_y + 1
        commandstr="cropping columns raw" 
        errorval,respone=FliSdk_V2.FliSerialCamera.SendCommand(self.cam_context,commandstr)
        self.offset_x, temp = map(int, respone.split('-'))
        self.width = temp - self.offset_x + 1

        return self.offset_x, self.offset_y, self.width, self.height
    
    def GetFrameID(self):
        self.frame_id = FliSdk_V2.GetBufferFilling(self.cam_context)
        return self.frame_id
    # ----------------------------
    # frame acquisition
    # ----------------------------
    def GetFrame(self):
        """
        In continuous mode: return latest frame.
        In software trigger mode: send one software trigger, then return latest frame.
        """

        if self.trigger_mode == "On" and self.trigger_source == "Software":
            errorval = FliSdk_V2.FliCredThree.SoftwareTrig(self.cam_context)

        frame = FliSdk_V2.GetRawImageAsNumpyArray(self.cam_context, -1)
        
        # self.frame_id = self.GetFrameID()
        # print("Buffer filling:", self.frame_id)
        return frame
