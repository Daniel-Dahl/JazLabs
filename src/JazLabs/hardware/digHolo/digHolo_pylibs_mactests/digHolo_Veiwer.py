import copy
import multiprocessing
import time
import traceback
from multiprocessing import shared_memory

import cv2
import matplotlib.pyplot as plt
import numpy as np

import JazLabs.hardware.digHolo.digHolo_pylibs.digholoObject as digholoMod
from JazLabs.hardware.Cameras.Camera_Client import CameraClient


plt.style.use("dark_background")
plt.rcParams["figure.figsize"] = [15, 15]


class digholoWindow:
    def __init__(
        self,
        CamObj=None,
        Wavelength=1550e-9,
        polCount=1,
        maxMG=1,
        fftWindowSizeX=256,
        fftWindowSizeY=256,
        FFTRadius=0.4,
        TransformMat=None,
        TransformMatrixFilename=None,
        digholoProperties=None,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        timeout_ms=5000,
        PixelSize=6.9e-6,
    ):
        super().__init__()

        manager = multiprocessing.Manager()
        self.digholo_queue = multiprocessing.Queue()

        self.host = host
        self.command_port = int(command_port)
        self.frame_pub_port = int(frame_pub_port)
        self.timeout_ms = int(timeout_ms)
        self.PixelSize = PixelSize if CamObj is None else getattr(CamObj, "PixelSize", PixelSize)

        self.shared_float = multiprocessing.Value("f", 0)
        self.shared_int = multiprocessing.Value("i", 0)
        self.shared_flag_int = multiprocessing.Value("i", 0)
        self.shared_batch_height = multiprocessing.Value("i", 0)
        self.shared_batch_width = multiprocessing.Value("i", 0)

        self.terminateDigholo = multiprocessing.Event()
        self.digiHoloPaused = multiprocessing.Event()
        self.AutoAlginFlag = multiprocessing.Event()
        self.Update_basisType_Flag = multiprocessing.Event()
        self.Set_DigholoProperties_Flag = multiprocessing.Event()
        self.Get_DigholoProperties_Flag = multiprocessing.Event()

        if TransformMatrixFilename is not None:
            basisType = 2
        elif TransformMat is not None:
            self.TransformMat = TransformMat
            basisType = 2
        else:
            basisType = 0

        self.WavelengthCount = 1
        self.batchCount = 1

        cam_client = CameraClient(
            host=self.host,
            command_port=self.command_port,
            frame_pub_port=self.frame_pub_port,
            timeout_ms=self.timeout_ms,
            client_id="digholo_window_setup",
        )
        try:
            first_frame = cam_client.GetFrame()
            self.CamFrameHeight = int(first_frame.shape[0])
            self.CamFrameWidth = int(first_frame.shape[1])
            self.Camera_dtype = np.dtype(first_frame.dtype)
        finally:
            cam_client.close()

        self.shared_batch_height.value = self.CamFrameHeight
        self.shared_batch_width.value = self.CamFrameWidth

        self.frameBufferBatch_shm = shared_memory.SharedMemory(
            create=True,
            size=int(
                self.batchCount
                * self.CamFrameHeight
                * self.CamFrameWidth
                * self.Camera_dtype.itemsize
            ),
        )
        self.frameBufferBatch_shmName = self.frameBufferBatch_shm.name
        self.FrameBuffer_SharedMem = np.ndarray(
            (self.batchCount, self.CamFrameHeight, self.CamFrameWidth),
            dtype=self.Camera_dtype,
            buffer=self.frameBufferBatch_shm.buf,
        )

        self.Metrics_shm = shared_memory.SharedMemory(
            create=True,
            size=int(digholoMod.digholoMetrics.COUNT * np.dtype(np.float32).itemsize),
        )
        self.Metrics_shmName = self.Metrics_shm.name
        self.Metrics_SharedMem = np.ndarray(
            (digholoMod.digholoMetrics.COUNT,),
            dtype=np.float32,
            buffer=self.Metrics_shm.buf,
        )

        if digholoProperties is not None:
            self.digholoWindowProperties = manager.dict(digholoProperties)
        else:
            self.digholoWindowProperties = manager.dict(
                {
                    "Wavelength": Wavelength,
                    "WavelengthCount": self.WavelengthCount,
                    "polCount": polCount,
                    "batchCount": 1,
                    "AvgCount": 1,
                    "PixelSize": self.PixelSize,
                    "maxMG": maxMG,
                    "fftWindowSizeX": fftWindowSizeX,
                    "fftWindowSizeY": fftWindowSizeY,
                    "FFTRadius": FFTRadius,
                    "BeamCentreXPolH": 0,
                    "BeamCentreXPolV": 0,
                    "BeamCentreYPolH": 0,
                    "BeamCentreYPolV": 0,
                    "BasisWaistPolH": 1,
                    "BasisWaistPolV": 1,
                    "DefocusPolH": 0,
                    "DefocusPolV": 0,
                    "XTiltPolH": 0,
                    "XTiltPolV": 0,
                    "YTiltPolH": 0,
                    "YTiltPolV": 0,
                    "AutoAlignBeamCentre": 1,
                    "AutoAlignDefocus": 1,
                    "AutoAlignTilt": 1,
                    "AutoAlignBasisWaist": 1,
                    "AutoAlignFourierWindowRadius": 0,
                    "goalIdx": 0,
                    "basisType": basisType,
                    "resolutionMode": 0,
                    "verbosity": 2,
                    "TransformMatrixFilename": TransformMatrixFilename,
                }
            )

        self.process_digholo, self.digholo_queue = self.start_digiHoloThread()

    def __del__(self):
        self.close()

    def close(self):
        self.terminateDigholo.set()

        if hasattr(self, "process_digholo") and self.process_digholo is not None:
            self.process_digholo.join(timeout=1)
            if self.process_digholo.is_alive():
                self.process_digholo.terminate()
                self.process_digholo.join(timeout=1)
            self.process_digholo = None

        try:
            self.frameBufferBatch_shm.close()
            self.frameBufferBatch_shm.unlink()
        except Exception:
            pass

        try:
            self.Metrics_shm.close()
            self.Metrics_shm.unlink()
        except Exception:
            pass

    def start_digiHoloThread(self):
        self.process_digholo = multiprocessing.Process(
            target=digiHoloThread,
            args=(
                self.digholo_queue,
                self.shared_float,
                self.shared_int,
                self.shared_flag_int,
                self.terminateDigholo,
                self.AutoAlginFlag,
                self.digiHoloPaused,
                self.digholoWindowProperties,
                self.Set_DigholoProperties_Flag,
                self.Get_DigholoProperties_Flag,
                self.Update_basisType_Flag,
                self.frameBufferBatch_shmName,
                self.Metrics_shmName,
                self.shared_batch_height,
                self.shared_batch_width,
                self.PixelSize,
                self.host,
                self.command_port,
                self.frame_pub_port,
                self.timeout_ms,
                str(self.Camera_dtype),
            ),
            daemon=False,
        )

        self.AutoAlginFlag.set()
        self.process_digholo.start()

        return self.process_digholo, self.digholo_queue

    def Set_digholoWindowProps(self, NewDigholoProperties=None):
        if NewDigholoProperties is not None:
            self.digholoWindowProperties.update(NewDigholoProperties)
        self.Set_DigholoProperties_Flag.set()
        while self.Set_DigholoProperties_Flag.is_set():
            time.sleep(1e-4)

    def Get_digholoWindowProps(self):
        self.Get_DigholoProperties_Flag.set()
        while self.Get_DigholoProperties_Flag.is_set():
            time.sleep(1e-4)
        return self.digholoWindowProperties

    def SetPausePlayDigholo(self):
        if self.digiHoloPaused.is_set():
            self.digiHoloPaused.clear()
        else:
            self.digiHoloPaused.set()

    def Set_digholoWindow_basisType(self, basisType=0, TransformMatrixFilename=None):
        if basisType == 2:
            if TransformMatrixFilename is None:
                print("Need to give the filename without the file type to the function.")
                return
            self.digholoWindowProperties["TransformMatrixFilename"] = TransformMatrixFilename

        self.digholoWindowProperties["basisType"] = basisType
        self.Update_basisType_Flag.set()
        while self.Update_basisType_Flag.is_set():
            time.sleep(1e-4)

    def digholoWindowAutoAlgin(self, CameraFrames: np.ndarray = None):
        if CameraFrames is not None:
            cam_dims = CameraFrames.shape
            if len(cam_dims) < 2 or len(cam_dims) > 3:
                print(
                    "AutoAlign NOT run.\n"
                    "CameraFrames must have shape [height,width] or [batch,height,width]."
                )
                return None

            batch_frames = np.asarray(CameraFrames, dtype=self.Camera_dtype)

            if len(cam_dims) == 2:
                self.batchCount = 1
                self.CamFrameHeight = int(cam_dims[0])
                self.CamFrameWidth = int(cam_dims[1])
                batch_frames = batch_frames[np.newaxis, :, :]
            else:
                self.batchCount = int(cam_dims[0])
                self.CamFrameHeight = int(cam_dims[1])
                self.CamFrameWidth = int(cam_dims[2])

            self.shared_int.value = int(self.batchCount)
            self.shared_batch_height.value = int(self.CamFrameHeight)
            self.shared_batch_width.value = int(self.CamFrameWidth)

            self.frameBufferBatch_shm.close()
            self.frameBufferBatch_shm.unlink()

            self.frameBufferBatch_shm = shared_memory.SharedMemory(
                name=self.frameBufferBatch_shmName,
                create=True,
                size=int(
                    self.batchCount
                    * self.CamFrameHeight
                    * self.CamFrameWidth
                    * self.Camera_dtype.itemsize
                ),
            )
            self.FrameBuffer_SharedMem = np.ndarray(
                (self.batchCount, self.CamFrameHeight, self.CamFrameWidth),
                dtype=self.Camera_dtype,
                buffer=self.frameBufferBatch_shm.buf,
            )
            np.copyto(self.FrameBuffer_SharedMem, batch_frames)
        else:
            self.shared_int.value = 1

        self.AutoAlginFlag.set()
        while self.AutoAlginFlag.is_set():
            time.sleep(1e-4)

        _ = self.Get_digholoWindowProps()
        return np.array(self.Metrics_SharedMem)


