# import Lab_Equipment.Config.config as config
from Lab_Equipment.Config import config 
import numpy as np
import matplotlib.pyplot as plt
import multiprocessing
from multiprocessing import shared_memory
import copy
import cv2
import time
import ctypes
import Lab_Equipment.Camera.CameraObject as CamForm
import os
import sys
import pip
import arena_api
import arena_api.system

# from vimba import * this is the old version 
class LucidVisCameraObject():
    def __init__(self,CameraIdx=0,CalibrationFile=None,PixelSize=5e-6):
        super().__init__() # inherit from parent class  
        devices = arena_api.system.system.create_device()
        device = devices[CameraIdx]
        CameraProperties = device.nodemap
        self.Nx=CameraProperties['Width'].max
        self.Ny=CameraProperties['Height'].max
        
        # set the frame grabing properties
        CameraProperties["AcquisitionMode"].value = "Continuous"
        CameraProperties["TriggerMode"].value = "On"
        CameraProperties["TriggerSource"].value = "Software"

        CameraProperties["ExposureAuto"].value = "Off"
        min_exp = CameraProperties["ExposureTime"].min
        max_exp = CameraProperties["ExposureTime"].max
        print("Min Exposure= ",min_exp)
        print("Max Exposure= ",max_exp)

        CameraProperties["ExposureTime"].value = (min_exp + max_exp) / 2
        ExposureTime=CameraProperties["ExposureTime"].value
        CameraProperties['PixelFormat'].value = 'Mono12'
        
        device.start_stream()
        
        CameraProperties["TriggerSoftware"].execute()   # camera takes one exposure
        image_buffer = device.get_buffer()
        if CameraProperties['PixelFormat'].value == 'Mono12':
            frame_ptr = ctypes.cast(image_buffer.pdata,ctypes.POINTER(ctypes.c_ushort))
        else :
            frame_ptr = ctypes.cast(image_buffer.pdata,ctypes.POINTER(ctypes.c_ubyte))
            
        nparray_reshaped = np.ctypeslib.as_array(frame_ptr,(image_buffer.height, image_buffer.width))
        frame=copy.deepcopy(nparray_reshaped)
        device.requeue_buffer(image_buffer)
        
        frame =CamForm.adjust_array_dimensions(frame)
        Framedtype=frame.dtype
        FrameDim=frame.shape
        FrameHeight = int(FrameDim[0])
        FrameWidth = int(FrameDim[1])
        FrameBuffer =CamForm.adjust_array_dimensions(np.squeeze((frame)))
        plt.imshow(FrameBuffer, cmap='gray')
        device.stop_stream()
        arena_api.system.system.destroy_device()
   
        

        self.CamObject=CamForm.GeneralCameraObject("LucidVisionCamera",CalibrationFile,self.Nx,self.Ny,FrameWidth,FrameHeight,FrameDim,Framedtype,FrameBuffer,PixelSize,ExposureTime,0,0,0,0,CameraName=CameraIdx)
        self.CamProcess= CamForm.start_FrameCaptureThread(self.CamObject,LucidVisionFrameCaptureThread)
        
                          
       
    def __del__(self):
        """Destructor to disconnect from camera."""
        print(self.CamObject.CameraType +" Class has been destroyed")
        self.CamObject.terminateCamera.set()# stop the camera thread
        self.CamObject.shm.close() # close access to shared memory
        self.CamObject.shm_digholo.close() # close access to shared memory
        self.CamProcess.terminate()
        self.CamObject.shm.unlink() # clean up the shared memory space
        self.CamObject.shm_digholo.unlink() # clean up the shared memory space

# so this camera SDK is so fucking shit interms of examples and I have no idea how to chnage
# the tigger so had to look at the text commands in the gui and these were the commands
# so put them in a function like a normal person  
def GetTriggerMode(CameraProperties):
    # set external trigger
    response=CameraProperties["TriggerSource"].value
    if  response == 'Software':
        mode=0   
    else:
        mode=1
    return mode

def SetTriggerMode(device,CameraProperties,triggermode):
    device.stop_stream()
    if triggermode==0:
        # set software trigger
        CameraProperties["AcquisitionMode"].value = "Continuous"
        CameraProperties["TriggerMode"].value = "On"
        CameraProperties["TriggerSource"].value = "Software"
    elif triggermode==1:
        # set external trigger
        CameraProperties["AcquisitionMode"].value = "Continuous"
        CameraProperties["TriggerMode"].value = "On"
        CameraProperties["TriggerSource"].value = "Line0"
        
    elif triggermode==-1:
        CameraProperties["TriggerMode"].value = "Off"
    device.start_stream()
    
