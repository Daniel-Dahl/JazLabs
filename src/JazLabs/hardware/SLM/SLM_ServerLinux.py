import uuid
import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMLinuxClient:
    def __init__(
        self,
        client_id=None,
        windows_host="10.196.0.67",
        windows_port=5555,
        timeout_ms=5000,
        stream_name=None,
    ):
        self.client_id = client_id if client_id is not None else str(uuid.uuid4())
        self.windows_host = windows_host
        self.windows_port = int(windows_port)
        self.timeout_ms = int(timeout_ms)

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.windows_host}:{self.windows_port}")

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

        self.stream_name = stream_name or f"slm_linux_{self.client_id}"

        self.image_cube = np.zeros(self.image_shape, dtype=np.uint8)

        self.shm = SHM(
            self.stream_name,
            self.image_cube,
            shared=True,
        )

        self.shm.set_data(self.image_cube)

        self.frame_id = 0

        print(f"[Linux SLM Client] client_id = {self.client_id}")
        print(f"[Linux SLM Client] stream_name = {self.stream_name}")
        print(f"[Linux SLM Client] image_shape = {self.image_shape}")

    def _send_json(self, msg):
        self.socket.send_json(msg)
        reply = self.socket.recv_json()

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown Windows SLM server error"))

        return reply

    def _send_image(self, header, image_cube):
        self.socket.send_multipart([
            zmq.utils.jsonapi.dumps(header),
            memoryview(np.ascontiguousarray(image_cube, dtype=np.uint8)),
        ])

        reply = self.socket.recv_json()

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown Windows SLM server error"))

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
            self.image_cube[:, :, 0] = NewImage

        elif self.NumberOfChannels == 3:
            if channelIdx is None:
                raise ValueError("channelIdx must be specified for multi-channel SLM")

            if channelIdx < 0 or channelIdx >= self.NumberOfChannels:
                raise ValueError(
                    f"channelIdx {channelIdx} out of range for {self.NumberOfChannels} channels"
                )

            self.image_cube[:, :, channelIdx] = NewImage

        else:
            raise ValueError(
                f"Unsupported number of SLM channels: {self.NumberOfChannels}"
            )

        self.frame_id += 1

        # Local Linux viewer sees this.
        self.shm.set_data(self.image_cube)

        # Windows physical SLM receives this.
        reply = self._send_image(
            {
                "cmd": "write_image",
                "client_id": self.client_id,
                "shape": list(self.image_shape),
                "dtype": "uint8",
                "frame_id": self.frame_id,
                "channelIdx": int(channelIdx),
            },
            self.image_cube,
        )

        return int(reply["result"])

    def acquire_control(self):
        return self._send_json({
            "cmd": "acquire_control",
            "client_id": self.client_id,
        })

    def release_control(self):
        return self._send_json({
            "cmd": "release_control",
            "client_id": self.client_id,
        })

    def SetRefreshRate(self, NewRefreshRate):
        reply = self._send_json({
            "cmd": "set_refresh_rate",
            "client_id": self.client_id,
            "value": float(NewRefreshRate),
        })
        return float(reply["result"])

    def SetTriggerOutput(self, TriggerOutputEnabled):
        reply = self._send_json({
            "cmd": "set_trigger_output",
            "client_id": self.client_id,
            "value": int(TriggerOutputEnabled),
        })
        return int(reply["result"])

    def LoadLutFile(self, PathToLut):
        reply = self._send_json({
            "cmd": "load_lut",
            "client_id": self.client_id,
            "path": PathToLut,
        })
        return int(reply["result"])

    def GetSLMTemperature(self):
        reply = self._send_json({
            "cmd": "get_temperature",
            "client_id": self.client_id,
        })
        return float(reply["result"])

    def GetProperties(self):
        reply = self._send_json({
            "cmd": "get_properties",
            "client_id": self.client_id,
        })
        return reply["result"]

    def close(self):
        try:
            self.socket.close()
            self.context.term()
        except Exception:
            pass