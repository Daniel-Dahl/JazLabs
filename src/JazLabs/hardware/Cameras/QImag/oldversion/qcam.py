# -*- coding: utf-8 -*-
"""
Created on Tue Sep 19 16:32:08 2023

@author: cfai2304
"""
import ctypes
import sys
import numpy as np

class Camera:     
    PARAM_KEYS = {
        "Gain": 0,
        "Offset": 1,
        "Exposure": 2,       # Exposure in microseconds
        "Binning": 3,        # Symmetrical binning	(ex: 1x1 or 4x4)
        "Cooler Active": 9,  # 1 turns cooler on, 0 turns off
        "Image Format":12,   # Image format (see QCam_ImageFormat)
        "ROI X": 13,         # Upper left X coordinate of the ROI
        "ROI Y": 14,         # Upper left Y coordinate of the ROI
        "ROI Width":15,      # Width of ROI, in pixels
        "ROI Height":16,     # Height of ROI, in pixels
        "Normalized Gain":25, # Normalized camera gain (micro units)
        "Post Processing": 27, # Turn post processing on/off
        "Blackout Mode": 34,   # Blackout mode, 1 turns all lights off, 0 turns them 
        "High Sensitivity Mode": 35 # High sensitivity mode, 1 turns high sensitivity mode on, 0 turns it off
        # ... and so on
    }  
    
    INFO_KEYS = {
        "Bit Depth": 5,
        "Cooled": 6,
        "Image Width": 8,
        "Image Height": 9,
        "Image Size": 10,
        "CCD Width": 12,
        "CCD Height": 13,
        "Regulated Cooling": 25,
        "Regulated Cooling Lock": 26,
        "High Sensitivity Mode": 30,
        "Blackout Mode": 31
    }

    def __init__(self):
        self.dll = ctypes.WinDLL('C:\\Windows\\System32\\QCamDriverx64.dll')

        self.QCam_LoadDriver = self.dll.QCam_LoadDriver
        self.QCam_LoadDriver.restype = ctypes.c_uint32

        self.QCam_ListCameras = self.dll.QCam_ListCameras
        self.QCam_ListCameras.argtypes = [ctypes.POINTER(QCam_CamListItem), ctypes.POINTER(ctypes.c_uint32)]
        self.QCam_ListCameras.restype = ctypes.c_uint32

        self.QCam_OpenCamera = self.dll.QCam_OpenCamera
        self.QCam_OpenCamera.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        self.QCam_OpenCamera.restype = ctypes.c_uint32

        self.QCam_GetCameraModelString = self.dll.QCam_GetCameraModelString
        self.QCam_GetCameraModelString.argtypes = [ctypes.c_uint32, ctypes.c_char_p, ctypes.c_uint32]
        self.QCam_GetCameraModelString.restype = ctypes.c_uint32
        
        self.pSettings = None
        
        self.parameters = {name: CameraParameter(name, key) for name, key in self.PARAM_KEYS.items()}
        self.info = {name: CameraInfo(name, key) for name, key in self.INFO_KEYS.items()}
    
        self.QCam_CloseCamera = self.dll.QCam_CloseCamera
        self.QCam_CloseCamera.argtypes = [ctypes.c_uint32]
        self.QCam_CloseCamera.restype = ctypes.c_uint32

        self.QCam_ReleaseDriver = self.dll.QCam_ReleaseDriver
        self.QCam_ReleaseDriver.restype = None
        
        self.QCam_GrabFrame = self.dll.QCam_GrabFrame
        self.QCam_GrabFrame.argtypes = [ctypes.c_void_p, ctypes.POINTER(QCam_Frame)]
        self.QCam_GrabFrame.restype = ctypes.c_uint32

        self.QCam_Trigger = self.dll.QCam_Trigger
        self.QCam_Trigger.argtypes = [ctypes.c_void_p]
        self.QCam_Abort = self.dll.QCam_Abort
        self.QCam_Abort.argtypes = [ctypes.c_void_p]
        self.QCam_Abort.restype = ctypes.c_uint32
        
    def connect_to_camera(self):
        # Load the driver
        result = self.load_driver()
        if result != 0:  # Replace with your actual success value
            print(f"Driver loading failed with error {result}")
            sys.exit(1)
            
        # Define the maximum number of cameras to list
        max_cameras = 10
        
        # Create an array of QCam_CamListItem
        pList = (QCam_CamListItem * max_cameras)()
        
        # Initialize pNumberInList to the number of QCam_CamListItem structures in pList
        pNumberInList = ctypes.c_uint32(max_cameras)
        
        # Call list_cameras
        result = self.list_cameras(ctypes.byref(pList[0]), ctypes.byref(pNumberInList))
        
        # Check how many cameras were found
        print(f"Number of cameras found: {pNumberInList.value}")
        
        # Store the dictionaries in a list
        camera_list = [pList[i].to_dict() for i in range(pNumberInList.value)]
        
        # Print each dictionary
        for i, camera_dict in enumerate(camera_list, start=1):
            print(f"Camera {i}:")
            for key, value in camera_dict.items():
                print(f"\t{key}: {value}")
        
        # Open the first camera
        result = self.open_camera(pList[0].cameraId)
        if result != 0:  # Replace with your actual success value
            print(f"Camera opening failed with error {result}")
            sys.exit(1)
        
        print(f"Camera opened with handle {self.camera_handle.value}")
        cameraOpened = True
        return cameraOpened

    def load_driver(self):
        return self.QCam_LoadDriver()

    def list_cameras(self, pList, pNumberInList):
        self.QCam_ListCameras.argtypes = [ctypes.POINTER(QCam_CamListItem), ctypes.POINTER(ctypes.c_uint32)]
        self.QCam_ListCameras.restype = ctypes.c_uint32
        return self.QCam_ListCameras(pList, pNumberInList)

    def open_camera(self, cameraId):
        self.QCam_OpenCamera.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        self.QCam_OpenCamera.restype = ctypes.c_uint32
        self.camera_handle = ctypes.c_void_p()
        return self.QCam_OpenCamera(cameraId, ctypes.byref(self.camera_handle))
    
    def get_camera_model(self, size=20):  # Assuming the maximum length of the model string is 20
        self.QCam_GetCameraModelString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
        self.QCam_GetCameraModelString.restype = ctypes.c_uint32
        model = ctypes.create_string_buffer(size)
        result = self.QCam_GetCameraModelString(self.camera_handle, model, size)
        return result, model.value.decode()
    
    def QCam_GetInfo(self, parameter):
        self.dll.QCam_GetInfo.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        self.dll.QCam_GetInfo.restype = ctypes.c_uint32
        info_value = ctypes.c_uint32()
        result = self.dll.QCam_GetInfo(self.camera_handle, parameter, ctypes.byref(info_value))
        return result, info_value.value
    
    def retrieve_info(self):
        for info in self.info.values():
            result, value = self.QCam_GetInfo(info.key)
            if result == 0:  # If the operation was successful
                info.value = value
            else:
                print(f"Failed to retrieve value of info {info.name}")
    
    def QCam_ReadSettingsFromCam(self):
        self.dll.QCam_ReadSettingsFromCam.argtypes = [ctypes.c_void_p, ctypes.POINTER(QCam_Settings)]
        self.dll.QCam_ReadSettingsFromCam.restype = ctypes.c_uint32
        self.pSettings = QCam_Settings()  # Initialize the settings structure
        result = self.dll.QCam_ReadSettingsFromCam(self.camera_handle, ctypes.byref(self.pSettings))
        return result, self.pSettings

    def QCam_GetParam(self, paramKey):
        self.dll.QCam_GetParam.argtypes = [ctypes.POINTER(QCam_Settings), ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        self.dll.QCam_GetParam.restype = ctypes.c_uint32
        pValue = ctypes.c_uint32()
        result = self.dll.QCam_GetParam(ctypes.byref(self.pSettings), paramKey, ctypes.byref(pValue))
        return result, pValue.value
    
    def retrieve_parameters(self):
        for param in self.parameters.values():
            result, value = self.QCam_GetParam(param.key)
            if result == 0:  # If the operation was successful
                param.value = value
            else:
                print(f"Failed to retrieve value of parameter {param.name}")
                
    def QCam_IsParamSupported(self, paramKey):
        self.dll.QCam_IsParamSupported.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        self.dll.QCam_IsParamSupported.restype = ctypes.c_uint32
        return self.dll.QCam_IsParamSupported(self.camera_handle, paramKey)

    def is_parameter_supported(self, paramKey):
        result = self.QCam_IsParamSupported(paramKey)
        if result == 0:  # Replace with your actual success value
            return True
        else:
            print(f"Parameter with key {paramKey} not supported with error {result}")
            return False
        
    def QCam_GetParamMin(self, paramKey):
        pValue = ctypes.c_ulong()
        self.dll.QCam_GetParamMin.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_ulong)]
        self.dll.QCam_GetParamMin.restype = ctypes.c_uint32
        result = self.dll.QCam_GetParamMin(ctypes.byref(self.pSettings), paramKey, ctypes.byref(pValue))
        return result, pValue.value

    def QCam_GetParamMax(self, paramKey):
        pValue = ctypes.c_ulong()
        self.dll.QCam_GetParamMax.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_ulong)]
        self.dll.QCam_GetParamMax.restype = ctypes.c_uint32
        result = self.dll.QCam_GetParamMax(ctypes.byref(self.pSettings), paramKey, ctypes.byref(pValue))
        return result, pValue.value    
        
    def close_camera(self):
        self.QCam_CloseCamera.argtypes = [ctypes.c_void_p]
        self.QCam_CloseCamera.restype = ctypes.c_uint32
        return self.QCam_CloseCamera(self.camera_handle)

    def release_driver(self):
        self.QCam_ReleaseDriver()
        
    def get_param_min_max(self, param):
        min_result, min_value = self.QCam_GetParamMin(param.key)
        max_result, max_value = self.QCam_GetParamMax(param.key)

        if min_result == 0 and max_result == 0:  # Replace with your actual success value
            param.min_value = min_value
            param.max_value = max_value
        else:
            print(f"Error {min_result} getting minimum for parameter {param.name}")
            print(f"Error {max_result} getting maximum for parameter {param.name}")
            
    def setup_camera(self):
        self.retrieve_info()
        self.QCam_ReadSettingsFromCam()
        self.retrieve_parameters()
        for param in self.parameters.values():
            if param.name not in ["Blackout Mode", "Post Processing", "High Sensitivity Mode"]:
                self.get_param_min_max(param)
            else:
                param.min_value = 0
                param.max_value = 1
    
    def grab_frame(self):
        sizeInBytes =  self.info['Image Size'].value
        frame = QCam_Frame()
        frame.bufferSize = sizeInBytes
        frame.pBuffer = ctypes.cast(ctypes.create_string_buffer(frame.bufferSize), ctypes.c_void_p)
        result = self.QCam_GrabFrame(self.camera_handle, ctypes.byref(frame))
        if result == 0:
            return frame
        else:
            print(f"Error {result} grabbing image")
            return None
    def grab_frameSingle(self):
        sizeInBytes =  self.info['Image Size'].value
        frame = QCam_Frame()
        frame.bufferSize = sizeInBytes
        frame.pBuffer = ctypes.cast(ctypes.create_string_buffer(frame.bufferSize), ctypes.c_void_p)
        test=self.QCam_Abort(self.camera_handle)
        print(test)
        result = self.QCam_GrabFrame(self.camera_handle, ctypes.byref(frame))
        if result == 0:
            return frame
        else:
            print(f"Error {result} grabbing image")
            return None
                
            
    def QCam_SetParam(self, paramKey, pValue):
        self.dll.QCam_SetParam.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_ulong]
        self.dll.QCam_SetParam.restype = ctypes.c_uint32
        result = self.dll.QCam_SetParam(ctypes.byref(self.pSettings), paramKey, pValue)
        return result

    def QCam_SendSettingsToCam(self, handle):
        self.dll.QCam_SendSettingsToCam.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.dll.QCam_SendSettingsToCam.restype = ctypes.c_uint32
        result = self.dll.QCam_SendSettingsToCam(handle, ctypes.byref(self.pSettings))
        return result

    def set_camera_param(self, param_name, value):
        param = self.parameters[param_name]

        if param.min_value <= value <= param.max_value:
            result = self.QCam_SetParam(param.key, value)
            if result == 0:  # replace 0 with the actual success code if it's different
                self.QCam_SendSettingsToCam(self.camera_handle)
                print(f"Parameter {param_name} set to {value}")
            else:
                print(f"Error {result} setting parameter {param_name}")
        else:
            print(f"Value {value} out of range for parameter {param_name} (min: {param.min_value}, max: {param.max_value})")
        

