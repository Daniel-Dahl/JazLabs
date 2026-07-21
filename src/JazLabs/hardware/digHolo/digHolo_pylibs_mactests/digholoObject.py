# Ok so my philosophy here is that the python functions I have written are same name as the C function version but the digHolo part
# of the name has a underscore (_) after it to let me and anyone else going through the code to see the differences between Joels
# C lib and my python wrapper
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import cv2
import multiprocessing
from multiprocessing import shared_memory
import time
import copy
from enum import IntEnum

# digH_hpy as in header file for python... pretty clever I know (Daniel 2 seconds after writing this comment. Head slap you are a idiot )
# Ok so I found a lib called ctypesgen that can look at a header file and make a python wrapper that can also include all the error
# stuff so i have generated the python version of the header file with that. I need to test it to see how it goes.
import JazLabs.hardware.digHolo.digHolo_pylibs.digholoHeader as digH_hpy 

import JazLabs.utils.PlotingFunctions.ComplexPlotFunction as cmplxplt


from multiprocessing import Manager
import ctypes
import os
import scipy.io
import math
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]

_DIGHOLO_DIR = Path(__file__).resolve().parent
_DATA_DIR = _DIGHOLO_DIR / "Data"


def _resolve_data_path(filename):
    path = Path(filename)
    if path.is_absolute():
        return path
    return _DATA_DIR / path


class digholoMetrics(IntEnum):
    COUNT = digH_hpy.DIGHOLO_METRIC_COUNT
    IL = digH_hpy.DIGHOLO_METRIC_IL
    MDL = digH_hpy.DIGHOLO_METRIC_MDL
    DIAG = digH_hpy.DIGHOLO_METRIC_DIAG
    SNRAVG = digH_hpy.DIGHOLO_METRIC_SNRAVG
    DIAGBEST = digH_hpy.DIGHOLO_METRIC_DIAGBEST
    DIAGWORST = digH_hpy.DIGHOLO_METRIC_DIAGWORST
    SNRBEST= digH_hpy.DIGHOLO_METRIC_SNRBEST
    SNRMG= digH_hpy.DIGHOLO_METRIC_SNRMG
    SNRWORST= digH_hpy.DIGHOLO_METRIC_SNRWORST
