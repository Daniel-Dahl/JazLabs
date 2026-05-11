
# import tomography.standard as standard
# import tomography.masks as masks

import numpy as np
import matplotlib.pyplot as plt
import copy
import cma
from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
from scipy.signal import find_peaks
from scipy.optimize import minimize

# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]
from typing import List

import pwi_inst.utils.camera_utils as cam_utils
import pwi_inst.hardware.SLM.SLM_ServerLinux as SLM_Serverlib
import pwi_inst.hardware.Cameras.Camera_Client as CamClientlib
import pwi_inst.hardware.SLM.PhaseMaskClass as PhaseMaskClass
import pwi_inst.utils.GenerateSimplePhaseMasks as SimpMaskLib
import  pwi_inst.utils.AlignmentFunctions as AlignFunc
import pwi_inst.utils.SpotArrayAnalysis.SpotArrayAnalysis as SpotAnlys_lib


def periodic_strip_mask_1(mask_shape, strip_width=10, strip_value=1, orientation='x'):
    """
    Create a 2D mask with periodic strips where the strip (0) 
    and background (strip_value) have equal widths.

    Parameters
    ----------
    mask_shape : tuple
        Shape of the mask (rows, cols).
    strip_width : int
        Width of each region (strip and gap).
    strip_value : int
        Value of the gap region (strip is 0).
    orientation : str
        'horizontal' or 'vertical'.

    Returns
    -------
    np.ndarray
        2D mask with alternating 0 / strip_value regions.
    """
    rows, cols = mask_shape
    mask = np.zeros(mask_shape, dtype=np.uint8)

    if orientation == 'x':
        idx = np.arange(rows) // strip_width
        mask[(idx % 2 == 1), :] = strip_value
    elif orientation == 'y':
        idx = np.arange(cols) // strip_width
        mask[:, (idx % 2 == 1)] = strip_value
    else:
        raise ValueError("orientation must be 'x' or 'y'")

    return mask
def FindFactors(num):
    # find factor of number
    factors=np.array([num])
    for i in range(num-1,0,-1):
        if(num % i) == 0:
            #print(i)
            factors=np.append(factors,[i])
    #print(factors)
    return factors

def set_superpixel(arr, ix, iy, superpixel_size, phase_value):
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
 
    arr_new[y_start:y_end, x_start:x_end] = (arr[y_start:y_end, x_start:x_end])*np.exp(phase_value*1j)

    return arr_new
