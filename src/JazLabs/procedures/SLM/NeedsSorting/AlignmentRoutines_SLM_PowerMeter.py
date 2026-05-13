from Lab_Equipment.Config import config

# import tomography.standard as standard
# import tomography.masks as masks

import cv2
import numpy as np
import matplotlib.pyplot as plt
import threading
import ctypes
import copy
from IPython.display import display, clear_output
import cma
import ipywidgets
import multiprocessing
import time
import scipy.io
import random

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
from scipy.signal import find_peaks
from scipy.optimize import minimize

# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]

# from script_functions import start_worker
# import CameraWindowForm as CamForm
#SLM Libs
import Lab_Equipment.SLM.pyLCOS as pyLCOS
import Lab_Equipment.ZernikeModule.ZernikeModule as zernMod

#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm

# Power Meter Libs
# import  Lab_Equipment.PowerMeter.PowerMeterObject as PMLib
import Lab_Equipment.PowerMeter.PowerMeter_Thorlabs_lib as pwrMeter


import Lab_Equipment.OpticalSwitch.JDSUniphaseOpticalSwitch as OpticalSwitchLib


# Alginment Functions
import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignFunc
from typing import List

def FindFactors(num):
    # find factor of number
    factors=np.array([num])
    for i in range(num-1,0,-1):
        if(num % i) == 0:
            #print(i)
            factors=np.append(factors,[i])
    #print(factors)
    return factors

def set_superpixel(arr, ix, iy, superpixel_size, phase_value,additive=True):
    """
    Set all values in a given superpixel block to a new value.

    Parameters
    ----------
    arr : 2D np.ndarray
        The array to modify.
    ix, iy : int
        Superpixel indices (not pixel indices).
    superpixel_size : int
        Size of each superpixel block (square).
    value : scalar or complex
        New value to assign to that superpixel.

    Returns
    -------
    arr : 2D np.ndarray
        The modified array (same object, modified in-place).
    """
    arr_new=np.copy(arr)
    # print(superpixel_size)
    x_start = ix * superpixel_size
    x_end   = x_start + superpixel_size
    y_start = iy * superpixel_size
    y_end   = y_start + superpixel_size
    if additive:
        arr_new[y_start:y_end, x_start:x_end] = (arr[y_start:y_end, x_start:x_end])*np.exp(phase_value*1j)

    else:
        arr_new[y_start:y_end, x_start:x_end] = np.abs(arr[y_start:y_end, x_start:x_end])*np.exp(phase_value*1j)

        

    return arr_new
def CourseSweepAcrossSLMPowerMeter(slm:pyLCOS.LCOS,channel,PwrObjs:pwrMeter.PowerMeterObj,flipCount=25):

    slm.LCOS_Clean()
    # flipMin=//2-flipCount//2
    flipMin=0
    flipMax=slm.slmHeigth//2+flipCount//2
    flipMax=slm.slmWidth//2+flipCount//2
    print(PwrObjs.GetPower())
    powerReadingX=np.empty(0)
    powerReadingY=np.empty(0)

    #Left to right sweep
    for iflip in range(0,slm.slmWidth,flipCount):

        powerReadingX=np.append(powerReadingX,PwrObjs.GetPower())
        # PiFlip_cmplx =np.ones((slm.slmHeigth,slm.slmWidth),dtype=complex)
        PiFlip_cmplx =np.zeros((slm.slmHeigth,slm.slmWidth),dtype=np.float32)
        # PiFlip_cmplx =np.ones((slm.slmHeigth,slm.slmWidth),dtype=np.float32)*(-1*np.pi)

        # PiFlip_cmplx[0:flipMin+iflip,:]=np.exp(1j*np.pi)
        # PiFlip_cmplx[:,0:flipMin+iflip]=np.exp(1j*np.pi)
        PiFlip_cmplx[:,0:flipMin+iflip]=(np.pi)


        # np.angle( np.random.rand(1200,1920) + np.random.rand(1200,1920) * 1j)
        ArryForSLM=slm.phaseTolevel(np.angle(PiFlip_cmplx), aperture = 1)
        # slm.LCOS_Display(ArryForSLM, slm.GLobProps[channel].rgbChannelIdx)
        slm.LCOS_Display(ArryForSLM, channel)
        
        
        time.sleep(slm.GLobProps[channel].RefreshTime)
        
    # top to bottom sweep    
    for iflip in range(0,slm.slmHeigth,flipCount):
        powerReadingY=np.append(powerReadingY,PwrObjs.GetPower())

        # PiFlip_cmplx =np.ones((slm.slmHeigth,slm.slmWidth),dtype=complex)
        PiFlip_cmplx =np.zeros((slm.slmHeigth,slm.slmWidth),dtype=np.float32)

        # PiFlip_cmplx[0:flipMin+iflip,:]=np.exp(1j*np.pi)
        PiFlip_cmplx[0:flipMin+iflip,:]=(np.pi)

        # PiFlip_cmplx[:,0:flipMin+iflip]=np.exp(1j*np.pi)

        # np.angle( np.random.rand(1200,1920) + np.random.rand(1200,1920) * 1j)
        ArryForSLM=slm.phaseTolevel(np.angle(PiFlip_cmplx), aperture = 1)
        # slm.LCOS_Display(ArryForSLM, slm.GLobProps[channel].rgbChannelIdx)
        slm.LCOS_Display(ArryForSLM, channel)
        
        time.sleep(slm.GLobProps[channel].RefreshTime)
    
    slm.LCOS_Clean(channel)
    return powerReadingX,powerReadingY

