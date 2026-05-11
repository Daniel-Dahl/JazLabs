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


import pwi_inst.utils.camera_utils as cam_utils
import pwi_inst.hardware.SLM.SLM_ServerLinux as SLM_Serverlib
import pwi_inst.hardware.Cameras.Camera_Client as CamClientlib
import pwi_inst.hardware.SLM.PhaseMaskClass as PhaseMaskClass





# def ProcessFramesFromPhaseCal(FrameBuffer,digholoObj:digholoLib.digholoObject, MaskNum,FFTRadiusIn=0.2,wavelength=1550e-9,Nx=256,Ny=256,CampixelSize=30e-6):
#     digholoObj.digholoProperties["FFTRadius"]=FFTRadiusIn
#     digholoObj.digholoProperties["fftWindowSizeX"]=Nx
#     digholoObj.digholoProperties["fftWindowSizeY"]=Ny
#     digholoObj.digholoProperties["wavelenght"]=wavelength



#     Frame_Initial= copy.deepcopy(FrameBuffer[-1,:,:])
#     digholoObj.digHolo_AutoAlign(Frame_Initial)
#     #Display he initial frame
#     Fullimage ,ViewPortRGB_cam,WindowString=digholoObj.GetViewport_arr(Frame_Initial)
#     plt.figure()
#     plt.imshow(Fullimage)
#     plt.show()
    
#     digholoObj.digHolo_ProcessBatch(FrameBuffer[0:-1,:,:])
#     Fields=digholoObj.digHolo_GetFields()
    
#     NewFileForBatch="phaseCal_" + str(int(wavelength*1e9)) + "MaskNum"+str(MaskNum)
#     digholoObj.SaveBatchFile(NewFileForBatch,FrameBuffer[0:-1,:,:],True)

#     return Fields,WindowString
    

#NOTE when you do a phase calibration you want to start at the 0 gray scale and move up through it. 
# If you dont do this the calibration has a lot of trouble when it flick around from 255 to 0 grey level
# Physically it really shouldnt matter but the SLM really hate going from 255 to 0 so makes a little bit of
# scence from that perspective. This took a week of my time as the phase cals where just absoultely terrible 
# that where coming out.
# Daniel 10min from writting this comment:
# Past Daniel is a absoulte idiot if you think about it for like 10 seconds you were doing
# the phase cal wrong. you have to start it off at 0 grey level and move it up to 255 as this is the
# whole point of the calibration. you are a idiot. I am leaving the comment here so you can feel 
# the shame every time you look at this code.
def PhaseCalibration(slm:PhaseMaskClass.PhaseMaskObject,channel,CamObj:CamClientlib.CameraClient,Direction="x", imask=0,pol="V",backgroundLevel=0):
    
    # CamObj.SetSingleFrameCapMode()
    phaseLevels=256
    masksize=slm.polProps[channel][pol].masksize
    
    Nx=masksize[0]
    Ny=masksize[1]
    
    y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
    x_center = slm.AllMaskProperties[channel][pol][imask].center[1]   
    
    FrameBuffer = np.zeros((phaseLevels+1, CamObj.frame_shape[0], CamObj.frame_shape[1]), dtype=np.float32)

    MASK=np.zeros((Nx,Ny),dtype=np.uint8)
    for level in range(phaseLevels):
        print(level, end=' ')
        # Create phase wrap 
        # MASK[:,0:int((Nx/2))]=128
        # MASK[:,int((Nx/2)):Nx]=level
        # MASK[0:int((Ny/2)),:]=128
        # MASK[int((Ny/2)):Ny,:]=level
        if(Direction=="y"):
            MASK[0:int((Ny/2)),:]=128
            MASK[int((Ny/2)):Ny,:]=level
        elif(Direction=="x"):
            MASK[:,0:int((Nx/2))]=128
            MASK[:,int((Nx/2)):Nx]=level
            
        MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, MASK,backgroundLevel)

        slm.Write_To_Display(MASKTODisplay_256,channel)
        
        FrameBuffer[level,:,:]=CamObj.GetFrame(True)
        
    slm.LCOS_Clean(channel)
    
    FrameBuffer[-1,:,:]=CamObj.GetFrame(True)
    
    #Turn continous mode back on for the camera
    # CamObj.SetContinousFrameCapMode(CamObj.Exposure)


    return FrameBuffer

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

# def PhaseCalibration_BinaryDiffraction_PwrMeter(slm:PhaseMaskClass.PhaseMaskObject,channel,PwrMeter:pwrMeter_lib.PowerMeterObj,
#                                        Direction="x", imask=0,pol="V",backgroundLevel=0,
#                                        strip_width=10):
#     phaseLevels=256
#     masksize=slm.polProps[channel][pol].masksize
    
#     Nx=masksize[0]
#     Ny=masksize[1]
    
#     y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
#     x_center = slm.AllMaskProperties[channel][pol][imask].center[1]   
    
#     PowerValues = np.zeros((phaseLevels+1), dtype=np.float32)

#     mask=np.zeros((Nx,Ny),dtype=np.uint8)
#     for level in range(0,phaseLevels,1):
#         print(level, end=' ')
#         mask=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=level, orientation=Direction)
            
#         MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask,backgroundLevel)

#         slm.Write_To_Display(MASKTODisplay_256,channel)
#         PowerValues[level]=PwrMeter.GetPower()
        
#     slm.LCOS_Clean(channel)
#     PowerValues[-1]=PwrMeter.GetPower()

