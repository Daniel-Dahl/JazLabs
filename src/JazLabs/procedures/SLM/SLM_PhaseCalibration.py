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
import json
from pathlib import Path
from matplotlib.patches import Rectangle

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]


import JazLabs.utils.camera_utils as cam_utils
import JazLabs.hardware.Cameras.Camera_Client as CamClientlib
import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass





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


def DisplayBinaryDiffractionPattern(slm:PhaseMaskClass.PhaseMaskObject,channel,
                                    Direction="y",strip_width=25,strip_value=128):
    """Display a full-SLM binary grating for locating diffraction orders."""
    slm_height=int(slm.slmHeigth)
    slm_width=int(slm.slmWidth)
    binary_pattern=periodic_strip_mask_1(
        mask_shape=[slm_height,slm_width],
        strip_width=strip_width,
        strip_value=strip_value,
        orientation=Direction,
    )
    slm.WriteImageToSLM(binary_pattern,channel)
    return binary_pattern


def CaptureTriggeredAverageFrame(Cam:CamClientlib.CameraClient,frame_count=1):
    """Capture and average frames while the camera is in software-trigger mode."""
    if frame_count < 1:
        raise ValueError("frame_count must be at least 1")

    averaged_frame=None
    for frame_index in range(frame_count):
        Cam.FireSoftwareTrigger()
        frame=np.asarray(Cam.GetFrame(),dtype=float)
        if averaged_frame is None:
            averaged_frame=np.zeros_like(frame,dtype=float)
        averaged_frame+=frame

    return averaged_frame/frame_count


def SelectDiffractionOrderCenters(frame,order_labels=("0th","+1st","-1st")):
    """Select diffraction orders using a notebook-friendly click callback.

    The returned dictionary is filled as the user clicks the displayed figure.
    This non-blocking behaviour lets Jupyter process the browser mouse events.
    """
    if str(plt.get_backend()).lower() == "agg":
        raise RuntimeError(
            "Interactive spot selection requires an interactive Matplotlib backend. "
            "Run '%matplotlib widget' before importing matplotlib.pyplot, then rerun "
            "this cell."
        )

    if len(order_labels) == 0:
        raise ValueError("At least one diffraction-order label is required")

    figure,axis=plt.subplots(figsize=(8,6))
    axis.imshow(frame)
    axis.set_title(
        f"Click {order_labels[0]} diffraction order "
        f"(1 of {len(order_labels)})"
    )
    axis.set_xlabel("Camera column [pixels]")
    axis.set_ylabel("Camera row [pixels]")
    order_centers={}

    def record_diffraction_order_click(event):
        if event.inaxes is not axis or event.xdata is None or event.ydata is None:
            return

        selected_index=len(order_centers)
        if selected_index >= len(order_labels):
            return

        order_label=order_labels[selected_index]
        column=int(round(event.xdata))
        row=int(round(event.ydata))
        order_centers[order_label]=[row,column]

        axis.plot(column,row,"rx")
        axis.text(column+3,row+3,order_label,color="white")
        selected_index+=1

        if selected_index == len(order_labels):
            figure.canvas.mpl_disconnect(click_connection_id)
            axis.set_title("Selection complete - run the aperture verification cell")
        else:
            next_label=order_labels[selected_index]
            axis.set_title(
                f"Click {next_label} diffraction order "
                f"({selected_index+1} of {len(order_labels)})"
            )

        figure.canvas.draw_idle()

    click_connection_id=figure.canvas.mpl_connect(
        "button_press_event",record_diffraction_order_click
    )
    plt.show()
    return order_centers


def PlotDiffractionOrderApertures(frame,order_centers,x_half_width,y_half_width):
    """Plot and label the camera apertures used for diffraction-order powers."""
    figure,axis=plt.subplots(figsize=(8,6))
    axis.imshow(frame)

    aperture_colors=("tab:orange","tab:green","tab:red")
    for aperture_index,(order_label,center) in enumerate(order_centers.items()):
        row,column=center
        aperture=Rectangle(
            (column-x_half_width,row-y_half_width),
            2*x_half_width,
            2*y_half_width,
            fill=False,
            edgecolor=aperture_colors[aperture_index%len(aperture_colors)],
            linewidth=1.5,
            label=f"{order_label}: [{row}, {column}]",
        )
        axis.add_patch(aperture)
        axis.plot(column,row,"+",color=aperture.get_edgecolor())

    axis.set_title("Diffraction-order measurement apertures")
    axis.set_xlabel("Camera column [pixels]")
    axis.set_ylabel("Camera row [pixels]")
    axis.legend()
    plt.show()
    return figure,axis


