import copy
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np

from JazLabs.hardware.MotorisedStages.Luminos.LuminosStage import Axes
from JazLabs.utils.camera_utils import get_relative_power


CameraLike = object
SLMLike = object
DigiholoLike = object
PowerMeterLike = object
LaserLike = object


def _as_list(objs: Union[object, Sequence[object]]) -> List[object]:
    if isinstance(objs, (list, tuple)):
        return list(objs)
    return [objs]


def _get_camera_frame(camera: CameraLike) -> np.ndarray:
    try:
        return camera.GetFrame(ConvertToFloat32=True)
    except TypeError:
        frame = camera.GetFrame()
        return frame.astype(np.float32, copy=False)

def _get_mode_indices(slm_obj: SLMLike, pol: str, slm_channel: Optional[int], mode_count: Optional[int], mode_idx_arr):
    if slm_channel is None:
        slm_channel = slm_obj.ActiveRGBChannels[0]

    if mode_count is None:
        mode_count = slm_obj.polProps[slm_channel][pol].modeCount

    mode_start = slm_obj.polProps[slm_channel][pol].modeCount_start
    mode_step = slm_obj.polProps[slm_channel][pol].modeCount_step

    if mode_idx_arr is not None:
        mode_indices = list(mode_idx_arr)
    else:
        mode_indices = list(range(mode_start, mode_count, mode_step))

    return slm_channel, mode_indices


def SLMMaskChangeGetFrame(
    slm_obj: SLMLike,
    cam_objs: Union[CameraLike, Sequence[CameraLike]],
    pol: str = "H",
    slm_channel: Optional[int] = None,
    mode_count: Optional[int] = None,
    avg_frame_count: int = 1,
    mode_idx_arr: Optional[Iterable[int]] = None,
) -> np.ndarray:
    cameras = _as_list(cam_objs)
    slm_channel, mode_indices = _get_mode_indices(slm_obj, pol, slm_channel, mode_count, mode_idx_arr)

    for cam in cameras:
        cam.SetSoftwareTriggerMode()

    first_frame = _get_camera_frame(cameras[0])
    ny, nx = first_frame.shape

    frames = np.empty((len(cameras), len(mode_indices) * avg_frame_count, ny, nx), dtype=np.float32)

    iframe = 0
    for mode_idx in mode_indices:
        slm_obj.setmask(slm_channel, mode_idx)
        for _ in range(avg_frame_count):
            for icam, cam in enumerate(cameras):
                frames[icam, iframe, :, :] = _get_camera_frame(cam)
            iframe += 1

    for cam in cameras:
        cam.SetContinuousMode()

    return frames


