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
    def __init__(self, CameraIdx=0, CalibrationFile=None, PixelSize=4.5e-6, verbose=False):
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

        self.pixelFormat = None
        self.pixelFormatRaw = None
        self.GetPixelFormat()
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

    # ----------------------------
    # acquisition helpers
    # ----------------------------
    def StartAcquisition(self):
        ok = FliSdk_V2.FliGenicamCamera.ExecuteFeature(self.cam_context, "AcquisitionStart")
    def StopAcquisition(self):
        ok = FliSdk_V2.FliGenicamCamera.ExecuteFeature(self.cam_context, "AcquisitionStop")
        
    def ResetCamera(self):
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)
        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()

    def ResetBuffer(self):
        FliSdk_V2.ResetBuffer(self.cam_context)

    # ----------------------------
    # buffer
    # ----------------------------
    def SetBufferSizeInNumberOfFrames(self, n_frames):
        ok = FliSdk_V2.FliGenicamCamera.ExecuteFeature(self.cam_context, "AcquisitionStop")
        FliSdk_V2.Stop(self.cam_context)
        FliSdk_V2.SetBufferSizeInImages(self.cam_context, int(n_frames))
        FliSdk_V2.Start(self.cam_context)

        # restart acquisition in current mode
        if self._get_str("TriggerMode") == "Off":
            self.StartAcquisition()
        else:
            # software-triggered mode still needs AcquisitionStart armed
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
        ok ,self.trigger_mode= FliSdk_V2.FliGenicamCamera.GetStringFeature(self.cam_context, "TriggerMode")
        ok ,self.trigger_selector= FliSdk_V2.FliGenicamCamera.GetStringFeature(self.cam_context, "TriggerSelector")
        ok ,self.trigger_source= FliSdk_V2.FliGenicamCamera.GetStringFeature(self.cam_context, "TriggerSource")
        ok ,self.acquisition_mode= FliSdk_V2.FliGenicamCamera.GetStringFeature(self.cam_context, "AcquisitionMode")
        

        if self.verbose:
            print(
                "AcquisitionMode:", self.acquisition_mode,
                "| TriggerMode:", self.trigger_mode,
                "| TriggerSource:", self.trigger_source,
                "| TriggerSelector:", self.trigger_selector
            )

        return {
            "AcquisitionMode": self.acquisition_mode,
            "TriggerMode": self.trigger_mode,
            "TriggerSource": self.trigger_source,
            "TriggerSelector": self.trigger_selector,
        }

    def SetContinuousMode(self):
        """
        Free-running continuous acquisition.
        """
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)
        # CB2 AcquisitionMode supports Continuous
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "AcquisitionMode","Continuous")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerSelector","FrameStart")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerMode","Off")
        # Start camera acquisition
        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()
        self.GetTriggerMode()

    def SetSoftwareTriggerMode(self):
        """
        One trigger starts one frame.
        """
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "AcquisitionMode","Continuous")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerSelector","FrameStart")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerSource","Software")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerMode","On")
        # Arm acquisition; frames only come when TriggerSoftware is executed
        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()
        self.GetTriggerMode()
        
    def SetHardwareTriggerMode(self,lineNumber=0,RiseEdgeOrFallEdge=1):
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "AcquisitionMode","Continuous")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerSelector","FrameStart")
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerSource","Line"+str(lineNumber))
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerMode","On")
        
        if RiseEdgeOrFallEdge == 1:
            ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerActivation","RisingEdge")
            
        elif RiseEdgeOrFallEdge == -1:
            ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerActivation","FallingEdge")
        else:
            ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "TriggerActivation","RisingEdge")
            if self.verbose:
                print("RiseEdgeOrFallEdge need to be 1(RisingEdge) or -1(FallingEdge)")
            
        # Arm acquisition; frames only come when TriggerSoftware is executed
        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()
        self.ResetBuffer()
        
        self.GetTriggerMode()
    
    # ----------------------------
    # exposure
    # ----------------------------
    def SetExposureTime(self, exposure_time):
        self.GetMaxMinFPS_ExposureTime()
        
        ok, self.ExposureTimeMin = FliSdk_V2.FliGenicamCamera.GetDoubleMinFeature(
            self.cam_context, "ExposureTime"
        )
        ok, self.ExposureTimeMax = FliSdk_V2.FliGenicamCamera.GetDoubleMaxFeature(
            self.cam_context, "ExposureTime"
        )
        if exposure_time < self.ExposureTimeMin:
            if self.verbose:
                print("Exposure time too low, setting to minimum:", self.ExposureTimeMin)
            exposure_time = self.ExposureTimeMin

        if exposure_time > self.ExposureTimeMax:
            if self.verbose:
                print("Exposure time too high, setting to maximum:", self.ExposureTimeMax)
            exposure_time = self.ExposureTimeMax

        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)
        

        ok = FliSdk_V2.FliGenicamCamera.SetDoubleFeature(
            self.cam_context, "ExposureTime", exposure_time
        )
        if not ok:
            raise RuntimeError("Failed to set ExposureTime")

        self.ExposureTime = self.GetExposureTime()
        
        FliSdk_V2.Start(self.cam_context)
        # restart acquisition
        self.StartAcquisition()
        # self.GetFrame()  # trigger update of camera state
        
        return self.ExposureTime

    def GetExposureTime(self):
        ok, self.ExposureTime = FliSdk_V2.FliGenicamCamera.GetDoubleFeature(
            self.cam_context, "ExposureTime"
        )
        if not ok:
            raise RuntimeError("Failed to read ExposureTime")
        return self.ExposureTime
    
    def SetGain(self, gain):
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)
        try:
            FliSdk_V2.FliGenicamCamera.SetStringFeature(self.cam_context, "GainSelector", "All")
        except:
            pass
        FliSdk_V2.FliGenicamCamera.SetDoubleFeature(self.cam_context, "Gain", gain)
        self.gain=self.GetGain()
        FliSdk_V2.Start(self.cam_context)
        # self.GetFrame()  # trigger update of camera state
        
        self.StartAcquisition()
        
    def GetGain(self):
        ok, self.gain = FliSdk_V2.FliGenicamCamera.GetDoubleFeature(self.cam_context, "Gain")
        return self.gain

    def SetPixelFormat(self, pixel_format):
        if isinstance(pixel_format, str):
            pixel_format_key = pixel_format.strip().lower()
            if pixel_format_key == "mono8":
                sdk_pixel_format = "Mono8"
            elif pixel_format_key == "mono10":
                sdk_pixel_format = "Mono10"
            elif pixel_format_key == "mono12":
                sdk_pixel_format = "Mono12"
            elif pixel_format_key == "mono16":
                sdk_pixel_format = "Mono16"
            else:
                raise ValueError("pixel_format must be one of: mono8, mono10, mono12, mono16")
        else:
            raise TypeError("pixel_format must be a string")

        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)

        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(
            self.cam_context, "PixelFormat", sdk_pixel_format
        )
        if not ok:
            raise RuntimeError(f"Failed to set PixelFormat to {sdk_pixel_format}")

        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()
        self.GetPixelFormat()
        self.Nx, self.Ny = FliSdk_V2.GetCurrentImageDimension(self.cam_context)
        return self.pixelFormat

    def GetPixelFormat(self):
        ok, self.pixelFormatRaw = FliSdk_V2.FliGenicamCamera.GetStringFeature(
            self.cam_context, "PixelFormat"
        )
        if not ok:
            raise RuntimeError("Failed to get PixelFormat")

        pixel_format_key = self.pixelFormatRaw.strip().lower()
        if pixel_format_key == "mono8":
            self.pixelFormat = "mono8"
        elif pixel_format_key == "mono10":
            self.pixelFormat = "mono10"
        elif pixel_format_key == "mono12":
            self.pixelFormat = "mono12"
        elif pixel_format_key == "mono16":
            self.pixelFormat = "mono16"
        else:
            self.pixelFormat = self.pixelFormatRaw

        return self.pixelFormat
    
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
        # Stop acquisition (safe)
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)

        # Enable frame rate control
        try:
            FliSdk_V2.FliGenicamCamera.SetBooleanFeature(
                self.cam_context, "AcquisitionFrameRateEnable", True
            )
        except:
            pass  # some cameras don't expose this

        # Set FPS
        ok = FliSdk_V2.FliGenicamCamera.SetDoubleFeature(
            self.cam_context, "AcquisitionFrameRate", float(fps)
        )
        if not ok:
            raise RuntimeError("Failed to set AcquisitionFrameRate")

        # Restart
        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()
        self.GetFPS()
        # self.GetFrame()  # trigger update of camera state
        return self.fps
    
    def GetFPS(self):
        ok, self.fps = FliSdk_V2.FliGenicamCamera.GetDoubleFeature(
            self.cam_context, "AcquisitionFrameRate"
        )
        if not ok:
            raise RuntimeError("Failed to get FPS")
        return self.fps
    
    def GetMaxMinFPS_ExposureTime(self):
        ok, self.ExposureTimeMin = FliSdk_V2.FliGenicamCamera.GetDoubleMinFeature(
            self.cam_context, "ExposureTime"
        )
        ok, self.ExposureTimeMax = FliSdk_V2.FliGenicamCamera.GetDoubleMaxFeature(
            self.cam_context, "ExposureTime"
        )
        ok, self.FPSMin = FliSdk_V2.FliGenicamCamera.GetDoubleMinFeature(
            self.cam_context, "AcquisitionFrameRate"
        )
        ok, self.FPSMax = FliSdk_V2.FliGenicamCamera.GetDoubleMaxFeature(
            self.cam_context, "AcquisitionFrameRate"
        )
        
        return self.ExposureTimeMin, self.ExposureTimeMax, self.FPSMin, self.FPSMax
    
    def SetROI(self, offset_x=None, offset_y=None, width=None, height=None, snap_values=True, enable=True, mode='nearest'):
        """
        Set or disable ROI.

        enable=True  → apply ROI
        enable=False → full frame
        """

        # Stop acquisition (ROI features are locked during acquisition)
        self.StopAcquisition()
        FliSdk_V2.Stop(self.cam_context)

        # Select region
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(
            self.cam_context, "RegionSelector", "Region0"
        )
        if not ok:
            raise RuntimeError("Failed to set RegionSelector")

        # Get sensor max size
        ok, width_max = FliSdk_V2.FliGenicamCamera.GetIntegerFeature(self.cam_context, "WidthMax")
        ok, height_max = FliSdk_V2.FliGenicamCamera.GetIntegerFeature(self.cam_context, "HeightMax")
        
        if not enable:
            # Disable ROI → full frame
            if self.verbose:
                print("ROI disabled full frame")
            offset_x = 0
            offset_y = 0
            width    = width_max
            height =height_max
            # Apply ROI geometry
            settings = [
                ("OffsetX", offset_x),
                ("OffsetY", offset_y),
                ("Width", width),
                ("Height", height),
                
            ]

        else:
            if snap_values:
            # Snap values
                offset_x = snap_to_value(offset_x, 8, mode=mode, minimum=0)
                offset_y = snap_to_value(offset_y, 8,  mode=mode, minimum=0)
                width    = snap_to_value(width,    8,  mode=mode, minimum=8)
                height   = snap_to_value(height,   8, mode=mode, minimum=8)

                # Clamp to sensor
                width = min(width, width_max)
                height = min(height, height_max)

                offset_x = min(offset_x, width_max - width)
                offset_y = min(offset_y, height_max - height)

                # Snap offsets again (keep inside bounds)
                offset_x = snap_to_value(offset_x, 8, mode='floor', minimum=0)
                offset_y = snap_to_value(offset_y, 8,  mode='floor', minimum=0)

            # Apply ROI geometry
            settings = [
                ("Width", width),
                ("Height", height),
                ("OffsetX", offset_x),
                ("OffsetY", offset_y)
            ]
            if self.verbose:
                print(f"Requested ROI: x={offset_x}, y={offset_y}, width={width}, height={height} (mode={mode})")

        for name, val in settings:
            ok = FliSdk_V2.FliGenicamCamera.SetIntegerFeature(
                self.cam_context, name, int(val)
            )
            if not ok:
                raise RuntimeError(f"Failed to set {name}")

        if self.verbose:
            print(
                f"ROI: x={offset_x}, y={offset_y}, "
                f"width={width}, height={height}"
            )

        # Restart
        FliSdk_V2.Start(self.cam_context)
        self.StartAcquisition()
        self.GetROI()
        # Update dims
        self.Nx, self.Ny = FliSdk_V2.GetCurrentImageDimension(self.cam_context)
        if self.verbose:
            print(f"Current image size: {self.Nx} x {self.Ny}")
        
    def GetROI(self):
        ok = FliSdk_V2.FliGenicamCamera.SetStringFeature(
            self.cam_context, "RegionSelector", "Region0"
        )
        if not ok:
            raise RuntimeError("Failed to set RegionSelector")

        ok, self.offset_x = FliSdk_V2.FliGenicamCamera.GetIntegerFeature(self.cam_context, "OffsetX")
        ok, self.offset_y = FliSdk_V2.FliGenicamCamera.GetIntegerFeature(self.cam_context, "OffsetY")
        ok, self.width = FliSdk_V2.FliGenicamCamera.GetIntegerFeature(self.cam_context, "Width")
        ok, self.height = FliSdk_V2.FliGenicamCamera.GetIntegerFeature(self.cam_context, "Height")
        

        return self.offset_x, self.offset_y, self.width, self.height
    # ----------------------------
    # frame acquisition
    # ----------------------------
    def GetFrameID(self):
        self.frame_id = FliSdk_V2.GetBufferFilling(self.cam_context)
        return self.frame_id
    
    def GetFrame(self):
        """
        In continuous mode: return latest frame.
        In software trigger mode: send one software trigger, then return latest frame.
        """

        if self.trigger_mode == "On" and self.trigger_source == "Software":
            ok = FliSdk_V2.FliGenicamCamera.ExecuteFeature(self.cam_context, "TriggerSoftware")

        frame = FliSdk_V2.GetRawImageAsNumpyArray(self.cam_context, -1)
        # self.frame_id = self.GetFrameID()
        # print("Buffer filling:", self.frame_id)
        return frame