class AlginmentObj():
    def __init__(self,
                slmObjs: List[pyLCOS.LCOS],
                PwrObjs: List[pwrMeter.PowerMeterObj]):
        super().__init__()
        
        # Store lists of devices
        self.slmObjs = slmObjs
        self.PwrObjs = PwrObjs
       
        # Ensure equal lengths
        assert len(slmObjs) == len(PwrObjs), \
            "slmObjects, camObjs, and digiholoObjs must have the same length"
        self.ObjCount = len(slmObjs)
        print(self.ObjCount)
        # Default to first channel
        # Initial properties

            
        # self.channel = Channel
        # self.pol = pol
        # self.ApplyZernike = ApplyZernike
        # self.imask = 0
        # self.PixelsCountFromCenters = 50
        # self.AvgFrameCount = 30
        # self.PlotTracking = True
        # self.MaskSize = [256,256]
        # Build reference field
        # self.MakeReferenceField()

        
        
    def __del__(self):
        print("Cleaning up AlginmentObj_SLM_PwrMeter")

    def PerformCenterAlignment_GoldenSearch(self,ObjIdx=0,channel=None,pol="H",
                                            ApplyZernike=False,MaskSize=None,
                                            PixelsCountFromCenters=50,
                                            PlotTracking=False,
                                            BackgroundPhase=np.pi):

        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        if MaskSize is  None:
            MaskSize=self.slmObjs[ObjIdx].polProps[channel][pol].masksize

        OriginialBackground_int=np.copy(self.slmObjs[ObjIdx].backgroundPattern_int)
        background=np.ones((self.slmObjs[ObjIdx].LCOSsize))*np.exp(1j*BackgroundPhase)
        self.slmObjs[ObjIdx].LCOS_Clean(channel=channel)
        self.slmObjs[ObjIdx].SetBackGroundPattern(channel=channel,backgroundPattern=background)
        self.RefPWR=self.PwrObjs[ObjIdx].GetPower()
         
        # Need to set up self variables for the the function to be passed to the golden search function
        self.channel=channel
        self.pol=pol
        self.ObjIdx=ObjIdx
        self.ApplyZernike=ApplyZernike
        self.PixelsCountFromCenters = PixelsCountFromCenters
        self.PlotTracking = PlotTracking
            
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        
        MinXCenter=np.zeros(MaskCount)
        MinYCenter=np.zeros(MaskCount)
        ifig=0
        
        for imask in range(MaskCount): 
            self.imask=imask
            oldxCenter=self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[1]
            oldyCenter=self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[0]
            print("Old X Center: ",oldxCenter)
            print("Old Y Center: ",oldyCenter)
            for iDirection in range(2): # This is for the X and Y direction Centers NOTE 0=Y and 1=X
                if (self.PlotTracking):
                    ifig=ifig+1
                    plt.figure(ifig+100)
                    plt.clf()
                # self.xValTrack=np.empty((0))
                # self.yValTrack=np.empty((0))
                self.iDirection=iDirection
                self.BoundMin=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[iDirection])-self.PixelsCountFromCenters
                self.BoundMax=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[iDirection])+self.PixelsCountFromCenters
                self.DiscretisedSpace_arr= np.arange(self.BoundMin,self.BoundMax,1)
                CenterAvg=0
                iphaseFlipCount=0
                for iPhaseFlip in range(2):#Need to do 2 flips in the same direction for a better center one has the flip reversed
                    self.xValTrack=np.empty((0))
                    self.yValTrack=np.empty((0))
                    self.Phasedir=iPhaseFlip # flipdir X
                    minVal_1,minIdx_1=AlignFunc.GoldenSelectionSearch(self.BoundMin,self.BoundMax,dspace_Tol=1,FuncToMinamise=self.ChangePiFlipTakePower)
                    CenterAvg=CenterAvg+minIdx_1
                    iphaseFlipCount=iphaseFlipCount+1
                    if (self.PlotTracking):
                        if iPhaseFlip==0:
                            plt.scatter(self.xValTrack,self.yValTrack,c="red")
                        else:
                            plt.scatter(self.xValTrack,self.yValTrack,c="green")
                if (self.PlotTracking):
                    plt.show()
        
                if (iDirection==0):# Xdirection
                    MinYCenter[imask]=CenterAvg//iphaseFlipCount
                else:# Ydirection
                    MinXCenter[imask]=CenterAvg//iphaseFlipCount
        
        self.slmObjs[ObjIdx].LCOS_Clean(channel)
        print("Setting new masks Centers")
        for imask in range(MaskCount):
            self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[1] = MinXCenter[imask]
            self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[0] = MinYCenter[imask]
        
        #Switch back to the orginial backgroud
        self.slmObjs[ObjIdx].backgroundPattern_int =np.copy(OriginialBackground_int)
        self.slmObjs[ObjIdx].setmask(channel,0)

        print("New X Centers: ",MinXCenter)
        print("New Y Centers: ",MinYCenter)
        return (MinXCenter),(MinYCenter)
    
    def ChangePiFlipTakePower(self,xVal):
        xVal,x1Idx=AlignFunc.CovertCont2Desc(xVal,self.DiscretisedSpace_arr);
        self.globalphaseshiftshift=-np.pi    
        # Nx=self.slm.masksize[0]
        # Ny=self.slm.masksize[1]
        MaskSize=self.slmObjs[self.ObjIdx].polProps[self.channel][self.pol].masksize
        
        Nx=MaskSize[0]
        Ny=MaskSize[1]
        
        # I dont think i need this but will keep comment
        # self.slm.AllMaskProperties[self.channel][self.pol][self.imask].zernike.zern_coefs[0]=0
        
        
        # need to put a blank mask with zernikes that are currelty on the masks. this is a little bit tedious but it works. I might but this as function in SLM module 
        # as maybe this is all people want to do
       
        MASK=np.ones((Nx,Ny),dtype=complex)
        #Left to right sweep
        if(self.iDirection==1):
            y_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[0])
            
            if( self.Phasedir==0):
                MASK[:,0:int((Nx/2))]=np.exp(1j*self.globalphaseshiftshift)
                MASK[:,int((Nx/2)):Nx]=np.exp(1j*(self.globalphaseshiftshift+np.pi))
            else:
                MASK[:,0:int((Nx/2))]=np.exp(1j*(self.globalphaseshiftshift+np.pi))
                MASK[:,int((Nx/2)):Nx]=np.exp(1j*self.globalphaseshiftshift)
                
            if (self.ApplyZernike):
                MASK_PlussZernike=self.slmObjs[self.ObjIdx].ApplyZernikesToSingleMask(self.channel,(MASK),imask=self.imask,pol=self.pol,imode=0)
            else:
                # MASK_PlussZernike=np.angle(MASK)
                MASK_PlussZernike=(MASK)

            MASKTODisplay_cmplx=self.slmObjs[self.ObjIdx].Draw_Single_Mask( xVal, y_center_Input, MASK_PlussZernike)

        else:
            x_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[1])
            
            if( self.Phasedir==0):
                MASK[0:int((Ny/2)),:]=np.exp(1j*self.globalphaseshiftshift)
                MASK[int((Ny/2)):Ny,:]=np.exp(1j*(self.globalphaseshiftshift+np.pi))
            else:
                MASK[0:int((Ny/2)),:]=np.exp(1j*(self.globalphaseshiftshift+np.pi))
                MASK[int((Ny/2)):Ny,:]=np.exp(1j*self.globalphaseshiftshift)
                
            if (self.ApplyZernike):
                    MASK_PlussZernike=self.slmObjs[self.ObjIdx].ApplyZernikesToSingleMask(self.channel,(MASK),imask=self.imask,pol=self.pol,imode=0)
            else:
                # MASK_PlussZernike=np.angle(MASK)
                MASK_PlussZernike=(MASK)

            MASKTODisplay_cmplx=self.slmObjs[self.ObjIdx].Draw_Single_Mask( x_center_Input,xVal, MASK_PlussZernike)
        
        self.slmObjs[self.ObjIdx].FullScreenBuffer_int=self.slmObjs[self.ObjIdx].convert_phase_to_uint8(MASKTODisplay_cmplx) # Note if nothing is passed it will use the self.FullScreenBuffer_cmplx array as the array it is going to convert      
        self.slmObjs[self.ObjIdx].Write_To_Display(self.slmObjs[self.ObjIdx].FullScreenBuffer_int,self.channel)
        # MASKTODisplay = self.slm.getAngle(MASKTODisplay_cmplx)
        # MASKTODisplay_256 = self.slm.phaseTolevel(MASKTODisplay)# Note that the -1*np.pi is so that the background is set to black it really doesn't matter though.
        # Display on SLM
        # slm.LCOS_Display(slm.LCOS_Screen_temp.astype(int), ch = 0)
        # self.slm.LCOS_Display(MASKTODisplay_256, self.channel)
        # get the power from the power metter
        RefSigPWR = self.PwrObjs[self.ObjIdx].GetPower()
        RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
        
        self.xValTrack=np.append(self.xValTrack,xVal)
        self.yValTrack=np.append(self.yValTrack,RefSigPWR_log)
        
        return xVal,RefSigPWR_log
    
    def SweepAcrossSLM_Mask(self,ObjIdx=0,imask=0,channel=None,pol="H",stepCount=10,PixelsFromCenter=50):
         # need to set the camera to singleFrameCapturemode
        # CamObj.Exposure
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        
        self.slmObjs[ObjIdx].LCOS_Clean(channel)
       
        #This is the reference Field that the other fields will be overlaped with
        self.RefPWR=self.PwrObjs[ObjIdx].GetPower()
        
        PixelFlipStep=np.zeros((2,2*PixelsFromCenter//stepCount,MaskCount))
        RefSigPWR=np.zeros((2,2*PixelsFromCenter//stepCount,MaskCount))
        # I may have to move this to inside the imask loop to reset the pi flip location
        PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(0.0*1j*np.pi)
        
        self.imask=imask
        # set up at the boundaries of the mask properties
        x_center=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[1])
        y_center=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[0])
        print(x_center,y_center)

        flipMinX=x_center-PixelsFromCenter
        if flipMinX<0:
            flipMinX=0
        flipMaxX=x_center+PixelsFromCenter
        if flipMaxX>self.slmObjs[ObjIdx].slmWidth:
            flipMaxX=self.slmObjs[ObjIdx].slmWidth-1
        flipMinY=y_center-PixelsFromCenter
        if flipMinY<0:
            flipMinY=0
        flipMaxY=y_center+PixelsFromCenter
        if flipMaxY>self.slmObjs[ObjIdx].slmHeigth:
            flipMaxY=self.slmObjs[ObjIdx].slmHeigth-1
            
        for iDirection in range(2):
            if (iDirection==1):
                flipMin=flipMinX
                flipMax=flipMaxX
            else:
                flipMin=flipMinY
                flipMax=flipMaxY
            iflipIdx=0
            for iflip in range(flipMin,flipMax,stepCount):
                PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(0.0*1j*np.pi)
    

                if (iDirection==1):
                    PiFlip_cmplx[:,0:iflip]=PiFlip_cmplx[:,0:iflip]*np.exp(1j*np.pi)
                else:
                    PiFlip_cmplx[0:iflip,:]= PiFlip_cmplx[0:iflip,:]*np.exp(1j*np.pi)
                
                # draw/display the actual masks
                self.slmObjs[ObjIdx].FullScreenBuffer_int=self.slmObjs[ObjIdx].convert_phase_to_uint8(PiFlip_cmplx)
                self.slmObjs[ObjIdx].Write_To_Display(self.slmObjs[ObjIdx].FullScreenBuffer_int,channel)
                
            
                RefSigPWR[iDirection,iflipIdx,imask]=self.PwrObjs[ObjIdx].GetPower()
                PixelFlipStep[iDirection,iflipIdx,imask]=iflip
                iflipIdx=iflipIdx+1
                    
            
        # RefSigPWR = np.sqrt(RefSigPWR)# not sure why I sqrt twice might be wrong will come back and check
        RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
        
        self.slmObjs[ObjIdx].LCOS_Clean(channel) 
        
        return RefSigPWR,RefSigPWR_log,PixelFlipStep


    def MultiDimAlignmentOfSLM(self,PwrMeterObjIdx=0,SLMModeGenIdx=0,SLMAlignObjIdx=[0],pol=["H"],polGenIdx=0,
                               modeIdxArr=None,
                               Optimiser='CMA-ES',
                               GoalMetric='Pwr',
                               PropertiesToAlign=None,
                               InitialStepSizes=None,
                               ErrTol=1e-7,
                               maxAttempts=100,
                               populationSize=None,
                               simga0=0.2, ):
        # if channel is None:#if no channel is passed in then use the first active channel on the SLM
        #     channel=self.slmObjs[SLMObjIdx].ActiveRGBChannels[0]
         # Need to set up self variables for the the function to be passed to the golden search function
        # self.channel=channel
        # self.pol=pol
        self.modeIdxArr=modeIdxArr
        if not isinstance(SLMAlignObjIdx, list):
                raise TypeError(f"Expected a list, got {type(SLMAlignObjIdx).__name__!r}")
                return
        self.SLMAlignObjIdx=SLMAlignObjIdx
        self.SLMModeGenIdx=SLMModeGenIdx
        self.PwrMeterObjIdx=PwrMeterObjIdx
        self.polIdxArr=pol
        self.polGenIdx=polGenIdx
        
       
        self.GoalMetric=GoalMetric
        
        
        if PropertiesToAlign is None:
            self.PropertiesToAlign = [{
                "AlignCenters": False,
                "AlignPiston": False,
                "AlignTiltX": False,
                "AlignTiltY": False,
                "AlignDefocus": False,
                "AlignFirstTiltX": False,
                "AlignFirstTiltY": False,
                "AlignLastTiltX": False,
                "AlignLastTiltY": False,
                "AlignDefocusFirst": False,
                "AlignDefocusLast": False
            }]
            print("You need to make a dict that follows the below format were you set the values you want to be aligned: ")
            print("PropertiesToAlign = {")
            for key, value in self.PropertiesToAlign[0].items():
                print(f'    "{key}": {value},')
            print("}")
            return
        else: 
            self.PropertiesToAlign=PropertiesToAlign
        if not isinstance(PropertiesToAlign, list):
                raise TypeError(f"Expected a list, got {type(PropertiesToAlign).__name__!r}")
                return
            
        if InitialStepSizes is None:
            self.InitialStepSizes = [{
                "d_Centers": 50,
                "d_Piston": 1,
                "d_TiltX": 20,
                "d_TiltY": 20,
                "d_Defocus": 20
            }]
            print("Initial step sizes have been auto set to the below values. If you wanted to change it you need to make a dict of that fromat and pass it in to function: ")
            print("InitialStepSizes = {")
            for key, value in self.InitialStepSizes[0].items():
                print(f'    "{key}": {value},')
            print("}")
        else:
            self.InitialStepSizes = InitialStepSizes
        if not isinstance(InitialStepSizes, list):
                raise TypeError(f"Expected a list, got {type(InitialStepSizes).__name__!r}")
                return
            
        StepArray,InitalPhysical=self.GetInitialVerticeForSLMAlignment()
        
        
        self.LowerPhysicalBounds,self.UpperPhysicalBounds=AlignFunc.MakeBoundsFromCentre(InitalPhysical,StepArray)
        InitalNorm=AlignFunc.physical_to_normalised(InitalPhysical,self.LowerPhysicalBounds,self.UpperPhysicalBounds)
   
        #this is the scipy minimisation function might be better then my one that i wrote
     
        self.counter = 0
        self.bestPhysicalVetex = None
        self.BestMetric = np.inf

        

        if Optimiser != 'CMA-ES':
            try:
                if Optimiser == 'Nelder-Mead':
                    intial_simplex = AlignFunc.MakeIntialSimplex(InitalPhysical, StepArray,self.LowerPhysicalBounds,self.UpperPhysicalBounds)
                    PhysicalVertex=AlignFunc.normalised_to_physical(intial_simplex,self.LowerPhysicalBounds,self.UpperPhysicalBounds)
                    print(PhysicalVertex)
                    result = minimize(
                        self.UpdateVertex_PwrReading,
                        InitalNorm,
                        method=Optimiser,
                        options={
                            'disp': True,
                            'initial_simplex': intial_simplex,
                            'xatol': 1e-6,
                            'fatol': ErrTol,
                            'maxiter': maxAttempts
                        }
                    )
                else:
                    result = minimize(
                        self.UpdateVertex_PwrReading,
                        InitalNorm,
                        method=Optimiser,
                        bounds=[(-1, 1)] * InitalNorm.size,
                        options={
                            'disp': True,
                            'xtol': 1e-6,
                            'ftol': ErrTol,
                            'maxiter': maxAttempts
                        }
                    )
            except RuntimeError as e:
                print(f"\nOptimisation stopped: {e}")
                print(f"Best-so-far: {self.BestMetric} at x = {self.bestPhysicalVetex}")
            else:
                print("\nOptimisation completed.")
                print(f"Result: {result.fun} at x = {result.x}")
                print(f"Best-so-far: {self.BestMetric} at x = {self.bestPhysicalVetex}")

        else:
            try:
                if populationSize is None:
                    populationSize = 4 + (3 * np.log10(InitalNorm.size))
                lower_bounds = np.array([-1.0] * len(InitalNorm))
                upper_bounds = np.array([1.0] * len(InitalNorm))
                result = cma.fmin(
                    objective_function=self.UpdateVertex_PwrReading,
                    x0=InitalNorm,
                    sigma0=simga0,
                    options={
                        'bounds': [lower_bounds, upper_bounds],
                        'popsize': populationSize,
                        'maxiter': maxAttempts,
                        'verb_disp': 1
                    }
                )
            except RuntimeError as e:
                print(f"\nOptimisation stopped: {e}")
                print(f"Best-so-far: {self.BestMetric} at x = {self.bestPhysicalVetex}")
            else:
                print("\nOptimisation completed.")
                print(f"Result: {result[1]} at x = {result[0]}")
                print(f"Best-so-far: {self.BestMetric} at x = {self.bestPhysicalVetex}")


        # self.CamObjs[CamObjIdx].SetContinousFrameCapMode()
       
        print("Updating the SLM to have the best properties")
        self.UpdateVerticesForSLMAlignment(self.bestPhysicalVetex)
        
        # result.x

        # AlignFunc.NelderMead(StepArray,InitalxVertex,ErrTol,maxAttempts,self.UpdateVertex_TakeDigholoBatch)
        AlignFunc.ChangeFileForStopAliginment(0)

        
        return 
    
    # def print_callback(self):
    #     x, y = params
    #     dErr = np.std(funcVertex);
    #     print(attemptCount,' Function Value= ',funcVertex[0],' Error Accros Values= ',dErr, ' Verterx Value= ',xVertex[:,0])
    #     print(funcVertex[:])
    #     print(f"Callback: x={x:.3f}, y={y:.3f}")

    def UpdateVertex_PwrReading(self,xVertexSingle):
        self.counter=self.counter+1
        if AlignFunc.CheckFileForStopAliginment():
            raise RuntimeError("Optimisation manually terminated.")
        PhysicalVertex=AlignFunc.normalised_to_physical(xVertexSingle,self.LowerPhysicalBounds,self.UpperPhysicalBounds)

        self.UpdateVerticesForSLMAlignment(PhysicalVertex)
        # Frames=np.zeros((self.batchCount,self.CamObj.Nx,self.CamObj.Ny))\
        MetricVaule=self.PwrObjs[self.PwrMeterObjIdx].GetPower()

        # print(Metrics)
        # MetricVaule=Metrics[self.GoalMetric,0]
        # print(MetricVaule)
        # print(xVertexSingle)
        # if self.GoalMetric==digholoMod.digholoMetrics.MDL:
        #     MetricVaule=-MetricVaule

        # return -MetricVaule,xVertexSingle
        print("Func Evals: "+str(self.counter) + " Metric: "+ str(MetricVaule))
        # print(f"x values = {PhysicalVertex}")
        # Update best result so far
        if -MetricVaule < self.BestMetric:
            self.BestMetric =-MetricVaule
            self.bestPhysicalVetex= PhysicalVertex.copy()

        return -MetricVaule
    
       
    def UpdateVerticesForSLMAlignment(self,VertexArr):
        vertexIdx=0  
        for slmObjIdx in self.SLMAlignObjIdx:
            channel=self.slmObjs[slmObjIdx].ActiveRGBChannels[0]
            MaskCount=self.slmObjs[slmObjIdx].polProps[channel][self.polIdxArr[slmObjIdx]].MaskCount
            
            if (self.PropertiesToAlign[slmObjIdx]["AlignCenters"]):
                for imask in range(MaskCount):#Centers
                    VertexArr[vertexIdx] = round(VertexArr[vertexIdx])
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].center[0]=VertexArr[vertexIdx]
                    vertexIdx=vertexIdx+1
                    VertexArr[vertexIdx] = round(VertexArr[vertexIdx])
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].center[1]=VertexArr[vertexIdx]
                    vertexIdx=vertexIdx+1
                    
            if (self.PropertiesToAlign[slmObjIdx]["AlignPiston"]):        
                step=2*np.pi/256
                for imask in range(MaskCount):# Piston
                    
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.PISTON.value]=VertexArr[vertexIdx]
                    vertexIdx=vertexIdx+1
                    
            if (self.PropertiesToAlign[slmObjIdx]["AlignAstigX"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.ASTIGX.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
            if (self.PropertiesToAlign[slmObjIdx]["AlignAstigY"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.ASTIGY.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
            if (self.PropertiesToAlign[slmObjIdx]["AlignTrefoilX"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TREFOILX.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
            if (self.PropertiesToAlign[slmObjIdx]["AlignTrefoilY"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TREFOILY.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
            if (self.PropertiesToAlign[slmObjIdx]["AlignComaX"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.COMAX.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
            if (self.PropertiesToAlign[slmObjIdx]["AlignComaY"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.COMAY.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
            if (self.PropertiesToAlign[slmObjIdx]["AlignSpherical"]):
                for imask in range(MaskCount):
                    self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.SPHERICAL.value] = VertexArr[vertexIdx]
                    vertexIdx += 1
                    
            if (self.PropertiesToAlign[slmObjIdx]["AlignTiltX"] or self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltX"] or self.PropertiesToAlign[slmObjIdx]["AlignLastTiltX"] 
                or self.PropertiesToAlign[slmObjIdx]["AlignTiltY"] or self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltY"] or self.PropertiesToAlign[slmObjIdx]["AlignLastTiltY"] ):
                for imask in range(MaskCount):#Tilt
                    if(self.PropertiesToAlign[slmObjIdx]["AlignTiltX"]):
                        self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTX.value]=VertexArr[vertexIdx]
                        vertexIdx=vertexIdx+1
                    else:
                        if(self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltX"] and imask==0):
                            self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTX.value]=VertexArr[vertexIdx]
                            vertexIdx=vertexIdx+1
                       
                        if (self.PropertiesToAlign[slmObjIdx]["AlignLastTiltX"] and imask==MaskCount-1):
                            self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTX.value]=VertexArr[vertexIdx]
                            vertexIdx=vertexIdx+1
                            
                    if(self.PropertiesToAlign[slmObjIdx]["AlignTiltY"]):
                        self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTY.value]=VertexArr[vertexIdx]
                        vertexIdx=vertexIdx+1
                    else:
                        if(self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltY"] and imask==0):
                            self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTY.value]=VertexArr[vertexIdx]
                            vertexIdx=vertexIdx+1
        
                        if (self.PropertiesToAlign[slmObjIdx]["AlignLastTiltY"] and imask==MaskCount-1):
                            self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTY.value]=VertexArr[vertexIdx]
                            vertexIdx=vertexIdx+1
                            
            if (self.PropertiesToAlign[slmObjIdx]["AlignDefocus"]or self.PropertiesToAlign[slmObjIdx]["AlignDefocusFirst"]or self.PropertiesToAlign[slmObjIdx]["AlignDefocusLast"]):                
                for imask in range(MaskCount):#Defocus            
                    if(self.PropertiesToAlign[slmObjIdx]["AlignDefocus"]):
                        self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.DEFOCUS.value] =VertexArr[vertexIdx]
                        vertexIdx=vertexIdx+1
                    else:
                        if(self.PropertiesToAlign[slmObjIdx]["AlignDefocusFirst"] and imask==0):
                            self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.DEFOCUS.value] =VertexArr[vertexIdx]
                            vertexIdx=vertexIdx+1
                        
                        if (self.PropertiesToAlign[slmObjIdx]["AlignDefocusLast"] and imask==MaskCount-1):
                            self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.DEFOCUS.value] =VertexArr[vertexIdx]
                            vertexIdx=vertexIdx+1

            self.slmObjs[slmObjIdx].setmask(channel,self.slmObjs[slmObjIdx].currentModeIdx)
        return VertexArr
    
    
    def GetInitialVerticeForSLMAlignment(self):
        
        VertexArr=np.empty(0)
        stepSizeVertexArr=np.empty(0)
        
        for slmObjIdx in self.SLMAlignObjIdx:
            channel=self.slmObjs[slmObjIdx].ActiveRGBChannels[0]
            MaskCount=self.slmObjs[slmObjIdx].polProps[channel][self.polIdxArr[slmObjIdx]].MaskCount
            
            
            # this is just to be safe is the user thinks they can ask the alginment to do something it really cant/would be double values
            if (self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltX"] or self.PropertiesToAlign[slmObjIdx]["AlignLastTiltX"]):
                self.PropertiesToAlign[slmObjIdx]["AlignTiltX"]=False
            if (self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltY"] or self.PropertiesToAlign[slmObjIdx]["AlignLastTiltY"]):
                self.PropertiesToAlign[slmObjIdx]["AlignTiltY"]=False   
            if (self.PropertiesToAlign[slmObjIdx]["AlignDefocusFirst"] or self.PropertiesToAlign[slmObjIdx]["AlignDefocusLast"]):
                self.PropertiesToAlign[slmObjIdx]["AlignDefocus"]=False   
                
            if (self.PropertiesToAlign[slmObjIdx]["AlignCenters"]):    
                for imask in range(MaskCount):#Centers
                    VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].center[0])
                    stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_Centers"])
                    VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].center[1])
                    stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_Centers"])
                    
            if (self.PropertiesToAlign[slmObjIdx]["AlignPiston"]):        
                for imask in range(MaskCount):# Piston
                    VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.PISTON.value])
                    stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_Piston"])
            if (self.PropertiesToAlign[slmObjIdx]["AlignAstigX"]):        
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.ASTIGX.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_AstigX"])
            if (self.PropertiesToAlign[slmObjIdx]["AlignAstigY"]):        
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.ASTIGY.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_AstigY"])
            if (self.PropertiesToAlign[slmObjIdx]["AlignTrefoilX"]):
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TREFOILX.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_TrefoilX"])
            if (self.PropertiesToAlign[slmObjIdx]["AlignTrefoilY"]):
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TREFOILY.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_TrefoilY"])
            if (self.PropertiesToAlign[slmObjIdx]["AlignComaX"]):
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.COMAX.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_ComaX"])
            if (self.PropertiesToAlign[slmObjIdx]["AlignComaY"]):
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.COMAY.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_ComaY"])
            
            if (self.PropertiesToAlign[slmObjIdx]["AlignSpherical"]):
                for imask in range(MaskCount):
                    VertexArr = np.append(VertexArr, self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.SPHERICAL.value])
                    stepSizeVertexArr = np.append(stepSizeVertexArr, self.InitialStepSizes[slmObjIdx]["d_Spherical"])
                    
            if (self.PropertiesToAlign[slmObjIdx]["AlignTiltX"] or self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltX"] or self.PropertiesToAlign[slmObjIdx]["AlignLastTiltX"] 
                or self.PropertiesToAlign[slmObjIdx]["AlignTiltY"] or self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltY"] or self.PropertiesToAlign[slmObjIdx]["AlignLastTiltY"] ):        
                for imask in range(MaskCount):#Tilt
                    if(self.PropertiesToAlign[slmObjIdx]["AlignTiltX"]):
                        VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTX.value])
                        stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_TiltX"])
                    else:
                        if(self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltX"] and imask==0):
                            VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTX.value])
                            stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_TiltX"])
                            
                        if (self.PropertiesToAlign[slmObjIdx]["AlignLastTiltX"] and imask==MaskCount-1):
                            VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTX.value])
                            stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_TiltX"])
                    
                    if(self.PropertiesToAlign[slmObjIdx]["AlignTiltY"]):
                        VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTY.value])
                        stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_TiltY"])
                        
                    else:
                        if(self.PropertiesToAlign[slmObjIdx]["AlignFirstTiltY"] and imask==0):
                            VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTY.value])
                            stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_TiltY"])
                            
        
                        if (self.PropertiesToAlign[slmObjIdx]["AlignLastTiltY"] and imask==MaskCount-1):
                            VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.TILTY.value])
                            stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_TiltY"])
                                
                                
            if (self.PropertiesToAlign[slmObjIdx]["AlignDefocus"]or self.PropertiesToAlign[slmObjIdx]["AlignDefocusFirst"]or self.PropertiesToAlign[slmObjIdx]["AlignDefocusLast"]):                    
                for imask in range(MaskCount):#Defocus            
                    if(self.PropertiesToAlign[slmObjIdx]["AlignDefocus"]):
                        VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.DEFOCUS.value])
                        stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_Defocus"])
                        
                    else:
                        if(self.PropertiesToAlign[slmObjIdx]["AlignDefocusFirst"] and imask==0):
                            VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.DEFOCUS.value])
                            stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_Defocus"])
                            
                        
                        if (self.PropertiesToAlign[slmObjIdx]["AlignDefocusLast"] and imask==MaskCount-1):
                            VertexArr=np.append(VertexArr,self.slmObjs[slmObjIdx].AllMaskProperties[channel][self.polIdxArr[slmObjIdx]][imask].zernike.zern_coefs[zernMod.ZernCoefs.DEFOCUS.value])
                            stepSizeVertexArr=np.append(stepSizeVertexArr,self.InitialStepSizes[slmObjIdx]["d_Defocus"])
                                

                            
        self.TotalDims=VertexArr.shape
            
        return stepSizeVertexArr,VertexArr
    
    def GetAvgRelativePowerOfSpot(self,OpticalSwitchObj:OpticalSwitchLib.JDSSCSwitch,spotCount=6):
        # spotPwrall_avg=0

        # spotPwrall=0
        # for ispot in range(spotCount):
        #     OpticalSwitchObj.set_channel(ispot+1) # switch channel is 1 indexed
        #     spotPwrall=spotPwrall+self.PwrObjs[0].GetPower() # very bad that i hard codeded the 0 index
        #     if ispot==self.icenter:
        #         spotPwr=self.PwrObjs[0].GetPower()

        # spotPwrall_avg=(spotPwr/spotPwrall)
        # print("Power of spot "+str(ispot)+" : "+str(spotPwr))
            
        # MetricVaule=spotPwrall_avg
        
        OpticalSwitchObj.set_channel(self.icenter+1) # switch channel is 1 indexed
        MetricVaule=self.PwrObjs[0].GetPower()
        # print("Power of spot "+str(self.icenter)+" : "+str(MetricVaule))
        return MetricVaule
    def ApplySuperPixelTakePower(self,OpticalSwitchObj:OpticalSwitchLib.JDSSCSwitch,MaskOfSuoerPixels,ix_SupPixel,iy_SupPixel , superpixel_size=1, phaseValue=np.pi/2,spotCount=1):  
            
            # Nx=self.slm.masksize[0]
            # Ny=self.slm.masksize[1]
            # MaskSize=self.slmObjs[self.ObjIdx].polProps[self.channel][self.pol].masksize
            y_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[0])
            x_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[1])
            
            # Nx=MaskSize[0]
            # Ny=MaskSize[1]
        
            # need to put a blank mask with zernikes that are currelty on the masks. this is a little bit tedious but it works. I might but this as function in SLM module 
            # as maybe this is all people want to do
            # MASK=np.ones((Nx,Ny),dtype=complex)
            MASK=set_superpixel(MaskOfSuoerPixels, ix_SupPixel,iy_SupPixel , superpixel_size=superpixel_size, phase_value=phaseValue)

            #apply superPixel

            if (self.ApplyZernike):
                MASK_PlussZernike=self.slmObjs[self.ObjIdx].ApplyZernikesToSingleMask(self.channel,(MASK),imask=self.imask,pol=self.pol,imode=0)
            
            MASK_PlussZernike=(MASK)
            MASKTODisplay_cmplx=self.slmObjs[self.ObjIdx].Draw_Single_Mask( x_center_Input,y_center_Input, MASK_PlussZernike)
            
            self.slmObjs[self.ObjIdx].FullScreenBuffer_int=self.slmObjs[self.ObjIdx].convert_phase_to_uint8(MASKTODisplay_cmplx) # Note if nothing is passed it will use the self.FullScreenBuffer_cmplx array as the array it is going to convert      
            self.slmObjs[self.ObjIdx].Write_To_Display(self.slmObjs[self.ObjIdx].FullScreenBuffer_int,self.channel)
            
            pwrOfSpot=self.GetAvgRelativePowerOfSpot(OpticalSwitchObj,spotCount)
            # pwrOfSpot=self.GetAvgPowerOfSpot(avgFrameCount=15)

            
            return pwrOfSpot

    
    def RunSuperPixelSweep(self,OpticalSwitchObj:OpticalSwitchLib.JDSSCSwitch,ObjIdx=0,pol="H",channel=None,StartingMask=None,NumberOfSuperPixels=None,superpixel_size=None,phaseorCount=4,ispot=0,spotCount=1, ApplyZernike=False,NumberOfPasses=1):
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        self.channel=channel
        self.pol=pol
        self.ObjIdx=ObjIdx
        self.icenter=ispot
        self.ApplyZernike=ApplyZernike
        self.imask=0
        self.CamObjIdx=ObjIdx

        # self.CamObjs[ObjIdx].SetSingleFrameCapMode()


        MaskSize=self.slmObjs[ObjIdx].polProps[self.channel][self.pol].masksize
        Nx=MaskSize[1]
        Ny=MaskSize[0]
        print(MaskSize)
        
        if StartingMask is None:
            MaskSize=self.slmObjs[ObjIdx].polProps[self.channel][self.pol].masksize
            Nx=MaskSize[1]
            Ny=MaskSize[0]
            print(MaskSize)
            Mask=np.ones((Ny,Nx),dtype=complex)
        else:
            MaskSize=StartingMask.shape
            Nx=MaskSize[1]
            Ny=MaskSize[0]
            print(MaskSize)
            Mask=np.copy(StartingMask)
        #should probably have a check hear for non sqare superpixel will fix later
        if superpixel_size is None:
            print("You have not entered a super pixel size the first factor of the mask size has been seleted other factors are:")
            # minFactor=None
            facotorVal=Ny
            minFactor=facotorVal
            PossibleSuperPixels=[]
            while minFactor>1:
                Factors=FindFactors(facotorVal)
                PossibleSuperPixels.append(Factors[1])
                minFactor=Factors[1]
                facotorVal=Factors[1]
                
            PossibleSuperPixels=np.asarray(PossibleSuperPixels)   
            # PossibleSuperPixels=FindFactors(Ny)
            NumOfPossibleSuperPixels = np.size(PossibleSuperPixels)
            print(PossibleSuperPixels[0:NumOfPossibleSuperPixels])
            superpixel_size=PossibleSuperPixels[0]
        else:
            PossibleSuperPixels=np.zeros(NumberOfSuperPixels+1,dtype=int)
            PossibleSuperPixels[0]=superpixel_size

        # if NumberOfSuperPixels ==1 :
        #     NumberOfSuperPixels=1

        for iSuperPixel in range(0,NumberOfSuperPixels+1):
            if NumberOfSuperPixels is not None:
                superpixel_size = PossibleSuperPixels[iSuperPixel]

            xShiftCount=int(np.round(Nx/superpixel_size))
            yShiftCount=int(np.round(Ny/superpixel_size))
            print("Estimated time= "+str(xShiftCount*xShiftCount*4*self.slmObjs[ObjIdx].GLobProps[self.channel].RefreshTime)+"min")
            print("Estimated time= "+str((xShiftCount*xShiftCount*4*self.slmObjs[ObjIdx].GLobProps[self.channel].RefreshTime)/60)+"min")
            kIdx_arr=np.arange(phaseorCount)
            phaseor_arr=(2*np.pi/phaseorCount)*(kIdx_arr)
            # print(phaseor_arr)
            # phaseor_arr=np.asarray([0,np.pi/2,np.pi,3*np.pi/2])
            for icount in range(NumberOfPasses):
                print("Pass number: "+str(icount+1)+ " out of "+str(NumberOfPasses)+" for superpixel size: "+str(superpixel_size))
                shuffledXSuperpixelsIdx=np.arange(xShiftCount)
                random.shuffle(shuffledXSuperpixelsIdx)
                
                shuffledYSuperpixelsIdx=np.arange(xShiftCount)
                random.shuffle(shuffledYSuperpixelsIdx)
                
                phaseor_pwr=np.zeros(phaseorCount)# This is the power of 0,pi/2,pi and 3pi/2 power values 
                for (ix_SupPixel) in shuffledXSuperpixelsIdx: #range(xShiftCount):
                    for (iy_SupPixel) in shuffledYSuperpixelsIdx: #range(yShiftCount):
                        Z=0
                        for iphaseor in range(phaseorCount):
                            phaseor_pwr_kIdx=self.ApplySuperPixelTakePower(OpticalSwitchObj,Mask,ix_SupPixel,iy_SupPixel ,
                                                                                superpixel_size=superpixel_size, phaseValue=-phaseor_arr[iphaseor],spotCount=spotCount)
                            phaseor_pwr[iphaseor]=phaseor_pwr_kIdx
                            phaseor_pwr_kIdx=phaseor_pwr_kIdx*np.exp(-1j*phaseor_arr[iphaseor])
                            Z=Z+phaseor_pwr_kIdx
                        # phaseOpt=np.angle((phaseor_pwr[0]-phaseor_pwr[2])+1j*((phaseor_pwr[1]-phaseor_pwr[3])))
                        # print(np.std(phaseor_pwr))
                        DoPWRCapping=False
                        if (np.std(phaseor_pwr)<9e-9 and DoPWRCapping):
                            phaseOpt=0
                            additive=False
                        else:
                            phaseOpt=np.angle((2/phaseorCount)*Z)
                            additive=True
                            
                        
                        # Set the superpixel to the optimal phase level based on phaseor anaylsis 
                        Mask=set_superpixel(Mask, ix_SupPixel,iy_SupPixel , superpixel_size=superpixel_size, phase_value=phaseOpt,additive=additive)
                        
                        powerOpt=self.GetAvgRelativePowerOfSpot(OpticalSwitchObj,spotCount)

                print(str(icount)+ " phaseor_pwr: "+str(phaseor_pwr)+"\t powerOpt: "+str(powerOpt))
        
        # self.CamObjs[self.CamObjIdx].SetContinousFrameCapMode()

        return Mask