
# import tomography.standard as standard
# import tomography.masks as masks

import numpy as np
import matplotlib.pyplot as plt
import copy
from IPython.display import display, clear_output
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

import JazLabs.utils.camera_utils as cam_utils
import JazLabs.hardware.Cameras.Camera_Client as CamClientlib
import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass
import JazLabs.utils.GenerateSimplePhaseMasks as SimpMaskLib
import  JazLabs.utils.AlignmentFunctions as AlignFunc
import JazLabs.utils.SpotArrayAnalysis.SpotArrayAnalysis as SpotAnlys_lib


def apply_circular_aperture(array, center, radius, fill_value=0):
    """
    Apply a circular aperture to a 2D numpy array.
    
    Parameters:
    -----------
    array : np.ndarray
        Input 2D array (e.g., image or data field).
    center : tuple of (float, float)
        (row, col) coordinates of the circle centre.
    radius : float
        Radius of the circular aperture (in pixels).
    fill_value : number, optional
        Value to assign outside the aperture (default = 0).
    
    Returns:
    --------
    masked_array : np.ndarray
        Array with circular aperture applied.
    """
    rows, cols = array.shape
    y, x = np.ogrid[:rows, :cols]
    
    cy, cx = center
    # mask = (x - cx)**2 + (y - cy)**2 <= radius**2
    mask = (x - cx)**2 + (y - cy)**2 >= radius**2

    
    masked_array = np.full_like(array, fill_value)
    masked_array[mask] = array[mask]
    return masked_array

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


def FindPlateauStart(x_values,metric_values,smoothing_window=15,plateau_tail_fraction=0.20,
                     PlotResults=True,xlabel="SLM aperture radius [pixels]",
                     ylabel="Alignment metric"):
    """Find the first measured-data intersection with a final plateau estimate.

    The final plateau is the median of the last ``plateau_tail_fraction`` of a
    Savitzky-Golay-smoothed curve.  The returned start is linearly interpolated
    at the earliest point where the measured data crosses that plateau.
    """
    x_values=np.asarray(x_values,dtype=float).reshape(-1)
    metric_values=np.asarray(metric_values,dtype=float).reshape(-1)

    if len(x_values) != len(metric_values):
        raise ValueError("x_values and metric_values must have the same length")
    if smoothing_window < 3:
        raise ValueError("smoothing_window must be at least 3")
    if plateau_tail_fraction <= 0 or plateau_tail_fraction > 1:
        raise ValueError("plateau_tail_fraction must be greater than 0 and no greater than 1")

    valid_values=np.isfinite(x_values) & np.isfinite(metric_values)
    x_values=x_values[valid_values]
    metric_values=metric_values[valid_values]

    sort_order=np.argsort(x_values)
    x_values=x_values[sort_order]
    metric_values=metric_values[sort_order]

    if len(x_values) < 3:
        raise ValueError("At least three valid measurements are required")

    smoothing_window=min(int(smoothing_window),len(metric_values))
    if smoothing_window % 2 == 0:
        smoothing_window-=1

    smoothed_metric=signal.savgol_filter(
        metric_values,
        window_length=smoothing_window,
        polyorder=min(2,smoothing_window-1),
    )

    plateau_count=max(3,int(np.ceil(plateau_tail_fraction*len(smoothed_metric))))
    plateau_count=min(plateau_count,len(smoothed_metric))
    plateau_level=np.median(smoothed_metric[-plateau_count:])

    points_above_plateau=np.flatnonzero(metric_values >= plateau_level)
    plateau_start=None

    if len(points_above_plateau) == 0:
        print("The measured curve does not intersect the plateau level.")
    else:
        crossing_index=points_above_plateau[0]

        if crossing_index == 0:
            plateau_start=x_values[0]
        else:
            x_before=x_values[crossing_index-1]
            x_after=x_values[crossing_index]
            metric_before=metric_values[crossing_index-1]
            metric_after=metric_values[crossing_index]

            if metric_after == metric_before:
                plateau_start=x_after
            else:
                plateau_start=x_before+(
                    (plateau_level-metric_before)
                    *(x_after-x_before)
                    /(metric_after-metric_before)
                )

        print(f"Final plateau level: {plateau_level:.6g}")
        print(f"First intersection: {plateau_start:.2f} pixels")

    if PlotResults:
        plt.figure(figsize=(8,5))
        plt.plot(x_values,metric_values,alpha=0.7,label="Measured")
        plt.plot(x_values,smoothed_metric,color="khaki",label="Smoothed")
        plt.axhline(plateau_level,color="white",linestyle="--",label="Final plateau")

        if plateau_start is not None:
            plt.axvline(
                plateau_start,
                color="tab:red",
                linestyle="--",
                label=f"First intersection: {plateau_start:.1f} px",
            )
            plt.scatter(plateau_start,plateau_level,color="tab:red",zorder=5)

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.grid(alpha=0.3)
        plt.legend()
        plt.show()

    return plateau_start,plateau_level


########
# This needs to be made into a function just dont have the time right now it is just a simple scan that probs the size of the beam on the slm
########
# def Beam_size_scan_on_SLM()
# channel="Red"
# Direction="y"
# imask=0
# pol="H"
# backgroundLevel=0                                       
# strip_width=5

