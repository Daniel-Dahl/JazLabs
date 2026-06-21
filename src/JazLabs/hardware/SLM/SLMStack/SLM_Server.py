import argparse
import json
import multiprocessing as mp
from multiprocessing import shared_memory
import time
import traceback

import numpy as np
import zmq


class SLMZMQServer:
    def __init__(
        self,
        host="0.0.0.0",
        command_port=5555,
        display_pub_port=5556,
        display_topic="slm.display",
        SLMType="Blink Plus",
        RefreshRate=0,
        LutFile=None,
        timeout_ms=5000,
        start_process=False,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.display_pub_port = int(display_pub_port)
        self.display_topic = str(display_topic)
        self.SLMType = SLMType
        self.RefreshRate = float(RefreshRate)
        self.LutFile = LutFile
        self.timeout_ms = int(timeout_ms)

        self.Process = None
        if start_process:
            self.startProcess()

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM ZMQ server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"SLM ZMQ server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://127.0.0.1:{self.command_port}")
            socket.send_json({"cmd": "shutdown", "client_id": "server_controller"})
            socket.recv_json()
            socket.close(0)
            context.term()
        except Exception:
            pass

        if self.Process is not None:
            self.Process.join(timeout=2)
            if self.Process.is_alive():
                self.Process.terminate()
                self.Process.join(timeout=1)
            self.Process = None

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
        slm_kwargs = {
            "board_number_in": 1,
            "RefreshRate": self.RefreshRate,
        }
        if self.LutFile is not None:
            slm_kwargs["LutFile"] = self.LutFile
        return slmobj.SLMObject(**slm_kwargs)

    @staticmethod
    def _int_from_ctypes_or_int(value, default=0):
        if value is None:
            return int(default)
        if hasattr(value, "value"):
            return int(value.value)
        return int(value)

    def run_forever(self):
        context = None
        command_socket = None
        display_pub_socket = None
        viewer_shm = None
        viewer_arr = None
        slmOBJ = None

        try:
            try:
                import os
                import psutil

                process = psutil.Process(os.getpid())
                if hasattr(psutil, "ABOVE_NORMAL_PRIORITY_CLASS"):
                    process.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            except Exception as exc:
                print(f"Priority set failed: {exc}")

            slmOBJ = self._open_slm()
            monitor_height = int(slmOBJ.monitor_height)
            monitor_width = int(slmOBJ.monitor_width)
            number_of_channels = int(slmOBJ.NumberOfChannels)
            single_channel_shape = (monitor_height, monitor_width)
            image_shape = (monitor_height, monitor_width, number_of_channels)
            image_dtype = np.dtype(np.uint8)
            image_nbytes = int(np.prod(image_shape) * image_dtype.itemsize)

            viewer_shm = shared_memory.SharedMemory(create=True, size=image_nbytes)
            viewer_arr = np.ndarray(image_shape, dtype=image_dtype, buffer=viewer_shm.buf)
            viewer_arr.fill(0)

            active_controller = None
            output_pulse_image_flip = self._int_from_ctypes_or_int(
                getattr(slmOBJ, "OutputPulseImageFlip", 0)
            )
            last_display_success = False
            last_frame_id = 0
            last_write_time_ns = 0
            last_timing = {}
            running = True

            context = zmq.Context()
            command_socket = context.socket(zmq.REP)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")

            display_pub_socket = context.socket(zmq.PUB)
            display_pub_socket.setsockopt(zmq.SNDHWM, 4)
            display_pub_socket.bind(f"tcp://{self.host}:{self.display_pub_port}")

            print("SLM ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Display PUB socket: tcp://{self.host}:{self.display_pub_port}")
            print(f"Display topic: {self.display_topic}")
            print(f"SLM shape: {image_shape}")
            print(f"Viewer SHM name: {viewer_shm.name}")

            def properties():
                return {
                    "monitor_width": monitor_width,
                    "monitor_height": monitor_height,
                    "number_of_channels": number_of_channels,
                    "input_expected_shape": list(image_shape),
                    "single_channel_shape": list(single_channel_shape),
                    "viewer_shared_memory_name": viewer_shm.name,
                    "viewer_shape": list(image_shape),
                    "viewer_dtype": str(image_dtype),
                    "command_port": self.command_port,
                    "display_pub_port": self.display_pub_port,
                    "display_topic": self.display_topic,
                    "refresh_rate": self.RefreshRate,
                    "lut_file": self.LutFile,
                    "active_controller": active_controller,
                    "output_pulse_image_flip": output_pulse_image_flip,
                    "last_display_success": bool(last_display_success),
                    "last_frame_id": int(last_frame_id),
                    "last_write_time_ns": int(last_write_time_ns),
                    "last_timing": last_timing,
                }

            while running:
                parts = command_socket.recv_multipart()
                msg = {}

                try:
                    if len(parts) == 1:
                        msg = json.loads(parts[0].decode("utf-8"))
                        cmd = msg.get("cmd")
                    elif len(parts) == 2:
                        msg = json.loads(parts[0].decode("utf-8"))
                        cmd = msg.get("cmd")
                    else:
                        raise ValueError("Command must be JSON or [JSON, image_bytes]")

                    client_id = msg.get("client_id", "unknown_client")

                    if cmd == "get_properties":
                        reply = {"ok": True, "result": properties(), "client_id": client_id}

                    elif cmd == "acquire_control":
                        if active_controller is None or active_controller == client_id:
                            active_controller = client_id
                            reply = {
                                "ok": True,
                                "result": {"active_controller": active_controller},
                                "client_id": client_id,
                            }
                        else:
                            reply = {
                                "ok": False,
                                "error": f"SLM is already controlled by {active_controller}",
                                "client_id": client_id,
                            }

                    elif cmd == "release_control":
                        if active_controller is None or active_controller == client_id:
                            active_controller = None
                            reply = {
                                "ok": True,
                                "result": {"active_controller": None},
                                "client_id": client_id,
                            }
                        else:
                            reply = {
                                "ok": False,
                                "error": "This client does not control the SLM",
                                "client_id": client_id,
                            }

                    elif cmd == "set_refresh_rate":
                        self.RefreshRate = float(msg["value"])
                        slmOBJ.RefreshRate = self.RefreshRate
                        reply = {"ok": True, "result": self.RefreshRate, "client_id": client_id}

                    elif cmd == "set_trigger_output":
                        value = int(msg["value"])
                        if value not in (0, 1):
                            raise ValueError("Trigger output must be 0 or 1")
                        result = slmOBJ.SetTriggerOutput(value)
                        output_pulse_image_flip = value
                        reply = {"ok": True, "result": int(result), "client_id": client_id}

                    elif cmd == "load_lut":
                        new_lut = msg["path"]
                        result = slmOBJ.LoadLutFile(new_lut)
                        self.LutFile = new_lut
                        reply = {"ok": True, "result": int(result), "client_id": client_id}

                    elif cmd == "get_temperature":
                        result = float(slmOBJ.GetSLMTemperature())
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "shutdown":
                        running = False
                        reply = {"ok": True, "result": "shutdown_ack", "client_id": client_id}

                    elif cmd == "write_to_display":
                        if len(parts) != 2:
                            raise ValueError("write_to_display requires [JSON, image_bytes]")

                        if active_controller is not None and active_controller != client_id:
                            raise RuntimeError(f"SLM is controlled by {active_controller}")

                        shape = tuple(msg["shape"])
                        dtype = np.dtype(msg.get("dtype", "uint8"))
                        channelIdx = int(msg.get("channelIdx", 0))

                        if shape != image_shape:
                            raise ValueError(
                                f"Expected image shape {image_shape}, got {shape}"
                            )
                        if dtype != np.uint8:
                            raise ValueError(f"Expected uint8 image, got {dtype}")
                        if channelIdx < 0 or channelIdx >= number_of_channels:
                            raise ValueError(
                                f"channelIdx {channelIdx} out of range for {number_of_channels} channels"
                            )

                        image_cube = np.frombuffer(parts[1], dtype=dtype).reshape(shape)
                        image_cube = np.ascontiguousarray(image_cube, dtype=np.uint8)

                        write_start_ns = time.perf_counter_ns()
                        display_ok = bool(slmOBJ.WriteImageToSLM(image_cube, channelIdx))
                        write_done_ns = time.perf_counter_ns()

                        last_frame_id += 1
                        last_write_time_ns = time.time_ns()
                        last_display_success = display_ok
                        last_timing = {
                            "frame_id": int(last_frame_id),
                            "write_start_perf_ns": int(write_start_ns),
                            "write_done_perf_ns": int(write_done_ns),
                            "sdk_write_ms": (write_done_ns - write_start_ns) / 1e6,
                            "image_nbytes": int(image_cube.nbytes),
                        }

                        if display_ok:
                            np.copyto(viewer_arr, image_cube)

                        publish_header = {
                            "type": "slm_display",
                            "client_id": client_id,
                            "shape": list(image_shape),
                            "dtype": "uint8",
                            "frame_id": int(last_frame_id),
                            "channelIdx": int(channelIdx),
                            "last_write_time_ns": int(last_write_time_ns),
                            "ok": bool(display_ok),
                            "timing": last_timing,
                        }
                        display_pub_socket.send_multipart(
                            [
                                self.display_topic.encode("utf-8"),
                                json.dumps(publish_header).encode("utf-8"),
                                viewer_arr.tobytes(),
                            ]
                        )

                        reply = {
                            "ok": True,
                            "result": {
                                "display_ok": bool(display_ok),
                                "frame_id": int(last_frame_id),
                                "last_write_time_ns": int(last_write_time_ns),
                                "timing": last_timing,
                            },
                            "client_id": client_id,
                        }

                    else:
                        reply = {
                            "ok": False,
                            "error": f"Unknown command: {cmd}",
                            "client_id": client_id,
                        }

                except Exception as exc:
                    reply = {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "client_id": msg.get("client_id", "unknown_client"),
                    }

                command_socket.send_json(reply)

        finally:
            print("Closing SLM ZMQ server...")

            for socket in (command_socket, display_pub_socket):
                try:
                    if socket is not None:
                        socket.close(0)
                except Exception:
                    pass

            try:
                if context is not None:
                    context.term()
            except Exception:
                pass

            try:
                if viewer_shm is not None:
                    viewer_shm.close()
                    viewer_shm.unlink()
            except Exception:
                pass

            print("SLM ZMQ server closed.")


if __name__ == "__main__":
    mp.freeze_support()

    parser = argparse.ArgumentParser(description="Run an SLMStack physical SLM server.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--command-port", type=int, default=5555)
    parser.add_argument("--display-pub-port", type=int, default=5556)
    parser.add_argument("--display-topic", default="slm.display")
    parser.add_argument("--slm-type", default="Blink Plus")
    parser.add_argument("--refresh-rate", type=float, default=0)
    parser.add_argument("--lut-file", default=None)
    args = parser.parse_args()

    server = SLMZMQServer(
        host=args.host,
        command_port=args.command_port,
        display_pub_port=args.display_pub_port,
        display_topic=args.display_topic,
        SLMType=args.slm_type,
        RefreshRate=args.refresh_rate,
        LutFile=args.lut_file,
    )
    server.run_forever()
