import copy
from typing import Iterable, List, Optional, Sequence, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np

import JazLabs.hardware.Cameras.Camera_Client as CamForm
import JazLabs.hardware.digHolo.digHolo_pylibs.digholoObject as digholoMod

DigiholoLike = object


def _as_list(objs: Union[object, Sequence[object]]) -> List[object]:
    if isinstance(objs, (list, tuple)):
        return list(objs)
    return [objs]


def ProcessBatchOfFrames(
    digiholoObj: DigiholoLike,
    FramesIn=None,
    DoAutoAlign=True,
    AverageBatch=False,
    batchCount=1,
    AvgCount=1,
    maxMG=1,
    goalIdx=digholoMod.digholoMetrics.IL,
    fftWindowSizeY=256,
    fftWindowSizeX=256,
    FFTRadius=0.2,
    basisType=0,
    digholoThreadObj=None,
    plotData=False,
):
    digiholoObj.digholoProperties["FFTRadius"] = FFTRadius
    digiholoObj.digholoProperties["fftWindowSizeY"] = fftWindowSizeY
    digiholoObj.digholoProperties["fftWindowSizeX"] = fftWindowSizeX
    digiholoObj.digholoProperties["maxMG"] = maxMG
    digiholoObj.digholoProperties["basisType"] = basisType
    digiholoObj.digholoProperties["goalIdx"] = goalIdx

    frames = copy.deepcopy(FramesIn)
    coefs, metrics = digiholoObj.digHolo_AutoAlign(
        frames,
        AverageBatch=AverageBatch,
        batchCount=batchCount,
        AvgCount=AvgCount,
        DoAutoAlgin=DoAutoAlign,
    )
    coefs_image, metrics_text = digiholoObj.GetCoefAndMetricsForOutput()

    if plotData:
        fullimage, _, _ = digiholoObj.GetViewport_arr(frames)
        plt.figure("digholoout", figsize=(8, 4))
        plt.subplot(1, 2, 1)
        plt.imshow(fullimage)
        plt.subplot(1, 2, 2)
        plt.imshow(coefs_image)
        plt.show()

    print(metrics_text)

    if digholoThreadObj is not None:
        digholoThreadObj.Set_digholoWindowProps(digiholoObj.digholoProperties)

    return coefs, metrics