# Nx=512
# Ny=512
# y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
# x_center = slm.AllMaskProperties[channel][pol][imask].center[1] 
# pwrin0Order=[]
# radius=[]
# ipwr=0
# Cam_FL_1.CamObject.SetSingleFrameCapMode()
# slm.LCOS_Clean(channel=channel)
# ref=Cam_FL_1.CamObject.GetRelativePower(frame=None, centre=[128,128], x_half_width=64, y_half_width=64,show_plot=False)
# for iradius in range(1,256,1):  
#     mask_piStrip=slmTimeCal.periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=128, orientation=Direction)
#     mask_piStrip=CamForm.apply_circular_aperture(mask_piStrip, 
#                                         [mask_piStrip.shape[0]//2,mask_piStrip.shape[1]//2],
#                                         iradius, fill_value=0)
#     MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_piStrip,backgroundLevel)
#     mask_piStrip_MASKTODisplay_256=np.copy(MASKTODisplay_256)
#     slm.Write_To_Display(mask_piStrip_MASKTODisplay_256,channel)

#     # appframe,_=CamForm.ApatrureFrame(frame,[122,129],32,32)
#     pwr=Cam_FL_1.CamObject.GetRelativePower(frame=None, centre=[128,128], x_half_width=64, y_half_width=64,show_plot=False)
#     # metric=np.abs(pwr-0.99*ref)#/iradius
#     metric=-((ref-pwr)*iradius**2)
    
#     # print(pwr)
#     pwrin0Order.append(metric)
#     radius.append(iradius)
#     ipwr=ipwr+1
# Cam_FL_1.CamObject.SetContinousFrameCapMode()

# plt.imshow(appframe)


