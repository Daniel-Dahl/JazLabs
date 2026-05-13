from Lab_Equipment.Config import config

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

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
from scipy.signal import find_peaks
from scipy.optimize import minimize

# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]

#SLM Libs
import Lab_Equipment.SLM.pyLCOS as pyLCOS
import Lab_Equipment.ZernikeModule.ZernikeModule as zernMod

#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm

# digiHolo Libs
import Lab_Equipment.digHolo.digHolo_pylibs.digholoObject as digholoMod
import Lab_Equipment.digHolo.digHolo_pylibs.digiholoWindowThread as digholoWindowThread


import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignFunc

import  Lab_Equipment.GeneralLibs.ComplexPlotFunction as cmplxplt
from typing import List
class AlginmentObj_digiholo():
    def __init__(self,
                slmObjs: List[pyLCOS.LCOS],
                CamObjs: List[CamForm.GeneralCameraObject],
                digiholoObjs: List[digholoMod.digholoObject]):
        super().__init__()
        
        # Store lists of devices
        self.slmObjs = slmObjs
        self.CamObjs = CamObjs
        self.digiholoObjs = digiholoObjs
        # Ensure equal lengths
        assert len(slmObjs) == len(CamObjs) == len(digiholoObjs), \
            "slmObjects, camObjs, and digiholoObjs must have the same length"
        self.ObjCount = len(slmObjs)
        print(self.ObjCount)
        # Default to first channel
        # Initial properties
        for iObj in range(self.ObjCount):
            self.digiholoObjs[iObj].digholoProperties["FFTRadius"] = 0.2
            
        # self.channel = Channel
        # self.pol = pol
        # self.ApplyZernike = ApplyZernike
        self.imask = 0
        self.PixelsCountFromCenters = 50
        self.AvgFrameCount = 30
        self.PlotTracking = True
        self.MaskSize = [256,256]
        # Build reference field
        # self.MakeReferenceField()

        
        
    def __del__(self):
        print("Cleaning up AlginmentObj_digiholo")
        # self.CamObjs[].SetContinousFrameCapMode()
    def MakeReferenceField(self,ObjIdx=0,channel=None,pol="H",ApplyZernike=False,MaskSize=None,digholoProperties=None):
             
        if digholoProperties is not None:
            self.digiholoObjs[ObjIdx].digholoProperties.update(digholoProperties)
            self.digiholoObjs[ObjIdx].digholo_SetProps()
            
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]

        self.channel=channel    
        if MaskSize is  None:
            MaskSize=self.slmObjs[ObjIdx].polProps[channel][pol].masksize
        # need to put a blank mask with zernikes that are currelty on the masks. this is a little bit tedious but it works. I might but this as function in SLM module 
        # as maybe this is all people want to do
        MASK=np.zeros(self.MaskSize,dtype=complex)
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        for imask in range(MaskCount):
            if (ApplyZernike):
                MASK_PlusZernike=self.slmObjs[ObjIdx].ApplyZernikesToSingleMask(channel,np.angle(MASK),imask=imask,pol=pol,imode=0)
            else:
                # MASK_PlusZernike=np.angle(MASK)
                MASK_PlusZernike=(MASK)

            x_center_Input=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[1])
            y_center_Input=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[0])    
            MASKTODisplay_cmplx=self.slmObjs[ObjIdx].Draw_Single_Mask( x_center_Input,y_center_Input, MASK_PlusZernike)
            self.slmObjs[ObjIdx].FullScreenBuffer_int=self.slmObjs[ObjIdx].convert_phase_to_uint8(MASKTODisplay_cmplx) # Note if nothing is passed it will use the self.FullScreenBuffer_cmplx array as the array it is going to convert      
            self.slmObjs[ObjIdx].Write_To_Display(self.slmObjs[ObjIdx].FullScreenBuffer_int,channel)
       
        
        
        self.digiholoObjs[ObjIdx].digholoProperties["maxMG"]=1
        self.digiholoObjs[ObjIdx].digholoProperties["batchCount"]=1
        self.digiholoObjs[ObjIdx].digholo_SetProps()
        Frame = self.CamObjs[ObjIdx].GetFrame(ConvertToFloat32=True)
        plt.figure(100)
        plt.imshow(Frame)
        self.digiholoObjs[ObjIdx].digHolo_AutoAlign(Frame)
        
        #This is the reference Field that the other fields will be overlaped with
        self.Field_Ref=np.squeeze(self.digiholoObjs[ObjIdx].digHolo_GetFields())# this might come out as a 1 by 1 vector not sure
        self.RefPWR=np.abs(self.digiholoObjs[ObjIdx].OverlapFields(self.Field_Ref,self.Field_Ref))**2 

        Fullimage ,_,_=self.digiholoObjs[ObjIdx].GetViewport_arr(Frame)
        plt.figure()
        plt.imshow(Fullimage)
        plt.show()
        print("If you are doing a center alignment and the image didnt come out like a Gaussian looking spot "\
              "you should adjust the digholo parameters and re-run MakeReferenceField()")
                
    def PerformCenterAlignment_GoldenSearch(self,ObjIdx=0,channel=None,pol="H",
                                            ApplyZernike=False,MaskSize=None,
                                            PixelsCountFromCenters=50,
                                            AvgFrameCount=30,
                                            MakeRefField=False,
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

        if MakeRefField:
            self.MakeReferenceField(ObjIdx=ObjIdx,channel=channel,pol=pol,ApplyZernike=ApplyZernike,MaskSize=MaskSize)
         
        # Need to set up self variables for the the function to be passed to the golden search function
        self.channel=channel
        self.pol=pol
        self.ObjIdx=ObjIdx
        self.ApplyZernike=ApplyZernike
        self.PixelsCountFromCenters = PixelsCountFromCenters
        self.AvgFrameCount = AvgFrameCount
        self.PlotTracking = PlotTracking
            
        self.CamObjs[ObjIdx].SetSingleFrameCapMode()
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        
        MinXCenter=np.zeros(MaskCount)
        MinYCenter=np.zeros(MaskCount)
        ifig=0
        for imask in range(MaskCount): 
            
            self.imask=imask
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
                    minVal_1,minIdx_1=AlignFunc.GoldenSelectionSearch(self.BoundMin,self.BoundMax,dspace_Tol=1,FuncToMinamise=self.ChangePiFlipTakeField)
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
        self.CamObjs[ObjIdx].SetContinousFrameCapMode()

        
        return (MinXCenter),(MinYCenter)
    
  # Need to update this function
    def ChangePiFlipTakeField(self,xVal):
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
        
        #Going to go through and grab a few frames to get a average overlap with the ref Field to make it a but more acutrate 
        overlap_avgPWR=0
        for iframe in range(self.AvgFrameCount):
            Frame = self.CamObjs[self.ObjIdx].GetFrame(ConvertToFloat32=True)
            self.digiholoObjs[self.ObjIdx].digHolo_ProcessBatch(Frame,CalculateMetrics=False)
            Field_Sig=np.squeeze(self.digiholoObjs[self.ObjIdx].digHolo_GetFields())
            overlap=self.digiholoObjs[self.ObjIdx].OverlapFields(Field_Sig,self.Field_Ref) 

            overlap_avgPWR=overlap_avgPWR+(np.abs(overlap)**2)

        RefSigPWR=np.sqrt(overlap_avgPWR/self.AvgFrameCount)
        RefSigPWR = np.sqrt(RefSigPWR)# not sure why I sqrt twice might be wrong will come back and check
        RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
        
        self.xValTrack=np.append(self.xValTrack,xVal)
        self.yValTrack=np.append(self.yValTrack,RefSigPWR_log)
        
        return xVal,RefSigPWR_log

    def CourseSweepAcrossSLM(self,ObjIdx=0,channel=None,pol="H",
                             MaskSize=None,flipCount=30,AvgFrameCount=30,
                             MakeRefField=True,
                             BackgroundPhase=-np.pi):

        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        if MaskSize is  None:
            MaskSize=self.slmObjs[ObjIdx].polProps[channel][pol].masksize

        OriginialBackground_int=np.copy(self.slmObjs[ObjIdx].backgroundPattern_int)
        background=np.ones((self.slmObjs[ObjIdx].LCOSsize))*np.exp(1j*BackgroundPhase)
        self.slmObjs[ObjIdx].SetBackGroundPattern(channel=channel,backgroundPattern=background)

        if MakeRefField:
            self.MakeReferenceField(ObjIdx=ObjIdx,channel=channel,pol=pol,ApplyZernike=False,MaskSize=MaskSize)

        self.slmObjs[ObjIdx].LCOS_Clean(channel)
        # flipMin=//2-flipCount//2
        self.AvgFrameCount=AvgFrameCount
        flipMin=0
        # flipMax=self.slmObjs[ObjIdx].slmHeigth//2+flipCount//2
        # flipMax=self.slmObjs[ObjIdx].slmWidth//2+flipCount//2
        
        totalSweepCountX=len(range(0,self.slmObjs[ObjIdx].slmWidth,flipCount))
        self.CourseTrackX_X=np.zeros(totalSweepCountX)
        self.CourseTrackX_Y=np.zeros(totalSweepCountX)

        totalSweepCountY=len(range(0,self.slmObjs[ObjIdx].slmHeigth//2,flipCount))
        self.CourseTrackY_X=np.zeros(totalSweepCountY)
        self.CourseTrackY_Y=np.zeros(totalSweepCountY)

        self.CourseXCenter=np.zeros(self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount)
        self.CourseYCenter=np.zeros(self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount)
        backgroundPhase=0
        PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(1j*backgroundPhase)
        #Left to right sweep
        idx=0
        for iflip in range(0,self.slmObjs[ObjIdx].slmWidth,flipCount):
            PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(1j*backgroundPhase)
            if pol=="H":
                PiFlip_cmplx[0:self.slmObjs[ObjIdx].slmHeigth//2,0:flipMin+iflip]=PiFlip_cmplx[0:self.slmObjs[ObjIdx].slmHeigth//2,0:flipMin+iflip]*np.exp(-1j*np.pi)
            else:
                PiFlip_cmplx[self.slmObjs[ObjIdx].slmHeigth//2::,0:flipMin+iflip]=PiFlip_cmplx[self.slmObjs[ObjIdx].slmHeigth//2::,0:flipMin+iflip]*np.exp(-1j*np.pi)
            

            self.slmObjs[ObjIdx].FullScreenBuffer_int=self.slmObjs[ObjIdx].convert_phase_to_uint8(PiFlip_cmplx)
            self.slmObjs[ObjIdx].Write_To_Display(self.slmObjs[ObjIdx].FullScreenBuffer_int,channel)

            #Going to go through and grab a few frames to get a average overlap with the ref Field to make it a but more acutrate 
            overlap_avgPWR=0
            for iframe in range(self.AvgFrameCount):
                Frame = self.CamObjs[ObjIdx].GetFrame(ConvertToFloat32=True)
                self.digiholoObjs[ObjIdx].digHolo_ProcessBatch(Frame,CalculateMetrics=False)
                Field_Sig=np.squeeze(self.digiholoObjs[ObjIdx].digHolo_GetFields())
                overlap=self.digiholoObjs[ObjIdx].OverlapFields(Field_Sig,self.Field_Ref) 

                overlap_avgPWR=overlap_avgPWR+(np.abs(overlap)**2)

            RefSigPWR=np.sqrt(overlap_avgPWR/self.AvgFrameCount)
            RefSigPWR = np.sqrt(RefSigPWR)# not sure why I sqrt twice might be wrong will come back and check
            RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
            self.CourseTrackX_X[idx]=iflip
            self.CourseTrackX_Y[idx]=RefSigPWR_log
            idx=idx+1

        # Find peaks in the inverted signal (which are dips in the original)
        inverted_y = - self.CourseTrackX_Y
        dip_indices, _ = find_peaks(inverted_y,prominence=[0.1])
        CourseCentersX=self.CourseTrackX_X[dip_indices]
        if(len(CourseCentersX)==self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount):
            for imask in range(self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount): 
                self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[1] = CourseCentersX[imask]
                self.CourseYCenter[imask]=CourseCentersX[imask]
        else:
            print("Incorrect number of centers where found should be the same as total masks.")
            plt.figure()
            plt.plot(self.CourseTrackX_X, inverted_y, label='Original signal')
            plt.plot(self.CourseTrackX_X[dip_indices], inverted_y[dip_indices], 'ro', label='Dips')
            plt.show()
            return self.CourseTrackX_X,self.CourseTrackX_Y


        
            
        # top to bottom sweep  
        for imask in range(self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount): 

            MaxSweepRegion= int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[1] +self.MaskSize[1]//2)
            MinSweepRegion = int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[1]-self.MaskSize[1]//2)
            if MinSweepRegion<0:
                MinSweepRegion=0
            if MaxSweepRegion>self.slmObjs[ObjIdx].slmWidth-1:
                MaxSweepRegion=self.slmObjs[ObjIdx].slmWidth-1

            if pol=="H":  
                flipMin=0
            else:
                flipMin=self.slmObjs[ObjIdx].slmHeigth//2
            idx=0
            for iflip in range(flipMin,self.slmObjs[ObjIdx].slmHeigth//2+flipMin-1,flipCount):
                PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(1j*backgroundPhase)
                
                PiFlip_cmplx[flipMin:iflip,MinSweepRegion:MaxSweepRegion]=PiFlip_cmplx[flipMin:iflip,MinSweepRegion:MaxSweepRegion]*np.exp(-1j*np.pi)
                self.slmObjs[ObjIdx].FullScreenBuffer_int=self.slmObjs[ObjIdx].convert_phase_to_uint8(PiFlip_cmplx)
                self.slmObjs[ObjIdx].Write_To_Display(self.slmObjs[ObjIdx].FullScreenBuffer_int,channel)
                    #Going to go through and grab a few frames to get a average overlap with the ref Field to make it a but more acutrate 
                overlap_avgPWR=0
                for iframe in range(self.AvgFrameCount):
                    Frame = self.CamObjs[ObjIdx].GetFrame(ConvertToFloat32=True)
                    self.digiholoObjs[ObjIdx].digHolo_ProcessBatch(Frame,CalculateMetrics=False)
                    Field_Sig=np.squeeze(self.digiholoObjs[ObjIdx].digHolo_GetFields())
                    overlap=self.digiholoObjs[ObjIdx].OverlapFields(Field_Sig,self.Field_Ref) 

                    overlap_avgPWR=overlap_avgPWR+(np.abs(overlap)**2)

                RefSigPWR=np.sqrt(overlap_avgPWR/self.AvgFrameCount)
                RefSigPWR = np.sqrt(RefSigPWR)# not sure why I sqrt twice might be wrong will come back and check
                RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
                self.CourseTrackY_X[idx]=iflip
                self.CourseTrackY_Y[idx]=RefSigPWR_log
                idx=idx+1

            inverted_y = - self.CourseTrackY_Y
            dip_indices, _ = find_peaks(inverted_y,distance=self.slmObjs[ObjIdx].slmHeigth//2)
            CourseCentersY=self.CourseTrackY_X[dip_indices]
            if(len(CourseCentersY)==1):
                self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[0] = CourseCentersY[0]
                self.CourseYCenter[imask]=CourseCentersY[0]

            else:
                print("Incorrect number of centers where found should be the same as total masks.")
                plt.figure()
                plt.plot(self.CourseTrackY_X, inverted_y, label='Original signal')
                plt.plot(self.CourseTrackY_X[dip_indices], inverted_y[dip_indices], 'ro', label='Dips')
                plt.show()
                return self.CourseTrackY_X,self.CourseTrackY_Y
        #Switch back to the orginial backgroud
        self.slmObjs[ObjIdx].backgroundPattern_int =np.copy(OriginialBackground_int)
        self.slmObjs[ObjIdx].LCOS_Clean(channel)
        return self.CourseXCenter,self.CourseYCenter
    
    def SweepAcrossSLM_Field(self,ObjIdx=0,channel=None,pol="H",stepCount=10,PixelsFromCenter=50):
         # need to set the camera to singleFrameCapturemode
        # CamObj.Exposure
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        
        self.slmObjs[ObjIdx].LCOS_Clean(channel)
        self.CamObjs[ObjIdx].SetSingleFrameCapMode()
        self.digiholoObjs[ObjIdx].digholoProperties["maxMG"]=1
        self.digiholoObjs[ObjIdx].digholoProperties["batchCount"]=1
        self.digiholoObjs[ObjIdx].digholo_SetProps()
        Frame = self.CamObjs[ObjIdx].GetFrame(ConvertToFloat32=True)
        self.digiholoObjs[ObjIdx].digHolo_AutoAlign(Frame)
        
        #This is the reference Field that the other fields will be overlaped with
        self.Field_Ref=np.squeeze(self.digiholoObjs[ObjIdx].digHolo_GetFields())# this might come out as a 1 by 1 vector not sure
        self.RefPWR=np.abs(self.digiholoObjs[ObjIdx].OverlapFields(self.Field_Ref,self.Field_Ref))**2 
        plt.figure()
        plt.imshow(cmplxplt.ComplexArrayToRgb(np.squeeze(self.Field_Ref)))
        plt.show()
        print("You should abort this measurment if the image displayed was not a Gaussian")
        print("perform another AutoAlign on a single frame of with the digholo object you passed into object then re-run sweep ")
        RefSigPWR=np.zeros((2,stepCount,MaskCount))
        PixelFlipStep=np.zeros((2,stepCount,MaskCount))
        
        # I may have to move this to inside the imask loop to reset the pi flip location
        PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(0.0*1j*np.pi)
        
        for imask in range(MaskCount):
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
                    
                   
                    overlap_avgPWR=0
                    for iframe in range(self.AvgFrameCount):
                        Frame = self.CamObjs[ObjIdx].GetFrame(ConvertToFloat32=True)
                        self.digiholoObjs[ObjIdx].digHolo_ProcessBatch(Frame,CalculateMetrics=False)
                        Field_Sig=np.squeeze(self.digiholoObjs[ObjIdx].digHolo_GetFields())
                        overlap=self.digiholoObjs[ObjIdx].OverlapFields(Field_Sig,self.Field_Ref) 
                        overlap_avgPWR=overlap_avgPWR+(np.abs(overlap)**2)
                        
                    RefSigPWR[iDirection,iflipIdx,imask]=np.sqrt(overlap_avgPWR/self.AvgFrameCount)# work out the average overlap and put it in the RefSigPWR_X array
                    PixelFlipStep[iDirection,iflipIdx,imask]=iflip
                    iflipIdx=iflipIdx+1
                    
            
        RefSigPWR = np.sqrt(RefSigPWR)# not sure why I sqrt twice might be wrong will come back and check
        RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
        
        self.slmObjs[ObjIdx].LCOS_Clean(channel) 
        self.CamObjs[ObjIdx].SetContinousFrameCapMode()
        
        return RefSigPWR,RefSigPWR_log,PixelFlipStep
    ######################
    # NOTE
    ######################
    # this should be added to the end of the above funciton it should plot the stuff out from the sweep  
    # import  Lab_Equipment.MyPythonLibs.FWHMFunctions as FWHMFun
 
    #     minXval=np.argmin(RefSigPWR_log_X)
    # NewXcenter=PixelFlipX[iminXval]
    # iminYval=np.argmin(RefSigPWR_log_Y)
    # NewYcenter=PixelFlipY[iminYval]
    # minusRefSigPWR_X=-RefSigPWR_X-np.min(-RefSigPWR_X)
    # # minusRefSigPWR_X=-RefSigPWR_Y-np.min(-RefSigPWR_Y)

    # # a,b,c=FWHMFun.OneOn_e_Squred_1d(minusRefSigPWR_X)
    # a,b,c=FWHMFun.fwhm_1d(minusRefSigPWR_X)
    # print(c/np.sqrt(np.log(2)))
    # print(a,b,c)
    # plt.subplot(2,2,1)
    # # plt.plot(RefSigPWR_X)
    # plt.plot((minusRefSigPWR_X))
    # plt.scatter(a,minusRefSigPWR_X[a])
    # plt.scatter(b,minusRefSigPWR_X[b])


    # plt.subplot(2,2,2)
    # plt.plot(RefSigPWR_Y)
    # plt.subplot(2,2,3)
    # plt.plot(RefSigPWR_log_X)
    # plt.subplot(2,2,4)
    # plt.plot(RefSigPWR_log_Y)



# print(NewXcenter,NewYcenter)
    def GetBatchOfFrames(self,CamObjIdx=0,SLMObjIdx=0,pol='H',channel=None,modeIdxArr=None):
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[SLMObjIdx].ActiveRGBChannels[0]
            
        modeCount=self.slmObjs[SLMObjIdx].polProps[channel][pol].modeCount
        modeCount_step=self.slmObjs[SLMObjIdx].polProps[channel][pol].modeCount_step
        modeCount_start=self.slmObjs[SLMObjIdx].polProps[channel][pol].modeCount_start
        
         # Run a intial batch/AutoAlign of the digholo so see if the systems is starting in a good spot
        if modeIdxArr is not None:
            batchcount=int(len(modeIdxArr))
        else:
            batchcount=int(np.ceil((modeCount-modeCount_start)/modeCount_step))

        Frames=np.empty((batchcount,self.CamObjs[CamObjIdx].FrameHeight,self.CamObjs[CamObjIdx].FrameWidth),dtype=np.float32)
        
        iframe=0
        if modeIdxArr is not None:
            for imode in modeIdxArr:
                self.slmObjs[SLMObjIdx].setmask(channel,imode)
                Frames[iframe,:,:]=self.CamObjs[CamObjIdx].GetFrame(ConvertToFloat32=True)
                iframe+=1
        else:
            for imode in range(modeCount_start,modeCount,modeCount_step):
                self.slmObjs[SLMObjIdx].setmask(channel,imode)
                Frames[iframe,:,:]=self.CamObjs[CamObjIdx].GetFrame(ConvertToFloat32=True)
                iframe+=1
        return Frames

    def MultiDimAlignmentOfSLM(self,CamObjIdx=0,SLMModeGenIdx=0,SLMAlignObjIdx=[0],pol=["H"],polGenIdx=0,
                               AutoAlignBatch=True,modeIdxArr=None,
                               digiholoObjThread:digholoWindowThread.digholoWindow=None,
                               Optimiser='CMA-ES',
                               GoalMetric=digholoMod.digholoMetrics.IL,
                               PropertiesToAlign=None,
                               InitialStepSizes=None,
                               ErrTol=1e-3,
                               maxAttempts=100,
                               populationSize=None,
                               simga0=0.2, ):
        # if channel is None:#if no channel is passed in then use the first active channel on the SLM
        #     channel=self.slmObjs[SLMObjIdx].ActiveRGBChannels[0]
         # Need to set up self variables for the the function to be passed to the golden search function
        # self.channel=channel
        # self.pol=pol
        self.modeIdxArr=modeIdxArr
        self.CamObjs[CamObjIdx].SetSingleFrameCapMode()
        if not isinstance(SLMAlignObjIdx, list):
                raise TypeError(f"Expected a list, got {type(SLMAlignObjIdx).__name__!r}")
                return
        self.SLMAlignObjIdx=SLMAlignObjIdx
        self.SLMModeGenIdx=SLMModeGenIdx
        self.CamObjIdx=CamObjIdx
        self.polIdxArr=pol
        self.polGenIdx=polGenIdx
        
        if digiholoObjThread is not None:
            self.digiholoObjThread=digiholoObjThread
            self.UsingDigholoThreadObject=True
        else:
            self.UsingDigholoThreadObject=False
            print("Using the digholo object passed into the this class when initialsied")
        self.GoalMetric=GoalMetric
        self.AutoAlignBatch=AutoAlignBatch
        # Run a intial batch/AutoAlign of the digholo so see if the systems is starting in a good spot
        # Frames=self.GetBatchOfFrames(CamObjIdx=CamObjIdx,SLMObjIdx=SLMModeGenIdx)
            
        # if (self.UsingDigholoThreadObject): 
        #     _=self.digiholoObjThread.digholoWindowAutoAlgin(Frames)
        # else:
        #     _,_=self.digiholoObjs[CamObjIdx].digHolo_AutoAlign(Frames)
        #     CoefsImage,MetricsText=self.digiholoObjs[CamObjIdx].GetCoefAndMetricsForOutput()
            # canvasToDispla_Coefs=self.digiholoObj.DisplayWindow_GraphWithText(CoefsImage,MetricsText)
            # plt.figure()
            # plt.imshow(canvasToDispla_Coefs)
            # plt.show()
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
                        self.UpdateVertex_TakeDigholoBatch,
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
                        self.UpdateVertex_TakeDigholoBatch,
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
                print(f"Best-so-far: {self.BestMetric:.6f} at x = {self.bestPhysicalVetex}")
            else:
                print("\nOptimisation completed.")
                print(f"Result: {result.fun:.6f} at x = {result.x}")
                print(f"Best-so-far: {self.BestMetric:.6f} at x = {self.bestPhysicalVetex}")

        else:
            try:
                if populationSize is None:
                    populationSize = 4 + (3 * np.log10(InitalNorm.size))
                lower_bounds = np.array([-1.0] * len(InitalNorm))
                upper_bounds = np.array([1.0] * len(InitalNorm))
                result = cma.fmin(
                    objective_function=self.UpdateVertex_TakeDigholoBatch,
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
                print(f"Best-so-far: {self.BestMetric:.6f} at x = {self.bestPhysicalVetex}")
            else:
                print("\nOptimisation completed.")
                print(f"Result: {result[1]:.6f} at x = {result[0]}")
                print(f"Best-so-far: {self.BestMetric:.6f} at x = {self.bestPhysicalVetex}")


        self.CamObjs[CamObjIdx].SetContinousFrameCapMode()
       
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

    def UpdateVertex_TakeDigholoBatch(self,xVertexSingle):
        self.counter=self.counter+1
        if AlignFunc.CheckFileForStopAliginment():
            raise RuntimeError("Optimisation manually terminated.")
        PhysicalVertex=AlignFunc.normalised_to_physical(xVertexSingle,self.LowerPhysicalBounds,self.UpperPhysicalBounds)

        self.UpdateVerticesForSLMAlignment(PhysicalVertex)
        # Frames=np.zeros((self.batchCount,self.CamObj.Nx,self.CamObj.Ny))
        Frames=self.GetBatchOfFrames(CamObjIdx=self.CamObjIdx,SLMObjIdx=self.SLMModeGenIdx,pol=self.polIdxArr[self.polGenIdx],modeIdxArr=self.modeIdxArr)
        

        if (self.UsingDigholoThreadObject): 
            Metrics=self.digiholoObjThread.digholoWindowAutoAlgin(Frames)
        else:
            if(self.AutoAlignBatch):
                _,Metrics=self.digiholoObjs[self.CamObjIdx].digHolo_AutoAlign(Frames)
                if self.GoalMetric==digholoMod.digholoMetrics.SNRAVG:
                    self.digiholoObjs[self.CamObjIdx].digholoProperties["goalIdx"]=digholoMod.digholoMetrics.IL
                    _,_=self.digiholoObjs[self.CamObjIdx].digHolo_AutoAlign(Frames)
                    self.digiholoObjs[self.CamObjIdx].digholoProperties["AutoAlignDefocus"]=0
                    self.digiholoObjs[self.CamObjIdx].digholoProperties["goalIdx"]=digholoMod.digholoMetrics.SNRAVG
                    _,Metrics=self.digiholoObjs[self.CamObjIdx].digHolo_AutoAlign(Frames)
                    self.digiholoObjs[self.CamObjIdx].digholoProperties["AutoAlignDefocus"]=1
                else:
                    _,Metrics=self.digiholoObjs[self.CamObjIdx].digHolo_AutoAlign(Frames)

            else:
                _,Metrics=self.digiholoObjs[self.CamObjIdx].digHolo_ProcessBatch(Frames)

        # print(Metrics)
        MetricVaule=Metrics[self.GoalMetric,0]
        # print(MetricVaule)
        # print(xVertexSingle)
        # if self.GoalMetric==digholoMod.digholoMetrics.MDL:
        #     MetricVaule=-MetricVaule

        # return -MetricVaule,xVertexSingle
        print("Func Evals: "+str(self.counter) + " Metric: "+ str(Metrics[self.GoalMetric,0]))
        # print(f"x values = {PhysicalVertex}")
        # Update best result so far
        if -MetricVaule < self.BestMetric:
            self.BestMetric =-Metrics[self.GoalMetric,0]
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
    
    
    
    