import traceback
import numpy as np
import zmq


class SLMWindowsServer:
    def __init__(
        self,
        host="0.0.0.0",
        port=5555,
        SLMType="Blink Plus",
        RefreshRate=0,
        LutFile=None,
    ):
        self.host = host
        self.port = int(port)
        self.SLMType = SLMType
        self.RefreshRate = float(RefreshRate)
        self.LutFile = LutFile

    def run_forever(self):
        try:
            import psutil, os
            p = psutil.Process(os.getpid())
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            print("Set ABOVE_NORMAL priority")
        except Exception as e:
            print(f"Priority set failed: {e}")
            
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

        expected_shape = (
            monitor_height,
            monitor_width,
            number_of_channels,
        )

        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(f"tcp://{self.host}:{self.port}")

        print(f"Windows SLM server running on tcp://{self.host}:{self.port}")
        print(f"SLM shape: {expected_shape}")

        active_controller = None
        last_display_success = False
        output_pulse_image_flip = 0
        last_image_cube = np.zeros(expected_shape, dtype=np.uint8)

        running = True

        try:
            while running:
                parts = socket.recv_multipart()

                try:
                    header = socket._deserialize(parts[0], zmq.utils.jsonapi.loads)
                    cmd = header.get("cmd")
                    client_id = header.get("client_id", "unknown_client")

                    if cmd == "write_image":
                        if active_controller is not None and client_id != active_controller:
                            reply = {
                                "ok": False,
                                "error": f"SLM is currently controlled by {active_controller}",
                            }

                        else:
                            if len(parts) != 2:
                                raise ValueError("write_image command must include image bytes")

                            shape = tuple(header["shape"])
                            dtype = np.dtype(header.get("dtype", "uint8"))
                            channelIdx = int(header.get("channelIdx", 0))
                            frame_id = header.get("frame_id", None)

                            if shape != expected_shape:
                                raise ValueError(
                                    f"Expected image shape {expected_shape}, got {shape}"
                                )

                            if dtype != np.uint8:
                                raise ValueError(f"Expected uint8 image, got {dtype}")

                            if channelIdx < 0 or channelIdx >= number_of_channels:
                                raise ValueError(
                                    f"channelIdx {channelIdx} out of range for {number_of_channels} channels"
                                )

                            image_cube = np.frombuffer(parts[1], dtype=dtype).reshape(shape).copy()

                            slmOBJ.OutputPulseImageFlip = int(output_pulse_image_flip)

                            last_display_success = bool(
                                slmOBJ.WriteImageToSLM(image_cube, channelIdx)
                            )

                            if last_display_success:
                                np.copyto(last_image_cube, image_cube)

                            reply = {
                                "ok": True,
                                "result": int(last_display_success),
                                "frame_id": frame_id,
                                "client_id": client_id,
                            }

                    elif cmd == "get_properties":
                        reply = {
                            "ok": True,
                            "result": {
                                "monitor_width": monitor_width,
                                "monitor_height": monitor_height,
                                "number_of_channels": number_of_channels,
                                "input_expected_shape": list(expected_shape),
                                "refresh_rate": self.RefreshRate,
                                "lut_file": self.LutFile,
                                "active_controller": active_controller,
                                "last_display_success": last_display_success,
                                "output_pulse_image_flip": output_pulse_image_flip,
                            },
                        }

                    elif cmd == "acquire_control":
                        if active_controller is None or active_controller == client_id:
                            active_controller = client_id
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

                    elif cmd == "set_refresh_rate":
                        self.RefreshRate = float(header["value"])
                        slmOBJ.RefreshRate = self.RefreshRate
                        reply = {"ok": True, "result": self.RefreshRate}

                    elif cmd == "set_trigger_output":
                        value = int(header["value"])
                        if value not in (0, 1):
                            raise ValueError("Trigger output must be 0 or 1")
                        err = slmOBJ.SetTriggerOutput(value)
                        output_pulse_image_flip = value
                        reply = {"ok": True,"result": int(err),}

                    elif cmd == "load_lut":
                        new_lut = header["path"]
                        err = slmOBJ.LoadLutFile(new_lut)
                        self.LutFile = new_lut
                        reply = {"ok": True, "result": int(err)}

                    elif cmd == "get_temperature":
                        temp = float(slmOBJ.GetSLMTemperature())
                        reply = {"ok": True, "result": temp}

                    elif cmd == "shutdown":
                        running = False
                        reply = {"ok": True, "result": "shutdown_ack"}

                    else:
                        reply = {"ok": False, "error": f"Unknown command: {cmd}"}

                except Exception as e:
                    reply = {
                        "ok": False,
                        "error": f"{type(e).__name__}: {e}",
                        "traceback": traceback.format_exc(),
                    }

                socket.send_json(reply)

        finally:
            socket.close()
            context.term()


if __name__ == "__main__":
    server = SLMWindowsServer(
        host="0.0.0.0",
        port=5555,
        SLMType="Blink Plus",
        RefreshRate=0.5,
        LutFile=None,
    )

    server.run_forever()