def CourseSweepAcrossSLMPowerMeter(slm:PhaseMaskClass.PhaseMaskObject,channel,CamObjs:CamClientlib.CameraClient,flipCount=25):
    CamObjs.SetSoftwareTriggerMode()
    slm.Clear_Display()
    # flipMin=//2-flipCount//2
    flipMin=0
    flipMax=slm.slmHeigth//2+flipCount//2
    flipMax=slm.slmWidth//2+flipCount//2
    CamObjs.FireSoftwareTrigger()
    frame=CamObjs.GetFrame() 
    relativepwr = cam_utils.get_relative_power(frame=frame)
    print(relativepwr)
    powerReadingX=np.empty(0)
    powerReadingY=np.empty(0)

    #Left to right sweep
    for iflip in range(0,slm.slmWidth,flipCount):
        CamObjs.FireSoftwareTrigger()
        frame=CamObjs.GetFrame() 
        relativepwr = cam_utils.get_relative_power(frame=frame)
        powerReadingX=np.append(powerReadingX,relativepwr)
        # PiFlip_cmplx =np.ones((slm.slmHeigth,slm.slmWidth),dtype=complex)
        PiFlip_cmplx =np.zeros((slm.slmHeigth,slm.slmWidth),dtype=np.float32)
        # PiFlip_cmplx =np.ones((slm.slmHeigth,slm.slmWidth),dtype=np.float32)*(-1*np.pi)

        # PiFlip_cmplx[0:flipMin+iflip,:]=np.exp(1j*np.pi)
        # PiFlip_cmplx[:,0:flipMin+iflip]=np.exp(1j*np.pi)
        PiFlip_cmplx[:,0:flipMin+iflip]=(np.pi)


        # np.angle( np.random.rand(1200,1920) + np.random.rand(1200,1920) * 1j)
        ArryForSLM=slm.convert_phase_to_uint8(PiFlip_cmplx)
        # slm.LCOS_Display(ArryForSLM, slm.GLobProps[channel].rgbChannelIdx)
        slm.WriteImageToSLM(ArryForSLM, channel)
        
        
    # top to bottom sweep    
    for iflip in range(0,slm.slmHeigth,flipCount):
        CamObjs.FireSoftwareTrigger()
        frame=CamObjs.GetFrame()
        relativepwr = cam_utils.get_relative_power(frame=frame)
        powerReadingY=np.append(powerReadingY,relativepwr)

        # PiFlip_cmplx =np.ones((slm.slmHeigth,slm.slmWidth),dtype=complex)
        PiFlip_cmplx =np.zeros((slm.slmHeigth,slm.slmWidth),dtype=np.float32)

        # PiFlip_cmplx[0:flipMin+iflip,:]=np.exp(1j*np.pi)
        PiFlip_cmplx[0:flipMin+iflip,:]=(np.pi)

        # PiFlip_cmplx[:,0:flipMin+iflip]=np.exp(1j*np.pi)

        # np.angle( np.random.rand(1200,1920) + np.random.rand(1200,1920) * 1j)
        ArryForSLM=slm.convert_phase_to_uint8((PiFlip_cmplx))
        # slm.LCOS_Display(ArryForSLM, slm.GLobProps[channel].rgbChannelIdx)
        slm.WriteImageToSLM(ArryForSLM, channel)
        
    slm.Clear_Display(channel)
    CamObjs.SetContinuousMode()
    return powerReadingX,powerReadingY

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

        
    def __del__(self):
        print("Cleaning up AlginmentObj_SLM_PwrMeter")
        
    def LoadSpotCenters(self,filename):
        arr = np.load(filename)
        self.SpotCenters = arr.astype(int)
    def SpotSelector_pwr(self,frame,ispot,radiusApp):
        singlespot,pwr=SpotAnlys_lib.extract_spot_minimal(frame, self.SpotCenters[ispot], radii_px=radiusApp, bg_value=0, return_mask=False)
        return pwr
    
    def GetAvgPowerOfSpot(self,avgFrameCount=25):
        spotPwrall_avg=0
        for iframe in range(avgFrameCount):
            self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
            frame=self.CamObjs[self.CamObjIdx].GetFrame()
            spotPwr=self.SpotSelector_pwr(frame,self.ispot,self.radiusApp)
            spotPwrall_avg=spotPwrall_avg+spotPwr
        MetricVaule=spotPwrall_avg/avgFrameCount
        return MetricVaule
    
    def GetAvgPowerOfAllSpots(self,avgFrameCount=25):
        spotPwrall_avg=0
        spotCount=self.SpotCenters.shape[0]
        for iframe in range(avgFrameCount):
            self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
            frame=self.CamObjs[self.CamObjIdx].GetFrame()
            spotPwrall=0
            for ispot in range(spotCount):
                spotPwrall=spotPwrall+self.SpotSelector_pwr(frame,ispot,self.radiusApp)            
            spotPwrall_avg=spotPwrall_avg+(spotPwrall)
        MetricVaule=spotPwrall_avg/avgFrameCount
        return MetricVaule

            
    def CalulateMetric(self,avgframeCount,CalulateRefMetric=False):
        if self.MetricType=="POWERSPOT":
            if CalulateRefMetric:
                metric= self.GetAvgPowerOfSpot(self.avgFrameCount)
            else:
                RefSigPWR = self.GetAvgPowerOfSpot(self.avgFrameCount)
                RefSigPWR_log = 10 * np.log10(RefSigPWR / self.Ref_Metric)
                metric=RefSigPWR_log
            
        elif self.MetricType=="SPATIAL":
            if CalulateRefMetric:
                if self.ApatureFrame:
                    self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
                    frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
                    metric,_= cam_utils.get_aperture(frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
            else:
                if self.ApatureFrame:
                    NewFrame,_=cam_utils.get_aperture(frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width,show_plot=False)
                else:
                    NewFrame=np.copy(frame)
                numerator=np.sum(self.Ref_Metric*NewFrame)
                denominator=np.sqrt(np.sum(self.Ref_Metric**2)*np.sum(NewFrame**2))
                metric=numerator/denominator
            
        elif self.MetricType=="POWERMinusHalfRef":
            if CalulateRefMetric:
                metric=0
                for iframe in range(avgframeCount):
                    self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
                    frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
                    # self.ifig+=1
                    # plt.figure(self.ifig)
                    # plt.imshow(frame)
                    metric=cam_utils.get_relative_power(frame=frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
                metric += metric
                metric=metric/avgframeCount
            else:
                pwr=0
                for iframe in range(avgframeCount):
                    self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
                    frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
                    pwr=cam_utils.get_relative_power(frame=frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
                pwr += pwr
                pwr=pwr/avgframeCount
                metric = np.abs(pwr - self.Ref_Metric/2)
        elif self.MetricType=="POWER":
            if CalulateRefMetric:
                metric=0
                for iframe in range(avgframeCount):
                    self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
                    frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
                    self.ifig+=1
                    plt.figure(self.ifig)
                    plt.imshow(frame)
                    metric=cam_utils.get_relative_power(frame=frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
                metric += metric
                metric=metric/avgframeCount
            else:
                pwr=0
                for iframe in range(avgframeCount):
                    self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
                    frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
                    pwr=cam_utils.get_relative_power(frame=frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
                pwr += pwr
                pwr=pwr/avgframeCount
                metric = np.abs(pwr)
        else:
            print("Incorrect Metric selected. You must select either POWER or SPATIAL")
        return metric
    
    def Beam_size_scan_on_SLM(self,ObjIdx=0,channel=None,pol="H",
                                            ApplyZernike=False,MaskSize=None,
                                            InitalRadius=1,FinalRadius=100,radiusStep=100,
                                            avgFrameCount=1,ispot=0,camradiusApp=6,
                                            PlotResults=True,
                                            MetricType="POWER",
                                            ixCamCenter=None,iyCamCenter=None,
                                    x_half_width=None,
                                    y_half_width=None ):
        
    
        self.ixCamCenter=ixCamCenter
        self.iyCamCenter=iyCamCenter
        self.x_half_width=x_half_width
        self.y_half_width=y_half_width
        self.MetricType=MetricType
        
        self.pol=pol
        self.ObjIdx=ObjIdx
        self.ApplyZernike=ApplyZernike
        self.imask=0
        
        if (self.ixCamCenter is not None and self.iyCamCenter is not None and self.x_half_width is not None and self.y_half_width is not None):
            self.ApatureFrame = True
        else:
            self.ApatureFrame = False
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        self.channel=channel
        
        print(self.MetricType)
        
        self.slmObjs[ObjIdx].Clear_Display(channel=channel)
        self.CamObjIdx=ObjIdx
        self.CamObjs[self.CamObjIdx].SetSoftwareTriggerMode()

        self.avgFrameCount=avgFrameCount
        self.ispot=ispot
        self.radiusApp=camradiusApp
        self.xValTrack=np.empty((0))
        self.yValTrack=np.empty((0))
            
        if self.MetricType == "POWERSPOT":
            self.Ref_Metric = self.GetAvgPowerOfSpot(self.avgFrameCount)
        elif self.MetricType == "SPATIAL":
            self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
            frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
            if self.ApatureFrame:
                self.Ref_Metric,_= cam_utils.get_aperture(frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
                # plt.imshow(self.Ref_Metric)
            else:
                self.Ref_Metric=np.copy(frame)
        elif self.MetricType == "POWER":
            self.CamObjs[self.CamObjIdx].FireSoftwareTrigger()
            frame=np.copy(self.CamObjs[self.CamObjIdx].GetFrame())
            self.Ref_Metric=cam_utils.get_relative_power(frame=frame,centre=[self.ixCamCenter,self.iyCamCenter],x_half_width=self.x_half_width,y_half_width=self.y_half_width)
        else:
            print("Incorrect Metric selected. You must select either POWER or SPATIAL")
            
        self.BoundMin=InitalRadius
        self.BoundMax=FinalRadius
        radiusCount=int((FinalRadius-InitalRadius)/radiusStep)+1
        self.DiscretisedSpace_arr= np.arange(self.BoundMin,self.BoundMax,1)
        
        xVal=np.empty(radiusCount)
        metric=np.empty(radiusCount)
        for irad in range(InitalRadius,FinalRadius,radiusStep):
            xVal,metric = self.ChangeApatureRadiusTakeMetric(irad)

        if PlotResults:
            plt.plot(self.xValTrack,self.yValTrack)
        self.CamObjs[self.CamObjIdx].SetContinuousMode()
        return self.xValTrack,self.yValTrack
    
    def ChangeApatureRadiusTakeMetric(self,xVal):
        
        xVal,x1Idx=AlignFunc.CovertCont2Desc(xVal,self.DiscretisedSpace_arr)
        
        self.globalphaseshiftshift=-np.pi    
        MaskSize=self.slmObjs[self.ObjIdx].polProps[self.channel][self.pol].masksize
        
        
        Nx=MaskSize[0]
        Ny=MaskSize[1]
        xCenter=self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[1]
        yCenter=self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[0]
        MASK=np.ones((Nx,Ny),dtype=complex)
        #Left to right sweep
        self.HalfMaskType="BinaryStrip"
        
        MASK = np.squeeze(SimpMaskLib.binary_stripe_phase(Nx=Nx,Ny=Ny,stripe_width =10,phase_value= 0.0,orientation = "vertical"))
        
        MASK=apply_circular_aperture(MASK,[MASK.shape[0]//2,MASK.shape[1]//2],xVal, fill_value=0)
        
        if (self.ApplyZernike):
                    MASK_PlussZernike=self.slmObjs[self.ObjIdx].ApplyZernikesToSingleMask(self.channel,(MASK),imask=self.imask,pol=self.pol,imode=0)
        else:
            # MASK_PlussZernike=np.angle(MASK)
            MASK_PlussZernike=(MASK)

            MASKTODisplay_cmplx=self.slmObjs[self.ObjIdx].Draw_Single_Mask( xCenter,yCenter, MASK_PlussZernike)
        
        self.slmObjs[self.ObjIdx].FullScreenBuffer_int=self.slmObjs[self.ObjIdx].convert_phase_to_uint8(MASKTODisplay_cmplx) # Note if nothing is passed it will use the self.FullScreenBuffer_cmplx array as the array it is going to convert      
        self.slmObjs[self.ObjIdx].WriteImageToSLM(self.slmObjs[self.ObjIdx].FullScreenBuffer_int,self.channel)
        
        metric=self.CalulateMetric(avgframeCount=self.avgFrameCount)

        self.xValTrack=np.append(self.xValTrack,xVal)
        self.yValTrack=np.append(self.yValTrack,metric)
        
        return xVal,metric
    

    
    def PerformCenterAlignment_GoldenSearch(self,ObjIdx=0,channel=None,pol="H",
                                            ApplyZernike=False,MaskSize=None,
                                            PixelsCountFromCenters=50,
                                            PlotTracking=False,
                                            BackgroundPhase=np.pi,avgFrameCount=10,ispot=0,radiusApp=6,
                                            MetricType="POWER",
                                            stripe_width=10,
                                            ixCamCenter=None,
                                    iyCamCenter=None,
                                    x_half_width=None,
                                    y_half_width=None,
                                    Verbose=False ):
        self.ixCamCenter=ixCamCenter
        self.iyCamCenter=iyCamCenter
        self.x_half_width=x_half_width
        self.y_half_width=y_half_width
        self.stripe_width=stripe_width
        self.MetricType=MetricType

        self.ifig=1
        if (self.ixCamCenter is not None and self.iyCamCenter is not None and self.x_half_width is not None and self.y_half_width is not None):
            self.ApatureFrame = True
        else:
            self.ApatureFrame = False

            
        # self.CamObjs[ObjIdx].SetSingleFrameCapMode()

        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        if MaskSize is  None:
            MaskSize=self.slmObjs[ObjIdx].polProps[channel][pol].masksize
        self.MaskSize=MaskSize
        self.CamObjIdx=ObjIdx
        self.ObjIdx=ObjIdx

        OriginialBackground_int=np.copy(self.slmObjs[ObjIdx].backgroundPattern_int)
        background=np.ones((self.slmObjs[ObjIdx].LCOSsize))*np.exp(1j*BackgroundPhase)
        self.slmObjs[ObjIdx].Clear_Display(channel=channel)
        # self.slmObjs[ObjIdx].SetBackGroundPattern(channel=channel,backgroundPattern=background)
        self.CamObjs[self.CamObjIdx].SetSoftwareTriggerMode()
        # self.RefPWR=self.CamObjs[self.ObjIdx].GetRelativePower()
        self.avgFrameCount=avgFrameCount
        self.ispot=ispot
        self.radiusApp=radiusApp
        self.Ref_Metric=self.CalulateMetric(avgframeCount=self.avgFrameCount,CalulateRefMetric=True)
      
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
        
        for imask in range(MaskCount): 
            self.imask=imask
            oldxCenter=self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[1]
            oldyCenter=self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[0]

            if Verbose:
                print(f"Mask {imask} original centre: X={oldxCenter}, Y={oldyCenter}")

            if self.PlotTracking:
                tracking_figure,tracking_axes=plt.subplots(
                    1,
                    2,
                    figsize=(12,4.5),
                    constrained_layout=True,
                )

            for iDirection in range(2): # This is for the X and Y direction Centers NOTE 0=Y and 1=X
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
                    AlignFunc.GoldenSelectionSearch(
                        self.BoundMin,
                        self.BoundMax,
                        dspace_Tol=1,
                        FuncToMinamise=self.ChangePiFlipTakeMetric,
                        Verbose=Verbose,
                    )

                    lowest_metric_index=np.nanargmin(self.yValTrack)
                    measured_minimum_position=self.xValTrack[lowest_metric_index]
                    CenterAvg=CenterAvg+measured_minimum_position
                    iphaseFlipCount=iphaseFlipCount+1

                    if self.PlotTracking:
                        tracking_axis=tracking_axes[iDirection]
                        phase_color=("tab:red","tab:green")[iPhaseFlip]
                        tracking_axis.scatter(
                            self.xValTrack,
                            self.yValTrack,
                            color=phase_color,
                            s=28,
                            alpha=0.85,
                            label=f"Phase flip {iPhaseFlip+1}",
                        )
                        tracking_axis.axvline(
                            measured_minimum_position,
                            color=phase_color,
                            linestyle="--",
                            linewidth=1.2,
                            alpha=0.9,
                            label=f"Flip {iPhaseFlip+1} minimum: {measured_minimum_position:.0f} px",
                        )

                selected_center=int(np.rint(CenterAvg/iphaseFlipCount))
                if (iDirection==0):# Y direction
                    MinYCenter[imask]=selected_center
                    direction_name="Y"
                    old_center=oldyCenter
                else:# X direction
                    MinXCenter[imask]=selected_center
                    direction_name="X"
                    old_center=oldxCenter

                if self.PlotTracking:
                    tracking_axis=tracking_axes[iDirection]
                    tracking_axis.axvline(
                        old_center,
                        color="0.65",
                        linestyle="--",
                        label=f"Original: {old_center:.0f} px",
                    )
                    tracking_axis.axvline(
                        selected_center,
                        color="white",
                        linestyle="--",
                        linewidth=1.5,
                        label=f"Selected: {selected_center:.0f} px",
                    )
                    tracking_axis.set_title(f"{direction_name} centre alignment")
                    tracking_axis.set_xlabel(f"SLM {direction_name} position [pixels]")
                    tracking_axis.set_ylabel("Alignment metric")
                    tracking_axis.grid(alpha=0.3)
                    tracking_axis.legend()

            if self.PlotTracking:
                tracking_figure.suptitle(f"Mask {imask} centre alignment")
                plt.show()

            if Verbose:
                print(
                    f"Mask {imask} selected centre: "
                    f"X={MinXCenter[imask]:.0f}, Y={MinYCenter[imask]:.0f}"
                )
        
        self.slmObjs[ObjIdx].Clear_Display(channel)
        for imask in range(MaskCount):
            self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[1] = MinXCenter[imask]
            self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][imask].center[0] = MinYCenter[imask]
        
        #Switch back to the orginial backgroud
        self.slmObjs[ObjIdx].backgroundPattern_int =np.copy(OriginialBackground_int)
        self.slmObjs[ObjIdx].setmask(channel,0)

        # self.CamObjs[ObjIdx].SetContinousFrameCapMode()
        self.CamObjs[self.CamObjIdx].SetContinuousMode()
        
        return (MinXCenter),(MinYCenter)
    
    def ChangePiFlipTakeMetric(self,xVal):
        xVal,x1Idx=AlignFunc.CovertCont2Desc(xVal,self.DiscretisedSpace_arr);
        self.globalphaseshiftshift=-np.pi    
        # Nx=self.slm.masksize[0]
        # Ny=self.slm.masksize[1]
        # MaskSize=self.slmObjs[self.ObjIdx].polProps[self.channel][self.pol].masksize
        
        Nx=self.MaskSize[0]
        Ny=self.MaskSize[1]
        # print(MaskSize)
        MASK=np.ones((Nx,Ny),dtype=complex)
        
        self.HalfMaskType="BinaryStrip"
        if(self.iDirection==1):
            y_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[0])
            
            if( self.Phasedir==0):
                if self.HalfMaskType=="BinaryStrip":
                    MASK = np.squeeze(SimpMaskLib.binary_stripe_phase(
                        Nx=Nx,Ny=Ny,
                        stripe_width =self.stripe_width,
                        phase_value= 0.0,
                        orientation = "horizontal",
                    ))
                else:
                    MASK[:,int((Nx/2)):Nx]=np.exp(1j*(self.globalphaseshiftshift+np.pi))
                    
                MASK[:,0:int((Nx/2))]=np.exp(1j*self.globalphaseshiftshift)
            else:
                if self.HalfMaskType=="BinaryStrip":
                    MASK = np.squeeze(SimpMaskLib.binary_stripe_phase(
                        Nx=Nx,Ny=Ny,
                        stripe_width =self.stripe_width,
                        phase_value= 0.0,
                        orientation = "horizontal",
                    ))
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
                if self.HalfMaskType=="BinaryStrip":
                    MASK = np.squeeze(SimpMaskLib.binary_stripe_phase(
                        Nx=Nx,Ny=Ny,
                        stripe_width =self.stripe_width,
                        phase_value= 0.0,
                        orientation = "vertical",
                    ))
                else:
                    MASK[int((Ny/2)):Ny,:]=np.exp(1j*(self.globalphaseshiftshift+np.pi))
                    
                MASK[0:int((Ny/2)),:]=np.exp(1j*self.globalphaseshiftshift)
            else:
                if self.HalfMaskType=="BinaryStrip":
                    MASK = np.squeeze(SimpMaskLib.binary_stripe_phase(
                        Nx=Nx,Ny=Ny,
                        stripe_width =self.stripe_width,
                        phase_value= 0.0,
                        orientation = "vertical",
                    ))
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
        self.slmObjs[self.ObjIdx].WriteImageToSLM(self.slmObjs[self.ObjIdx].FullScreenBuffer_int,self.channel)
        
        metric=self.CalulateMetric(avgframeCount=self.avgFrameCount)
        self.xValTrack=np.append(self.xValTrack,xVal)
        self.yValTrack=np.append(self.yValTrack,metric)
        
        return xVal,metric
    
    def SweepAcrossSLM_Mask(self,ObjIdx=0,imask=0,channel=None,pol="H",stepCount=10,PixelsFromCenter=50,
                            ixCamCenter=None,iyCamCenter=None,x_half_width=None,y_half_width=None,MetricType="POWER",
                            avgFrameCount=1):

        self.MetricType=MetricType
        self.ixCamCenter=ixCamCenter
        self.iyCamCenter=iyCamCenter
        self.x_half_width=x_half_width
        self.y_half_width=y_half_width
        self.ObjIdx=ObjIdx
        self.CamObjIdx=ObjIdx
        self.avgFrameCount=avgFrameCount
        self.pol=pol
        self.imask=imask
        if (self.ixCamCenter is not None and self.iyCamCenter is not None and self.x_half_width is not None and self.y_half_width is not None):
            self.ApatureFrame = True
        else:
            self.ApatureFrame = False
        # CamObj.Exposure
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        self.channel=channel
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        
        self.slmObjs[ObjIdx].Clear_Display(channel)
        self.CamObjs[self.CamObjIdx].SetSoftwareTriggerMode()
        
       
        #This is the reference Field that the other fields will be overlaped with
        # self.RefPWR=self.CamObjs[self.ObjIdx].GetRelativePower(centre=[xcentre,ycentre],x_half_width=x_half_width,y_half_width=y_half_width)
        self.Ref_Metric=self.CalulateMetric(avgframeCount=self.avgFrameCount,CalulateRefMetric=True)
        
        
        PixelFlipStep=np.zeros((2,2*PixelsFromCenter//stepCount,MaskCount))
        RefSigPWR=np.zeros((2,2*PixelsFromCenter//stepCount,MaskCount))
        # I may have to move this to inside the imask loop to reset the pi flip location
        PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(0.0*1j*np.pi)
        
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
                self.slmObjs[ObjIdx].WriteImageToSLM(self.slmObjs[ObjIdx].FullScreenBuffer_int,channel)
                RefSigPWR[iDirection,iflipIdx,imask]=self.CalulateMetric(avgframeCount=self.avgFrameCount)
                PixelFlipStep[iDirection,iflipIdx,imask]=iflip
                iflipIdx=iflipIdx+1
                    
            
        # RefSigPWR = np.sqrt(RefSigPWR)# not sure why I sqrt twice might be wrong will come back and check
        # RefSigPWR_log =1# 10 * np.log10(RefSigPWR / self.RefPWR)
        RefSigPWR_log =10 * np.log10(np.maximum(RefSigPWR, np.finfo(float).tiny))
        
        self.slmObjs[ObjIdx].Clear_Display(channel) 
        self.CamObjs[self.CamObjIdx].SetContinuousMode()
        
        return RefSigPWR,RefSigPWR_log,PixelFlipStep
    
    def SweepAcrossSLM_Mask_binaryGrating(self,ObjIdx=0,imask=0,channel=None,pol="H",stepCount=10,PixelsFromCenter=50,strip_width=10,
                            MaskSize=None,avgFrameCount=1,
                            ixCamCenter=None,iyCamCenter=None,x_half_width=None,y_half_width=None,MetricType="POWER"):

        self.MetricType=MetricType
        self.ixCamCenter=ixCamCenter
        self.iyCamCenter=iyCamCenter
        self.x_half_width=x_half_width
        self.y_half_width=y_half_width
        self.ObjIdx=ObjIdx
        self.CamObjIdx=ObjIdx
        self.avgFrameCount=avgFrameCount
        self.pol=pol
        self.imask=imask
        if (self.ixCamCenter is not None and self.iyCamCenter is not None and self.x_half_width is not None and self.y_half_width is not None):
            self.ApatureFrame = True
        else:
            self.ApatureFrame = False
        # CamObj.Exposure
        if channel is None:#if no channel is passed in then use the first active channel on the SLM
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        self.channel=channel
        if MaskSize is None:
            MaskSize=self.slmObjs[ObjIdx].polProps[channel][pol].masksize
        self.MaskSize=MaskSize
        Nx=int(MaskSize[0])
        Ny=int(MaskSize[1])
        MaskCount=self.slmObjs[ObjIdx].polProps[channel][pol].MaskCount
        
        self.slmObjs[ObjIdx].Clear_Display(channel)
        self.CamObjs[self.CamObjIdx].SetSoftwareTriggerMode()
        #This is the reference Field that the other fields will be overlaped with
        self.Ref_Metric=self.CalulateMetric(avgframeCount=self.avgFrameCount,CalulateRefMetric=True)
        
        
        PixelFlipStep=np.zeros((2,2*PixelsFromCenter//stepCount,MaskCount))
        RefSigPWR=np.zeros((2,2*PixelsFromCenter//stepCount,MaskCount))
        # I may have to move this to inside the imask loop to reset the pi flip location
        PiFlip_cmplx =np.ones((self.slmObjs[ObjIdx].slmHeigth,self.slmObjs[ObjIdx].slmWidth),dtype=complex)*np.exp(0.0*1j*np.pi)
        
        # set up at the boundaries of the mask properties
        x_center=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[1])
        y_center=int(self.slmObjs[ObjIdx].AllMaskProperties[channel][pol][self.imask].center[0])
        print(x_center,y_center)
        # strip_width=5
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
                if (iDirection==1):
                    mask_piStrip=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=128, orientation="x")
                    mask_piStrip[:,Ny//2:]=0
                    
                    # PiFlip_cmplx[:,0:iflip]=PiFlip_cmplx[:,0:iflip]*np.exp(1j*np.pi)
                    MASKTODisplay_256=self.slmObjs[ObjIdx].Draw_Single_Mask( iflip, y_center, mask_piStrip)
                    
                else:
                    mask_piStrip=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=128, orientation="y")
                    
                    mask_piStrip[Nx//2:,:]=0
                    # PiFlip_cmplx[0:iflip,:]= PiFlip_cmplx[0:iflip,:]*np.exp(1j*np.pi)
                    MASKTODisplay_256=self.slmObjs[ObjIdx].Draw_Single_Mask( x_center, iflip, mask_piStrip)
                    
                mask_piStrip_MASKTODisplay_256=np.copy(MASKTODisplay_256)
                self.slmObjs[ObjIdx].WriteImageToSLM(mask_piStrip_MASKTODisplay_256,channel)

                RefSigPWR[iDirection,iflipIdx,imask]=self.CalulateMetric(avgframeCount=self.avgFrameCount)   
                
                PixelFlipStep[iDirection,iflipIdx,imask]=iflip
                iflipIdx=iflipIdx+1
                    

        RefSigPWR_log =10 * np.log10(np.maximum(RefSigPWR, np.finfo(float).tiny))
        
        self.slmObjs[ObjIdx].Clear_Display(channel) 
        self.CamObjs[self.CamObjIdx].SetContinuousMode()
        
        
        return RefSigPWR,RefSigPWR_log,PixelFlipStep

    def SweepAcrossSLM_StripProfile(self,ObjIdx=0,channel=None,stepCount=10,StartingSweepPoint=0,strip_width=10,
                                    avgFrameCount=1,
                                    ixCamCenter=None,iyCamCenter=None,x_half_width=None,y_half_width=None,
                                    MetricType="POWER"):
        """Reveal a full-SLM striped pattern in Y and X while recording the metric.

        The SLM begins blank.  Direction index 0 moves a horizontal edge in Y,
        filling the area behind it with horizontal stripes.  Direction index 1
        moves a vertical edge in X, filling the area behind it with vertical
        stripes.  The completed pattern fills the entire SLM.  The returned
        arrays use the same
        ``[direction, sample, 0]`` layout as
        ``SweepAcrossSLM_Mask_binaryGrating``.  Because the SLM height and width
        can differ, unused samples at the end of the shorter sweep are NaN.
        """
        if stepCount <= 0:
            raise ValueError("stepCount must be greater than zero")
        if StartingSweepPoint < 0:
            raise ValueError("StartingSweepPoint must be zero or greater")
        if strip_width <= 0:
            raise ValueError("strip_width must be greater than zero")

        self.MetricType=MetricType
        self.ixCamCenter=ixCamCenter
        self.iyCamCenter=iyCamCenter
        self.x_half_width=x_half_width
        self.y_half_width=y_half_width
        self.ObjIdx=ObjIdx
        self.CamObjIdx=ObjIdx
        self.avgFrameCount=avgFrameCount
        self.ifig=1
        self.ApatureFrame=(
            self.ixCamCenter is not None
            and self.iyCamCenter is not None
            and self.x_half_width is not None
            and self.y_half_width is not None
        )

        if channel is None:
            channel=self.slmObjs[ObjIdx].ActiveRGBChannels[0]
        self.channel=channel

        slm_height=int(self.slmObjs[ObjIdx].slmHeigth)
        slm_width=int(self.slmObjs[ObjIdx].slmWidth)
        if StartingSweepPoint >= slm_height or StartingSweepPoint >= slm_width:
            raise ValueError("StartingSweepPoint must be inside both SLM dimensions")

        y_sweep_positions=np.arange(StartingSweepPoint,slm_height,stepCount,dtype=int)
        x_sweep_positions=np.arange(StartingSweepPoint,slm_width,stepCount,dtype=int)
        y_sweep_positions=np.append(y_sweep_positions,slm_height)
        x_sweep_positions=np.append(x_sweep_positions,slm_width)
        max_sample_count=max(len(y_sweep_positions),len(x_sweep_positions))

        StripSweepStep=np.full((2,max_sample_count,1),np.nan,dtype=float)
        RefSigPWR=np.full((2,max_sample_count,1),np.nan,dtype=float)

        self.slmObjs[ObjIdx].Clear_Display(channel)
        self.CamObjs[self.CamObjIdx].SetSoftwareTriggerMode()

        try:
            self.Ref_Metric=self.CalulateMetric(avgframeCount=self.avgFrameCount,CalulateRefMetric=True)

            horizontal_stripe_profile=periodic_strip_mask_1(
                mask_shape=[slm_height,slm_width],
                strip_width=strip_width,
                strip_value=128,
                orientation="x",
            )
            vertical_stripe_profile=periodic_strip_mask_1(
                mask_shape=[slm_height,slm_width],
                strip_width=strip_width,
                strip_value=128,
                orientation="y",
            )

            # Y sweep: reveal horizontal stripes behind a downward-moving edge.
            for sample_index,stripe_edge in enumerate(y_sweep_positions):
                displayed_stripe_profile=np.zeros((slm_height,slm_width),dtype=np.uint8)
                displayed_stripe_profile[StartingSweepPoint:stripe_edge,:]=horizontal_stripe_profile[StartingSweepPoint:stripe_edge,:]

                self.slmObjs[ObjIdx].WriteImageToSLM(displayed_stripe_profile,channel)
                RefSigPWR[0,sample_index,0]=self.CalulateMetric(avgframeCount=self.avgFrameCount)
                StripSweepStep[0,sample_index,0]=stripe_edge

            # X sweep: reveal vertical stripes behind a right-moving edge.
            for sample_index,stripe_edge in enumerate(x_sweep_positions):
                displayed_stripe_profile=np.zeros((slm_height,slm_width),dtype=np.uint8)
                displayed_stripe_profile[:,StartingSweepPoint:stripe_edge]=vertical_stripe_profile[:,StartingSweepPoint:stripe_edge]

                self.slmObjs[ObjIdx].WriteImageToSLM(displayed_stripe_profile,channel)
                RefSigPWR[1,sample_index,0]=self.CalulateMetric(avgframeCount=self.avgFrameCount)
                StripSweepStep[1,sample_index,0]=stripe_edge
        finally:
            self.slmObjs[ObjIdx].Clear_Display(channel)
            self.CamObjs[self.CamObjIdx].SetContinuousMode()

        RefSigPWR_log=10*np.log10(np.maximum(RefSigPWR,np.finfo(float).tiny))
        return RefSigPWR,RefSigPWR_log,StripSweepStep
    

        
        
        

    
    
    
