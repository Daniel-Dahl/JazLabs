from Lab_Equipment.Config import config 

# Python Libs
import cv2
import numpy as np
import matplotlib.pyplot as plt
import ctypes
import copy
from IPython.display import display, clear_output
import ipywidgets
import multiprocessing
import time
import scipy.io

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]

#SLM Libs
import Lab_Equipment.SLM.pyLCOS as pyLCOS
import Lab_Equipment.ZernikeModule.ZernikeModule as zernMod

#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm


#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm

# digiHolo Libs
import Lab_Equipment.digHolo.digHolo_pylibs.digholoObject as digholoLib
import Lab_Equipment.PowerMeter.PowerMeter_Thorlabs_lib as pwrMeter_lib


import  Lab_Equipment.GeneralLibs.ComplexPlotFunction as cmplxplt



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



def slmRefreshRateCalibration(slm:pyLCOS.LCOS,Cam:CamForm.GeneralCameraObject,channel="Red",
                              refreshCount=10,refreshRateMin=0,refreshRateMax=100,MeasCount=1,
                               Direction="y", imask=0,pol="H",backgroundLevel=0,strip_value=128,
                                       strip_width=10,
                                       ixCamCenter=None,iyCamCenter=None,
                                    x_half_width=None,
                                    y_half_width=None):
    
    masksize=slm.polProps[channel][pol].masksize
    
    Nx=masksize[0]
    Ny=masksize[1]
    
    y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
    x_center = slm.AllMaskProperties[channel][pol][imask].center[1]   
    

    
    
    mask_NoStrip=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=0, orientation=Direction)
    MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_NoStrip,backgroundLevel)
    mask_NoStrip_MASKTODisplay_256=np.copy(MASKTODisplay_256)
    
    mask_piStrip=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=strip_value, orientation=Direction)
    MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_piStrip,backgroundLevel)
    mask_piStrip_MASKTODisplay_256=np.copy(MASKTODisplay_256)
    
    plt.figure(100)
    plt.subplot(1,2,1)
    plt.imshow(mask_NoStrip_MASKTODisplay_256)
    plt.subplot(1,2,2)
    plt.imshow(mask_piStrip_MASKTODisplay_256)
    plt.show()
    


    refreshArr = np.linspace(refreshRateMin,refreshRateMax,refreshCount)*1e-3
    metricValues=np.zeros((MeasCount,refreshCount))
    intialpwrTracker=np.zeros((MeasCount,refreshCount))
    # CameraPowerMeterSwitch=1
    # if CameraPowerMeterSwitch==1:
    Cam.SetSingleFrameCapMode()
    timetotal_slm=0
    timetotal_cam=0
    
    
    for imeas in range(MeasCount):
        slm.GLobProps[channel].RefreshTime=100.0e-3
        # MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_NoStrip,backgroundLevel)
        start = time.perf_counter()
        slm.Write_To_Display(mask_NoStrip_MASKTODisplay_256,channel)
        elapsed = time.perf_counter() - start
        timetotal_slm+=elapsed
        start = time.perf_counter()
        Cam.GetFrame() 
        # Cam.GetFrameSingleCapture() 
        
        
        elapsed = time.perf_counter() - start
        timetotal_cam+=elapsed
        
        initalpwr=Cam.GetRelativePower(centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)
        print("Initial Power: "+str(initalpwr/Cam.GetRelativePower() ))
        for irefreshrate in range(refreshCount):
            slm.GLobProps[channel].RefreshTime=refreshArr[irefreshrate]
            # MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_piStrip,backgroundLevel)
            slm.Write_To_Display(mask_piStrip_MASKTODisplay_256,channel)
            
            pwrAfterTilt=Cam.GetRelativePower(centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)

            # MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_NoStrip,backgroundLevel)
            slm.Write_To_Display(mask_NoStrip_MASKTODisplay_256,channel)
            pwrAfterReflat=Cam.GetRelativePower(centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)


            metricValues[imeas,irefreshrate]=pwrAfterTilt/initalpwr
            intialpwrTracker[imeas,irefreshrate]=pwrAfterReflat/initalpwr
            if imeas==0:
                print(metricValues[imeas,irefreshrate])
        if imeas==0:
            plt.plot(refreshArr*1e3,metricValues[imeas,:])
            
            print(metricValues[imeas,irefreshrate])
            
    print(timetotal_slm/MeasCount)
    print(timetotal_cam/MeasCount)
        # print(imeas) 

    Cam.SetContinousFrameCapMode()
    return refreshArr,metricValues,intialpwrTracker
        
        
