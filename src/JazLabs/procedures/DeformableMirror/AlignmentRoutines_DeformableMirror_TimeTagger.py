from Lab_Equipment.Config import config

import cv2
import numpy as np
import matplotlib.pyplot as plt
import threading
import ctypes
import copy
from IPython.display import display, clear_output
import IntEnum
import ipywidgets
import multiprocessing
import time
import scipy.io
import cma

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
from scipy.signal import find_peaks
from scipy.optimize import minimize

# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]

import  Lab_Equipment.OpticalSimulations.libs.OpticalOperators as OpticOp
import Lab_Equipment.ZernikeModule.ZernikeModule as zernlib
import TimeTagger
import Lab_Equipment.TimeTagger.TimeTaggerFunction as TimetaggerFunc
# import Lab_Equipment.TimeTagger.TimeTaggerLiveWindow as TTLiveWindow
import Lab_Equipment.DeformableMirror.DeformableMirror as DeformMirror_lib

import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignFunc

import  Lab_Equipment.GeneralLibs.ComplexPlotFunction as cmplxplt
from typing import List


class DM_TT_Metrics(IntEnum):
    Counts = 0
    COIN = 1
    G2 = 2
class AlginmentObj_DM_TT():
    def __init__(self,
                DeformableMirror:DeformMirror_lib.DeformanbleMirror_Obj,
                Tagger:TimeTagger.TimeTagger
                ):
        super().__init__()
        
        # Store lists of devices
        self.DeformableMirror = DeformableMirror
        self.Tagger = Tagger
        

        
        
    def __del__(self):
        print("Cleaning up AlginmentObj_DM_TT")
        # self.CamObjs[].SetContinousFrameCapMode()
    
                
    

