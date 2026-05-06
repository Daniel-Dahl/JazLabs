import time
import traceback
import multiprocessing as mp
from multiprocessing import shared_memory

import numpy as np
import zmq

class CameraClient:
    def __init__(
        self,
        host="127.0.0.1",
        port=50731,
        timeout_ms=5000,
        client_id="camera_client",
    ):
        self.host = host
        self.port = int(port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = client_id

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)

        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)

        self.socket.connect(f"tcp://{self.host}:{self.port}")

        properties = self.GetProperties()
        self.frame_layout_version = int(properties.get("frame_layout_version", 1))

        self.frame_shm = shared_memory.SharedMemory(
            name=properties["frame_shared_memory_name"]
        )

        self.meta_shm = shared_memory.SharedMemory(
            name=properties["meta_shared_memory_name"]
        )

        self.frame_shape = tuple(properties["frame_shape"])
        self.frame_dtype = np.dtype(properties["frame_dtype"])

        self.frame_arr = np.ndarray(
            self.frame_shape,
            dtype=self.frame_dtype,
            buffer=self.frame_shm.buf,
        )

        self.meta_arr = np.ndarray(
            (5,),
            dtype=np.int64,
            buffer=self.meta_shm.buf,
        )

    def SendCommand(self, msg):
        msg["client_id"] = self.client_id

        self.socket.send_json(msg)
        reply = self.socket.recv_json()

        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown camera server error")
                + "\n"
                + reply.get("traceback", "")
            )

        return reply.get("result", None)
    def RefreshFrameSharedMemoryIfNeeded(self):
        current_version = int(self.meta_arr[4])

        if current_version == self.frame_layout_version:
            return

        # Server is resizing or has resized the frame memory.
        while int(self.meta_arr[0]) == 1:
            time.sleep(0.0005)

        try:
            self.frame_shm.close()
        except Exception:
            pass

        properties = self.GetProperties()

        self.frame_shape = tuple(properties["frame_shape"])
        self.frame_dtype = np.dtype(properties["frame_dtype"])
        self.frame_layout_version = int(properties["frame_layout_version"])

        self.frame_shm = shared_memory.SharedMemory(
            name=properties["frame_shared_memory_name"]
        )

        self.frame_arr = np.ndarray(
            self.frame_shape,
            dtype=self.frame_dtype,
            buffer=self.frame_shm.buf,
        )

        print("Client reattached to resized frame shared memory.")
        print(f"New frame shape: {self.frame_shape}")

    # --------------------------------------------------------
    # Frame reading
    # --------------------------------------------------------

    def GetFrame(self, WaitForNewFrame=False, LastFrameCounter=None):
        self.RefreshFrameSharedMemoryIfNeeded()

        if WaitForNewFrame:
            if LastFrameCounter is None:
                LastFrameCounter = self.GetFrameCounter()

            while self.GetFrameCounter() == LastFrameCounter:
                self.RefreshFrameSharedMemoryIfNeeded()
                time.sleep(0.0005)

        while True:
            self.RefreshFrameSharedMemoryIfNeeded()

            counter_before = int(self.meta_arr[1])
            writing_before = int(self.meta_arr[0])
            version_before = int(self.meta_arr[4])

            if writing_before:
                time.sleep(0.0001)
                continue

            frame = self.frame_arr.copy()

            counter_after = int(self.meta_arr[1])
            writing_after = int(self.meta_arr[0])
            version_after = int(self.meta_arr[4])

            if version_after != version_before:
                self.RefreshFrameSharedMemoryIfNeeded()
                continue

            if counter_before == counter_after and not writing_after:
                return frame
            
    def GetFrameCounter(self):
        return int(self.meta_arr[1])

    def GetLastFrameTimeNS(self):
        return int(self.meta_arr[2])

    def IsServerAlive(self):
        return bool(self.meta_arr[3])

    # --------------------------------------------------------
    # Server commands
    # --------------------------------------------------------

    def GetProperties(self):
        return self.SendCommand({"cmd": "get_properties"})

    def PauseAcquisition(self):
        return self.SendCommand({"cmd": "pause_acquisition"})

    def ResumeAcquisition(self):
        return self.SendCommand({"cmd": "resume_acquisition"})

    def ShutdownServer(self):
        return self.SendCommand({"cmd": "shutdown"})

    # --------------------------------------------------------
    # Camera-like commands
    # --------------------------------------------------------

    def StartAcquisition(self):
        return self.SendCommand({"cmd": "start_acquisition"})

    def StopAcquisition(self):
        return self.SendCommand({"cmd": "stop_acquisition"})

    def ResetCamera(self):
        return self.SendCommand({"cmd": "reset_camera"})

    def ResetBuffer(self):
        return self.SendCommand({"cmd": "reset_buffer"})

    def SetBufferSizeInNumberOfFrames(self, n_frames):
        return self.SendCommand({
            "cmd": "set_buffer_size_in_number_of_frames",
            "n_frames": n_frames,
        })

    def GetBufferSizeInNumberOfFrames(self):
        return self.SendCommand({
            "cmd": "get_buffer_size_in_number_of_frames",
        })

    def GetNumberOfFramesInBuffer(self):
        return self.SendCommand({
            "cmd": "get_number_of_frames_in_buffer",
        })

    def GetTriggerMode(self):
        return self.SendCommand({"cmd": "get_trigger_mode"})

    def SetContinuousMode(self):
        return self.SendCommand({"cmd": "set_continuous_mode"})

    def SetSoftwareTriggerMode(self):
        return self.SendCommand({"cmd": "set_software_trigger_mode"})

    def SetHardwareTriggerMode(self, lineNumber=0, RiseEdgeOrFallEdge=1):
        return self.SendCommand({
            "cmd": "set_hardware_trigger_mode",
            "lineNumber": lineNumber,
            "RiseEdgeOrFallEdge": RiseEdgeOrFallEdge,
        })

    def SetExposureTime(self, exposure_time):
        return self.SendCommand({
            "cmd": "set_exposure_time",
            "exposure_time": exposure_time,
        })

    def GetExposureTime(self):
        return self.SendCommand({"cmd": "get_exposure_time"})

    def SetGain(self, gain):
        return self.SendCommand({
            "cmd": "set_gain",
            "gain": gain,
        })

    def GetGain(self):
        return self.SendCommand({"cmd": "get_gain"})

    def SetFPS(self, fps):
        return self.SendCommand({
            "cmd": "set_fps",
            "fps": fps,
        })

    def GetFPS(self):
        return self.SendCommand({"cmd": "get_fps"})

    def GetMaxMinFPS_ExposureTime(self):
        return self.SendCommand({
            "cmd": "get_max_min_fps_exposure_time",
        })

    def SetROI(
        self,
        offset_x=None,
        offset_y=None,
        width=None,
        height=None,
        snap_values=True,
        enable=True,
        mode="nearest",
    ):
        return self.SendCommand({
            "cmd": "set_roi",
            "offset_x": offset_x,
            "offset_y": offset_y,
            "width": width,
            "height": height,
            "snap_values": snap_values,
            "enable": enable,
            "mode": mode,
        })

    def GetROI(self):
        return self.SendCommand({"cmd": "get_roi"})

    def GetFrameID(self):
        return self.SendCommand({"cmd": "get_frame_id"})

    def SetPixelFormat(self, pixel_format):
        return self.SendCommand({
            "cmd": "set_pixel_format",
            "pixel_format": pixel_format,
        })

    def GetPixelFormat(self):
        return self.SendCommand({"cmd": "get_pixel_format"})

    def close(self):
        try:
            self.frame_shm.close()
        except Exception:
            pass

        try:
            self.meta_shm.close()
        except Exception:
            pass

        try:
            self.socket.close(0)
        except Exception:
            pass

        try:
            self.context.term()
        except Exception:
            pass