class AlginmentObj():
    def __init__(self,
                slmObjs: List[PhaseMaskClass.PhaseMaskObject],
                CamObjs: List[CamClientlib.CameraClient]):
        super().__init__()
        
        # Store lists of devices
        self.slmObjs = slmObjs
        self.CamObjs = CamObjs
       
        # Ensure equal lengths
        assert len(slmObjs) == len(CamObjs), \
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
    def MultiDimAlignmentOfSLM(self,functionToOptimise=None,CamObjIdx=0,SLMModeGenIdx=0,SLMAlignObjIdx=[0],pol=["H"],polGenIdx=0,
                                modeIdxArr=None,
                                Optimiser='CMA-ES',
                                GoalMetric='Pwr',
                                PropertiesToAlign=None,
                                InitialStepSizes=None,
                                ErrTol=1e-7,
                                maxAttempts=100,
                                populationSize=None,
                                simga0=0.2,
                                ispot=0,
                                radiusApp=6,
                                avgFrameCount=1):
            # if channel is None:#if no channel is passed in then use the first active channel on the SLM
            #     channel=self.slmObjs[SLMObjIdx].ActiveRGBChannels[0]
            # Need to set up self variables for the the function to be passed to the golden search function
            # self.channel=channel
            # self.pol=pol
            if functionToOptimise is None:
                print("You need to specify a function to optimise")
                return
            self.ispot=ispot
            self.radiusApp=radiusApp
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
            self.avgFrameCount=avgFrameCount
            
        
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
                            functionToOptimise,
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
                            functionToOptimise,
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
                        objective_function=functionToOptimise,
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
    def UpdateVertex_PwrTotal(self,xVertexSingle):
            self.counter=self.counter+1
            if AlignFunc.CheckFileForStopAliginment():
                raise RuntimeError("Optimisation manually terminated.")
            PhysicalVertex=AlignFunc.normalised_to_physical(xVertexSingle,self.LowerPhysicalBounds,self.UpperPhysicalBounds)

            self.UpdateVerticesForSLMAlignment(PhysicalVertex)
            # Frames=np.zeros((self.batchCount,self.CamObj.Nx,self.CamObj.Ny))\
            spotPwrall_avg=0
            avgFrameCount=25
            for iframe in range(avgFrameCount):
                frame=self.CamObjs[self.CamObjIdx].GetFrame()
                spotCount=self.SpotCenters.shape[0]
                spotPwrall=0
                for ispot in range(spotCount):
                    spotPwrall=spotPwrall+self.SpotSelector_pwr(frame,ispot,self.radiusApp)
                spotPwrall_avg=spotPwrall_avg+spotPwrall
            # spotPwr=self.SpotSelector_pwr(frame,self.icenter,self.radiusApp)
            # framePwr=self.CamObjs[self.CamObjIdx].GetRelativePower(frame)
            MetricVaule=spotPwrall_avg/avgFrameCount
            # MetricVaule=self.PwrObjs[self.PwrMeterObjIdx].GetPower()

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
    
    def GetAvgRelativePowerOfSpot(self,avgFrameCount=25):
        spotPwrall_avg=0

        for iframe in range(avgFrameCount):
            frame=self.CamObjs[self.CamObjIdx].GetFrame()
            spotCount=self.SpotCenters.shape[0]
            spotPwrall=0
            for ispot in range(spotCount):
                spotPwrall=spotPwrall+self.SpotSelector_pwr(frame,ispot,self.radiusApp)
                if ispot==self.ispot:
                    spotPwr=self.SpotSelector_pwr(frame,self.ispot,self.radiusApp)
            
            spotPwrall_avg=spotPwrall_avg+(spotPwr/spotPwrall)
            
        MetricVaule=spotPwrall_avg/avgFrameCount
        return MetricVaule
    
    def GetFrameChangeMetric(self):
        frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
        if self.ApatureFrame:
            NewFrame,_=cam_utils.get_aperture(frame,
                    centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width,show_plot=False)
        else:
            NewFrame=np.copy(frame)
        # plt.subplot(1,2,1)
        # plt.imshow(NewFrame)
        # plt.subplot(1,2,2)
        # plt.imshow(self.Ref_Metric)
        numerator=np.sum(self.Ref_Metric*NewFrame)
        denominator=np.sqrt(np.sum(self.Ref_Metric**2)*np.sum(NewFrame**2))
        MetricVaule=numerator/denominator
        return MetricVaule 
    
    def GetFramePower(self):
        pwr=self.CamObjs[self.ObjIdx].GetRelativePower(centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width,avgCount=self.avgFrameCount)
        pwr=self.CamObjs[self.ObjIdx].GetRelativePower(centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width,avgCount=1)
        
        return pwr 
        
    def GetAvgPowerOfSpot(self,avgFrameCount=25):
        spotPwrall_avg=0
        for iframe in range(avgFrameCount):
            frame=self.CamObjs[self.CamObjIdx].GetFrame()
            spotPwr=self.SpotSelector_pwr(frame,self.ispot,self.radiusApp)
            spotPwrall_avg=spotPwrall_avg+spotPwr
        MetricVaule=spotPwrall_avg/avgFrameCount
        return MetricVaule
    
    def GetAvgPowerOfAllSpots(self,avgFrameCount=25):
        spotPwrall_avg=0
        spotCount=self.SpotCenters.shape[0]
        for iframe in range(avgFrameCount):
            frame=self.CamObjs[self.CamObjIdx].GetFrame()
            spotPwrall=0
            for ispot in range(spotCount):
                spotPwrall=spotPwrall+self.SpotSelector_pwr(frame,ispot,self.radiusApp)            
            spotPwrall_avg=spotPwrall_avg+(spotPwrall)
        MetricVaule=spotPwrall_avg/avgFrameCount
        return MetricVaule
    
    def UpdateVertex_PwrOfSpot(self,xVertexSingle):
        self.counter=self.counter+1
        if AlignFunc.CheckFileForStopAliginment():
            raise RuntimeError("Optimisation manually terminated.")
        PhysicalVertex=AlignFunc.normalised_to_physical(xVertexSingle,self.LowerPhysicalBounds,self.UpperPhysicalBounds)

        self.UpdateVerticesForSLMAlignment(PhysicalVertex)
        # Frames=np.zeros((self.batchCount,self.CamObj.Nx,self.CamObj.Ny))\
        spotPwrall_avg=0
        # self.avgFrameCount=25
        for iframe in range(self.avgFrameCount):
            frame=self.CamObjs[self.CamObjIdx].GetFrame()
            spotCount=self.SpotCenters.shape[0]
            spotPwrall=0
            for ispot in range(spotCount):
                spotPwrall=spotPwrall+self.SpotSelector_pwr(frame,ispot,self.radiusApp)
                # if ispot==self.icenter:
                #     spotPwr=self.SpotSelector_pwr(frame,self.icenter,self.radiusApp)
            
            # spotPwrall_avg=spotPwrall_avg+(spotPwr/spotPwrall)
            spotPwrall_avg=spotPwrall_avg+(spotPwrall)
            
            
        MetricVaule=spotPwrall_avg/self.avgFrameCount
        
            # frame=self.CamObjs[self.CamObjIdx].GetFrame()
            # spotCount=self.SpotCenters.shape[0]
            # spotPwrall=0
            # for ispot in range(spotCount):
            #     spotPwrall=spotPwrall+self.SpotSelector_pwr(frame,ispot,self.radiusApp)
                
            # spotPwr=self.SpotSelector_pwr(frame,self.icenter,self.radiusApp)
            # # framePwr=self.CamObjs[self.CamObjIdx].GetRelativePower(frame)
            # MetricVaule=spotPwr/spotPwrall
            # MetricVaule=self.PwrObjs[self.PwrMeterObjIdx].GetPower()

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



    def ApplySuperPixelTakePower(self,MaskOfSuoerPixels,ix_SupPixel,iy_SupPixel , superpixel_size=1, phaseValue=np.pi/2,avgFrameCount=1):  
            
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
            
            pwrOfSpot=self.GetAvgRelativePowerOfSpot(avgFrameCount)
            # pwrOfSpot=self.GetAvgPowerOfSpot(avgFrameCount=15)

            
            return pwrOfSpot



    def RunSuperPixelSweep(self,ObjIdx=0,pol="H",channel=None,StartingMask=None,NumberOfSuperPixels=None,superpixel_size=None,phaseorCount=4,ispot=0,radiusApp=6,avgframeCount=1, ApplyZernike=False):
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        self.channel=channel
        self.pol=pol
        self.ObjIdx=ObjIdx
        self.ispot=ispot
        self.radiusApp=radiusApp
        self.ApplyZernike=ApplyZernike
        self.imask=0
        self.CamObjIdx=ObjIdx

        self.CamObjs[ObjIdx].SetSingleFrameCapMode()


        MaskSize=self.slmObjs[ObjIdx].polProps[self.channel][self.pol].masksize
        Nx=MaskSize[1]
        Ny=MaskSize[0]
        print(MaskSize)
        
        if StartingMask is None:
            Mask=np.ones((Ny,Nx),dtype=complex)
        else:
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
            print(phaseor_arr)
            # phaseor_arr=np.asarray([0,np.pi/2,np.pi,3*np.pi/2])
            
            phaseor_pwr=np.zeros(phaseorCount)# This is the power of 0,pi/2,pi and 3pi/2 power values 
            for (ix_SupPixel) in range(xShiftCount):
                for (iy_SupPixel) in range(yShiftCount):
                    Z=0
                    for iphaseor in range(phaseorCount):
                        phaseor_pwr_kIdx=self.ApplySuperPixelTakePower(Mask,ix_SupPixel,iy_SupPixel ,
                                                                            superpixel_size=superpixel_size, phaseValue=-phaseor_arr[iphaseor])
                        phaseor_pwr[iphaseor]=phaseor_pwr_kIdx
                        phaseor_pwr_kIdx=phaseor_pwr_kIdx*np.exp(-1j*phaseor_arr[iphaseor])
                        Z=Z+phaseor_pwr_kIdx
                    # phaseOpt=np.angle((phaseor_pwr[0]-phaseor_pwr[2])+1j*((phaseor_pwr[1]-phaseor_pwr[3])))
                    phaseOpt=np.angle((2/phaseorCount)*Z)
                    
                    # Set the superpixel to the optimal phase level based on phaseor anaylsis 
                    Mask=set_superpixel(Mask, ix_SupPixel,iy_SupPixel , superpixel_size=superpixel_size, phase_value=phaseOpt)
                    powerOpt=self.GetAvgRelativePowerOfSpot(avgframeCount)

                    print("phaseor_pwr: "+str(phaseor_pwr)+"\n powerOpt: "+str(powerOpt))
        
        self.CamObjs[self.CamObjIdx].SetContinousFrameCapMode()

        return Mask
        