def slmRefreshRateCalibration_HardwareTrigger(slm:pyLCOS.LCOS,Cam:CamForm.GeneralCameraObject,channel="Red",
                            refreshCount=10,refreshRateMin=0,refreshRateMax=100,MeasCount=1,
                            Direction="y", imask=0,pol="H",backgroundLevel=0,
                                    strip_width=10,
                                    ixCamCenter=None,iyCamCenter=None,
                                    x_half_width=None,
                                    y_half_width=None):

    masksize=slm.polProps[channel][pol].masksize
    
    Nx=masksize[0]
    Ny=masksize[1]
    
    y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
    x_center = slm.AllMaskProperties[channel][pol][imask].center[1]   
    

    
    
    mask_NoStrip=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=0, orientation=Direction)
    MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_NoStrip,backgroundLevel)
    mask_NoStrip_MASKTODisplay_256=np.copy(MASKTODisplay_256)
    
    mask_piStrip=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=127, orientation=Direction)
    MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_piStrip,backgroundLevel)
    mask_piStrip_MASKTODisplay_256=np.copy(MASKTODisplay_256)
    
    plt.figure(100)
    plt.subplot(1,2,1)
    plt.imshow(mask_NoStrip_MASKTODisplay_256)
    plt.subplot(1,2,2)
    plt.imshow(mask_piStrip_MASKTODisplay_256)
    plt.show()
    


    refreshArr = np.linspace(refreshRateMin,refreshRateMax,refreshCount)*1e-3
    metricValues=np.zeros((MeasCount,refreshCount))
    intialpwrTracker=np.zeros((MeasCount,refreshCount))
    # CameraPowerMeterSwitch=1
    # if CameraPowerMeterSwitch==1:
    Cam.SetSingleFrameCapMode()
    timetotal_slm=0
    timetotal_cam=0
    
    Cam.SetTriggerMode(1)
    for imeas in range(MeasCount):
        print(imeas)
        slm.GLobProps[channel].RefreshTime=100.0e-3
        # MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_NoStrip,backgroundLevel)
        # start = time.perf_counter()
        slm.Write_To_Display(mask_NoStrip_MASKTODisplay_256,channel)
        # elapsed = time.perf_counter() - start
        # timetotal_slm+=elapsed
        # # start = time.perf_counter()
        # # # Cam.GetFrame() 
        # # Cam.GetFrameSingleCapture() 
        
        
        # # elapsed = time.perf_counter() - start
        # # timetotal_cam+=elapsed
        fameInital=np.copy(Cam.GetFrame(ExtTriggerImageIdx=0))
        # # print(fameInital.shape)
        # # plt.figure(100)
        # # plt.subplot(1,1,1)
        # # plt.imshow(fameInital)
        # # plt.show()
        initalpwr=Cam.GetRelativePower(fameInital,centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)

        # initalpwr=Cam.GetRelativePower(frame=fameInital)    
        Cam.SetTriggerMode(1)# this is to clear the buffer as the set trigger mode has that automatically
        
        # print("Initial Power: "+str(initalpwr/Cam.GetRelativePower() ))
        for irefreshrate in range(refreshCount):
            slm.GLobProps[channel].RefreshTime=refreshArr[irefreshrate]
            # MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_piStrip,backgroundLevel)
            slm.Write_To_Display(mask_NoStrip_MASKTODisplay_256,channel)
            
            # slm.Write_To_Display(mask_piStrip_MASKTODisplay_256,channel)
            

            # MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask_NoStrip,backgroundLevel)
            # slm.Write_To_Display(mask_NoStrip_MASKTODisplay_256,channel)
            slm.Write_To_Display(mask_piStrip_MASKTODisplay_256,channel)
            # dumbby=Cam.GetFrame(ExtTriggerImageIdx=1)
            # copy.deepcopy(dumbby,fameWithOutSpot)
            fameWithOutSpot=np.copy(Cam.GetFrame(ExtTriggerImageIdx=1))
            pwrAfterTilt=Cam.GetRelativePower(fameWithOutSpot,centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)
            
            # pwrAfterTilt=Cam.GetRelativePower(fameWithOutSpot)
            # print(pwrAfterTilt)
            # print("tilt")
            # time.sleep(2)
            
            fameWithSpot=np.copy(Cam.GetFrame(ExtTriggerImageIdx=0))
            # print("tiltoff")
            pwrAfterReflat=Cam.GetRelativePower(fameWithSpot,centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)
            # pwrAfterReflat=Cam.GetRelativePower(fameWithSpot)
            # print(pwrAfterReflat)
            # time.sleep(2)
            
            
            # pwrAfterTilt=Cam.GetRelativePower(fameWithOutSpot)
            # print(pwrAfterTilt)
            
            # pwrAfterReflat=Cam.GetRelativePower(fameWithSpot)
            # print(pwrAfterTilt)
            
            Cam.SetTriggerMode(1)# this is to clear the buffer as the set trigger mode has that automatically


            # metricValues[imeas,irefreshrate]=pwrAfterReflat/pwrAfterTilt#pwrAfterTilt/pwrAfterReflat
            metricValues[imeas,irefreshrate]=pwrAfterTilt/pwrAfterReflat#pwrAfterTilt/pwrAfterReflat
            
            intialpwrTracker[imeas,irefreshrate]=pwrAfterReflat/initalpwr
            if imeas==0:
                print(metricValues[imeas,irefreshrate])
        if imeas==0:
            plt.plot(refreshArr*1e3,metricValues[imeas,:])
            
            print(metricValues[imeas,irefreshrate])
            
    print(timetotal_slm/MeasCount)
    print(timetotal_cam/MeasCount)
        # print(imeas) 
    Cam.SetTriggerMode(0)
    Cam.SetContinousFrameCapMode()
    return refreshArr,metricValues,intialpwrTracker
    



            
    # if CameraPowerMeterSwitch==0:
    #     tiltvalue=0.030

    #     InitalTiltx=slm.AllMaskProperties["Red"]["H"][0].zernike.zern_coefs[1] 
    #     InitalTilty=slm.AllMaskProperties["Red"]["H"][0].zernike.zern_coefs[2]
    #     initalpwr=pwrMeter.GetPower()

    #     for irefreshrate in range(refreshCount):
    #         slm.GLobProps["Red"].RefreshTime=refreshArr[irefreshrate]
    #         slm.AllMaskProperties["Red"]["H"][0].zernike.zern_coefs[1] = tiltvalue
    #         slm.AllMaskProperties["Red"]["H"][0].zernike.zern_coefs[2] = tiltvalue
    #         slm.setmask(channel="Red",imode=0)
    #         pwrAfterTilt=pwrMeter.GetPower()

    #         slm.AllMaskProperties["Red"]["H"][0].zernike.zern_coefs[1] = InitalTiltx
    #         slm.AllMaskProperties["Red"]["H"][0].zernike.zern_coefs[2] = InitalTilty
    #         slm.setmask(channel="Red",imode=0)

    #         metricValues[irefreshrate]=pwrAfterTilt/initalpwr
    #         print(metricValues[irefreshrate])

    # plt.plot(refreshArr,metricValues)