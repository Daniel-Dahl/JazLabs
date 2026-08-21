import json
import time
import traceback

import numpy as np
import zmq


class SLMZMQServer:
    def __init__(
        self,
        host="0.0.0.0",
        command_port=5555,
        image_sub_port=5556,
        ack_pub_port=5557,
        image_topic="slm.image",
        ack_topic="slm.ack",
        SLMType="Blink Plus",
        BoardNumber=1,
        MonitorIndex=1,
        RefreshRate=0,
        LutFile=None,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.image_sub_port = int(image_sub_port)
        self.ack_pub_port = int(ack_pub_port)
        self.image_topic = str(image_topic)
        self.ack_topic = str(ack_topic)
        self.SLMType = SLMType
        self.BoardNumber = int(BoardNumber)
        self.MonitorIndex = int(MonitorIndex)
        self.RefreshRate = float(RefreshRate)
        self.LutFile = LutFile

    def _send_display_ack_to_bridge(self, bridge_ack_socket, ack):
        ack = dict(ack)
        ack.setdefault("type", "slm_display_ack")
        ack.setdefault("ack_time_ns", time.time_ns())
        try:
            bridge_ack_socket.send_multipart(
                [
                    self.ack_topic.encode("utf-8"),
                    json.dumps(ack).encode("utf-8"),
                ],
                flags=zmq.NOBLOCK,
            )
        except zmq.Again:
            pass

    def _load_slm_module(self):
        if self.SLMType == "Blink Plus":
            import JazLabs.hardware.SLM.MeadowlarkBlinkPlus.MeadowlarkBlinkPlusObject as slmobj
        elif self.SLMType == "Blink OverDrive Plus":
            import JazLabs.hardware.SLM.MeadowlarkBlinkOverDrivePlus.MeadowlarkBlinkOverDrivePlusObject as slmobj
        elif self.SLMType == "HDMI SLM":
            import JazLabs.hardware.SLM.HDMI_SLM.HDMIFullDisplayObject as slmobj
        else:
            raise ValueError(f"Unknown SLMType: {self.SLMType}")
        return slmobj

    def _open_slm(self):
        slmobj = self._load_slm_module()
        if self.SLMType == "HDMI SLM":
            return slmobj.SLMObject(
                monitor_index=self.MonitorIndex,
                RefreshRate=self.RefreshRate,
            )

        slm_kwargs = {
            "board_number_in": self.BoardNumber,
            "RefreshRate": self.RefreshRate,
        }
        if self.LutFile is not None:
            slm_kwargs["LutFile"] = self.LutFile
        return slmobj.SLMObject(**slm_kwargs)

    def _set_slm_geometry_fields(self):
        self.monitor_height = int(self.slmOBJ.monitor_height)
        self.monitor_width = int(self.slmOBJ.monitor_width)
        self.number_of_channels = int(self.slmOBJ.NumberOfChannels)
        self.expected_shape = (self.monitor_height, self.monitor_width)

    def _get_properties(self):
        return {
            "monitor_width": self.monitor_width,
            "monitor_height": self.monitor_height,
            "number_of_channels": self.number_of_channels,
            "input_expected_shape": list(self.expected_shape),
            "refresh_rate": self.RefreshRate,
            "lut_file": self.LutFile,
            "active_controller": self.active_controller,
            "last_display_success": bool(self.last_display_success),
            "output_pulse_image_flip": self.output_pulse_image_flip,
            "command_port": self.command_port,
            "image_sub_port": self.image_sub_port,
            "ack_pub_port": self.ack_pub_port,
            "image_topic": self.image_topic,
            "ack_topic": self.ack_topic,
            "last_frame_id": int(self.last_frame_id),
            "last_timing": self.last_timing,
        }

    def _process_bridge_command(self, msg):
        cmd = msg.get("cmd")
        client_id = msg.get("client_id", "unknown_client")

        if cmd == "get_properties":
            return {"ok": True, "result": self._get_properties()}

        if cmd == "acquire_control":
            if self.active_controller is None or self.active_controller == client_id:
                self.active_controller = client_id
                return {"ok": True, "active_controller": self.active_controller}
            return {
                "ok": False,
                "error": f"SLM is already controlled by {self.active_controller}",
            }

        if cmd == "release_control":
            if self.active_controller == client_id:
                self.active_controller = None
                return {"ok": True, "active_controller": None}
            return {
                "ok": False,
                "error": "This client does not control the SLM",
                "active_controller": self.active_controller,
            }

        if cmd == "set_refresh_rate":
            self.RefreshRate = float(msg["value"])
            self.slmOBJ.RefreshRate = self.RefreshRate
            return {"ok": True, "result": self.RefreshRate}

        if cmd == "set_trigger_output":
            value = int(msg["value"])
            if value not in (0, 1):
                raise ValueError("Trigger output must be 0 or 1")
            err = self.slmOBJ.SetTriggerOutput(value)
            self.output_pulse_image_flip = value
            return {"ok": True, "result": int(err)}

        if cmd == "load_lut":
            new_lut = msg["path"]
            err = self.slmOBJ.LoadLutFile(new_lut)
            self.LutFile = new_lut
            return {"ok": True, "result": int(err)}

        if cmd == "get_temperature":
            temp = float(self.slmOBJ.GetSLMTemperature())
            return {"ok": True, "result": temp}

        if cmd == "shutdown":
            self.running = False
            return {"ok": True, "result": "shutdown_ack"}

        return {"ok": False, "error": f"Unknown command: {cmd}"}

    def _build_confirmed_display_state_reply(self, client_id):
        channel_headers = []
        image_parts = []

        for channel_index in range(self.number_of_channels):
            channel_header = dict(self.confirmed_channel_metadata[channel_index])
            channel_header["channelIdx"] = channel_index
            channel_header["shape"] = list(self.expected_shape)
            channel_header["dtype"] = "uint8"
            channel_header["part_index"] = channel_index + 1
            channel_headers.append(channel_header)
            image_parts.append(
                memoryview(self.confirmed_channel_images[channel_index])
            )

        reply = {
            "ok": True,
            "result": {"channels": channel_headers},
            "client_id": client_id,
        }
        return [json.dumps(reply).encode("utf-8"), *image_parts]

    def run_forever(self):
        try:
            import os
            import psutil

            p = psutil.Process(os.getpid())
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            print("Set ABOVE_NORMAL priority")
        except Exception as e:
            print(f"Priority set failed: {e}")

        self.slmOBJ = self._open_slm()
        self._set_slm_geometry_fields()
        self.active_controller = None
        self.last_display_success = False
        self.output_pulse_image_flip = 0
        self.last_frame_id = 0
        self.last_timing = {}
        self.running = True
        self.confirmed_channel_images = [
            np.zeros(self.expected_shape, dtype=np.uint8)
            for _ in range(self.number_of_channels)
        ]
        self.confirmed_channel_metadata = [
            {
                "confirmed": False,
                "frame_id": 0,
                "write_id": None,
                "last_write_time_ns": 0,
            }
            for _ in range(self.number_of_channels)
        ]

        context = zmq.Context()
        bridge_command_socket = context.socket(zmq.REP)
        bridge_command_socket.bind(f"tcp://{self.host}:{self.command_port}")

        bridge_image_socket = context.socket(zmq.SUB)
        bridge_image_socket.setsockopt(zmq.RCVHWM, 1)
        bridge_image_socket.setsockopt_string(zmq.SUBSCRIBE, self.image_topic)
        bridge_image_socket.bind(f"tcp://{self.host}:{self.image_sub_port}")

        bridge_ack_socket = context.socket(zmq.PUB)
        bridge_ack_socket.setsockopt(zmq.SNDHWM, 16)
        bridge_ack_socket.bind(f"tcp://{self.host}:{self.ack_pub_port}")

        poller = zmq.Poller()
        poller.register(bridge_command_socket, zmq.POLLIN)
        poller.register(bridge_image_socket, zmq.POLLIN)

        print(f"SLM server command REP on tcp://{self.host}:{self.command_port}")
        print(f"SLM server image SUB on tcp://{self.host}:{self.image_sub_port}")
        print(f"SLM server ACK PUB on tcp://{self.host}:{self.ack_pub_port}")
        print(f"SLM shape: {self.expected_shape}")

        try:
            while self.running:
                events = dict(poller.poll(timeout=1000))

                if bridge_image_socket in events:
                    header = {}
                    try:
                        # Drain queued image messages and display only the latest one.
                        latest_image_parts = None
                        recv_start_ns = time.perf_counter_ns()
                        while True:
                            try:
                                latest_image_parts = bridge_image_socket.recv_multipart(
                                    flags=zmq.NOBLOCK
                                )
                            except zmq.Again:
                                break
                        recv_done_ns = time.perf_counter_ns()

                        if latest_image_parts is not None:
                            if len(latest_image_parts) != 3:
                                raise ValueError(
                                    "Image publish must be multipart [topic, header, image]"
                                )

                            _, header_bytes, image_bytes = latest_image_parts
                            decode_start_ns = time.perf_counter_ns()
                            header = json.loads(header_bytes.decode("utf-8"))

                            client_id = header.get("client_id", "unknown_client")
                            if (
                                self.active_controller is not None
                                and client_id != self.active_controller
                            ):
                                continue

                            shape = tuple(header["shape"])
                            dtype = np.dtype(header.get("dtype", "uint8"))
                            channelIdx = int(header.get("channelIdx", 0))
                            frame_id = int(header.get("frame_id", 0))
                            shm_counter = int(header.get("shm_counter", -1))

                            if shape != self.expected_shape:
                                raise ValueError(
                                    f"Expected image shape {self.expected_shape}, got {shape}"
                                )
                            if dtype != np.uint8:
                                raise ValueError(f"Expected uint8 image, got {dtype}")
                            if channelIdx < 0 or channelIdx >= self.number_of_channels:
                                raise ValueError(
                                    "channelIdx "
                                    f"{channelIdx} out of range for "
                                    f"{self.number_of_channels} channels"
                                )

                            image = np.frombuffer(image_bytes, dtype=dtype).reshape(shape)
                            decode_done_ns = time.perf_counter_ns()

                            self.slmOBJ.OutputPulseImageFlip = int(
                                self.output_pulse_image_flip
                            )
                            write_start_ns = time.perf_counter_ns()
                            display_ok = bool(
                                self.slmOBJ.WriteImageToSLM(image, channelIdx)
                            )
                            write_done_ns = time.perf_counter_ns()

                            self.last_display_success = display_ok
                            self.last_frame_id = frame_id
                            self.last_timing = {
                                "frame_id": int(frame_id),
                                "publish_time_ns": int(header.get("publish_time_ns", 0)),
                                "server_recv_start_perf_ns": int(recv_start_ns),
                                "server_recv_done_perf_ns": int(recv_done_ns),
                                "server_decode_done_perf_ns": int(decode_done_ns),
                                "server_write_start_perf_ns": int(write_start_ns),
                                "server_write_done_perf_ns": int(write_done_ns),
                                "recv_call_ms": (recv_done_ns - recv_start_ns) / 1e6,
                                "decode_and_validate_ms": (
                                    decode_done_ns - decode_start_ns
                                )
                                / 1e6,
                                "sdk_write_ms": (write_done_ns - write_start_ns) / 1e6,
                                "server_process_ms": (write_done_ns - recv_start_ns) / 1e6,
                                "image_nbytes": int(len(image_bytes)),
                            }

                            if display_ok:
                                np.copyto(
                                    self.confirmed_channel_images[channelIdx],
                                    image,
                                )
                                self.confirmed_channel_metadata[channelIdx] = {
                                    "confirmed": True,
                                    "frame_id": int(frame_id),
                                    "write_id": int(shm_counter),
                                    "last_write_time_ns": time.time_ns(),
                                }

                            self._send_display_ack_to_bridge(
                                bridge_ack_socket,
                                {
                                    "client_id": client_id,
                                    "frame_id": frame_id,
                                    "shm_counter": shm_counter,
                                    "ok": display_ok,
                                    "timing": self.last_timing,
                                },
                            )

                    except Exception as e:
                        print(
                            "[SLM server] image receive/display error: "
                            f"{type(e).__name__}: {e}"
                        )
                        print(traceback.format_exc())
                        if header:
                            self._send_display_ack_to_bridge(
                                bridge_ack_socket,
                                {
                                    "client_id": header.get("client_id", "unknown_client"),
                                    "frame_id": int(header.get("frame_id", 0)),
                                    "shm_counter": int(header.get("shm_counter", -1)),
                                    "ok": False,
                                    "error": f"{type(e).__name__}: {e}",
                                },
                            )

                if bridge_command_socket in events:
                    msg = bridge_command_socket.recv_json()
                    reply_parts = None
                    try:
                        if msg.get("cmd") == "get_confirmed_display_state":
                            reply_parts = self._build_confirmed_display_state_reply(
                                msg.get("client_id", "unknown_client")
                            )
                        else:
                            reply = self._process_bridge_command(msg)
                    except Exception as e:
                        reply_parts = None
                        reply = {
                            "ok": False,
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(),
                        }
                    if reply_parts is not None:
                        bridge_command_socket.send_multipart(reply_parts)
                    else:
                        bridge_command_socket.send_json(reply)

        finally:
            try:
                bridge_command_socket.close(0)
            except Exception:
                pass
            try:
                bridge_image_socket.close(0)
            except Exception:
                pass
            try:
                bridge_ack_socket.close(0)
            except Exception:
                pass
            try:
                context.term()
            except Exception:
                pass


if __name__ == "__main__":
    server = SLMZMQServer(
        host="0.0.0.0",
        command_port=5555,
        image_sub_port=5556,
        ack_pub_port=5557,
        image_topic="slm.image",
        ack_topic="slm.ack",
        SLMType="Blink Plus",
        RefreshRate=0.5,
        LutFile=None,
    )

    server.run_forever()
