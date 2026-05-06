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


directory = r'C:\\Program Files\\Common Files\\XenICs\\Runtime\\xeneth64.dll'
xenethdll = ctypes.cdll.LoadLibrary(directory)

#Need to define a bunch of Functions in the ddl 


xenethdll.XC_OpenCamera.restype = ctypes.c_int32

xenethdll.XC_ErrorToString.restype = ctypes.c_int32
xenethdll.XC_ErrorToString.argtypes = (ctypes.c_int32, ctypes.c_char_p,ctypes.c_int32)

xenethdll.XC_IsInitialised.restype = ctypes.c_int32
xenethdll.XC_IsInitialised.argtypes = (ctypes.c_int32,)

    
xenethdll.XC_StartCapture.restype = ctypes.c_ulong  # ErrCode
xenethdll.XC_StartCapture.argtypes = (ctypes.c_int32,)# Handle

    
xenethdll.XC_IsCapturing.restype = ctypes.c_bool
xenethdll.XC_IsCapturing.argtypes = (ctypes.c_int32,)

xenethdll.XC_GetFrameSize.restype = ctypes.c_ulong
xenethdll.XC_GetFrameSize.argtypes = (ctypes.c_int32,)  # Handle

xenethdll.XC_GetFrameType.restype = ctypes.c_ulong  # Returns enum
xenethdll.XC_GetFrameType.argtypes = (ctypes.c_int32,)  # Handle

xenethdll.XC_GetWidth.restype = ctypes.c_ulong
xenethdll.XC_GetWidth.argtypes = (ctypes.c_int32,)  # Handle

xenethdll.XC_GetHeight.restype = ctypes.c_ulong
xenethdll.XC_GetHeight.argtypes = (ctypes.c_int32,)  # Handle

xenethdll.XC_GetFrame.restype = ctypes.c_ulong  # ErrCode
xenethdll.XC_GetFrame.argtypes = (ctypes.c_int32, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_uint)

xenethdll.XC_StopCapture.restype = ctypes.c_ulong  # ErrCode
xenethdll.XC_StopCapture.argtypes = (ctypes.c_int32,)

    # Returns void
xenethdll.XC_CloseCamera.argtypes = (ctypes.c_int32,)  # Handle

    # Calibration
xenethdll.XC_LoadCalibration.restype = ctypes.c_ulong  # ErrCode
xenethdll.XC_LoadCalibration.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_ulong)
     # Calibration

    # ColourProfile
xenethdll.XC_LoadColourProfile.restype = ctypes.c_ulong
xenethdll.XC_LoadColourProfile.argtypes = (ctypes.c_char_p,)

    # Settings
xenethdll.XC_LoadSettings.restype = ctypes.c_ulong
xenethdll.XC_LoadSettings.argtypes = (ctypes.c_char_p, ctypes.c_ulong)

    # FileAccessCorrectionFile
xenethdll.XC_GetPropertyValue.argtypes = (ctypes.c_int32, ctypes.c_char_p,ctypes.c_char_p, ctypes.c_int32);
xenethdll.XC_GetPropertyValue.restype = ctypes.c_ulong  # ErrCode

# ErrCode IMPEXPC  XC_SetPropertyValue (XCHANDLE h, const char *pPrp, const char *pValue, const char *pUnit) 
xenethdll.XC_SetPropertyValue.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p,ctypes.c_char_p,);
xenethdll.XC_SetPropertyValue.restype = ctypes.c_ulong  # ErrCode
    # set_property_value.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p)
xenethdll.XC_GetPropertyValueF.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double));
xenethdll.XC_GetPropertyValueF.restype = ctypes.c_ulong

# ErrCode  IMPEXPC XC_SetPropertyValueF(XCHANDLE h, const char * pPrp, double dValue, const char * pUnit);    
xenethdll.XC_SetPropertyValueF.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.c_double,ctypes.c_char_p,);
xenethdll.XC_SetPropertyValueF.restype = ctypes.c_ulong

# ErrCode XCamera::SetPropertyValueE  ( const char *  pPrp,const char *  pValue) 
xenethdll.XC_SetPropertyValueE.argtypes = (ctypes.c_int32,ctypes.c_char_p,ctypes.c_char_p);
xenethdll.XC_SetPropertyValueE.restype = ctypes.c_ulong
# ErrCode XCamera::GetPropertyValueE  ( const char *  pPrp,  char *  pValue,  int  iMaxLen  ) 
xenethdll.XC_GetPropertyValueE.argtypes = (ctypes.c_int32,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int32);
xenethdll.XC_GetPropertyValueE.restype = ctypes.c_ulong