def SavePhaseCalibrationMeasurements(filename,PowerValues_0th,PowerValues_plus1st,
                                     PowerValues_minus1st,metadata=None):
    """Save raw diffraction-order measurements and acquisition metadata."""
    output_path=Path(filename)
    output_path.parent.mkdir(parents=True,exist_ok=True)
    metadata_json=json.dumps(metadata if metadata is not None else {},indent=2)
    np.savez(
        output_path,
        PowerValues_0th=np.asarray(PowerValues_0th),
        PowerValues_plus1st=np.asarray(PowerValues_plus1st),
        PowerValues_minus1st=np.asarray(PowerValues_minus1st),
        metadata_json=np.asarray(metadata_json),
    )
    return output_path


def LoadPhaseCalibrationMeasurements(filename):
    """Load raw diffraction-order measurements and their metadata."""
    with np.load(filename,allow_pickle=False) as calibration_data:
        measurements={
            "PowerValues_0th":np.copy(calibration_data["PowerValues_0th"]),
            "PowerValues_plus1st":np.copy(calibration_data["PowerValues_plus1st"]),
            "PowerValues_minus1st":np.copy(calibration_data["PowerValues_minus1st"]),
        }
        if "metadata_json" in calibration_data:
            metadata=json.loads(str(calibration_data["metadata_json"].item()))
        else:
            metadata={}
    return measurements,metadata


def PlotPhaseCalibrationMeasurements(PowerValues_0th,PowerValues_plus1st,
                                     PowerValues_minus1st,include_reference=False):
    """Plot raw powers for the zeroth and first diffraction orders."""
    if include_reference:
        levels=np.arange(len(PowerValues_0th))
        plot_slice=slice(None)
    else:
        levels=np.arange(len(PowerValues_0th)-1)
        plot_slice=slice(0,-1)

    figure,axis=plt.subplots(figsize=(9,5))
    axis.plot(levels,np.asarray(PowerValues_0th)[plot_slice],label="0th")
    axis.plot(levels,np.asarray(PowerValues_plus1st)[plot_slice],label="+1st")
    axis.plot(levels,np.asarray(PowerValues_minus1st)[plot_slice],label="-1st")
    axis.set_xlabel("SLM grey level")
    axis.set_ylabel("Camera power")
    axis.grid(alpha=0.3)
    axis.legend()
    plt.show()
    return figure,axis