#     return PowerValues
def PhaseCalibration_BinaryDiffraction_Cam_zerothOrder(slm:PhaseMaskClass.PhaseMaskObject,channel,Cam:CamClientlib.CameraClient,
                                       Direction="x", imask=0,pol="H",backgroundLevel=0,
                                       strip_width=10,camframeAvg=1,
                                        ixCamCenter=None,iyCamCenter=None,
                                    x_half_width=None,
                                    y_half_width=None):
    # Cam.SetSingleFrameCapMode()
    phaseLevels=256
    masksize=slm.polProps[channel][pol].masksize
    
    Nx=masksize[0]
    Ny=masksize[1]
    
    y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
    x_center = slm.AllMaskProperties[channel][pol][imask].center[1]   
    
    PowerValues = np.zeros((phaseLevels+1), dtype=np.float32)

    mask=np.zeros((Nx,Ny),dtype=np.uint8)
    for level in range(0,phaseLevels,1):
        print(level, end=' ')
        mask=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=level, orientation=Direction)
            
        MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask,backgroundLevel)

        slm.Write_To_Display(MASKTODisplay_256,channel)
        frame=Cam.GetFrame() 
        PowerValues[level] = cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)
        
        # PowerValues[level]=Cam.GetRelativePower(centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width,avgCount=camframeAvg)
    
        
    slm.Clear_Display(channel)
    frame=Cam.GetFrame() 
    PowerValues[-1] = cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)
        
    # PowerValues[-1]=Cam.GetRelativePower(centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width,avgCount=camframeAvg)
    # Cam.SetContinousFrameCapMode(Cam.Exposure)
    
    return PowerValues
def PhaseCalibration_BinaryDiffraction_Cam_0thAnd1stOrder(slm:PhaseMaskClass.PhaseMaskObject,channel,Cam:CamClientlib.CameraClient,
                                       Direction="x", imask=0,pol="H",backgroundLevel=0,
                                       strip_width=10,camframeAvg=1,
                                        ixCamCenter0th=None,iyCamCenter0th=None,
                                        ixCamCenter_plus1st=None,iyCamCenter_plus1st=None,
                                        ixCamCenter_minus1st=None,iyCamCenter_minus1st=None,
                                    x_half_width=None,
                                    y_half_width=None):
    # Cam.SetSingleFrameCapMode()
    phaseLevels=256
    masksize=slm.polProps[channel][pol].masksize
    
    Nx=masksize[0]
    Ny=masksize[1]
    
    y_center = slm.AllMaskProperties[channel][pol][imask].center[0]
    x_center = slm.AllMaskProperties[channel][pol][imask].center[1]   
    
    PowerValues0th = np.zeros((phaseLevels+1), dtype=np.float32)
    PowerValues_plus1st = np.zeros((phaseLevels+1), dtype=np.float32)
    PowerValues_minus1st = np.zeros((phaseLevels+1), dtype=np.float32)
    

    mask=np.zeros((Nx,Ny),dtype=np.uint8)
    for level in range(0,phaseLevels,1):
        print(level, end=' ')
        mask=periodic_strip_mask_1(mask_shape=[Nx,Ny], strip_width=strip_width, strip_value=level, orientation=Direction)
            
        MASKTODisplay_256=slm.Draw_Single_Mask( x_center, y_center, mask,backgroundLevel)

        slm.Write_To_Display(MASKTODisplay_256,channel)
        # _=Cam.GetRelativePower(centre=[ixCamCenter0th,iyCamCenter0th],x_half_width=x_half_width,y_half_width=y_half_width,avgCount=camframeAvg)
        frame=Cam.GetFrame() 
        PowerValues0th[level] = cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter0th,iyCamCenter0th],x_half_width=x_half_width,y_half_width=y_half_width)
        PowerValues_plus1st[level]= cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter_plus1st,iyCamCenter_plus1st],x_half_width=x_half_width,y_half_width=y_half_width)
        PowerValues_minus1st[level]= cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter_minus1st,iyCamCenter_minus1st],x_half_width=x_half_width,y_half_width=y_half_width)
        
        # PowerValues0th[level]=Cam.GetRelativePower(centre=[ixCamCenter0th,iyCamCenter0th],x_half_width=x_half_width,y_half_width=y_half_width,avgCount=camframeAvg)
        # PowerValues_plus1st[level]=Cam.GetRelativePower(centre=[ixCamCenter_plus1st,iyCamCenter_plus1st],x_half_width=x_half_width,y_half_width=y_half_width,avgCount=camframeAvg)
        # PowerValues_minus1st[level]=Cam.GetRelativePower(centre=[ixCamCenter_minus1st,iyCamCenter_minus1st],x_half_width=x_half_width,y_half_width=y_half_width,avgCount=camframeAvg)
        

        
    slm.Clear_Display(channel)
    frame=Cam.GetFrame() 
    
    PowerValues0th[level]=cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter0th,iyCamCenter0th],x_half_width=x_half_width,y_half_width=y_half_width)
    PowerValues_plus1st[level]=cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter_plus1st,iyCamCenter_plus1st],x_half_width=x_half_width,y_half_width=y_half_width)
    PowerValues_minus1st[level]=cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter_minus1st,iyCamCenter_minus1st],x_half_width=x_half_width,y_half_width=y_half_width)
    
    
    # Cam.SetContinousFrameCapMode(Cam.Exposure)
    
    return PowerValues0th,PowerValues_plus1st,PowerValues_minus1st