def SLMMaskChangeWavelengthChangeGetFrame(
    laser: LaserLike,
    slm_obj: SLMLike,
    cam_objs: Union[CameraLike, Sequence[CameraLike]],
    pol: str = "H",
    slm_channel: Optional[int] = None,
    mode_count: Optional[int] = None,
    avg_frame_count: int = 1,
    mode_idx_arr: Optional[Iterable[int]] = None,
    wavelength_count: int = 100,
    min_wavelength: float = 1465,
    max_wavelength: float = 1665,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    cameras = _as_list(cam_objs)
    slm_channel, mode_indices = _get_mode_indices(slm_obj, pol, slm_channel, mode_count, mode_idx_arr)

    for cam in cameras:
        cam.SetSoftwareTriggerMode()

    first_frame = _get_camera_frame(cameras[0])
    ny, nx = first_frame.shape

    frames_wavelength = np.empty(
        (len(cameras), wavelength_count, len(mode_indices) * avg_frame_count, ny, nx), dtype=np.float32
    )

    wavelength_set_values = np.linspace(min_wavelength, max_wavelength, wavelength_count)
    wavelength_get_values = np.zeros(wavelength_count, dtype=np.float64)

    for iwave, wavelength in enumerate(wavelength_set_values):
        if hasattr(laser, "set_wavelength_nm"):
            wavelength_get_values[iwave]= float(laser.set_wavelength_nm(wavelength))
        else:
            raise AttributeError("Laser object must implement set_wavelength_nm(...)")

        iframe = 0
        for mode_idx in mode_indices:
            slm_obj.setmask(slm_channel, mode_idx)
            for _ in range(avg_frame_count):
                for icam, cam in enumerate(cameras):
                    frames_wavelength[icam, iwave, iframe, :, :] = _get_camera_frame(cam)
                iframe += 1

    for cam in cameras:
        cam.SetContinuousMode()

    return frames_wavelength, wavelength_set_values, wavelength_get_values


def WavelengthChangeGetFrame(
    laser: LaserLike,
    cam_objs: Union[CameraLike, Sequence[CameraLike]],
    avg_frame_count: int = 1,
    wavelength_count: int = 100,
    min_wavelength: float = 1465,
    max_wavelength: float = 1665,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    cameras = _as_list(cam_objs)

    for cam in cameras:
        cam.SetSoftwareTriggerMode()
        

    first_frame = _get_camera_frame(cameras[0])
    ny, nx = first_frame.shape

    frames_wavelength = np.empty((len(cameras), wavelength_count, avg_frame_count, ny, nx), dtype=np.float32)

    wavelength_set_values = np.linspace(min_wavelength, max_wavelength, wavelength_count)
    wavelength_get_values = np.zeros(wavelength_count, dtype=np.float64)

    for iwave, wavelength in enumerate(wavelength_set_values):
        if hasattr(laser, "set_wavelength_nm"):
            wavelength_get_values[iwave]= float(laser.set_wavelength_nm(wavelength))
        else:
            raise AttributeError("Laser object must implement set_wavelength_nm(...)")
        for iframe in range(avg_frame_count):
            for icam, cam in enumerate(cameras):
                frames_wavelength[icam, iwave, iframe, :, :] = _get_camera_frame(cam)

    for cam in cameras:
        cam.SetContinuousMode()

    return frames_wavelength, wavelength_set_values, wavelength_get_values


def SLMMaskChangeGetPower(
    pwr_meter_input_mode: PowerMeterLike,
    pwr_meter_gate_mode: PowerMeterLike,
    slm_obj: SLMLike,
    avg_power_count: int = 50,
    pol: str = "H",
    slm_channel: Optional[int] = None,
    mode_count: Optional[int] = None,
    mode_idx_arr: Optional[Iterable[int]] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    slm_channel, mode_indices = _get_mode_indices(slm_obj, pol, slm_channel, mode_count, mode_idx_arr)

    power_arr_input_modes = np.zeros(len(mode_indices), dtype=np.float64)
    power_arr_gate_modes = np.zeros(len(mode_indices), dtype=np.float64)

    for i, mode_idx in enumerate(mode_indices):
        slm_obj.setmask(slm_channel, mode_idx)

        power_avg_input = 0.0
        power_avg_gate = 0.0
        for _ in range(avg_power_count):
            power_avg_input += pwr_meter_input_mode.GetPower()
            power_avg_gate += pwr_meter_gate_mode.GetPower()

        power_arr_input_modes[i] = power_avg_input / avg_power_count
        power_arr_gate_modes[i] = power_avg_gate / avg_power_count

    return power_arr_input_modes, power_arr_gate_modes






def LuminosXYSnakeScanGetFrameMetrics(
    stage_obj,
    cam_obj,
    start_x: Optional[float] = None,
    start_y: Optional[float] = None,
    step_away_from_start_x: float = 200,
    step_away_from_start_y: float = 200,
    step_count_x: int = 10,
    step_count_y: int = 10,
    mount_pos_no_feature_x: Optional[float] = None,
    mount_pos_no_feature_y: Optional[float] = None,
    roi_half_width_ref: int = 5,
    roi_half_width_scan: int = 32,
    flux_floor: float = 0.5,
    lam: float = 5.0,
    plot_progress: bool = False,
):
    if step_count_x < 1 or step_count_y < 1:
        raise ValueError("step_count_x and step_count_y must both be >= 1.")

    stage_positions = stage_obj.Get_all_stage_Positions()
    if start_x is None:
        start_x = float(stage_positions[Axes.X])
    if start_y is None:
        start_y = float(stage_positions[Axes.Y])

    x_positions = np.linspace(
        start_x - step_away_from_start_x,
        start_x + step_away_from_start_x,
        step_count_x,
    )
    y_positions = np.linspace(
        start_y - step_away_from_start_y,
        start_y + step_away_from_start_y,
        step_count_y,
    )

    grid_points = np.zeros((step_count_y, step_count_x, 2), dtype=float)
    for iy in range(step_count_y):
        if iy % 2 == 0:
            grid_points[iy, :, 0] = x_positions
        else:
            grid_points[iy, :, 0] = x_positions[::-1]
        grid_points[iy, :, 1] = y_positions[iy]

    if mount_pos_no_feature_x is not None:
        stage_obj.Set_Single_Stage_State_abs(Axes.X, mount_pos_no_feature_x)
    if mount_pos_no_feature_y is not None:
        stage_obj.Set_Single_Stage_State_abs(Axes.Y, mount_pos_no_feature_y)

    ref_frame = _get_camera_frame(cam_obj)
    ref_centre = np.unravel_index(np.nanargmax(ref_frame), ref_frame.shape)
    ref_flux = get_relative_power(
        frame=ref_frame,
        centre=[ref_centre[0], ref_centre[1]],
        x_half_width=roi_half_width_ref,
        y_half_width=roi_half_width_ref,
        avg_count=1,
    )
    ref_corr_temp = ref_frame.astype(float).ravel()
    ref_corr_temp = ref_corr_temp - np.mean(ref_corr_temp)

    total_scan_count = step_count_x * step_count_y
    all_frames = np.zeros((total_scan_count, ref_frame.shape[0], ref_frame.shape[1]), dtype=ref_frame.dtype)
    metric_matrix_flux = np.zeros((step_count_y, step_count_x), dtype=float)
    metric_matrix_corr = np.zeros((step_count_y, step_count_x), dtype=float)
    metric_matrix_weighted = np.zeros((step_count_y, step_count_x), dtype=float)

    icount = 0
    for iy in range(step_count_y):
        ypos = grid_points[iy, 0, 1]
        stage_obj.Set_Single_Stage_State_abs(Axes.Y, ypos)

        for ix in range(step_count_x):
            idx_x = ix if iy % 2 == 0 else step_count_x - 1 - ix

            xpos = grid_points[iy, ix, 0]
            stage_obj.Set_Single_Stage_State_abs(Axes.X, xpos)

            frame = _get_camera_frame(cam_obj)
            all_frames[icount] = frame

            flux = get_relative_power(
                frame=frame,
                centre=[ref_centre[0], ref_centre[1]],
                x_half_width=roi_half_width_scan,
                y_half_width=roi_half_width_scan,
                avg_count=1,
            )

            frame_corr_temp = frame.astype(float).ravel()
            frame_corr_temp = frame_corr_temp - np.mean(frame_corr_temp)
            denom = np.sqrt(np.sum(frame_corr_temp**2) * np.sum(ref_corr_temp**2))
            corr = 1.0 if denom == 0 else np.sum(frame_corr_temp * ref_corr_temp) / denom

            flux_norm = flux / (ref_flux + 1e-12)
            penalty = lam * np.maximum(0.0, flux_floor - flux_norm) ** 2
            metric_weighted = corr + penalty

            metric_matrix_corr[iy, idx_x] = corr
            metric_matrix_flux[iy, idx_x] = flux
            metric_matrix_weighted[iy, idx_x] = metric_weighted

            if plot_progress:
                plt.figure("scan_metrics", figsize=(12, 4))
                plt.clf()
                plt.subplot(1, 3, 1)
                plt.imshow(metric_matrix_flux)
                plt.title("Flux")
                plt.colorbar()
                plt.subplot(1, 3, 2)
                plt.imshow(metric_matrix_corr)
                plt.title("Correlation")
                plt.colorbar()
                plt.subplot(1, 3, 3)
                plt.imshow(metric_matrix_weighted)
                plt.title("Weighted")
                plt.colorbar()
                plt.tight_layout()
                plt.pause(0.001)

            icount += 1

    flux_min_idx = np.unravel_index(np.argmin(metric_matrix_flux), metric_matrix_flux.shape)
    corr_min_idx = np.unravel_index(np.argmin(metric_matrix_corr), metric_matrix_corr.shape)
    weighted_min_idx = np.unravel_index(np.argmin(metric_matrix_weighted), metric_matrix_weighted.shape)

    stage_pos_flux_min = grid_points[flux_min_idx]
    stage_pos_corr_min = grid_points[corr_min_idx]
    stage_pos_weighted_min = grid_points[weighted_min_idx]

    return {
        "grid_points": grid_points,
        "ref_frame": ref_frame,
        "ref_centre": ref_centre,
        "all_frames": all_frames,
        "metric_matrix_flux": metric_matrix_flux,
        "metric_matrix_corr": metric_matrix_corr,
        "metric_matrix_weighted": metric_matrix_weighted,
        "flux_metric_min_idx": flux_min_idx,
        "corr_metric_min_idx": corr_min_idx,
        "weighted_metric_min_idx": weighted_min_idx,
        "stage_pos_flux_metric_min": stage_pos_flux_min,
        "stage_pos_corr_metric_min": stage_pos_corr_min,
        "stage_pos_weighted_metric_min": stage_pos_weighted_min,
    }

def ChangeOpticalSwitchGetFrame():
    # GetBatchOfFrames(self,SLMObjIdx=0,pol='H',CamObjIdx=[0],slmChannel=None,modeCount=None,AvgFrameCount=1,modeIdxArr=None):
    AvgFrameCount=1  
    modeCount=6
    wavelengthCount=40
    wavelenMin=1520e-9
    wavelenMax=1600e-9
    # Laser.set_power_mw(0.5)
    Wavelengths=np.linspace(wavelenMin,wavelenMax,wavelengthCount)    
        

    frames_wavelengths_modes=np.empty((wavelengthCount,modeCount*AvgFrameCount,Cam.CamObject.FrameHeight.value,Cam.CamObject.FrameWidth.value),dtype=np.float32)
    # frames_wavelengths_modes_superposition=np.empty((wavelengthCount,modeCount*AvgFrameCount,Cam.CamObject.FrameHeight.value,Cam.CamObject.FrameWidth.value),dtype=np.float32)
    # frame_wavelength_NoRef=np.empty((wavelengthCount,modeCount*AvgFrameCount,Cam.CamObject.FrameHeight.value,Cam.CamObject.FrameWidth.value),dtype=np.float32)
    imodeStart=1
    iframe=0
    Cam.CamObject.SetSingleFrameCapMode()
    for iwave in range(wavelengthCount):
        Laser.set_wavelength_nm(Wavelengths[iwave]*1e9)
        time.sleep(2)
        iframe =0
        for imode in range(modeCount):
            ichan=imode+imodeStart
            OpticalSwitch.set_channel(ichan)
            for iavg in range(AvgFrameCount):
                frames_wavelengths_modes[iwave,iframe,:,:]=Cam.CamObject.GetFrame(ConvertToFloat32=True)
                iframe+=1
    Cam.CamObject.SetContinousFrameCapMode()