def snap_to_value(x,snap_value, mode='nearest'):
    """
    Snap x to a multiple of 32.
    mode: 'nearest' (ties up), 'up' (ceiling), or 'down' (floor).
    Returns int.
    """
    x = float(x)
    if mode == 'up':
        return int(snap_value * np.ceil(x / snap_value))
    if mode == 'down':
        return int(snap_value * np.floor(x / snap_value))
    # nearest (ties go up)
    down = snap_value * np.floor(x / snap_value)
    up   = down + snap_value
    return int(up if (x - down) >= (up - x) else down)

        
def LucidVisionFrameCaptureThread(queue,Cam_Calibtation,SetCalibrationEvent,
                             CameraIdx,GetFrameFlag,GetFrameFlag_digholo,terminateCamFlag,FrameObtained,
                             shared_memory_name,shared_memory_name_digholo,FrameHeight,FrameWidth,RIO_xpoint,RIO_ypoint,ClipFrame,
                             ResetFrameMemFlag,CleanFrameMemFlag,SetRIOFlag,SetDisplayWindowScaleFlag,
                                   SetExposureFlag,SetfpsFlag,SetTriggerFlag,SetGainFlag,SetBiasStateFlag,SetClearCamBufferFlag,
                                   SetInternalFrameBufferSizeFlag,SetReSetCameraFlag,
                                   SetFrameClipingMinFlag,SetFrameClipingMaxFlag,
                                   SetFrameCaptureDelayFlag,ContinuesMode,SingleFrameMode,DoorBell,FrameCaptured,
                                   shared_float,shared_int,shared_flag_int):
    # Setup Shared memory
    # queue.put("testa")   
    shm = shared_memory.SharedMemory(name=shared_memory_name)
    frame_buffer = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint16, buffer=shm.buf) 
    
    shm_digholo = shared_memory.SharedMemory(name=shared_memory_name_digholo)
    frame_buffer_digholo = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint16, buffer=shm_digholo.buf) 
    # Need to make a empty array so that a pointer can be made to get the frame from Xenics getframe
    frame= np.zeros((FrameHeight.value, FrameWidth.value),dtype=np.uint16)
    devices = arena_api.system.system.create_device()
    device = devices[CameraIdx]
    CameraProperties = device.nodemap
    
    # Set up the intial properties of the camera
    CameraProperties["AcquisitionMode"].value = "Continuous"
    CameraProperties["TriggerMode"].value = "Off"
    CameraProperties["TriggerSource"].value = "Software"
    CameraProperties["ExposureAuto"].value = "Off"
    ExposureTimeMin=CameraProperties["ExposureTime"].min 
    ExposureTimeMax=CameraProperties["ExposureTime"].max 
    
    minfps=CameraProperties["AcquisitionFrameRate"].min 
    maxfps=CameraProperties["AcquisitionFrameRate"].max

    ContinuesMode.set()
    opencvWindowName="Lucid Vision Camera Image"
    settriggermode=0
    frameMinClip=0
    frameMaxClip=0
    scale=1
    DisplayFrameInSingleCapature=True
    device.start_stream(10)
    
    while not terminateCamFlag.is_set():
        if (ContinuesMode.is_set()):
            device.stop_stream()
            CameraProperties["TriggerMode"].value = "Off"
            device.start_stream(10)
            image_buffer = device.get_buffer()
            if CameraProperties['PixelFormat'].value == 'Mono12':
                frame_ptr = ctypes.cast(image_buffer.pdata,ctypes.POINTER(ctypes.c_ushort))
            else :
                frame_ptr = ctypes.cast(image_buffer.pdata,ctypes.POINTER(ctypes.c_ubyte))
                
            nparray_reshaped = np.ctypeslib.as_array(frame_ptr,(image_buffer.height, image_buffer.width))
            frame=copy.deepcopy(nparray_reshaped)
            device.requeue_buffer(image_buffer)
            Frame_int =CamForm.adjust_array_dimensions(frame)
            if ClipFrame.value:
                Frame_int =CamForm.clip_frame(Frame_int,
                                              vmin_percent=frameMinClip,
                                              vmax_percent=frameMaxClip)
                Frame_intFordisplay = CamForm.rescaleFrame_256(Frame_int)
            else:
                Frame_intFordisplay=np.copy(Frame_int)
            if scale!=1:
                Frame_intFordisplay = cv2.resize(Frame_intFordisplay, 
                                                (int(FrameWidth.value*scale), int(FrameHeight.value*scale)), interpolation=cv2.INTER_LINEAR)
            cv2.imshow(opencvWindowName, Frame_intFordisplay)

            if ( GetFrameFlag.is_set() ):
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
            # I am not really worried about getting the latest frame just want to see something updating on the digholo
            if ( GetFrameFlag_digholo.is_set() ):
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
                
        elif(SingleFrameMode.is_set()):
            # DoorBell.wait()
            # DoorBell.clear()
            device.stop_stream()
            CameraProperties["TriggerMode"].value = "On"
            device.start_stream()
            if ( GetFrameFlag.is_set() ):
                if settriggermode==0:
                    CameraProperties["TriggerSoftware"].execute()   # camera takes one exposure
                    image_buffer = device.get_buffer()
                    if CameraProperties['PixelFormat'].value == 'Mono12':
                        frame_ptr = ctypes.cast(image_buffer.pdata,ctypes.POINTER(ctypes.c_ushort))
                    else :
                        frame_ptr = ctypes.cast(image_buffer.pdata,ctypes.POINTER(ctypes.c_ubyte))
                        
                    nparray_reshaped = np.ctypeslib.as_array(frame_ptr,(image_buffer.height, image_buffer.width))
                    frame=copy.deepcopy(nparray_reshaped)
                    device.requeue_buffer(image_buffer)
                    Frame_int =CamForm.adjust_array_dimensions(frame)
                elif settriggermode==1:
                    # I am not implementing this today but will get around to it. should do it in a similar way to the firstlight camera which resets the buffer count to the number of triggered frames
                    pass
                
                np.copyto(frame_buffer, Frame_int)
                
                if DisplayFrameInSingleCapature:
                    Frame_intFordisplay = cv2.resize(Frame_int, 
                                                (int(FrameWidth.value*scale), int(FrameHeight.value*scale)), 
                                                interpolation=cv2.INTER_LINEAR)
                    cv2.imshow(opencvWindowName, Frame_intFordisplay)
                FrameObtained.value=1
                GetFrameFlag.clear()
            # FrameCaptured.set()
                

            if ( GetFrameFlag_digholo.is_set() ):
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
                
                
        if(SetClearCamBufferFlag.is_set()):
            # not sure if there is a eviqualent command for lucid vision cameras but this is to clear the buffer
            SetClearCamBufferFlag.clear()
            
        if(SetExposureFlag.is_set()):
            ExposureTime=shared_float.value
            # if ( (ExposureTime)>=ExposureTimeMin and (ExposureTime)<ExposureTimeMax ):
                #Need to set some prameters up 
            if ExposureTime<ExposureTimeMin:
                ExposureTime=ExposureTimeMin
            if ExposureTime>ExposureTimeMax:
                ExposureTime=ExposureTimeMax    
            CameraProperties["ExposureTime"].value = ExposureTime
            shared_float.value=CameraProperties["ExposureTime"].value
            SetExposureFlag.clear()
            
        if(SetfpsFlag.is_set()):
            fps=shared_float.value
            if fps<minfps:
                fps=minfps
            if fps>maxfps:
                fps=maxfps    
            CameraProperties["AcquisitionFrameRate"].value = fps
            shared_float.value=CameraProperties["AcquisitionFrameRate"].value
            SetfpsFlag.clear()
        
        if(SetFrameClipingMinFlag.is_set()):
            # frameMinClip=shared_int.value
            # shared_int.value=frameMinClip
            frameMinClip=shared_float.value
            shared_float.value=frameMinClip
            SetFrameClipingMinFlag.clear()
            
        if(SetFrameClipingMaxFlag.is_set()):
            # frameMaxClip=shared_int.value
            # shared_int.value=frameMaxClip
            frameMaxClip=shared_float.value
            shared_float.value=frameMaxClip
            
            SetFrameClipingMaxFlag.clear()
            
        if(SetTriggerFlag.is_set()):
            triggermode=shared_int.value
            SetTriggerMode(device,CameraProperties,triggermode)
            settriggermode=GetTriggerMode(CameraProperties)
            shared_int.value=settriggermode
            # if we are setting the trigger mode to external we need to clear the buffer as this at the end 
            # of a external trigger sequence of images we call the getframe to grab the 
            if settriggermode==1:
                # FliSdk_V2.ResetBuffer(cam_context)
                # need to set the camera to single frame mode
                # this is so that it does burn through the buffer and you lose frames that where externally triggered
                ContinuesMode.clear()
                SingleFrameMode.set()

            SetTriggerFlag.clear()
            
        if(SetFrameCaptureDelayFlag.is_set()):
            FrameCaptureDelay=shared_float.value
            # commandstr="set syncdelay "+ str(FrameCaptureDelay)
            # errorval, response = FliSdk_V2.FliSerialCamera.SendCommand(cam_context, commandstr) 
            # commandstr="syncdelay raw"
            # _,SetFrameCaptureDelay = FliSdk_V2.FliSerialCamera.SendCommand(cam_context, commandstr)
            shared_float.value=-1.0#float(SetFrameCaptureDelay)

            SetFrameCaptureDelayFlag.clear()
            
        if(SetGainFlag.is_set()):
            NewGain=shared_float.value
            CameraProperties["GainAuto"].value = "Off"
            CameraProperties["Gain"].value = NewGain
            shared_float.value= CameraProperties["Gain"].value
            SetGainFlag.clear()
            
                
        if(SetBiasStateFlag.is_set()):
            NewBias=shared_int.value
            shared_int.value= -1
            SetBiasStateFlag.clear()
    
        # I dont think this camera has internal frame buffer size setting but leaving here for now
        if(SetInternalFrameBufferSizeFlag.is_set()):
            NewInternalFrameBufferSize=shared_int.value
            # FliSdk_V2.SetBufferSizeInImages(cam_context, NewInternalFrameBufferSize)
            SetInternalFrameBufferSizeFlag.clear()
            
        if(SetReSetCameraFlag.is_set()):
            # FliSdk_V2.Stop(cam_context)
                    
            # FliSdk_V2.Start(cam_context)
            SetReSetCameraFlag.clear()
            
        if(CleanFrameMemFlag.is_set()):
            shm.close()   
            del frame_buffer
            shm_digholo.close() 
            del frame_buffer_digholo
            del frame
            CleanFrameMemFlag.clear()   
        
        if(SetRIOFlag.is_set()):
            # This camera has certian value the the RIO points and frame size can be set to, it is very common in cameras for this.
            # the x points and FrameHeight can only be int 32 values and y points be FrameWidth be int 4
            RIO_xpoint.value=snap_to_value(RIO_xpoint.value,4, mode='nearest')
            RIO_ypoint.value=snap_to_value(RIO_ypoint.value,2, mode='nearest')
            FrameHeight.value=snap_to_value(FrameHeight.value,4, mode='nearest')
            FrameWidth.value=snap_to_value(FrameWidth.value,2, mode='nearest')
            
            device.stop_stream()
            CameraProperties['Width'].value=FrameWidth.value
            CameraProperties['Height'].value=FrameHeight.value
            CameraProperties['OffsetX'].value=RIO_xpoint.value
            CameraProperties['OffsetY'].value=RIO_ypoint.value
            device.start_stream()
            
            SetRIOFlag.clear() 
        
        if(ResetFrameMemFlag.is_set()):
            shm = shared_memory.SharedMemory(name=shared_memory_name)
            frame_buffer = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint16, buffer=shm.buf) 
            
            shm_digholo = shared_memory.SharedMemory(name=shared_memory_name_digholo)
            frame_buffer_digholo = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint16, buffer=shm_digholo.buf) 
            # Need to make a empty array so that a pointer can be made to get the frame from Xenics getframe
            frame= np.zeros((FrameHeight.value, FrameWidth.value),dtype=np.uint16)
            
            ResetFrameMemFlag.clear() 
        if(SetDisplayWindowScaleFlag.is_set()):
            scale=shared_float.value
            cv2.resizeWindow(opencvWindowName, int(FrameHeight.value*scale), int(FrameWidth.value*scale))
            SetDisplayWindowScaleFlag.clear()

       
          

        
            
        # if(SetCalibrationEvent.is_set()):
        #     CalibrationFile=Cam_Calibtation["CalibrationFilename"]
        #     # queue.put(CalibrationFile)
        #     if os.path.exists(CalibrationFile):
        #         load_calibration(Cam_handdle,CalibrationFile)
        #         shared_int.value=0
        #     else:
        #         shared_int.value=-1
        #     SetCalibrationEvent.clear()


        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    device.stop_stream()
    arena_api.system.system.destroy_device()


    shm.close() 
    shm_digholo.close() 
    

    # XC_SetPropertyValueF(handle, "SETTLE", (double)temperatureGoal, "k");
	# 	XC_SetPropertyValueL(handle, "Fan", (long)tecEnabled, "bool");