def _frame_to_float32(frame):
    return np.asarray(frame).astype(np.float32, copy=False)


def _make_uint8_display(image):
    image = np.asarray(image)
    if image.dtype == np.uint8:
        return image

    image_float = image.astype(np.float32)
    finite = np.isfinite(image_float)
    if not np.any(finite):
        return np.zeros(image.shape, dtype=np.uint8)

    min_val = float(np.nanmin(image_float[finite]))
    max_val = float(np.nanmax(image_float[finite]))
    if max_val <= min_val:
        return np.zeros(image.shape, dtype=np.uint8)

    return ((image_float - min_val) * (255.0 / (max_val - min_val))).clip(0, 255).astype(np.uint8)


def digiHoloThread(
    queue,
    shared_float,
    shared_int,
    shared_flag_int,
    terminateDigholo,
    AutoAlginFlag,
    digiHoloPaused,
    digholoWindowProperties,
    Set_DigholoProperties_Flag,
    Get_DigholoProperties_Flag,
    Update_basisType_Flag,
    frameBufferBatch_shmName,
    Metrics_shmName,
    shared_batch_height,
    shared_batch_width,
    PixelSize,
    host,
    command_port,
    frame_pub_port,
    timeout_ms,
    frame_dtype,
):
    cam = None
    Metrics_shm = None
    digiholoObj = None

    try:
        cam = CameraClient(
            host=host,
            command_port=command_port,
            frame_pub_port=frame_pub_port,
            timeout_ms=timeout_ms,
            client_id="digholo_window",
        )

        first_frame = cam.GetFrame()
        frameBuffer = _frame_to_float32(first_frame)

        Metrics_shm = shared_memory.SharedMemory(name=Metrics_shmName)
        MetricValuesArr_shm = np.ndarray(
            (digholoMod.digholoMetrics.COUNT,),
            dtype=np.float32,
            buffer=Metrics_shm.buf,
        )
        Metric_valueArr = np.zeros((digholoMod.digholoMetrics.COUNT,), dtype=np.float32)

        digiholoObj = digholoMod.digholoObject(
            IntialCameraFrame=frameBuffer,
            PixelSize=PixelSize,
            digholoProperties=dict(digholoWindowProperties),
        )

        windowName_digHoloViewPort = "digHolo_Viewport"
        windowName_Coefs = "digHolo_Coefs"

        cv2.namedWindow(windowName_digHoloViewPort, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(windowName_digHoloViewPort, 800, 600)

        shared_int.value = 1

        while not terminateDigholo.is_set():
            if digiHoloPaused.is_set():
                if cv2.waitKey(20) & 0xFF == ord("q"):
                    break
                continue

            frameBuffer = _frame_to_float32(cam.GetFrame())

            if AutoAlginFlag.is_set():
                try:
                    if shared_int.value == 1:
                        _, Metric_valueArr = digiholoObj.digHolo_AutoAlign(frameBuffer)
                    else:
                        batch_count = int(shared_int.value)
                        batch_height = int(shared_batch_height.value)
                        batch_width = int(shared_batch_width.value)

                        shm_frameBufferBatch = shared_memory.SharedMemory(name=frameBufferBatch_shmName)
                        try:
                            frameBufferBatch_shm = np.ndarray(
                                (batch_count, batch_height, batch_width),
                                dtype=np.dtype(frame_dtype),
                                buffer=shm_frameBufferBatch.buf,
                            )
                            frameBufferBatch = np.array(frameBufferBatch_shm, copy=True).astype(np.float32)
                        finally:
                            shm_frameBufferBatch.close()

                        _, Metric_valueArr = digiholoObj.digHolo_AutoAlign(frameBufferBatch)

                    if Metric_valueArr is not None:
                        Metric_valueArr = np.asarray(Metric_valueArr, dtype=np.float32).reshape(-1)
                        copy_count = min(MetricValuesArr_shm.size, Metric_valueArr.size)
                        MetricValuesArr_shm[:copy_count] = Metric_valueArr[:copy_count]

                    CoefsImage, MetricsText = digiholoObj.GetCoefAndMetricsForOutput()
                    cv2.namedWindow(windowName_Coefs, cv2.WINDOW_NORMAL)
                    cv2.resizeWindow(windowName_Coefs, 800, 600)
                    canvasToDispla_Coefs = digiholoObj.DisplayWindow_GraphWithText(
                        _make_uint8_display(CoefsImage),
                        MetricsText,
                    )
                    cv2.imshow(windowName_Coefs, canvasToDispla_Coefs)
                finally:
                    AutoAlginFlag.clear()

            if Update_basisType_Flag.is_set():
                digiholoObj.digholoProperties.update(dict(digholoWindowProperties))
                digiholoObj.digholo_SetProps()
                if digiholoObj.digholoProperties["basisType"] == 2:
                    digiholoObj.loadTransformMatrix(
                        digiholoObj.digholoProperties["TransformMatrixFilename"]
                    )
                Update_basisType_Flag.clear()

            if Set_DigholoProperties_Flag.is_set():
                digiholoObj.digholoProperties.update(dict(digholoWindowProperties))
                digiholoObj.digholo_SetProps()
                Set_DigholoProperties_Flag.clear()

            if Get_DigholoProperties_Flag.is_set():
                PropsTemp = digiholoObj.digholo_GetProps()
                digholoWindowProperties.update(PropsTemp)
                Get_DigholoProperties_Flag.clear()

            _, _ = digiholoObj.digHolo_ProcessBatch(frameBuffer, CalculateMetrics=False)
            Fullimage, _, WindowString = digiholoObj.GetViewport_arr(frameBuffer)

            canvasToDispla_viewPort = digiholoObj.DisplayWindow_GraphWithText(
                _make_uint8_display(Fullimage),
                WindowString,
            )
            cv2.imshow(windowName_digHoloViewPort, canvasToDispla_viewPort)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    except Exception:
        queue.put(("error", traceback.format_exc()))
        print("digHolo thread crashed:")
        print(traceback.format_exc())
        raise

    finally:
        try:
            cv2.destroyAllWindows()
            cv2.waitKey(1)
            cv2.destroyAllWindows()
        except Exception:
            pass

        try:
            if cam is not None:
                cam.close()
        except Exception:
            pass

        try:
            if Metrics_shm is not None:
                Metrics_shm.close()
        except Exception:
            pass

        try:
            del digiholoObj
        except Exception:
            pass

    return 0