xenethdll.XC_GetPropertyRangeF.argtypes = (ctypes.c_int32, ctypes.c_char_p, ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_double));
xenethdll.XC_GetPropertyRangeF.restype = ctypes.c_ulong

# byte IMPEXPC XC_GetBitSize  ( XCHANDLE  h ) 
xenethdll.XC_GetBitSize.restype = ctypes.c_ubyte
xenethdll.XC_GetBitSize.argtypes = (ctypes.c_int32,);

# ErrCode XCamera::GetPropertyType  ( const char *  pPrp,  XPropType *  pPropType) 
xenethdll.XC_GetPropertyType.argtypes = (ctypes.c_int32,ctypes.c_char_p,  ctypes.POINTER(ctypes.c_uint));
xenethdll.XC_GetPropertyType.restype = ctypes.c_ulong
# ErrCode IMPEXPC  XC_GetPropertyUnit (XCHANDLE h, const char *pPrp, char *pUnit, int iMaxLen) 
xenethdll.XC_GetPropertyUnit.argtypes = (ctypes.c_int32,ctypes.c_char_p, ctypes.c_char_p,ctypes.c_uint);
xenethdll.XC_GetPropertyUnit.restype = ctypes.c_ulong

# ErrCode IMPEXPC XC_LoadSettings  ( XCHANDLE  h, const char *  p_cFileName) 
xenethdll.XC_LoadSettings.argtypes = (ctypes.c_int32,ctypes.c_char_p);
xenethdll.XC_LoadSettings.restype = ctypes.c_ulong
# ErrCode     IMPEXPC XC_SetPropertyValueF            (XCHANDLE h, const char * pPrp, double dValue, const char * pUnit);
xenethdll.XC_FLT_Queue.argtypes = (ctypes.c_int32,ctypes.c_char_p,ctypes.c_char_p);
xenethdll.XC_FLT_Queue.restype = ctypes.c_ulong

# fltSoftwareCorrection = XC_FLT_Queue(handle, "SoftwareCorrection", 0);

# Error codes
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
E_RFU = 10023

# Used for conversion to string
errcodes = {I_OK: 'I_OK',
            I_DIRTY: 'I_DIRTY',
            E_BUG: 'E_BUG',
            E_NOINIT: 'E_NOINIT',
            E_LOGICLOADFAILED: 'E_LOGICLOADFAILED',
            E_INTERFACE_ERROR: 'E_INTERFACE_ERROR',
            E_OUT_OF_RANGE: 'E_OUT_OF_RANGE',
            E_NOT_SUPPORTED: 'E_NOT_SUPPORTED',
            E_NOT_FOUND: 'E_NOT_FOUND',
            E_FILTER_DONE: 'E_FILTER_DONE',
            E_NO_FRAME: 'E_NO_FRAME',
            E_SAVE_ERROR: 'E_SAVE_ERROR',
            E_MISMATCHED: 'E_MISMATCHED',
            E_BUSY: 'E_BUSY',
            E_INVALID_HANDLE: 'E_INVALID_HANDLE',
            E_TIMEOUT: 'E_TIMEOUT',
            E_FRAMEGRABBER: 'E_FRAMEGRABBER',
            E_NO_CONVERSION: 'E_NO_CONVERSION',
            E_FILTER_SKIP_FRAME: 'E_FILTER_SKIP_FRAME',
            E_WRONG_VERSION: 'E_WRONG_VERSION',
            E_PACKET_ERROR: 'E_PACKET_ERROR',
            E_WRONG_FORMAT: 'E_WRONG_FORMAT',
            E_WRONG_SIZE: 'E_WRONG_SIZE',
            E_CAPSTOP: 'E_CAPSTOP',
            E_OUT_OF_MEMORY: 'E_OUT_OF_MEMORY',
            E_RFU: 'E_RFU'}  # The last one is uncertain

# Frame types, ulong
FT_UNKNOWN = -1
FT_NATIVE = 0
FT_8_BPP_GRAY = 1
FT_16_BPP_GRAY = 2
FT_32_BPP_GRAY = 3
FT_32_BPP_RGBA = 4
FT_32_BPP_RGB = 5
FT_32_BPP_BGRA = 6
FT_32_BPP_BGR = 7