def adjust_array_dimensions(arr):
    # Get the current dimensions of the array
    rows, cols = arr.shape

    # Calculate the number of rows and columns to add on each side
    rows_to_add = (16 - (rows % 16)) % 16
    cols_to_add = (16 - (cols % 16)) % 16

    # Calculate the new dimensions
    new_rows = rows + rows_to_add
    new_cols = cols + cols_to_add
    # Check if adjustment is needed
    if new_rows != rows or new_cols != cols:
        # Create a new array with the desired dimensions and fill it with zeros
        # adjusted_arr = np.zeros((new_rows, new_cols), dtype=arr.dtype)
        adjusted_arr = np.zeros((new_rows, new_cols), dtype=arr.dtype)
        # Copy the original array into the center of the new array
        adjusted_arr[rows_to_add//2:rows_to_add//2+rows, cols_to_add//2:cols_to_add//2+cols] = arr

        # # Copy the original array into the center of the new array
        # adjusted_arr[:rows, :cols] = arr
        return adjusted_arr
    else:
        # No adjustment needed, return the original array
        return arr

class digholoObject():
    def __init__(self,IntialCameraFrame=np.zeros((256,256),dtype=float),PixelSize=30e-6,Wavelength=1565e-9,
                 polCount=1,maxMG=1,fftWindowSizeX=256,fftWindowSizeY=256,FFTRadius=0.4,
                 TransformMat=None,TransformMatrixFilename=None,digholoProperties=None):
        super().__init__() # inherit from parent class  
              
        self.handleIdx=digH_hpy.digHoloCreate()
        self.MetricCounts=digH_hpy.DIGHOLO_METRIC_COUNT # this is the total number of metrics that the can be calculated from coefs matrix 
        self.WavelengthCount=1 # i am a little surprise at this but there is no built in function that set the wavelength count it is set when and if you have a array of wavelength to go over.
        self.Metrics=np.zeros((self.MetricCounts,self.WavelengthCount+1))
        self.coefs = np.zeros((1,1))*1j

        # if you the user has a custom matrix they want to algin to this will set it up at the begin
        self.TransformMat = TransformMat
        self.TransformMatrixFilename = TransformMatrixFilename
        basisType = 2 if TransformMatrixFilename is not None or TransformMat is not None else 0

    
        if digholoProperties is not None:
            self.digholoProperties=digholoProperties
            self.TransformMatrixFilename = self.digholoProperties.get(
                "TransformMatrixFilename",
                TransformMatrixFilename
            )
            if self.TransformMatrixFilename is not None or self.TransformMat is not None:
                self.digholoProperties["basisType"] = 2
        else:
            self.digholoProperties={ "Wavelength": Wavelength,
                "WavelengthCount": self.WavelengthCount,          
                "polCount": polCount,
                "batchCount": 1,
                "AvgCount":1,
                "PixelSize":PixelSize,
                "maxMG": maxMG,
                "fftWindowSizeX": fftWindowSizeX,
                "fftWindowSizeY": fftWindowSizeY,
                "FFTRadius": FFTRadius,
                "BeamCentreXPolH":0,
                "BeamCentreXPolV":0,
                "BeamCentreYPolH":0,
                "BeamCentreYPolV":0,
                "BasisWaistPolH":1,
                "BasisWaistPolV":1,
                "DefocusPolH":0,
                "DefocusPolV":0,
                "XTiltPolH":0,
                "XTiltPolV":0,
                "YTiltPolH":0,
                "YTiltPolV":0,
                "AutoAlignBeamCentre": 1,
                "AutoAlignDefocus": 1,
                "AutoAlignTilt": 1,
                "AutoAlignBasisWaist":1,
                "AutoAlignFourierWindowRadius":0,
                "goalIdx":0,
                "basisType":basisType,
                "resolutionMode":0,
                "verbosity":2,
                "TransformMatrixFilename":TransformMatrixFilename
            }
        # NOTE You need to setup this output file detial before you do any thing; I think. It use to get called/setup every time AutoAlign function but i 
        # dont think you have to do this every time.
        #Amount of detail to print to console. 0: Console off. 1: Basic info. 2:Debug mode. 3: You've got serious issues
        #Sets the resolution mode of the reconstructed field.
        #0 : Full resolution. Reconstructed field will have same pixel
        #size/dimensions as the FFT window.
        #1 : Low resolution. Reconstructed field will have dimension of the IFFT
        #window. 
        consoleRedirectToFile=True
        consoleFilename = "digHoloConsole.txt"
        if consoleRedirectToFile:
            digH_hpy.digHoloConfigSetVerbosity(self.handleIdx,self.digholoProperties["verbosity"])
            self.charPtr = ctypes.c_char_p(consoleFilename.encode('utf-8'))
            digH_hpy.digHoloConsoleRedirectToFile(self.charPtr)
        # This is not need exactly but when you start the digiholo up it is nice to see it initially aligned to something.
        
        #Get a frame for to make the reference field. This needs to be done to initalise every thing
        # if  CamObj is not None:
        #     self.CamObj=CamObj
        #     self.FrameWidth=self.CamObj.FrameWidth
        #     self.FrameHeight=self.CamObj.FrameHeight
        #     digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        #     self.digholoProperties["PixelSize"]=self.CamObj.PixelSize
        #     FrameBufferInitial= self.CamObj.GetFrame(True)
        #     self.digholo_SetProps()
        #     self.digHolo_AutoAlign(FrameBufferInitial)
        # else:
        #     self.FrameWidth=256
        #     self.FrameHeight=256
        #     digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        #     print("No Camera object has been passed to the digHolo object. You can call a digHolo_AutoAlign function to align the digiholo object to a frame")
        if len(IntialCameraFrame.shape)==2:
            self.FrameWidth=IntialCameraFrame.shape[1] 
            self.FrameHeight=IntialCameraFrame.shape[0]
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
            self.digholoProperties["PixelSize"]=PixelSize
            self.digholo_SetProps()
            self._apply_transform_matrix()
            self.digHolo_AutoAlign(IntialCameraFrame)
        elif len(IntialCameraFrame.shape)==3:
            self.FrameWidth=IntialCameraFrame.shape[-1] 
            self.FrameHeight=IntialCameraFrame.shape[-2]
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
            self.digholoProperties["PixelSize"]=PixelSize
            self.digholo_SetProps()
            self._apply_transform_matrix()
            self.digHolo_AutoAlign(IntialCameraFrame[0,:,:])
        else:
            print("The IntialCameraFrame that you have passed to the digHolo object is not the correct shape. \
                  It should be [CamHeight,CamWidth] or [batchCount,CamHeight,CamWidth]\
                  The digHolo object has been set to the default values of 256x256. No auto aligment has been run.")
            self.FrameWidth=256
            self.FrameHeight=256
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
            self.digholoProperties["PixelSize"]=PixelSize
            
        self.digholo_SetProps()
            
    def __del__(self):
        """Destructor to destory the digital holograph object."""
        error=digH_hpy.digHoloDestroy(self.handleIdx)
        if (error==0):
            print("Digholo Object has been destroyed")
        else:
            print("problems destorying digholo Error code: ",error)

    def _apply_transform_matrix(self):
        if self.TransformMatrixFilename is not None:
            self.loadTransformMatrix(self.TransformMatrixFilename)
        elif self.TransformMat is not None:
            self.digHolo_ConfigSetBasisTypeCustom(self.TransformMat)
            

    def digholo_SetProps(self):
        """
        Configure holography properties. If an argument is omitted (None),
        the object will use its existing attribute for that property.
        """
        # 1) Extract needed values from self.digholoProperties
        Wavelength = self.digholoProperties["Wavelength"]
        WavelengthCount=self.WavelengthCount
        polCount   = self.digholoProperties["polCount"]
        batchCount = self.digholoProperties["batchCount"]
        AvgCount = self.digholoProperties["AvgCount"]
        pixelsize = self.digholoProperties["PixelSize"]
        maxMG      = self.digholoProperties["maxMG"]
        fftWindowSizeX = self.digholoProperties["fftWindowSizeX"]
        fftWindowSizeY = self.digholoProperties["fftWindowSizeY"]
        FFTRadius      = self.digholoProperties["FFTRadius"]
        resolutionMode = self.digholoProperties["resolutionMode"]
        
        BeamCentreXPolH = self.digholoProperties["BeamCentreXPolH"]
        BeamCentreXPolV = self.digholoProperties["BeamCentreXPolV"]
        BeamCentreYPolH = self.digholoProperties["BeamCentreYPolH"]
        BeamCentreYPolV = self.digholoProperties["BeamCentreYPolV"]
        BasisWaistPolH = self.digholoProperties["BasisWaistPolH"]
        BasisWaistPolV = self.digholoProperties["BasisWaistPolV"]
        DefocusPolH = self.digholoProperties["DefocusPolH"]
        DefocusPolV = self.digholoProperties["DefocusPolV"]
        XTiltPolH = self.digholoProperties["XTiltPolH"]
        XTiltPolV = self.digholoProperties["XTiltPolV"]
        YTiltPolH = self.digholoProperties["YTiltPolH"] 
        YTiltPolV = self.digholoProperties["YTiltPolV"]        
               
        AutoAlignBeamCentre         = int(self.digholoProperties["AutoAlignBeamCentre"])
        AutoAlignDefocus            = int(self.digholoProperties["AutoAlignDefocus"])
        AutoAlignTilt               = int(self.digholoProperties["AutoAlignTilt"])
        AutoAlignBasisWaist         = int(self.digholoProperties["AutoAlignBasisWaist"])
        AutoAlignFourierWindowRadius = int(self.digholoProperties["AutoAlignFourierWindowRadius"])
        goalIdx= self.digholoProperties["goalIdx"]
        if goalIdx<0 or goalIdx>7:
            goalIdx =0
            print("Invaild goalIdx must be 0=>goalIdx<=7. goalIdx has been set to 0")
        basisType = self.digholoProperties["basisType"]
        if basisType<0 or basisType>2:
            basisType =0
            print("Invaild basisType must be 0=>basisType<=2. basisType has been set to 0")
        verbosity=self.digholoProperties["verbosity"]
        resolutionMode=self.digholoProperties["resolutionMode"]

        
        # If you store verbosity in self.digholoProperties, you can do:
        # verbosity = self.digholoProperties["verbosity"]
        # otherwise just use self.verbosity

        # 2) Push them to the library
        digH_hpy.digHoloConfigSetFramePixelSize(self.handleIdx, pixelsize)
        digH_hpy.digHoloConfigSetBatchCount(self.handleIdx, batchCount)
        digH_hpy.digHoloConfigSetBatchAvgCount(self.handleIdx, AvgCount)

        
        digH_hpy.digHoloConfigSetWavelengthCentre(self.handleIdx, Wavelength)
        digH_hpy.digHoloConfigSetPolCount(self.handleIdx, polCount)
           
        digH_hpy.digHoloConfigSetBasisGroupCount(self.handleIdx, maxMG)
        

        digH_hpy.digHoloConfigSetfftWindowSizeX(self.handleIdx, fftWindowSizeX)
        digH_hpy.digHoloConfigSetfftWindowSizeY(self.handleIdx, fftWindowSizeY)
    
        digH_hpy.digHoloConfigSetFourierWindowRadius(self.handleIdx, FFTRadius)
        digH_hpy.digHoloConfigSetIFFTResolutionMode(self.handleIdx, resolutionMode)
        
        digH_hpy.digHoloConfigSetBeamCentre(self.handleIdx,int(0),int(0), BeamCentreXPolH)
        digH_hpy.digHoloConfigSetBeamCentre(self.handleIdx,int(0),int(1), BeamCentreXPolV)
        digH_hpy.digHoloConfigSetBeamCentre(self.handleIdx,int(1),int(0), BeamCentreYPolH)
        digH_hpy.digHoloConfigSetBeamCentre(self.handleIdx,int(1),int(1), BeamCentreYPolV)
        
        digH_hpy.digHoloConfigSetBasisWaist(self.handleIdx,int(0),BasisWaistPolH)
        digH_hpy.digHoloConfigSetBasisWaist(self.handleIdx,int(1),BasisWaistPolV)
        
        digH_hpy.digHoloConfigSetDefocus(self.handleIdx,int(0),DefocusPolH)
        digH_hpy.digHoloConfigSetDefocus(self.handleIdx,int(1),DefocusPolV)
        
        digH_hpy.digHoloConfigSetTilt(self.handleIdx,int(0),int(0), XTiltPolH)
        digH_hpy.digHoloConfigSetTilt(self.handleIdx,int(0),int(1), XTiltPolV)
        digH_hpy.digHoloConfigSetTilt(self.handleIdx,int(1),int(0), YTiltPolH)
        digH_hpy.digHoloConfigSetTilt(self.handleIdx,int(1),int(1), YTiltPolV)

        digH_hpy.digHoloConfigSetAutoAlignBeamCentre(self.handleIdx, AutoAlignBeamCentre)
        digH_hpy.digHoloConfigSetAutoAlignDefocus(self.handleIdx, AutoAlignDefocus)
        digH_hpy.digHoloConfigSetAutoAlignTilt(self.handleIdx, AutoAlignTilt)
        digH_hpy.digHoloConfigSetAutoAlignBasisWaist(self.handleIdx, AutoAlignBasisWaist)
        digH_hpy.digHoloConfigSetAutoAlignFourierWindowRadius(self.handleIdx, AutoAlignFourierWindowRadius)
  
        digH_hpy.digHoloConfigSetAutoAlignGoalIdx (self.handleIdx,goalIdx)
        digH_hpy.digHoloConfigSetBasisType(self.handleIdx,basisType)

        digH_hpy.digHoloConfigSetVerbosity(self.handleIdx,verbosity)

        

    def digholo_GetProps(self):
        """
        Reads the current settings from the digHolo library into self.digholoProperties,
        then returns that dictionary.
        """
        self.digholoProperties["Wavelength"] = digH_hpy.digHoloConfigGetWavelengthCentre(self.handleIdx)
        self.digholoProperties["WavelengthCount"] = self.WavelengthCount
        
        self.digholoProperties["polCount"]   = int(digH_hpy.digHoloConfigGetPolCount(self.handleIdx))
        self.digholoProperties["maxMG"]      = digH_hpy.digHoloConfigGetBasisGroupCount(self.handleIdx)
        self.digholoProperties["batchCount"] = int(digH_hpy.digHoloConfigGetBatchCount(self.handleIdx))
        self.digholoProperties["AvgCount"] = int(digH_hpy.digHoloConfigGetBatchAvgCount(self.handleIdx))

 
        self.digholoProperties["fftWindowSizeY"] = digH_hpy.digHoloConfigGetfftWindowSizeY(self.handleIdx)
        self.digholoProperties["fftWindowSizeX"] = digH_hpy.digHoloConfigGetfftWindowSizeX(self.handleIdx)

        self.digholoProperties["FFTRadius"]      = digH_hpy.digHoloConfigGetFourierWindowRadius(self.handleIdx)
        self.digholoProperties["resolutionMode"] = digH_hpy.digHoloConfigGetIFFTResolutionMode(self.handleIdx)
        
        self.digholoProperties["BeamCentreXPolH"] = digH_hpy.digHoloConfigGetBeamCentre(self.handleIdx,int(0),int(0))
        self.digholoProperties["BeamCentreXPolV"] = digH_hpy.digHoloConfigGetBeamCentre(self.handleIdx,int(0),int(1))
        self.digholoProperties["BeamCentreYPolH"] = digH_hpy.digHoloConfigGetBeamCentre(self.handleIdx,int(1),int(0))
        self.digholoProperties["BeamCentreYPolV"] = digH_hpy.digHoloConfigGetBeamCentre(self.handleIdx,int(1),int(1))
        
        self.digholoProperties["BasisWaistPolH"] = digH_hpy.digHoloConfigGetBasisWaist(self.handleIdx,int(0))
        self.digholoProperties["BasisWaistPolV"] = digH_hpy.digHoloConfigGetBasisWaist(self.handleIdx,int(1))
        
        self.digholoProperties["DefocusPolH"] = digH_hpy.digHoloConfigGetDefocus(self.handleIdx,int(0))
        self.digholoProperties["DefocusPolV"] = digH_hpy.digHoloConfigGetDefocus(self.handleIdx,int(1))

        self.digholoProperties["XTiltPolH"] = digH_hpy.digHoloConfigGetTilt(self.handleIdx,int(0),int(0))
        self.digholoProperties["XTiltPolV"] = digH_hpy.digHoloConfigGetTilt(self.handleIdx,int(0),int(1))
        
        self.digholoProperties["YTiltPolH"] = digH_hpy.digHoloConfigGetTilt(self.handleIdx,int(1),int(0))
        self.digholoProperties["YTiltPolV"] = digH_hpy.digHoloConfigGetTilt(self.handleIdx,int(1),int(1))

        self.digholoProperties["AutoAlignBeamCentre"]         = digH_hpy.digHoloConfigGetAutoAlignBeamCentre(self.handleIdx)
        self.digholoProperties["AutoAlignDefocus"]            = digH_hpy.digHoloConfigGetAutoAlignDefocus(self.handleIdx)
        self.digholoProperties["AutoAlignTilt"]               = digH_hpy.digHoloConfigGetAutoAlignTilt(self.handleIdx)
        self.digholoProperties["AutoAlignBasisWaist"]         = digH_hpy.digHoloConfigGetAutoAlignBasisWaist(self.handleIdx)
        self.digholoProperties["AutoAlignFourierWindowRadius"] = digH_hpy.digHoloConfigGetAutoAlignFourierWindowRadius(self.handleIdx)

        
        self.digholoProperties["goalIdx"] = digH_hpy.digHoloConfigGetAutoAlignGoalIdx(self.handleIdx)
        self.digholoProperties["basisType"] = digH_hpy.digHoloConfigGetBasisType(self.handleIdx)
        
        

        return self.digholoProperties



    ######
    # NOTE So i am going to put these function into the object but i might change my mind later on I am not sure yet
    ######
    def digHolo_AutoAlign(self,frameBuffer,AverageBatch=False,batchCount=1,AvgCount=1,AvgMode=digH_hpy.DIGHOLO_AVGMODE_SEQUENTIAL,DoAutoAlgin=True):
        Camdims=frameBuffer.shape
        if len(Camdims)<2 or len(Camdims)>3:
            print(" AutoAlgin NOT run.\n The Camera frames that you have passed are not the correct dims. They should be [batchCount,CamHieght,CamWidth].")
            return 
        
        if len(Camdims)==2:
            self.digholoProperties["batchCount"]=1
            self.digholoProperties["maxMG"]=1
            frameBuffer = adjust_array_dimensions(frameBuffer)
            Camdims=frameBuffer.shape
            
            self.FrameWidth=int(Camdims[1])
            self.FrameHeight=int(Camdims[0])
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        else:
            for iframe in range(Camdims[0]):
                frameBuffer[iframe,:,:] = adjust_array_dimensions(frameBuffer[iframe,:,:])
            Camdims=frameBuffer.shape
            if AverageBatch==False:
                self.digholoProperties["batchCount"]=Camdims[0]
            else: 
                self.digholoProperties["batchCount"]=batchCount
                self.digholoProperties["AvgCount"]=AvgCount
            self.FrameWidth=Camdims[2]
            self.FrameHeight=Camdims[1]
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        self.digholo_SetProps()
        
        digH_hpy.digHoloConsoleRedirectToFile(self.charPtr)
        
        frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))        
        if AverageBatch:
           digH_hpy.digHoloSetBatchAvg (self.handleIdx, int(self.digholoProperties["batchCount"]), frameBufferPtr, 
                                        self.digholoProperties["AvgCount"], AvgMode)   
        else:
            digH_hpy.digHoloSetBatch(self.handleIdx,int(self.digholoProperties["batchCount"]),frameBufferPtr)
        if DoAutoAlgin:
            digH_hpy.digHoloAutoAlign(self.handleIdx)
        

        self.digHolo_ProcessBatch(frameBuffer,CalculateMetrics=True,
                                  AverageBatch=AverageBatch,batchCount=batchCount
                                  ,AvgCount=AvgCount,AvgMode=AvgMode
                                  )
        
        self.digholo_GetProps()
       
        self.SaveBatchFile("Batch",frameBuffer,False)
        
        # Get the Coef matrix and metrics  
        self.coefs,*_=self.digHolo_BasisGetCoefs()
        Metrics_ptr = ctypes.POINTER(ctypes.c_float)()
        for MetricIdx in range(self.MetricCounts):
            Metrics_ptr = digH_hpy.digHoloAutoAlignGetMetrics(self.handleIdx,int(MetricIdx))
            self.Metrics[MetricIdx,:]= np.ctypeslib.as_array(Metrics_ptr,shape=(int(self.digholoProperties["WavelengthCount"])+1,))
        self.digholo_SetProps()
        
        return self.coefs,self.Metrics



    # This is if you dont want digiholo to change any of its setting but you want to process some frames
    def digHolo_ProcessBatch(self,frameBuffer,CalculateMetrics=True,AverageBatch=False,batchCount=1,AvgCount=1,AvgMode=digH_hpy.DIGHOLO_AVGMODE_SEQUENTIAL):
        Camdims=frameBuffer.shape
        # if len(Camdims)==2:
        #     self.digholoProperties["batchCount"]=1
        #     self.digholoProperties["maxMG"]=1
        #     self.FrameWidth=Camdims[1]
        #     self.FrameHeight=Camdims[0]
        #     digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        # else:
        #     if AverageBatch==False:
        #         self.digholoProperties["batchCount"]=Camdims[0]
        #     else: 
        #         self.digholoProperties["batchCount"]=batchCount
        #         self.digholoProperties["AvgCount"]=AvgCount
        if len(Camdims)==2:
            self.digholoProperties["batchCount"]=1
            self.digholoProperties["maxMG"]=1
            frameBuffer = adjust_array_dimensions(frameBuffer)
            Camdims=frameBuffer.shape
            print(Camdims)
            
            self.FrameWidth=int(Camdims[1])
            self.FrameHeight=int(Camdims[0])
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        else:
            for iframe in range(Camdims[0]):
                frameBuffer[iframe,:,:] = adjust_array_dimensions(frameBuffer[iframe,:,:])
            Camdims=frameBuffer.shape
            if AverageBatch==False:
                self.digholoProperties["batchCount"]=Camdims[0]
            else: 
                self.digholoProperties["batchCount"]=batchCount
                self.digholoProperties["AvgCount"]=AvgCount
            self.FrameWidth=Camdims[2]
            self.FrameHeight=Camdims[1]
            digH_hpy.digHoloConfigSetFrameDimensions(self.handleIdx,self.FrameWidth,self.FrameHeight)
        
        frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        digH_hpy.digHoloSetBatch(self.handleIdx,int(self.digholoProperties["batchCount"]),frameBufferPtr)
        if AverageBatch:
           digH_hpy.digHoloSetBatchAvg (self.handleIdx, int(self.digholoProperties["batchCount"]), frameBufferPtr, 
                                        self.digholoProperties["AvgCount"], AvgMode)  
      
        else:
            digH_hpy.digHoloSetBatch(self.handleIdx,int(self.digholoProperties["batchCount"]),frameBufferPtr)

        batchCount_c = ctypes.c_int(int(self.digholoProperties["batchCount"]))
        polCount_c = ctypes.c_int(self.digholoProperties["polCount"])
        modeCount_c= ctypes.c_int()
        
        CoefptrOut = ctypes.POINTER(ctypes.c_float)()
        CoefptrOut=digH_hpy.digHoloProcessBatch(self.handleIdx,ctypes.byref(batchCount_c),ctypes.byref(modeCount_c),ctypes.byref(polCount_c))
        coefs = np.ctypeslib.as_array(CoefptrOut,shape=(batchCount_c.value,2*modeCount_c.value*polCount_c.value))# NOTE the 2 is to account for complex values
        self.coefs = coefs[:,0::2]+1j*coefs[:,1::2]
        
        if (CalculateMetrics):
            # becasue you have called digHoloProcessBatch and not AutoAlgin the metrics on the current coeffs matrix need to be calculated that were determined 
            # from digHoloProcessBatch
            digH_hpy.digHoloAutoAlignCalcMetrics(self.handleIdx)
            # Now we are going to get the metric values
            Metrics_ptr = ctypes.POINTER(ctypes.c_float)()
            for MetricIdx in range(self.MetricCounts):
                Metrics_ptr = digH_hpy.digHoloAutoAlignGetMetrics(self.handleIdx,MetricIdx)
                self.Metrics[MetricIdx,:] = np.ctypeslib.as_array(Metrics_ptr,shape=(int(self.digholoProperties["WavelengthCount"])+1,))
       
        return self.coefs,self.Metrics
    def interleave_complex64_to_float32(self,matrix: np.ndarray) -> np.ndarray:
        """Convert a complex64 matrix to a float32 array with interleaved [real, imag]"""
        # assert matrix.dtype == np.complex64
        # flat = matrix
        interleaved = np.empty((matrix.shape[0], matrix.shape[1]* 2), dtype=np.float32)
        interleaved[:,0::2] = matrix.real
        interleaved[:,1::2] = matrix.imag
        return interleaved
    # def interleave_complex64_to_float32(self,matrix: np.ndarray) -> np.ndarray:
    #     """Convert a complex64 matrix to a float32 array with interleaved [real, imag]"""
    #     # assert matrix.dtype == np.complex64
    #     flat = matrix.flatten()
    #     interleaved = np.empty((flat.size* 2), dtype=np.float32)
    #     interleaved[0::2] = flat.real
    #     interleaved[1::2] = flat.imag
    #     return interleaved
    
    def digHolo_ConfigSetBasisTypeCustom(self,transformMatrix):
        self.digholoProperties["basisType"]=2
        self.digholo_SetProps()
        TransformMatrix_dims=transformMatrix.shape
        modeCountIn=TransformMatrix_dims[0]
        modeCountOut=TransformMatrix_dims[1]
        # transformMatrix_as_float = transformMatrix.view(np.float32)
         # Interleave manually for C code
        transformMatrix_as_float = self.interleave_complex64_to_float32(transformMatrix)

        transformMatrixPtr = transformMatrix_as_float.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        error=digH_hpy.digHoloConfigSetBasisTypeCustom (self.handleIdx,  modeCountIn, modeCountOut,transformMatrixPtr)
        print(error)
        self.test=transformMatrix_as_float
        
    def digHolo_BasisGetCoefs(self):
        batchCount_c = ctypes.c_int()
        polCount_c = ctypes.c_int()
        modeCount_c = ctypes.c_int()
        
        CoefptrOut = ctypes.POINTER(ctypes.c_float)()
        CoefptrOut= digH_hpy.digHoloBasisGetCoefs(self.handleIdx,ctypes.byref(batchCount_c),ctypes.byref(modeCount_c),ctypes.byref(polCount_c))
        coefs = np.ctypeslib.as_array(CoefptrOut,shape=(batchCount_c.value,2*modeCount_c.value*polCount_c.value))
        coefs = coefs[:,0::2]+1j*coefs[:,1::2]
        return coefs,batchCount_c.value,modeCount_c.value,polCount_c.value
    
    def digHolo_GetFields16(self):
        batchCount_c = ctypes.c_int()
        polCount_c = ctypes.c_int()
        fieldR_ptr = ctypes.POINTER(ctypes.c_short)()
        fieldI_ptr = ctypes.POINTER(ctypes.c_short)()
        fieldScale_ptr = ctypes.POINTER(ctypes.c_float)()
        x_ptr = ctypes.POINTER(ctypes.c_float)()
        y_ptr = ctypes.POINTER(ctypes.c_float)()
        fieldWidth_ptr=ctypes.c_int()
        fieldHeight_ptr=ctypes.c_int()
        digH_hpy.digHoloGetFields16(self.handleIdx,ctypes.byref(batchCount_c),ctypes.byref(polCount_c),
                                            ctypes.byref(fieldR_ptr),ctypes.byref(fieldI_ptr),
                                            ctypes.byref(fieldScale_ptr),ctypes.byref(x_ptr),ctypes.byref(y_ptr),
                                            ctypes.byref(fieldWidth_ptr),ctypes.byref(fieldHeight_ptr))
        
        width= np.int32(fieldWidth_ptr)
        height= np.int32(fieldHeight_ptr)
        
        fieldR = np.ctypeslib.as_array(fieldR_ptr,shape=(batchCount_c.value*polCount_c.value,height,width))
        fieldI = np.ctypeslib.as_array(fieldI_ptr,shape=(batchCount_c.value*polCount_c.value,height,width)) 
        fieldScale = np.ctypeslib.as_array(fieldScale_ptr,shape=(polCount_c.value,batchCount_c.value)) 
        y = np.ctypeslib.as_array(y_ptr,shape=(1,height)) 
        x = np.ctypeslib.as_array(x_ptr,shape=(1,width)) 
        
        return fieldR,fieldI,fieldScale, x,y
    
    def digHolo_GetFields(self):
        """
        Retrieves the reconstructed field(s) from the library.
        Returns:
            fields: A numpy array of shape (batchCount, polCount, width, height)
                    containing complex-valued field data.
        """
        # Prepare pointers/variables to store outputs from the DLL
        batchCount_c = ((ctypes.c_int))()
        polCount_c   = ((ctypes.c_int))()
        w_c          = ((ctypes.c_int))()
        h_c          = ((ctypes.c_int))()

        # x and y pointers (if you need the axis arrays too)
        xPtr = (ctypes.POINTER(ctypes.c_float))()
        yPtr = (ctypes.POINTER(ctypes.c_float))()

        # Call digHoloGetFields
        ptrOut = digH_hpy.digHoloGetFields(
            self.handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(xPtr),
            ctypes.byref(yPtr),
            ctypes.byref(w_c),
            ctypes.byref(h_c)
        )

        # Convert to Python ints
        batchCount = batchCount_c.value
        polCount   = polCount_c.value
        w          = w_c.value
        h          = h_c.value

        # Convert the returned pointer into a NumPy array.
        # The library packs real/imag in the last dimension => shape=(batchCount, polCount, w, 2*h).
        raw_fields = np.ctypeslib.as_array(ptrOut, shape=(batchCount, polCount, w, h*2))

        # Convert interleaved [Re,Im] into a single complex array
        fields = raw_fields[:, :, :, 0::2] + 1j * raw_fields[:, :, :, 1::2]

        return fields


    def digHolo_GetFourierPlaneFull(self):
        """
        Retrieves the full Fourier plane for each field.
        Returns:
            fourierPlanes: A numpy array of shape 
                        (batchCount, polCount, FourierHeight, ((FourierWidth//2)+1)*2)
                        containing complex-valued data for the full Fourier plane.
        """
        # Prepare pointers/variables
        batchCount_c = ctypes.c_int()
        polCount_c   = ctypes.c_int()
        FourierWidth_c  = ctypes.c_int()
        FourierHeight_c = ctypes.c_int()

        # Call digHoloGetFourierPlaneFull
        FourierPtrOut = digH_hpy.digHoloGetFourierPlaneFull(
            self.handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(FourierWidth_c),
            ctypes.byref(FourierHeight_c)
        )

        # Convert to Python ints
        batchCount    = batchCount_c.value
        polCount      = polCount_c.value
        FourierWidth  = FourierWidth_c.value
        FourierHeight = FourierHeight_c.value

        # Convert pointer to NumPy array
        # The library returns real+imag in last dimension => shape=(..., 2).
        # Typically, shape = (batchCount, polCount, FourierHeight, ((FourierWidth//2)+1)*2).
        raw_fourier = np.ctypeslib.as_array(
            FourierPtrOut,
            shape=(batchCount, polCount, FourierHeight, ((FourierWidth // 2) + 1)*2)
        )

        # Convert interleaved [Re,Im] into complex
        fourierPlanes = raw_fourier[:, :, :, 0::2] + 1j * raw_fourier[:, :, :, 1::2]

        return fourierPlanes


    def digHolo_GetFourierPlaneWindow(self):
        """
        Retrieves the (windowed) Fourier plane for each field.
        Returns:
            fourierPlanesWin: A numpy array of shape 
                            (batchCount, polCount, FourierWidthWindow, FourierHeightWindow)
                            containing complex-valued data for the *windowed* Fourier plane.
        """
        # Prepare pointers/variables
        batchCount_c = ctypes.c_int()
        polCount_c   = ctypes.c_int()
        wWin_c       = ctypes.c_int()
        hWin_c       = ctypes.c_int()

        # Call digHoloGetFourierPlaneWindow
        FourierPtrOut_Win = digH_hpy.digHoloGetFourierPlaneWindow(
            self.handleIdx,
            ctypes.byref(batchCount_c),
            ctypes.byref(polCount_c),
            ctypes.byref(wWin_c),
            ctypes.byref(hWin_c)
        )

        # Convert to Python ints
        batchCount = batchCount_c.value
        polCount   = polCount_c.value
        wWin       = wWin_c.value
        hWin       = hWin_c.value

        # Convert pointer to NumPy array
        # Real/imag data interleaved => shape=(batchCount, polCount, wWin, 2*hWin).
        raw_fourier_win = np.ctypeslib.as_array(
            FourierPtrOut_Win,
            shape=(batchCount, polCount, wWin, hWin*2)
        )
        fourierPlanesWin = raw_fourier_win[:, :, :, 0::2] + 1j * raw_fourier_win[:, :, :, 1::2]

        return fourierPlanesWin
    
    def loadTransformMatrix(self,Filename="TransformMatrix.npy"):
        self.digholoProperties["TransformMatrixFilename"]=str(Filename)
        FileToLoad=_resolve_data_path(Filename)
        if not FileToLoad.exists():
            raise FileNotFoundError(f"Transform matrix file not found: {FileToLoad}")

        if FileToLoad.suffix.lower() == ".mat":
            mat_data = scipy.io.loadmat(str(FileToLoad))
            matrix_candidates = [
                value for key, value in mat_data.items()
                if not key.startswith("__")
                and isinstance(value, np.ndarray)
                and value.ndim == 2
                and np.issubdtype(value.dtype, np.number)
            ]
            if not matrix_candidates:
                raise ValueError(f"No 2D numeric matrix found in transform file: {FileToLoad}")
            self.TransformMat = matrix_candidates[0]
        else:
            self.TransformMat= np.load(str(FileToLoad))
        plt.imshow(cmplxplt.ComplexArrayToRgb(self.TransformMat))
        self.digHolo_ConfigSetBasisTypeCustom(self.TransformMat)
        return self.TransformMat
    

    def SaveBatchFile(self,NewFilePathName,framebuffer,fieldOnly):   
        # get the field in the most memory efficent format
        fieldR,fieldI,fieldScale,x,y= self.digHolo_GetFields16()
        
        FileSavePath = Path(NewFilePathName)
        if FileSavePath.suffix == "":
            FileSavePath = FileSavePath.with_suffix(".mat")
        if not FileSavePath.is_absolute():
            FileSavePath = _DATA_DIR / FileSavePath
        FileSavePath.parent.mkdir(parents=True, exist_ok=True)
        if( not fieldOnly):    
            coefs,batchCount,modeCount,polCount=self.digHolo_BasisGetCoefs()           
            polIdx = ((ctypes.c_int))()
            polIdx=0
            waist=np.zeros(polCount)
            #Get the wasit of the reconstruct beams
            waist[polIdx]= digH_hpy.digHoloConfigGetBasisWaist (self.handleIdx,polIdx)
            if (polCount>1):
                polIdx=1
                #Get the wasit of the reconstruct beams
                waist[polIdx]= digH_hpy.digHoloConfigGetBasisWaist (self.handleIdx,polIdx)
            DataStructure = {"fieldScale":fieldScale,
            "x": x,
            "y": y,
            "pixelBuffer": framebuffer,
            "coefs": coefs,
            "waist": waist,
            "fieldR": fieldR,
            "fieldI": fieldI}
        else:
            DataStructure = {"fieldScale":fieldScale,
            "x": x,
            "y": y,
            "pixelBuffer": framebuffer,
            "fieldR": fieldR,
            "fieldI": fieldI}
        # I know it is a little weird that I am saving it as a .mat file but this is just so that it is 
        # backwards compatiable with other code I have written that process the batch files
        scipy.io.savemat(str(FileSavePath),DataStructure)
        return 
    def GetCoefAndMetricsForOutput(self):
        
        CoefsImage= cmplxplt.ComplexArrayToRgb(self.coefs)
        FullText=""
        # for MetricIdx in range(self.MetricCounts)
        FullText=FullText+"IL= "+str(self.Metrics[digH_hpy.DIGHOLO_METRIC_IL])+"\n "
        FullText=FullText+"MDL= "+str(self.Metrics[digH_hpy.DIGHOLO_METRIC_MDL])+"\n "
        FullText=FullText+"DIAG= "+str(self.Metrics[digH_hpy.DIGHOLO_METRIC_DIAG])+"\n "
        FullText=FullText+"SNRAvg= "+str(self.Metrics[digH_hpy.DIGHOLO_METRIC_SNRAVG])+" "
        return CoefsImage,FullText
        
        
        
    def remove_after_tab(self,text):
        """Return the substring before the first tab character."""
        return text.split('\t', 1)[0]  # Split at the first tab and keep only the first part
            
    def GetViewport_arr(self,framebuffer):
        FullText=""
        displayMode_arr=[1,2,4,6]
        for idisplay in displayMode_arr:
            windowString = ((ctypes.c_char_p))()
            ViewPortHeight=ctypes.c_int(0)
            ViewPortWidth=ctypes.c_int(0)
            ViewPortPtr=ctypes.c_char_p()# this is were the output is
            ViewPortPtr=digH_hpy.digHoloGetViewport(int(self.handleIdx), idisplay, 0,ctypes.byref(ViewPortWidth),ctypes.byref(ViewPortHeight),ctypes.byref(windowString))
            
            ViewPortWidth = np.int32(ViewPortWidth)
            ViewPortHeight = np.int32(ViewPortHeight)
            ViewPortRGB = np.ctypeslib.as_array(ViewPortPtr,shape=(ViewPortHeight,ViewPortWidth,3))
            if idisplay==1:
                ViewPortRGB_cam=copy.deepcopy(ViewPortRGB)
                FullText=FullText+"Cam: "+self.remove_after_tab(str(windowString.value.decode('utf-8')))+" \n"
            elif idisplay==2:
                ViewPortRGB_fft=copy.deepcopy(ViewPortRGB)
                FullText=FullText+"FFT_full: "+self.remove_after_tab(str(windowString.value.decode('utf-8')))+" \n"
            elif idisplay==4:
                ViewPortRGB_fftWin=copy.deepcopy(ViewPortRGB)
                FullText=FullText+"FFT_Window: "+self.remove_after_tab(str(windowString.value.decode('utf-8')))+" \n"
                
            elif idisplay==6:
                ViewPortRGB_Field=copy.deepcopy(ViewPortRGB)
                FullText=FullText+"Field: "+self.remove_after_tab(str(windowString.value.decode('utf-8')))
                
            else:
                print("haven't picked a valid displayMode you really shouldnt see this message.The universe is broken if you have as lines above this would have crashed code") 
        #  reshape camera windwo
        FieldDims=ViewPortRGB_Field.shape
        ViewPortRGB_cam_resized = cv2.resize(ViewPortRGB_cam, (FieldDims[1], FieldDims[0]))

        #  reshape fft full plane window
        fftDims=ViewPortRGB_fft.shape
        fftWinDims=ViewPortRGB_fftWin.shape
        row_top_pad  =0
        row_bottom_pad  = 0
        # col_left_pad   = (fftDims[0])//2-1
        col_left_pad   = (FieldDims[1])//2-1
        col_right_pad  = 0
        # Pad the array with zeros
        ViewPortRGB_fft_pad = np.pad(ViewPortRGB_fft, ((row_top_pad, row_bottom_pad), (col_left_pad, col_right_pad), (0, 0)), mode='constant', constant_values=0)
        
        FullimageTop = np.concatenate((ViewPortRGB_cam_resized, ViewPortRGB_fft_pad), axis=1)
        FullimageBottom= np.concatenate((ViewPortRGB_Field,ViewPortRGB_fftWin), axis=1)
        Fullimage = np.concatenate((FullimageTop, FullimageBottom), axis=0)
        
        return Fullimage ,ViewPortRGB_cam, FullText
    
    def DisplayWindow_GraphWithText(self, image: np.ndarray,
                                text: str,
                                font=cv2.FONT_HERSHEY_SIMPLEX,
                                font_scale=1,
                                thickness=2,
                                text_color=(255, 255, 255),
                                bg_color=(0, 0, 0),
                                margin=10,
                                line_spacing=5):
        """
        Displays an image at the top with multi-line text at the bottom.
        
        Parameters:
        image (np.ndarray): Image in BGR format.
        text (str): Multi-line text with lines separated by '\n'.
        font: OpenCV font.
        font_scale (float): Scale factor for the text.
        thickness (int): Text thickness.
        text_color (tuple): Text color in BGR.
        bg_color (tuple): Background color for the text area.
        margin (int): Margin around the text.
        line_spacing (int): Extra spacing between lines.
        """

        # Split the text into lines
        lines = text.split('\n')

        # Get text sizes for each line
        line_info = [cv2.getTextSize(line, font, font_scale, thickness) for line in lines]
        line_sizes = [info[0] for info in line_info]  # (width, height) for each line
        line_heights = [size[1] for size in line_sizes]  # Heights of each text line

        # Calculate text area size
        max_text_width = max(size[0] for size in line_sizes) if lines else 0
        total_text_height = sum(line_heights) + (len(lines) - 1) * line_spacing + 2 * margin

        # Determine canvas size (image on top, text at the bottom)
        canvas_width = max(image.shape[1], max_text_width + 2 * margin)
        canvas_height = image.shape[0] + total_text_height

        # Ensure the image is in BGR (if grayscale, convert to 3-channel)
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        # Create a blank canvas
        canvas = np.full((canvas_height, canvas_width, 3), bg_color, dtype=np.uint8)

        # Place the image at the top
        image_x = (canvas_width - image.shape[1]) // 2  # Center horizontally
        canvas[0:image.shape[0], image_x:image_x+image.shape[1]] = image

        # Draw text at the bottom
        text_y_start = image.shape[0] + margin  # Start text after the image
        for i, line in enumerate(lines):
            text_y = text_y_start + sum(line_heights[:i]) + i * line_spacing + line_heights[i]
            cv2.putText(canvas, line, (margin, text_y), font, font_scale, text_color, thickness)

        return canvas
    
    # This is for a pywidget ploting 
    def Plot_Cam_Field_FouierPlane_FouirerWindow(self,imode,ipol,frameBuffer,fields,FourierPlanes,FourierPlanes_Window):
        frame = frameBuffer[imode,:,:]
        field = np.squeeze(fields[imode,ipol,:,:])
        fourierPlane=np.squeeze(FourierPlanes[imode,ipol,:,:])
        fourierWindow=np.squeeze(FourierPlanes_Window[imode,ipol,:,:])
        textSize=16
        fig, ax1=plt.subplots(2,2);
        fig.subplots_adjust(wspace=0.1, hspace=0.1);
        # ax1[0][0].subplot(2,4,1)
        ax1[0][0].imshow(frame,cmap='gray');
        ax1[0][0].set_title('Cam Image',fontsize = textSize);
        ax1[0][0].axis('off')
        ax1[0][1].imshow(cmplxplt.ComplexArrayToRgb(field));
        ax1[0][1].set_title('Field',fontsize = textSize);
        ax1[0][1].axis('off')
        # ax1[1][0].imshow(cmplxplt.ComplexArrayToRgb(fourierPlane));
        ax1[1][0].imshow((np.abs(fourierPlane)));
        ax1[1][0].set_title('Full Fourier Plane',fontsize = textSize);
        ax1[1][0].axis('off')
        ax1[1][1].imshow(cmplxplt.ComplexArrayToRgb(fourierWindow));
        ax1[1][1].set_title('Fourier Window',fontsize = textSize);
        ax1[1][1].axis('off')

    def PlotFields(self,iframe,polIdx,Fields):
            fig, ax1=plt.subplots();
            ax1.imshow(cmplxplt.ComplexArrayToRgb(np.squeeze(Fields[iframe,polIdx,:,:])));
            ax1.set_title('Field',fontsize = 8);
            ax1.axis('off');
    def OverlapFields(self,FieldA,FieldB):
        return (np.sum(np.sum(FieldA*np.conj(FieldB))))
                
   
