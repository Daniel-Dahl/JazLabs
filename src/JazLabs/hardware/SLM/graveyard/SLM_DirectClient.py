import uuid
import json
import time

import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMLinuxClient:
    def __init__(
        self,
        client_id=None,
        windows_host="10.196.0.67",
        windows_command_port=5555,
        windows_image_port=5556,
        image_topic="slm.image",
        windows_port=None,
        timeout_ms=5000,
        stream_name=None,
    ):
        self.client_id = client_id if client_id is not None else str(uuid.uuid4())
        self.windows_host = windows_host
        if windows_port is not None:
            windows_command_port = windows_port
        self.windows_command_port = int(windows_command_port)
        self.windows_image_port = int(windows_image_port)
        self.image_topic = str(image_topic)
        self.timeout_ms = int(timeout_ms)

        self.context = zmq.Context()

        self.command_socket = self.context.socket(zmq.REQ)
        self.command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.command_socket.connect(
            f"tcp://{self.windows_host}:{self.windows_command_port}"
        )

        self.image_pub_socket = self.context.socket(zmq.PUB)
        self.image_pub_socket.connect(
            f"tcp://{self.windows_host}:{self.windows_image_port}"
        )

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
        print(
            "[Linux SLM Client] command REQ = "
            f"tcp://{self.windows_host}:{self.windows_command_port}"
        )
        print(
            "[Linux SLM Client] image PUB = "
            f"tcp://{self.windows_host}:{self.windows_image_port} "
            f"topic={self.image_topic}"
        )

    def _send_json(self, msg):
        self.command_socket.send_json(msg)
        reply = self.command_socket.recv_json()

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown Windows SLM server error"))

        return reply

    def _send_image(self, header, image_cube):
        header = dict(header)
        header.setdefault("type", "slm_image")
        header.setdefault("publish_time_ns", time.time_ns())

        self.image_pub_socket.send_multipart(
            [
                self.image_topic.encode("utf-8"),
                json.dumps(header).encode("utf-8"),
                memoryview(np.ascontiguousarray(image_cube, dtype=np.uint8)),
            ]
        )

        # PUB/SUB is one-way; the Windows server updates last_display_success
        # and last_frame_id, which can be checked with GetProperties().
        return 1

    def WaitForFrameDisplayed(self, frame_id=None, timeout_ms=None, poll_interval_s=0.0005):
        if frame_id is None:
            frame_id = self.frame_id

        frame_id = int(frame_id)
        timeout_s = (self.timeout_ms if timeout_ms is None else int(timeout_ms)) / 1000.0
        deadline = time.monotonic() + timeout_s

        while time.monotonic() < deadline:
            props = self.GetProperties()

            if int(props.get("last_frame_id", 0)) >= frame_id:
                return bool(props.get("last_display_success", False))

            time.sleep(float(poll_interval_s))

        raise TimeoutError(
            f"Timed out waiting for Windows SLM server to display frame {frame_id}"
        )

    def WriteImageToSLM(
        self,
        NewImage=None,
        channelIdx=None,
        wait_for_display=False,
        display_timeout_ms=None,
    ):
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

        # Windows physical SLM receives this over PUB/SUB.
        result = self._send_image(
            {
                "client_id": self.client_id,
                "shape": list(self.image_shape),
                "dtype": "uint8",
                "frame_id": self.frame_id,
                "channelIdx": int(channelIdx),
            },
            self.image_cube,
        )

        if wait_for_display:
            return int(
                self.WaitForFrameDisplayed(
                    frame_id=self.frame_id,
                    timeout_ms=display_timeout_ms,
                )
            )

        return int(result)

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
            self.command_socket.close(0)
        except Exception:
            pass
        try:
            self.image_pub_socket.close(0)
        except Exception:
            pass
        try:
            self.context.term()
        except Exception:
            pass