# Pixel size in bytes, used for conversion
pixel_sizes = {FT_UNKNOWN: 0,  # Unknown
                FT_NATIVE: 0,  # Unknown, ask with get_frame_type
                FT_8_BPP_GRAY: 1,
                FT_16_BPP_GRAY: 2,
                FT_32_BPP_GRAY: 4,
                FT_32_BPP_RGBA: 4,
                FT_32_BPP_RGB: 4,
                FT_32_BPP_BGRA: 4,
                FT_32_BPP_BGR: 4}

# GetFrameFlags, ulong
XGF_Blocking = 1
XGF_NoConversion = 2
XGF_FetchPFF = 4
XGF_RFU_1 = 8
XGF_RFU_2 = 16
XGF_RFU_3 = 32

# LoadCalibration flags
# Starts the software correction filter after unpacking the
# calibration data
XLC_StartSoftwareCorrection = 1
XLC_RFU_1 = 2
XLC_RFU_2 = 4
XLC_RFU_3 = 8

    
    

# from vimba import * this is the old version 
class XenicsCameraObject():
    def __init__(self,CameraName='cam://0',CalibrationFile=None,PixelSize=30e-6):
        super().__init__() # inherit from parent class  
        Cam_handdle=xenethdll.XC_OpenCamera(CameraName.encode('utf-8'), 0, 0)
        self.Ny = xenethdll.XC_GetWidth(Cam_handdle)
        self.Nx = xenethdll.XC_GetHeight(Cam_handdle)    
        Framedtype=np.uint16
        err=xenethdll.XC_IsInitialised(Cam_handdle)
        err=xenethdll.XC_StartCapture(Cam_handdle)
        check=xenethdll.XC_IsCapturing(Cam_handdle)
        print("Camera is in capture mode ",check)
        # SettingFile=ctypes.create_string_buffer(b"C:\\Program Files\\Xeneth\\Settings\\auto_8110.xcf")
        # xenethdll.XC_LoadSettings(Cam_handdle,SettingFile)
        # "C:\\Program Files\\Xeneth\Settings\\auto_8110.xcf"

        # The stuff commented out here is getting a bunch of varibles and things as examples
        ### This is the bit size of a frame it will got the the large of regular bit sizes like 8 and 16. i.e. it comes out as 12 but the software gives it as 16
        # FrameByteSize = ctypes.c_ubyte(0)
        # print('framebytesize = ',FrameByteSize.value) 
        # FrameByteSize.value = xenethdll.XC_GetBitSize(Cam_handdle)
        # print('framebytesize = ',FrameByteSize) 

        ### Get the data type of a property NOTE you have to look at the XCamera.h file to work out the type by converting the int output to hex an then looking at the XPROP enum list
        # proptype=ctypes.c_uint()
        # lowGaintxt='LowGain'
        # xenethdll.XC_GetPropertyType(Cam_handdle,lowGaintxt.encode('utf-8'), ctypes.byref(proptype));
        # print(proptype.value)

        ### Get the units of a poperty
        # GainUnits=ctypes.create_string_buffer(100)
        # xenethdll.XC_GetPropertyUnit(Cam_handdle,lowGaintxt.encode('utf-8'), GainUnits,100);
        # print('GainUnits= ',GainUnits.value.decode())
     
        # calibrationFile=config.CAMERA_LIB_PATH+"CameraSoftware\\Xenics\\Calibrations\\xeva8755-TrueNUC_8755_test3_Black_and_clean.xca"
        # calibrationFile=config.CAMERA_LIB_PATH+"CameraSoftware\\Xenics\\Calibrations\\xeva8755-Settings.xcf"

        def file_exists(file_path):
            """Check if a file exists at the given path."""
            return os.path.isfile(file_path)
        

        # SettingFile=ctypes.create_string_buffer(b"C:\\Program Files\\Xeneth\\Settings\\auto_8110.xcf")
        # SettingFile=ctypes.create_string_buffer(b"C:\\Program Files\\Xeneth\\Settings\\xeva8755-TrueNUC_8755_test3_Black_and_clean_BestOneToUse.xca")

        # SettingFile=ctypes.create_string_buffer(calibrationFile.encode('utf-8'))

        # errorcode = xenethdll.XC_LoadSettings(Cam_handdle,SettingFile)
        # print(errorcode)

        # Load Calibration
        # load_calibration(Cam_handdle,"xeva8755-TrueNUC_8755_test3_Black_and_clean_BestOneToUse.xca")
        Units='bool'
        LowGaintxt='LowGain'
        GainSet='False'
        xenethdll.XC_SetPropertyValue(Cam_handdle,LowGaintxt.encode('utf-8'),GainSet.encode('utf-8'),Units.encode('utf-8'),)               
        GainValueSting=ctypes.create_string_buffer(100)
        xenethdll.XC_GetPropertyValue(Cam_handdle,LowGaintxt.encode('utf-8'),GainValueSting,100)
        GainValue=float(GainValueSting.value.decode())
        print('Gain state= ',GainValue)

        Units='bool'
        PropText='Fan'
        PropSet='False'
        xenethdll.XC_SetPropertyValue(Cam_handdle,PropText.encode('utf-8'),PropSet.encode('utf-8'),Units.encode('utf-8'),)               
        PropSting=ctypes.create_string_buffer(100)
        xenethdll.XC_GetPropertyValue(Cam_handdle,PropText.encode('utf-8'),PropSting,100)
        PropValue=float(PropSting.value.decode())
        print('Fan state= ',PropValue)

        ExposureTime=ctypes.c_double(0)
        ExposureTimetxt='IntegrationTime'# Note that it could also be called 'ExposureTime'
        xenethdll.XC_GetPropertyValueF(Cam_handdle,ExposureTimetxt.encode('utf-8'),ctypes.byref(ExposureTime))
        Exposure=ExposureTime.value
        print('Exposure time= ',ExposureTime.value,'us')


        frame= np.zeros((self.Nx,self.Ny),dtype=Framedtype)
        frameBufferPtr = frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16))
        FT_NATIVE=0
        XGF_NoConversion=2
        size = xenethdll.XC_GetFrameSize(Cam_handdle)
        #For some reason you need to wait a little bit at the start before trying to grab a frame it will just never grab if you
        #dont wait 
        # time.sleep(2)
        gotframe = xenethdll.XC_GetFrame(Cam_handdle, FT_NATIVE, XGF_Blocking | XGF_NoConversion, frameBufferPtr, size)
        frame = np.ctypeslib.as_array(frameBufferPtr,shape=(self.Nx,self.Ny))
        frametpye=xenethdll.XC_GetFrameType(Cam_handdle)
        print('frametype= ',frametpye)
        FrameDim=frame.shape
        FrameHeight = int(FrameDim[0])
        FrameWidth = int(FrameDim[1])
        # FrameBuffer =CamForm.adjust_array_dimensions(np.squeeze( (frame)))
        FrameBuffer=np.copy(frame)
        # Frame_12 = (FrameBuffer/65535.0*255.0).astype(np.uint8)
        # Frame_12= (FrameBuffer >> 8).astype(np.uint8)

        plt.imshow(frame)
        #Stop capture and close the connection to the camera
        err=xenethdll.XC_StopCapture(Cam_handdle)
        err=xenethdll.XC_CloseCamera(Cam_handdle)
        
        self.CamObject=CamForm.GeneralCameraObject("XenicsCamera",CalibrationFile,self.Nx,self.Ny,FrameWidth,FrameHeight,FrameDim,Framedtype,FrameBuffer,PixelSize,Exposure,0,0,0,0,CameraName)
        self.CamProcess= CamForm.start_FrameCaptureThread(self.CamObject,XenicsFrameCaptureThread)
        
        if CalibrationFile is not None:
            self.CamObject.SetCalibrationFile(CalibrationFile)
        # self.CamObject.SetFanState(0)
                          
       
    def __del__(self):
        """Destructor to disconnect from camera."""
        print(self.CamObject.CameraType +" Class has been destroyed")
        self.CamObject.terminateCamera.set()# stop the camera thread
        self.CamObject.shm.close() # close access to shared memory
        self.CamObject.shm_digholo.close() # close access to shared memory
        self.CamProcess.terminate()
        self.CamObject.shm.unlink() # clean up the shared memory space
        self.CamObject.shm_digholo.unlink() # clean up the shared memory space

