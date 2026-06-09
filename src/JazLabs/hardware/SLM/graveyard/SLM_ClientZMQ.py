# SLM_ZMQ_Client.py

import uuid
import numpy as np
import zmq
from multiprocessing import shared_memory


class SLMClientObject:
    def __init__(
        self,
        client_id=None,
        host="127.0.0.1",
        port=50721,
        timeout_ms=5000,
    ):
        self.client_id = client_id if client_id is not None else str(uuid.uuid4())
        self.host = host
        self.port = int(port)
        self.timeout_ms = int(timeout_ms)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.port}")

        props = self.GetProperties()

        self.monitor_width = int(props["monitor_width"])
        self.monitor_height = int(props["monitor_height"])
        self.NumberOfChannels = int(props["number_of_channels"])

        self.single_channel_shape = (
            self.monitor_height,
            self.monitor_width,
        )

        self.image_shape = (
            self.monitor_height,
            self.monitor_width,
            self.NumberOfChannels,
        )

        self.dtype = np.dtype(np.uint8)
        self.image_nbytes = int(np.prod(self.image_shape) * self.dtype.itemsize)

        self.shm = shared_memory.SharedMemory(
            create=True,
            size=self.image_nbytes,
        )

        self.image_arr = np.ndarray(
            self.image_shape,
            dtype=self.dtype,
            buffer=self.shm.buf,
        )

        self.image_arr.fill(0)
        self.frame_id = 0

        print(f"[SLM Client] client_id = {self.client_id}")
        print(f"[SLM Client] shared_memory_name = {self.shm.name}")
        print(f"[SLM Client] image_shape = {self.image_shape}")

    def _send(self, msg):
        self.socket.send_json(msg)
        reply = self.socket.recv_json()

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown SLM server error"))

        return reply

    def WriteImageToSLM(self, NewImage=None, channelIdx=None):
        if NewImage is None:
            raise ValueError("No image sent")

        NewImage = np.asarray(NewImage, dtype=np.uint8)

        if NewImage.shape != self.single_channel_shape:
            raise ValueError(
                f"Expected image shape {self.single_channel_shape}, got {NewImage.shape}"
            )

        if self.NumberOfChannels == 1:
            channelIdx = 0
            np.copyto(self.image_arr[:, :, 0], NewImage)

        elif self.NumberOfChannels == 3:
            if channelIdx is None:
                raise ValueError("channelIdx must be specified for multi-channel SLM")

            if channelIdx < 0 or channelIdx >= self.NumberOfChannels:
                raise ValueError(
                    f"channelIdx {channelIdx} out of range for {self.NumberOfChannels} channels"
                )

            np.copyto(self.image_arr[:, :, channelIdx], NewImage)

        else:
            raise ValueError(
                f"Unsupported number of SLM channels: {self.NumberOfChannels}"
            )

        self.frame_id += 1

        reply = self._send({
            "cmd": "write_image",
            "client_id": self.client_id,
            "shared_memory_name": self.shm.name,
            "shape": list(self.image_shape),
            "dtype": "uint8",
            "frame_id": self.frame_id,
            "channelIdx": int(channelIdx),
        })

        return int(reply["result"])

    def acquire_control(self):
        return self._send({
            "cmd": "acquire_control",
            "client_id": self.client_id,
        })

    def release_control(self):
        return self._send({
            "cmd": "release_control",
            "client_id": self.client_id,
        })

    def SetRefreshRate(self, NewRefreshRate):
        reply = self._send({
            "cmd": "set_refresh_rate",
            "client_id": self.client_id,
            "value": float(NewRefreshRate),
        })

        return float(reply["result"])

    def SetTriggerOutput(self, TriggerOutputEnabled):
        reply = self._send({
            "cmd": "set_trigger_output",
            "client_id": self.client_id,
            "value": int(TriggerOutputEnabled),
        })

        return int(reply["result"])

    def LoadLutFile(self, PathToLut):
        reply = self._send({
            "cmd": "load_lut",
            "client_id": self.client_id,
            "path": PathToLut,
        })

        return int(reply["result"])

    def GetSLMTemperature(self):
        reply = self._send({
            "cmd": "get_temperature",
            "client_id": self.client_id,
        })

        return float(reply["result"])

    def GetProperties(self):
        reply = self._send({
            "cmd": "get_properties",
            "client_id": self.client_id,
        })

        return reply["result"]

    def shutdown_server(self):
        return self._send({
            "cmd": "shutdown",
            "client_id": self.client_id,
        })

    def close(self):
        try:
            self.shm.close()
        except Exception:
            pass

        try:
            self.shm.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass

        try:
            self.socket.close()
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


if __name__ == "__main__":
    slm = SLMClient(client_id="test_client")

    try:
        img = np.random.randint(
            0,
            255,
            (slm.monitor_height, slm.monitor_width),
            dtype=np.uint8,
        )

        ok = slm.WriteImageToSLM(img, channelIdx=0)
        print("Write success:", ok)

    finally:
        slm.close()