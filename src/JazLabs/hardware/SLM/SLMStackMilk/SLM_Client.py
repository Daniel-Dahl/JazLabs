import json
import uuid

import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMClient:
    """
    Meadowlark-style client for SLMZMQBridgeServer.

    WriteImageToSLM writes a 2D mask and its channel metadata to the pymilk
    requested-image SHM. The bridge forwards complete updates to the physical
    server and writes a separate confirmed SHM only after a successful ACK.
    """

    def __init__(
        self,
        client_id=None,
        bridge_host="127.0.0.1",
        bridge_command_port=5565,
        shm_name=None,
        timeout_ms=5000,
        create_shm_if_missing=False,
        **_,
    ):
        self.client_id = client_id if client_id is not None else str(uuid.uuid4())
        self.bridge_host = bridge_host
        self.bridge_command_port = int(bridge_command_port)
        self.timeout_ms = int(timeout_ms)

        self.context = zmq.Context()
        self.bridge_command_socket = self.context.socket(zmq.REQ)
        self.bridge_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.bridge_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.bridge_command_socket.connect(
            f"tcp://{self.bridge_host}:{self.bridge_command_port}"
        )
        props = self.GetProperties()

        self.shm_name = shm_name or props["shm_name"]
        self.monitor_width = int(props["monitor_width"])
        self.monitor_height = int(props["monitor_height"])
        self.NumberOfChannels = int(props["number_of_channels"])
        self.single_channel_shape = tuple(props["single_channel_shape"])
        self.image_shape = tuple(props["input_expected_shape"])
        self.RefreshRate = self._server_property(props, "refresh_rate", 0)
        self.OutputPulseImageFlip = int(props.get("output_pulse_image_flip", 0))

        if create_shm_if_missing:
            self.image = np.zeros(self.single_channel_shape, dtype=np.uint8)
            self.shm = SHM(self.shm_name, self.image, shared=True, autoSqueeze=False)
        else:
            self.shm = SHM(self.shm_name, autoSqueeze=False)
            self.image = np.asarray(self.shm.get_data(copy=True), dtype=np.uint8)
            if self.image.shape != self.single_channel_shape:
                raise ValueError(
                    f"Expected 2D SLM SHM shape {self.single_channel_shape}; "
                    f"got {self.image.shape}"
                )

        self.last_write_counter = int(self.shm.get_counter())

    def _server_property(self, props, name, default=None):
        server_properties = props.get("server_properties", {})
        return server_properties.get(name, props.get(name, default))

    def _reset_bridge_command_socket(self):
        try:
            self.bridge_command_socket.close(0)
        except Exception:
            pass
        self.bridge_command_socket = self.context.socket(zmq.REQ)
        self.bridge_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.bridge_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.bridge_command_socket.connect(
            f"tcp://{self.bridge_host}:{self.bridge_command_port}"
        )

    def _send_command_to_bridge(self, msg):
        msg = dict(msg)
        msg.setdefault("client_id", self.client_id)

        try:
            self.bridge_command_socket.send_json(msg)
            reply = self.bridge_command_socket.recv_json()
        except Exception:
            self._reset_bridge_command_socket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown SLM bridge error"))

        return reply

    def _prepare_image_for_shm(self, image, channelIdx):
        arr = np.asarray(image, dtype=np.uint8)

        if arr.shape != self.single_channel_shape:
            raise ValueError(
                f"Expected 2D image shape {self.single_channel_shape}; got {arr.shape}"
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

    def _timeout_ms(self, timeout_ms):
        return self.timeout_ms if timeout_ms is None else int(timeout_ms)

    def WriteImageToSLM(
        self,
        image,
        channelIdx=0,
        wait=True,
        display_timeout_ms=None,
    ):
        self.image, channelIdx = self._prepare_image_for_shm(image, channelIdx)
        self.shm.set_keywords(
            {
                "WRITING": 1,
                "CHANIDX": int(channelIdx),
            }
        )
        self.shm.set_data(self.image)
        self.last_write_counter = int(self.shm.get_counter())
        self.shm.set_keywords(
            {
                "WRITING": 0,
                "CHANIDX": int(channelIdx),
                "SHMCNT": self.last_write_counter,
            }
        )

        if wait:
            return int(
                self.WaitForSLMDisplayAck(
                    shm_counter=self.last_write_counter,
                    timeout_ms=display_timeout_ms,
                )
            )
        return 1

    def WaitForSLMDisplayAck(self, shm_counter=None, timeout_ms=None):
        if shm_counter is None:
            shm_counter = self.last_write_counter
        reply = self._send_command_to_bridge(
            {
                "cmd": "wait_for_slm_display_ack",
                "shm_counter": int(shm_counter),
                "timeout_ms": self._timeout_ms(timeout_ms),
            }
        )
        return bool(reply["result"])

    def SetRefreshRate(self, NewRefreshRate):
        reply = self._send_command_to_bridge(
            {
                "cmd": "set_refresh_rate",
                "value": float(NewRefreshRate),
            }
        )
        self.RefreshRate = float(reply["result"])
        return self.RefreshRate

    def SetTriggerOutput(self, TriggerOutputEnabled):
        reply = self._send_command_to_bridge(
            {
                "cmd": "set_trigger_output",
                "value": int(TriggerOutputEnabled),
            }
        )
        self.OutputPulseImageFlip = int(TriggerOutputEnabled)
        return int(reply["result"])

    def LoadLutFile(self, PathToLut):
        reply = self._send_command_to_bridge(
            {
                "cmd": "load_lut",
                "path": PathToLut,
            }
        )
        return int(reply["result"])

    def GetSLMTemperature(self):
        reply = self._send_command_to_bridge({"cmd": "get_temperature"})
        return float(reply["result"])

    def GetProperties(self):
        reply = self._send_command_to_bridge({"cmd": "get_properties"})
        return reply["result"]

    def GetConfirmedDisplayState(self):
        request = {
            "cmd": "get_confirmed_display_state",
            "client_id": self.client_id,
        }

        try:
            self.bridge_command_socket.send_json(request)
            reply_parts = self.bridge_command_socket.recv_multipart()
        except Exception:
            self._reset_bridge_command_socket()
            raise

        if not reply_parts:
            raise RuntimeError("SLM bridge returned an empty snapshot reply")

        reply = json.loads(reply_parts[0].decode("utf-8"))
        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown SLM bridge error"))

        channel_states = []
        for channel_header in reply.get("result", {}).get("channels", []):
            part_index = int(channel_header["part_index"])
            if part_index <= 0 or part_index >= len(reply_parts):
                raise RuntimeError(
                    f"Display-state part index {part_index} is missing"
                )

            shape = tuple(channel_header["shape"])
            dtype = np.dtype(channel_header["dtype"])
            channel_image = np.frombuffer(
                reply_parts[part_index],
                dtype=dtype,
            ).reshape(shape).copy()
            channel_state = dict(channel_header)
            channel_state["image"] = channel_image
            channel_states.append(channel_state)

        return channel_states

    def acquire_control(self):
        return self._send_command_to_bridge({"cmd": "acquire_control"})

    def release_control(self):
        return self._send_command_to_bridge({"cmd": "release_control"})

    def shutdown(self):
        return self._send_command_to_bridge({"cmd": "shutdown"})["result"]

    def close(self):
        try:
            self.shm.close()
        except Exception:
            pass
        try:
            self.bridge_command_socket.close(0)
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
