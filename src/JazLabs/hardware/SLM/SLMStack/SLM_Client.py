import inspect
import json
import uuid
from multiprocessing import shared_memory

import numpy as np
import zmq


_SHARED_MEMORY_SUPPORTS_TRACK = (
    "track" in inspect.signature(shared_memory.SharedMemory).parameters
)


def _attach_shared_memory(name):
    if _SHARED_MEMORY_SUPPORTS_TRACK:
        return shared_memory.SharedMemory(name=name, track=False)

    return shared_memory.SharedMemory(name=name)


class SLMClient:
    """
    Network client for SLMStack servers and bridge servers.

    The SLM is updated only by WriteToDisplay/WriteImageToSLM. Shared memory is
    a local viewer buffer owned by the server or bridge, not a control path.
    """

    def __init__(
        self,
        host="127.0.0.1",
        command_port=5555,
        display_pub_port=5556,
        timeout_ms=5000,
        client_id=None,
        attach_viewer_shared_memory=True,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.display_pub_port = int(display_pub_port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = client_id if client_id is not None else str(uuid.uuid4())
        self.attach_viewer_shared_memory = bool(attach_viewer_shared_memory)

        self.context = zmq.Context()
        self.command_socket = None
        self.display_sub_socket = self.context.socket(zmq.SUB)
        self.display_sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.display_sub_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.display_sub_socket.connect(f"tcp://{self.host}:{self.display_pub_port}")

        self.viewer_shm = None
        self.viewer_arr = None
        self.viewer_shape = None
        self.viewer_dtype = None

        self._connect_command_socket()

        properties = self.GetProperties()
        self.monitor_width = int(properties["monitor_width"])
        self.monitor_height = int(properties["monitor_height"])
        self.NumberOfChannels = int(properties["number_of_channels"])
        self.single_channel_shape = tuple(properties["single_channel_shape"])
        self.image_shape = tuple(properties["input_expected_shape"])
        self.RefreshRate = float(properties.get("refresh_rate", 0))
        self.OutputPulseImageFlip = int(properties.get("output_pulse_image_flip", 0))

        if self.attach_viewer_shared_memory and properties.get("viewer_shared_memory_name"):
            self.viewer_shape = tuple(properties["viewer_shape"])
            self.viewer_dtype = np.dtype(properties["viewer_dtype"])
            self.viewer_shm = _attach_shared_memory(
                properties["viewer_shared_memory_name"]
            )
            self.viewer_arr = np.ndarray(
                self.viewer_shape,
                dtype=self.viewer_dtype,
                buffer=self.viewer_shm.buf,
            )

    def _connect_command_socket(self):
        if self.command_socket is not None:
            try:
                self.command_socket.close(0)
            except Exception:
                pass

        self.command_socket = self.context.socket(zmq.REQ)
        self.command_socket.setsockopt(zmq.LINGER, 0)
        self.command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.command_socket.connect(f"tcp://{self.host}:{self.command_port}")

    def ResetCommandSocket(self):
        self._connect_command_socket()

    def SendCommand(self, msg):
        msg = dict(msg)
        msg["client_id"] = self.client_id

        try:
            self.command_socket.send_json(msg)
            reply = self.command_socket.recv_json()
        except Exception:
            self.ResetCommandSocket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown SLM server error")
                + "\n"
                + reply.get("traceback", "")
            )

        return reply.get("result", None)

    def SendImageCommand(self, image, channelIdx=0, wait=True, timeout_ms=None):
        image, channelIdx = self._prepare_image_for_display(image, channelIdx)
        header = {
            "cmd": "write_to_display",
            "client_id": self.client_id,
            "shape": list(image.shape),
            "dtype": str(image.dtype),
            "channelIdx": int(channelIdx),
            "wait": bool(wait),
            "timeout_ms": self.timeout_ms if timeout_ms is None else int(timeout_ms),
        }

        try:
            self.command_socket.send_multipart(
                [
                    json.dumps(header).encode("utf-8"),
                    memoryview(np.ascontiguousarray(image)),
                ]
            )
            reply = self.command_socket.recv_json()
        except Exception:
            self.ResetCommandSocket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown SLM server error")
                + "\n"
                + reply.get("traceback", "")
            )

        return reply.get("result", None)

    def _prepare_image_for_display(self, image, channelIdx):
        arr = np.asarray(image, dtype=np.uint8)

        if arr.shape != self.image_shape:
            raise ValueError(
                f"Expected 2D image shape {self.image_shape}; got {arr.shape}"
            )

        if self.NumberOfChannels == 1:
            channelIdx = 0
        elif channelIdx is None:
            raise ValueError("channelIdx must be specified for multi-channel SLM")

        channelIdx = int(channelIdx)
        if channelIdx < 0 or channelIdx >= self.NumberOfChannels:
            raise ValueError(
                f"channelIdx {channelIdx} out of range for {self.NumberOfChannels} channels"
            )

        return np.ascontiguousarray(arr), channelIdx

    def WriteToDisplay(self, image, channelIdx=0, wait=True, display_timeout_ms=None):
        return self.SendImageCommand(
            image,
            channelIdx=channelIdx,
            wait=wait,
            timeout_ms=display_timeout_ms,
        )

    def WriteImageToSLM(self, image, channelIdx=0, wait=True, display_timeout_ms=None):
        return self.WriteToDisplay(
            image,
            channelIdx=channelIdx,
            wait=wait,
            display_timeout_ms=display_timeout_ms,
        )

    def GetDisplayedImage(self):
        if self.viewer_arr is None:
            raise RuntimeError("Client is not attached to a local viewer shared memory")
        return self.viewer_arr.copy()

    def WaitForDisplayNotification(self, LastFrameID=None):
        while True:
            parts = self.display_sub_socket.recv_multipart()
            if len(parts) == 3:
                _, header_bytes, _ = parts
            elif len(parts) == 2:
                header_bytes, _ = parts
            elif len(parts) == 1:
                header_bytes = parts[0]
            else:
                continue

            msg = json.loads(header_bytes.decode("utf-8"))
            if msg.get("type") != "slm_display":
                continue
            if LastFrameID is None:
                return msg
            if int(msg.get("frame_id", -1)) != int(LastFrameID):
                return msg

    def GetProperties(self):
        return self.SendCommand({"cmd": "get_properties"})

    def SetRefreshRate(self, NewRefreshRate):
        self.RefreshRate = float(
            self.SendCommand({"cmd": "set_refresh_rate", "value": float(NewRefreshRate)})
        )
        return self.RefreshRate

    def SetTriggerOutput(self, TriggerOutputEnabled):
        self.OutputPulseImageFlip = int(TriggerOutputEnabled)
        return int(
            self.SendCommand(
                {"cmd": "set_trigger_output", "value": int(TriggerOutputEnabled)}
            )
        )

    def LoadLutFile(self, PathToLut):
        return int(self.SendCommand({"cmd": "load_lut", "path": PathToLut}))

    def GetSLMTemperature(self):
        return float(self.SendCommand({"cmd": "get_temperature"}))

    def acquire_control(self):
        return self.SendCommand({"cmd": "acquire_control"})

    def release_control(self):
        return self.SendCommand({"cmd": "release_control"})

    def ShutdownServer(self):
        return self.SendCommand({"cmd": "shutdown"})

    def shutdown(self):
        return self.ShutdownServer()

    def close(self):
        self.viewer_arr = None

        try:
            if self.viewer_shm is not None:
                self.viewer_shm.close()
        except Exception:
            pass

        try:
            self.command_socket.close(0)
        except Exception:
            pass

        try:
            self.display_sub_socket.close(0)
        except Exception:
            pass

        try:
            self.context.term()
        except Exception:
            pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


SLMObject = SLMClient
