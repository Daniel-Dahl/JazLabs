import uuid

import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMObject:
    """
    Meadowlark-style Linux client for SLMLinuxServer.

    WriteImageToSLM writes to the pymilk SHM. The Linux server watches that SHM
    and forwards updates to the Windows SLM server, so other processes can also
    update the SHM directly and still drive the physical SLM.
    """

    def __init__(
        self,
        client_id=None,
        linux_host="127.0.0.1",
        linux_command_port=5565,
        shm_name=None,
        timeout_ms=5000,
        create_shm_if_missing=False,
        **_,
    ):
        self.client_id = client_id if client_id is not None else str(uuid.uuid4())
        self.linux_host = linux_host
        self.linux_command_port = int(linux_command_port)
        self.timeout_ms = int(timeout_ms)

        self.context = zmq.Context()
        self.linux_server_command_socket = self.context.socket(zmq.REQ)
        self.linux_server_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.linux_server_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.linux_server_command_socket.connect(
            f"tcp://{self.linux_host}:{self.linux_command_port}"
        )
        props = self.GetProperties()

        self.shm_name = shm_name or props["shm_name"]
        self.monitor_width = int(props["monitor_width"])
        self.monitor_height = int(props["monitor_height"])
        self.NumberOfChannels = int(props["number_of_channels"])
        self.single_channel_shape = tuple(props["single_channel_shape"])
        self.image_shape = tuple(props["input_expected_shape"])
        self.RefreshRate = self._windows_property(props, "refresh_rate", 0)
        self.OutputPulseImageFlip = int(props.get("output_pulse_image_flip", 0))

        if create_shm_if_missing:
            self.image_cube = np.zeros(self.image_shape, dtype=np.uint8)
            self.shm = SHM(self.shm_name, self.image_cube, shared=True, autoSqueeze=False)
        else:
            self.shm = SHM(self.shm_name, autoSqueeze=False)
            self.image_cube = np.asarray(self.shm.get_data(copy=True), dtype=np.uint8)
            if self.image_cube.shape != self.image_shape:
                self.image_cube = self._prepare_image_cube_for_shm(
                    self.image_cube,
                    channelIdx=0,
                )

        self.last_write_counter = int(self.shm.get_counter())

    def _windows_property(self, props, name, default=None):
        windows_props = props.get("windows_properties", {})
        return windows_props.get(name, props.get(name, default))

    def _reset_linux_server_command_socket(self):
        try:
            self.linux_server_command_socket.close(0)
        except Exception:
            pass
        self.linux_server_command_socket = self.context.socket(zmq.REQ)
        self.linux_server_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.linux_server_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.linux_server_command_socket.connect(
            f"tcp://{self.linux_host}:{self.linux_command_port}"
        )

    def _send_command_to_linux_server(self, msg):
        msg = dict(msg)
        msg.setdefault("client_id", self.client_id)

        try:
            self.linux_server_command_socket.send_json(msg)
            reply = self.linux_server_command_socket.recv_json()
        except Exception:
            self._reset_linux_server_command_socket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown Linux SLM server error"))

        return reply

    def _prepare_image_cube_for_shm(self, image, channelIdx):
        arr = np.asarray(image, dtype=np.uint8)

        if arr.shape == self.single_channel_shape:
            if self.NumberOfChannels == 1:
                channelIdx = 0
            elif channelIdx is None:
                raise ValueError("channelIdx must be specified for multi-channel SLM")

            channelIdx = int(channelIdx)
            if channelIdx < 0 or channelIdx >= self.NumberOfChannels:
                raise ValueError(
                    f"channelIdx {channelIdx} out of range for {self.NumberOfChannels} channels"
                )

            cube = np.asarray(self.shm.get_data(copy=True), dtype=np.uint8)
            if cube.shape != self.image_shape:
                cube = np.zeros(self.image_shape, dtype=np.uint8)
            cube[:, :, channelIdx] = arr
            return np.ascontiguousarray(cube, dtype=np.uint8)

        if arr.shape == self.image_shape:
            return np.ascontiguousarray(arr, dtype=np.uint8)

        if (
            arr.ndim == 3
            and arr.shape[0] == self.NumberOfChannels
            and arr.shape[1:] == self.single_channel_shape
        ):
            return np.ascontiguousarray(np.transpose(arr, (1, 2, 0)), dtype=np.uint8)

        raise ValueError(
            f"Expected image shape {self.single_channel_shape}, "
            f"{self.image_shape}, or channels-first equivalent; got {arr.shape}"
        )

    def _timeout_ms(self, timeout_ms):
        return self.timeout_ms if timeout_ms is None else int(timeout_ms)

    def WriteImageToSLM(
        self,
        image,
        channelIdx=0,
        wait=True,
        display_timeout_ms=None,
    ):
        self.image_cube = self._prepare_image_cube_for_shm(image, channelIdx)
        self.shm.set_data(self.image_cube)
        self.last_write_counter = int(self.shm.get_counter())

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
        reply = self._send_command_to_linux_server(
            {
                "cmd": "wait_for_slm_display_ack",
                "shm_counter": int(shm_counter),
                "timeout_ms": self._timeout_ms(timeout_ms),
            }
        )
        return bool(reply["result"])

    def SetRefreshRate(self, NewRefreshRate):
        reply = self._send_command_to_linux_server(
            {
                "cmd": "set_refresh_rate",
                "value": float(NewRefreshRate),
            }
        )
        self.RefreshRate = float(reply["result"])
        return self.RefreshRate

    def SetTriggerOutput(self, TriggerOutputEnabled):
        reply = self._send_command_to_linux_server(
            {
                "cmd": "set_trigger_output",
                "value": int(TriggerOutputEnabled),
            }
        )
        self.OutputPulseImageFlip = int(TriggerOutputEnabled)
        return int(reply["result"])

    def LoadLutFile(self, PathToLut):
        reply = self._send_command_to_linux_server(
            {
                "cmd": "load_lut",
                "path": PathToLut,
            }
        )
        return int(reply["result"])

    def GetSLMTemperature(self):
        reply = self._send_command_to_linux_server({"cmd": "get_temperature"})
        return float(reply["result"])

    def GetProperties(self):
        reply = self._send_command_to_linux_server({"cmd": "get_properties"})
        return reply["result"]

    def acquire_control(self):
        return self._send_command_to_linux_server({"cmd": "acquire_control"})

    def release_control(self):
        return self._send_command_to_linux_server({"cmd": "release_control"})

    def shutdown(self):
        return self._send_command_to_linux_server({"cmd": "shutdown"})["result"]

    def close(self):
        try:
            self.shm.close()
        except Exception:
            pass
        try:
            self.linux_server_command_socket.close(0)
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


SLMLinuxClient = SLMObject