def load_calibration(Cam_handdle,calibrationFile):
    # calibrationFile=config.CAMERA_LIB_PATH+"CameraSoftware\\Xenics\\Calibrations\\"+Filename 
    # xeva8755-TrueNUC_8755_test3_Black_and_clean_BestOneToUse.xca"
    SettingFile=ctypes.create_string_buffer(calibrationFile.encode('utf-8'))
    errcodes=xenethdll.XC_LoadCalibration(Cam_handdle, SettingFile, 0)
    error = xenethdll.XC_FLT_Queue(Cam_handdle, b"SoftwareCorrection", b"0");
        
def XenicsFrameCaptureThread(queue,Cam_Calibtation,SetCalibrationEvent,
                             CameraName,GetFrameFlag,GetFrameFlag_digholo,terminateCamFlag,FrameObtained,
                             shared_memory_name,shared_memory_name_digholo,
                             FrameHeight,FrameWidth,
                             ClipFrame,SetDisplayWindowScaleFlag,
                            ROI_visual_SharedMemName,SetVisualROIFlag,
                            SetFrameClipingMinFlag,SetFrameClipingMaxFlag,
                                   SetExposureFlag,SetGainFlag,SetFanFlag,SetfpsFlag,
                                   ContinuesMode,SingleFrameMode,
                                   shared_float,shared_int,shared_flag_int):
    # Setup Shared memory
    # queue.put("testa")   
    shm = shared_memory.SharedMemory(name=shared_memory_name)
    frame_buffer = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint16, buffer=shm.buf) 
    
    shm_digholo = shared_memory.SharedMemory(name=shared_memory_name_digholo)
    frame_buffer_digholo = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint16, buffer=shm_digholo.buf) 
    
    shm_ROI_visual =shared_memory.SharedMemory(name=ROI_visual_SharedMemName)
    ROI_visual_arr_shm=np.ndarray((4), dtype=np.int64, buffer=shm_ROI_visual.buf) 
    ROI_visual_arr=np.zeros(4,dtype=np.int64)
    
    # Need to make a empty array so that a pointer can be made to get the frame from Xenics getframe
    frame= np.zeros((FrameHeight.value, FrameWidth.value),dtype=np.uint16)
    framePtr = frame.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)) 
    FT_NATIVE=0
    XGF_NoConversion=2
    XGF_Blocking=1
    ContinuesMode.set()
    opencvWindowName="Xenics Camera Image"

    Cam_handdle=xenethdll.XC_OpenCamera(CameraName.encode('utf-8'), 0, 0)
       
    errorcode=xenethdll.XC_IsInitialised(Cam_handdle)
    errorcode=xenethdll.XC_StartCapture(Cam_handdle)
    check=xenethdll.XC_IsCapturing(Cam_handdle)
    Units='bool'
    PropText='Fan'
    PropSet='False'
    xenethdll.XC_SetPropertyValue(Cam_handdle,PropText.encode('utf-8'),PropSet.encode('utf-8'),Units.encode('utf-8'),)               
    PropSting=ctypes.create_string_buffer(100)
    xenethdll.XC_GetPropertyValue(Cam_handdle,PropText.encode('utf-8'),PropSting,100)
    # PropValue=float(GainValueSting.value.decode())
    # print('Fan state= ',PropValue)


    # calibrationFile=config.CAMERA_LIB_PATH+"CameraSoftware\\Xenics\\Calibrations\\xeva8755-Settings.xcf"
    # # SettingFile=ctypes.create_string_buffer(b"C:\\Program Files\\Xeneth\\Settings\\auto_8110.xcf")
    # SettingFile=ctypes.create_string_buffer(calibrationFile.encode('utf-8'))

    # xenethdll.XC_LoadSettings(Cam_handdle,SettingFile)
    frameMinClip=0
    frameMaxClip=1
    scale=1
    DisplayPowerOverROI=0
    pixelFormat="Mono16"
    size = xenethdll.XC_GetFrameSize(Cam_handdle)
    while not terminateCamFlag.is_set():
        if (ContinuesMode.is_set()):
            err = xenethdll.XC_GetFrame(Cam_handdle, FT_NATIVE, XGF_Blocking | XGF_NoConversion , framePtr,size);
            Frame_int = np.ctypeslib.as_array(framePtr,shape=(FrameHeight.value,FrameWidth.value))
            
            CameraDisplayWindow(Frame_int,FrameWidth.value,FrameHeight.value,
                         ClipFrame.value,frameMinClip,frameMaxClip,
                         DisplayPowerOverROI,ROI_visual_arr,
                         scale,pixelFormat,opencvWindowName)

            # change bit depth
            # if(True):
            #     Frame_int = CamForm.adjust_array_dimensions(frame)
            #     Frame_int12 = CamForm.adjust_bit_depth(Frame_int)

            #     cv2.imshow(opencvWindowName, Frame_int12)
            # else:
            #     Frame_int =CamForm.adjust_array_dimensions(frame)

            #     cv2.imshow(opencvWindowName, Frame_int)

            if ( GetFrameFlag.is_set() ):
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
            # I am not really worried about getting the latest frame just want to see something updating on the digholo
            if ( GetFrameFlag_digholo.is_set() ):
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
                
        elif(SingleFrameMode.is_set()):
            if ( GetFrameFlag.is_set() ):
                err= xenethdll.XC_GetFrame(Cam_handdle, FT_NATIVE, XGF_Blocking | XGF_NoConversion, framePtr,size);
                queue.put(err)   
                Frame_int = np.ctypeslib.as_array(framePtr,shape=(FrameHeight.value,FrameWidth.value))
                # frame = cam.get_frame ()
                # Frame_int =CamForm.adjust_array_dimensions(np.squeeze(frame))  
                CameraDisplayWindow(Frame_int,FrameWidth.value,FrameHeight.value,
                         ClipFrame.value,frameMinClip,frameMaxClip,
                         DisplayPowerOverROI,ROI_visual_arr,
                         scale,pixelFormat,opencvWindowName)     
                         
                # cv2.imshow(opencvWindowName, Frame_int)
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
            if ( GetFrameFlag_digholo.is_set() ):
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
                
        if(SetDisplayWindowScaleFlag.is_set()):
            scale=shared_float.value
            cv2.resizeWindow(opencvWindowName, int(FrameHeight.value*scale), int(FrameWidth.value*scale))
            SetDisplayWindowScaleFlag.clear()
        if(SetVisualROIFlag.is_set()):
            DisplayPowerOverROI=shared_int.value
            np.copyto(ROI_visual_arr, ROI_visual_arr_shm)
            SetVisualROIFlag.clear()
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
            
        if(SetExposureFlag.is_set()):
            ExposureTime=ctypes.c_double(shared_float.value)
            if ( (ExposureTime.value)>=1 and (ExposureTime.value)<2e6 ):
                #Need to set some prameters up 
                Units='us'
                ExposureTimetxt='IntegrationTime'
                errorcode=xenethdll.XC_SetPropertyValueF(Cam_handdle, ExposureTimetxt.encode('utf-8'), ExposureTime.value,Units.encode('utf-8'));
                shared_flag_int.value=1
                xenethdll.XC_GetPropertyValueF(Cam_handdle,ExposureTimetxt.encode('utf-8'),ctypes.byref(ExposureTime))
           
                shared_float.value=ExposureTime.value
            SetExposureFlag.clear()

        if(SetGainFlag.is_set()):
            Gain=shared_float.value
            Units='bool'
            LowGaintxt='LowGain'
            if ( (Gain)==0 or (Gain)==1 ):
                if(Gain)==0:
                    GainSet='False'
                else:
                    GainSet='True'
                xenethdll.XC_SetPropertyValue(Cam_handdle,LowGaintxt.encode('utf-8'),GainSet.encode('utf-8'),Units.encode('utf-8'),)               
                GainValueSting=ctypes.create_string_buffer(100)
                xenethdll.XC_GetPropertyValue(Cam_handdle,LowGaintxt.encode('utf-8'),GainValueSting,100)
                Gain=float(GainValueSting.value.decode())
                shared_float.value=Gain
            SetGainFlag.clear()

        if(SetFanFlag.is_set()):
            FanState=shared_float.value
            Units='bool'
            Proptxt='Fan'
            if ( (FanState)==0 or (FanState)==1 ):
                if(FanState)==0:
                    PropSet='False'
                else:
                    PropSet='True'
                xenethdll.XC_SetPropertyValue(Cam_handdle,Proptxt.encode('utf-8'),PropSet.encode('utf-8'),Units.encode('utf-8'),)               
                PropValueSting=ctypes.create_string_buffer(100)
                xenethdll.XC_GetPropertyValue(Cam_handdle,Proptxt.encode('utf-8'),PropValueSting,100)
                FanState=float(PropValueSting.value.decode())
                shared_float.value=FanState
            SetFanFlag.clear()
            
        if(SetfpsFlag.is_set()):
            fps=shared_float.value
            shared_float.value=fps
            # errorval, ExposureTimeMin,ExposureTimeMax = FliSdk_V2.FliCredThree.GetTintRange(cam_context)
            SetfpsFlag.clear()   
            
        if(SetCalibrationEvent.is_set()):
            CalibrationFile=Cam_Calibtation["CalibrationFilename"]
            # queue.put(CalibrationFile)
            if os.path.exists(CalibrationFile):
                load_calibration(Cam_handdle,CalibrationFile)
                shared_int.value=0
            else:
                shared_int.value=-1
            SetCalibrationEvent.clear()


        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    xenethdll.XC_StopCapture(Cam_handdle)
    xenethdll.XC_CloseCamera(Cam_handdle)
    shm.close() 
    shm_digholo.close() 
    

    # XC_SetPropertyValueF(handle, "SETTLE", (double)temperatureGoal, "k");
	# 	XC_SetPropertyValueL(handle, "Fan", (long)tecEnabled, "bool");