def PlotPhaseCalibrationFit(fit_result,PowerValues_0th,PowerValues_plus1st,
                            PowerValues_minus1st):
    """Plot measured powers, their fitted curves, and recovered SLM phase."""
    zeroth_order=np.asarray(PowerValues_0th)[:-1]
    summed_first_orders=(
        np.asarray(PowerValues_plus1st)[:-1]
        +np.asarray(PowerValues_minus1st)[:-1]
    )

    figure,axes=plt.subplots(1,3,figsize=(15,4))
    axes[0].plot(fit_result["g"],zeroth_order,label="Measured")
    axes[0].plot(fit_result["g"],fit_result["I0_fit"],label="Fit")
    axes[0].set_title("Zeroth order")
    axes[0].set_xlabel("SLM grey level")
    axes[0].set_ylabel("Camera power")
    axes[0].grid(alpha=0.3)
    axes[0].legend()

    axes[1].plot(fit_result["g"],summed_first_orders,label="Measured")
    axes[1].plot(fit_result["g"],fit_result["I1_fit"],label="Fit")
    axes[1].set_title("Summed first orders")
    axes[1].set_xlabel("SLM grey level")
    axes[1].grid(alpha=0.3)
    axes[1].legend()

    axes[2].plot(fit_result["g"],fit_result["phi"])
    axes[2].set_title(f"Recovered phase: {fit_result['phi_end']/np.pi:.3f}π")
    axes[2].set_xlabel("SLM grey level")
    axes[2].set_ylabel("Phase [rad]")
    axes[2].grid(alpha=0.3)

    figure.tight_layout()
    plt.show()
    return figure,axes

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
                                    y_half_width=None,
                                    phaseLevels=256,
                                    Verbose=False):
    """Measure zeroth and first diffraction-order powers over SLM grey level.

    The final array element contains the cleared-SLM reference measurement.
    """
    camera_centers=(
        ixCamCenter0th,iyCamCenter0th,
        ixCamCenter_plus1st,iyCamCenter_plus1st,
        ixCamCenter_minus1st,iyCamCenter_minus1st,
    )
    if any(center is None for center in camera_centers):
        raise ValueError("All zeroth- and first-order camera centres must be provided")
    if x_half_width is None or y_half_width is None:
        raise ValueError("x_half_width and y_half_width must be provided")
    if phaseLevels < 1 or phaseLevels > 256:
        raise ValueError("phaseLevels must be between 1 and 256")
    if camframeAvg < 1:
        raise ValueError("camframeAvg must be at least 1")

    masksize=slm.polProps[channel][pol].masksize
    Nx=masksize[0]
    Ny=masksize[1]
    y_center=slm.AllMaskProperties[channel][pol][imask].center[0]
    x_center=slm.AllMaskProperties[channel][pol][imask].center[1]

    PowerValues0th=np.zeros(phaseLevels+1,dtype=np.float32)
    PowerValues_plus1st=np.zeros(phaseLevels+1,dtype=np.float32)
    PowerValues_minus1st=np.zeros(phaseLevels+1,dtype=np.float32)

    Cam.SetSoftwareTriggerMode()
    try:
        for level in range(phaseLevels):
            if Verbose and (level%16 == 0 or level == phaseLevels-1):
                print(f"Acquiring grey level {level}/{phaseLevels-1}")

            mask=periodic_strip_mask_1(
                mask_shape=[Nx,Ny],
                strip_width=strip_width,
                strip_value=level,
                orientation=Direction,
            )
            mask_to_display=slm.Draw_Single_Mask(x_center,y_center,mask,backgroundLevel)
            slm.WriteImageToSLM(mask_to_display,channel)
            frame=CaptureTriggeredAverageFrame(Cam,frame_count=camframeAvg)

            PowerValues0th[level]=cam_utils.get_relative_power(
                frame=frame,
                centre=[ixCamCenter0th,iyCamCenter0th],
                x_half_width=x_half_width,
                y_half_width=y_half_width,
            )
            PowerValues_plus1st[level]=cam_utils.get_relative_power(
                frame=frame,
                centre=[ixCamCenter_plus1st,iyCamCenter_plus1st],
                x_half_width=x_half_width,
                y_half_width=y_half_width,
            )
            PowerValues_minus1st[level]=cam_utils.get_relative_power(
                frame=frame,
                centre=[ixCamCenter_minus1st,iyCamCenter_minus1st],
                x_half_width=x_half_width,
                y_half_width=y_half_width,
            )

        slm.Clear_Display(channel)
        reference_frame=CaptureTriggeredAverageFrame(Cam,frame_count=camframeAvg)
        PowerValues0th[-1]=cam_utils.get_relative_power(
            frame=reference_frame,
            centre=[ixCamCenter0th,iyCamCenter0th],
            x_half_width=x_half_width,
            y_half_width=y_half_width,
        )
        PowerValues_plus1st[-1]=cam_utils.get_relative_power(
            frame=reference_frame,
            centre=[ixCamCenter_plus1st,iyCamCenter_plus1st],
            x_half_width=x_half_width,
            y_half_width=y_half_width,
        )
        PowerValues_minus1st[-1]=cam_utils.get_relative_power(
            frame=reference_frame,
            centre=[ixCamCenter_minus1st,iyCamCenter_minus1st],
            x_half_width=x_half_width,
            y_half_width=y_half_width,
        )
    finally:
        slm.Clear_Display(channel)
        Cam.SetContinuousMode()

    return PowerValues0th,PowerValues_plus1st,PowerValues_minus1st