# print(NewXcenter,NewYcenter)
    def GetBatchOfFrames(self,CamObjIdx=0,SLMObjIdx=0,channel=None):
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[SLMObjIdx].ActiveRGBChannels[0]
            
        modeCount=self.slmObjs[SLMObjIdx].GLobProps[channel].modeCount
        modeCount_step=self.slmObjs[SLMObjIdx].GLobProps[channel].modeCount_step
        modeCount_start=self.slmObjs[SLMObjIdx].GLobProps[channel].modeCount_start
        
         # Run a intial batch/AutoAlign of the digholo so see if the systems is starting in a good spot
        batchcount=int(np.ceil((modeCount-modeCount_start)/modeCount_step))
        Frames=np.empty((batchcount,self.CamObjs[CamObjIdx].FrameHeight,self.CamObjs[CamObjIdx].FrameWidth),dtype=np.float32)
        
        iframe=0
        for imode in range(modeCount_start,modeCount,modeCount_step):
            self.slmObjs[SLMObjIdx].setmask(channel,imode)
            Frames[iframe,:,:]=self.CamObjs[CamObjIdx].GetFrame(ConvertToFloat32=True)
            iframe+=1
        return Frames
           
    def MultiDimAlignmentOfDM(self,Optimiser='CMA-ES',
                              GoalMetric=DM_TT_Metrics.Counts,
                              measurementChannel=1,
                              binWidth=100000,
                              countingTime=5,
                               PropertiesToAlign=None,
                               InitialStepSizes=None,
                               ErrTol=1e-3,
                               maxAttempts=100,
                               populationSize=None,
                               simga0=0.2,):
      
        
        self.measurementChannel=measurementChannel
        self.GoalMetric=GoalMetric
        self.countingTime=countingTime
        self.binWidth=binWidth
        if PropertiesToAlign is None:
            self.PropertiesToAlign = np.arange(self.DeformableMirror.NumAct)
            print("No array was given for actuators to align so all actuators will be aligned")
        else: 
            self.PropertiesToAlign=PropertiesToAlign
       
            
        if InitialStepSizes is None:
            AllInitialStepSizes=0.5
            self.InitialStepSizes = np.ones(self.DeformableMirror.NumAct)*AllInitialStepSizes
            print("No intial Step Size was given for initial step sizes so all step sizes will be set to 0.5")
        else:
            self.InitialStepSizes = copy.deepcopy(InitialStepSizes)
            
        StepArray,InitalNorm=self.GetInitialVerticeForDMAlignment()
        
        
        # Launch thread running the Multidim alignment Routine
        # I am going with threading as i should be able to change values of objects and varibles in the notebook while the alginment is going in
        # thread_multidimAlignment = threading.Thread( AlignFunc.NelderMead(StepArray,InitalxVertex,ErrTol,maxAttempts,self.UpdateVertex_TakeDigholoBatch))
        # thread_multidimAlignment.start()
        # intial_simplex=AlignFunc.MakeIntialSimplex(InitalxVertex,StepArray)

        #this is the scipy minimisation function might be better then my one that i wrote
        self.counter=0
        self.bestVetex=None
        self.BestMetric=np.inf

        
        if Optimiser!='CMA-ES':
            try:
                if Optimiser=='Nelder-Mead':
                
                    intial_simplex=AlignFunc.MakeIntialSimplex(InitalNorm,StepArray)
                    
                    result = minimize(
                        self.UpdateVertex_TakeTimeTaggerData,
                        InitalNorm,
                        method=Optimiser,
                        # callback=self.print_callback,
                        options={
                            'disp': True,
                            'initial_simplex': intial_simplex,
                            'xatol': ErrTol,
                            'fatol': ErrTol,
                            'maxiter': maxAttempts
                        }
                    )
                else:
                    result = minimize(
                        self.UpdateVertex_TakeTimeTaggerData,
                        InitalNorm,
                        method=Optimiser,
                        bounds=[(-1, 1)]*InitalNorm.size,
                        # callback=self.print_callback,
                        options={
                            'disp': True,
                            'xatol': ErrTol,
                            'fatol': ErrTol,
                            'maxiter': maxAttempts
                        }
                    )
                    
            except RuntimeError as e:
                print(f"\n Optimisation stopped: {e}")
                print(f"Best-so-far: {self.BestMetric:.6f} at x = {self.bestVetex}")
            else:
                print("\n Optimisation completed.")
                print(f"Result: {result.fun:.6f} at x = {result.x}")
                    
        elif Optimiser=='CMA-ES':
            try:
                lower_bounds = np.array([-1.0] * len(InitalNorm))
                upper_bounds = np.array([1.0] * len(InitalNorm))
                if populationSize is None:
                    populationSize=4+(3*np.log10(InitalNorm.size))
                result = cma.fmin(
                    objective_function=self.UpdateVertex_TakeTimeTaggerData,
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
                print(f"\n Optimisation stopped: {e}")
                print(f"Best-so-far: {self.BestMetric:.6f} at x = {self.bestVetex}")
            else:
                print("\n Optimisation completed.")
                print(f"Result: {result[1]:.6f} at x = {result[0]}")
       
        print("Updating the DM to have the best properties")
        self.UpdateVerticesForDMAlignment(self.bestVetex)
        AlignFunc.ChangeFileForStopAliginment(0)

        
        return 
    
    # def print_callback(self):
    #     x, y = params
    #     dErr = np.std(funcVertex);
    #     print(attemptCount,' Function Value= ',funcVertex[0],' Error Accros Values= ',dErr, ' Verterx Value= ',xVertex[:,0])
    #     print(funcVertex[:])
    #     print(f"Callback: x={x:.3f}, y={y:.3f}")

    def UpdateVertex_TakeTimeTaggerData(self,xVertexSingle):
        
        self.counter=self.counter+1
        if AlignFunc.CheckFileForStopAliginment():
            raise RuntimeError("Optimisation manually terminated.")
        
        
        self.UpdateVerticesForDMAlignment(xVertexSingle)
        if self.GoalMetric==DM_TT_Metrics.Counts:
            MetricVaule=TimetaggerFunc.getCountrate(self.Tagger, self.measurementChannel,self.countingTime,clearbuffer=True)
        elif self.GoalMetric==DM_TT_Metrics.COIN:
            CoincidenceData=TimetaggerFunc.getCoincidences(self.Tagger, self.measurementChannel,self.binWidth,self.countingTime,clearbuffer=True)
            MetricVaule=CoincidenceData.coincidences
        elif self.GoalMetric==DM_TT_Metrics.G2:
            pass
        
        print("Func Evals: "+str(self.counter) + " Metric: "+ str(MetricVaule))
        print(f"x values = {xVertexSingle}")
        # Update best result so far
        if -MetricVaule < self.BestMetric:
            self.BestMetric =-MetricVaule
            self.bestVetex= xVertexSingle.copy()

        return -MetricVaule
    
    
    def UpdateVerticesForDMAlignment(self,VertexArr):
        self.DeformableMirror.Set_MirrorSurface(VertexArr)
        return VertexArr
    
    def GetInitialVerticeForDMAlignment(self):
        self.DeformableMirror.ActArr
        VertexArr=np.empty(0)
        stepSizeVertexArr=np.empty(0)
        VertexArr=copy.deepcopy(self.DeformableMirror.ActArr)
        stepSizeVertexArr=self.DeformableMirror.ActArr+self.InitialStepSizes
        
                            
        self.TotalDims=VertexArr.shape
            
        return stepSizeVertexArr,VertexArr
    
    