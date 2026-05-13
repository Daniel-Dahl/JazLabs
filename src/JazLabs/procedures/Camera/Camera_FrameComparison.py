import copy
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np

import JazLabs.hardware.Cameras.Camera_Client as CamForm
import JazLabs.hardware.digHolo.digHolo_pylibs.digholoObject as digholoMod


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



def FrameComparisonAcrossWavelengths(
    frame_wavelength_NoRef,
    darkframe,
    iwaveIdxSelect=0,
    ApatureFrame=False,
    xcentre=None,
    ycentre=None,
    x_half_width=None,
    y_half_width=None,
    plotData=False,
):
    wavelenCount, modeCount, Ny, Nx = frame_wavelength_NoRef.shape
    frameOverlap = np.empty((wavelenCount, modeCount), dtype=np.float32)
    for imode in range(modeCount):
        if ApatureFrame:
            frame1, _ = CamForm.ApatrureFrame(
                frame_wavelength_NoRef[iwaveIdxSelect, imode, :, :] - darkframe,
                centre=[xcentre, ycentre],
                x_half_width=x_half_width,
                y_half_width=y_half_width,
                show_plot=False,
            )
        else:
            frame1 = frame_wavelength_NoRef[iwaveIdxSelect, imode, :, :] - darkframe
        for iwave in range(wavelenCount):
            if ApatureFrame:
                frame2, _ = CamForm.ApatrureFrame(
                    frame_wavelength_NoRef[iwave, imode, :, :] - darkframe,
                    centre=[xcentre, ycentre],
                    x_half_width=x_half_width,
                    y_half_width=y_half_width,
                    show_plot=False,
                )
            else:
                frame2 = frame_wavelength_NoRef[iwave, imode, :, :] - darkframe
            numerator = np.sum(frame1 * frame2)
            denominator = np.sqrt(np.sum(frame1**2) * np.sum(frame2**2))
            frameOverlap[iwave, imode] = numerator / denominator if denominator != 0 else 0.0
    if plotData:
        modedeepCount = modeCount
        plt.figure(figsize=(10, 5))
        plt.subplot(1, 2, 1)
        for imode in range(modedeepCount):
            if imode == 0:
                plt.plot(frameOverlap[:, imode], ".", label=f"Mode {imode}")
            else:
                plt.plot(frameOverlap[:, imode])
        plt.subplot(1, 2, 2)
        plt.imshow(frameOverlap)
        plt.colorbar()
    return frameOverlap



