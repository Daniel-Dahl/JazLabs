# SLM_ZMQ_Server.py

import traceback
import multiprocessing as mp
import numpy as np
import zmq
from multiprocessing import shared_memory


class SLMServerObject:
    def __init__(
        self,
        host="127.0.0.1",
        port=50721,
        SLMType="Blink Plus",
        RefreshRate=0,
        LutFile=None,
    ):
        self.host = host
        self.port = int(port)
        self.SLMType = SLMType
        self.RefreshRate = float(RefreshRate)
        self.LutFile = LutFile

        self.output_shm = None
        self.output_arr = None
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM server process is already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"SLM server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            self._send_command_to_running_server(
                {
                    "cmd": "shutdown",
                    "client_id": "server_process_controller",
                },
                timeout_ms=1000,
            )
        except Exception:
            pass

        if self.Process is not None:
            self.Process.join(timeout=2.0)

            if self.Process.is_alive():
                self.Process.terminate()
                self.Process.join(timeout=1.0)

            self.Process = None

    def _send_command_to_running_server(self, msg, timeout_ms=3000):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)

        try:
            socket.setsockopt(zmq.RCVTIMEO, int(timeout_ms))
            socket.setsockopt(zmq.SNDTIMEO, int(timeout_ms))
            socket.connect(f"tcp://{self.host}:{self.port}")

            socket.send_json(msg)
            reply = socket.recv_json()

            if not reply.get("ok", False):
                raise RuntimeError(reply.get("error", "Unknown SLM server error"))

            return reply

        finally:
            try:
                socket.close()
            except Exception:
                pass

            try:
                context.term()
            except Exception:
                pass

    def GetProperties(self, timeout_ms=3000):
        reply = self._send_command_to_running_server(
            {
                "cmd": "get_properties",
                "client_id": "server_object",
            },
            timeout_ms=timeout_ms,
        )

        return reply["result"]

    def run_forever(self):
        if self.SLMType == "Blink Plus":
            import pwi_inst.hardware.SLM.MeadowlarkBlinkPlus.MeadowlarkBlinkPlusObject as slmobj
        elif self.SLMType == "Blink OverDrive Plus":
            import pwi_inst.hardware.SLM.MeadowlarkBlinkOverDrivePlus.MeadowlarkBlinkOverDrivePlusObject as slmobj
        elif self.SLMType == "HDMI SLM":
            import pwi_inst.hardware.SLM.HDMI_SLM.HDMIFullDisplayObject as slmobj
        else:
            raise ValueError(f"Unknown SLMType: {self.SLMType}")

        slmOBJ = slmobj.SLMObject(
            board_number_in=1,
            RefreshRate=self.RefreshRate,
            LutFile=self.LutFile,
        )

        monitor_height = int(slmOBJ.monitor_height)
        monitor_width = int(slmOBJ.monitor_width)
        number_of_channels = int(slmOBJ.NumberOfChannels)

        input_expected_shape = (
            monitor_height,
            monitor_width,
            number_of_channels,
        )

        # Viewer buffer is now the full display cube:
        #   Meadowlark PCIe: H x W x 1
        #   HDMI SLM:        H x W x 3
        output_shape = (
            monitor_height,
            monitor_width,
            number_of_channels,
        )

        output_dtype = np.dtype(np.uint8)
        output_nbytes = int(np.prod(output_shape) * output_dtype.itemsize)

        self.output_shm = shared_memory.SharedMemory(
            create=True,
            size=output_nbytes,
        )

        self.output_arr = np.ndarray(
            output_shape,
            dtype=output_dtype,
            buffer=self.output_shm.buf,
        )
        self.output_arr.fill(0)

        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(f"tcp://{self.host}:{self.port}")

        print(f"SLM ZMQ server running on tcp://{self.host}:{self.port}")
        print(f"SLM input shape: {input_expected_shape}")
        print(f"Number of channels: {number_of_channels}")
        print(f"Viewer shared memory name: {self.output_shm.name}")
        print(f"Viewer shared memory shape: {output_shape}")
        print("Viewer shared memory dtype: uint8")

        active_controller = None
        last_display_success = False
        output_pulse_image_flip = 0
        running = True

        try:
            while running:
                msg = socket.recv_json()

                try:
                    cmd = msg.get("cmd")
                    client_id = msg.get("client_id", "unknown_client")

                    if cmd == "write_image":
                        if active_controller is not None and client_id != active_controller:
                            reply = {
                                "ok": False,
                                "error": f"SLM is currently controlled by {active_controller}",
                            }

                        else:
                            shm_name = msg["shared_memory_name"]
                            shape = tuple(msg["shape"])
                            dtype = np.dtype(msg.get("dtype", "uint8"))
                            channelIdx = int(msg.get("channelIdx", 0))
                            frame_id = msg.get("frame_id", None)

                            if dtype != np.uint8:
                                raise ValueError(f"Expected dtype uint8, got {dtype}")

                            if shape != input_expected_shape:
                                raise ValueError(
                                    f"Expected input shared memory shape {input_expected_shape}, got {shape}"
                                )

                            if channelIdx < 0 or channelIdx >= number_of_channels:
                                raise ValueError(
                                    f"channelIdx {channelIdx} out of range for {number_of_channels} channels"
                                )

                            input_shm = shared_memory.SharedMemory(name=shm_name)

                            try:
                                image_view = np.ndarray(
                                    shape,
                                    dtype=dtype,
                                    buffer=input_shm.buf,
                                )

                                image_cube = image_view.copy()

                            finally:
                                input_shm.close()

                            slmOBJ.OutputPulseImageFlip = int(output_pulse_image_flip)

                            last_display_success = bool(
                                slmOBJ.WriteImageToSLM(image_cube, channelIdx)
                            )

                            if last_display_success:
                                np.copyto(self.output_arr, image_cube)

                            reply = {
                                "ok": True,
                                "result": int(last_display_success),
                                "frame_id": frame_id,
                                "client_id": client_id,
                                "viewer_shared_memory_name": self.output_shm.name,
                            }

                    elif cmd == "acquire_control":
                        if active_controller is None:
                            active_controller = client_id
                            reply = {
                                "ok": True,
                                "active_controller": active_controller,
                            }

                        elif active_controller == client_id:
                            reply = {
                                "ok": True,
                                "active_controller": active_controller,
                            }

                        else:
                            reply = {
                                "ok": False,
                                "error": f"SLM is already controlled by {active_controller}",
                            }

                    elif cmd == "release_control":
                        if active_controller == client_id:
                            active_controller = None
                            reply = {
                                "ok": True,
                                "active_controller": None,
                            }

                        else:
                            reply = {
                                "ok": False,
                                "error": "This client does not control the SLM",
                                "active_controller": active_controller,
                            }

                    elif cmd == "get_properties":
                        reply = {
                            "ok": True,
                            "result": {
                                "monitor_width": monitor_width,
                                "monitor_height": monitor_height,
                                "number_of_channels": number_of_channels,
                                "input_expected_shape": list(input_expected_shape),
                                "refresh_rate": self.RefreshRate,
                                "lut_file": self.LutFile,
                                "active_controller": active_controller,
                                "last_display_success": last_display_success,
                                "output_pulse_image_flip": output_pulse_image_flip,
                                "viewer_shared_memory_name": self.output_shm.name,
                                "viewer_shape": list(output_shape),
                                "viewer_dtype": "uint8",
                            },
                        }

                    elif cmd == "set_refresh_rate":
                        value = float(msg["value"])
                        self.RefreshRate = value
                        slmOBJ.RefreshRate = value

                        reply = {
                            "ok": True,
                            "result": self.RefreshRate,
                        }

                    elif cmd == "set_trigger_output":
                        value = int(msg["value"])

                        if value not in (0, 1):
                            raise ValueError("Trigger output must be 0 or 1")
                        err = slmOBJ.SetTriggerOutput(value)
                        output_pulse_image_flip = value
                        reply = {
                            "ok": True,
                            "result": int(err),
                        }

                    elif cmd == "load_lut":
                        new_lut = msg["path"]
                        err = slmOBJ.LoadLutFile(new_lut)
                        self.LutFile = new_lut

                        reply = {
                            "ok": True,
                            "result": int(err),
                        }

                    elif cmd == "get_temperature":
                        temp = float(slmOBJ.GetSLMTemperature())

                        reply = {
                            "ok": True,
                            "result": temp,
                        }

                    elif cmd == "shutdown":
                        running = False

                        reply = {
                            "ok": True,
                            "result": "shutdown_ack",
                        }

                    else:
                        reply = {
                            "ok": False,
                            "error": f"Unknown command: {cmd}",
                        }

                except Exception as e:
                    reply = {
                        "ok": False,
                        "error": f"{type(e).__name__}: {e}",
                        "traceback": traceback.format_exc(),
                    }

                socket.send_json(reply)

        finally:
            print("Closing SLM ZMQ server...")

            try:
                socket.close()
            except Exception:
                pass

            try:
                context.term()
            except Exception:
                pass

            try:
                if self.output_shm is not None:
                    self.output_shm.close()
            except Exception:
                pass

            try:
                if self.output_shm is not None:
                    self.output_shm.unlink()
            except FileNotFoundError:
                pass
            except Exception:
                pass


if __name__ == "__main__":
    mp.freeze_support()

    server = SLMZMQServer(
        host="127.0.0.1",
        port=50721,
        SLMType="Blink Plus",
        RefreshRate=0.5,
        LutFile=None,
    )

    server.run_forever()