class QCam_CamListItem(ctypes.Structure):
    _fields_ = [
        ("cameraId", ctypes.c_uint32),
        ("cameraType", ctypes.c_uint32),
        ("uniqueId", ctypes.c_uint32),
        ("isOpen", ctypes.c_uint32)
    ] + [("reserved" + str(i), ctypes.c_uint32) for i in range(1, 11)]  # Adding 10 reserved fields

    def to_dict(self):
        return {
            'cameraId': self.cameraId,
            'cameraType': self.cameraType,
            'uniqueId': self.uniqueId,
            'isOpen': self.isOpen
        }

class QCam_Settings(ctypes.Structure):
    _fields_ = [
        ("size", ctypes.c_uint32),
        ("_private_data", ctypes.c_uint32 * 64),  # Array of 64 uint32 elements
    ]

class CameraParameter:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.value = None
        self.min_value = None
        self.max_value = None

    def __str__(self):
        return f"{self.name}: {self.value}"
    
    __repr__ = __str__
    
class CameraInfo:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.value = None

    def __str__(self):
        return f"{self.name}: {self.value}"
    
    __repr__ = __str__

class QCam_Frame(ctypes.Structure):
    _fields_ = [
        ("pBuffer", ctypes.c_void_p),
        ("bufferSize", ctypes.c_ulong),
        ("format", ctypes.c_ulong),
        ("width", ctypes.c_ulong),
        ("height", ctypes.c_ulong),
        ("size", ctypes.c_ulong),
        ("bits", ctypes.c_ushort),
        ("frameNumber", ctypes.c_ushort),
        ("bayerPattern", ctypes.c_ulong),
        ("errorCode", ctypes.c_ulong),
        ("timeStamp", ctypes.c_ulong),
        ("_reserved", ctypes.c_ulong * 8)
    ]