def CameraDisplayWindow(Frame_int,FrameWidth,FrameHeight,
                         ClipFrame,frameMinClip,frameMaxClip,
                         DisplayPowerOverROI,ROI_visual_arr,
                         scale,pixelFormat,opencvWindowName):
    
    Frame_intFordisplay = CamForm.rescaleFrame_256(Frame_int)
                
    if ClipFrame:
        Frame_intFordisplay =CamForm.clip_frame(Frame_intFordisplay,
                                    vmin_percent=frameMinClip,
                                    vmax_percent=frameMaxClip)
        # Frame_intFordisplay = CamForm.rescaleFrame_256(Frame_int)
    # else:
        # Frame_intFordisplay=np.copy(Frame_int)
    

    if (DisplayPowerOverROI):
        # bg = np.nanmedian(Frame_int)
        roi,_ =CamForm.ApatrureFrame(Frame_int,centre=[ROI_visual_arr[0],ROI_visual_arr[1]]
                                        ,x_half_width=ROI_visual_arr[2],
                                        y_half_width=ROI_visual_arr[3],show_plot=False)
        # framePwr = np.nansum(roi - bg)
        # framePwr = np.nansum(roi)/(ROI_visual_arr[2]*ROI_visual_arr[3])
        framePwr = np.mean(roi)#np.nansum(roi)/(np.prod(roi.shape))
        framePwr_std = np.std(roi)


        Frame_intFordisplay=CamForm.draw_roi_box(Frame_intFordisplay,centre=[ROI_visual_arr[0],ROI_visual_arr[1]]
                                        ,x_half_width=ROI_visual_arr[2],
                                        y_half_width=ROI_visual_arr[3],
                                        thickness=int(1),
                                        colour=(0,0,255),draw_cross=False)
    else:
        framePwr=0
        framePwr_std=0
    if scale!=1:
        Frame_intFordisplay = cv2.resize(Frame_intFordisplay, 
                                        (int(FrameWidth*scale), int(FrameHeight*scale)), interpolation=cv2.INTER_LINEAR)
    # WindowSting=f"ROI Sum: {np.sum(frame)/np.prod(frame.shape):.0f}\n"
    WindowSting=f"ROI Mean: {framePwr:.0f} Std: {framePwr_std:.0f}\n"
    if pixelFormat=="Mono8":
        WindowSting=WindowSting+ f"Max Value on Frame: {100*np.max(Frame_int)/255:3.0f}%\n"
    elif pixelFormat=="Mono10":
        WindowSting=WindowSting+ f"Max Value on Frame: {100*np.max(Frame_int)/1023:3.0f}%\n"
    elif pixelFormat=="Mono12":
        WindowSting=WindowSting+ f"Max Value on Frame: {100*np.max(Frame_int)/4095:3.0f}%\n"
    elif pixelFormat=="Mono14":
        WindowSting=WindowSting+ f"Max Value on Frame: {100*(np.max(Frame_int)/16383):3.0f}%\n"
    elif pixelFormat=="Mono16":
        WindowSting=WindowSting+ f"Max Value on Frame: {100*np.max(Frame_int)/65535:3.0f}%\n"
    else:
        WindowSting=WindowSting+ f"Unsuporrted pixel format! Max Value on Frame: {np.max(Frame_int):.0f}%\n"
    canvasToDispla_viewPort=CamForm.DisplayWindow_GraphWithText(Frame_intFordisplay,WindowSting,thickness=int(1),font_scale=5*scale)

    cv2.imshow(opencvWindowName, canvasToDispla_viewPort)     
     