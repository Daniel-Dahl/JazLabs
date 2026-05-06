# SLM_Multiprocess_Server.py

import multiprocessing as mp
import numpy as np
from multiprocessing import shared_memory
import traceback
import uuid


class SLMServerObject:
    def __init__(
        self,
        SLMType="Blink Plus",
        RefreshRate=0,
        LutFile=None,
        timeout=1.0,
        start_process=True,
    ):
        self.SLMType = SLMType
        self.RefreshRate = float(RefreshRate)
        self.LutFile = LutFile
        self.timeout = float(timeout)

        self.Process = None

        # Events
        self.Doorbell = mp.Event()
        self.UpdateDisplay = mp.Event()
        self.DisplayDone = mp.Event()
        self.terminateEvent = mp.Event()

        # Queues
        self.control_queue = mp.Queue()
        self.reply_queue = mp.Queue()
        self.init_queue = mp.Queue()

        # Shared values
        self.ChannelIdx = mp.Value("i", 0)
        self.SLMwriteSuccess = mp.Value("i", 0)

        # Shared memory handles in parent
        self.input_shm = None
        self.output_shm = None
        self.input_arr = None
        self.output_arr = None

        self.monitor_height = None
        self.monitor_width = None
        self.NumberOfChannels = None
        self.image_shape = None
        self.single_channel_shape = None
        self.dtype = np.uint8

        if start_process:
            self.startProcess()

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM process already running")
            return

        self.Process = mp.Process(
            target=self.run_forever,
            daemon=False,
        )
        self.Process.start()

        print(f"SLM process started PID {self.Process.pid}")

        init_msg = self.init_queue.get(timeout=10.0)

        if not init_msg.get("ok", False):
            raise RuntimeError(init_msg.get("error", "SLM worker failed to initialise"))

        self.monitor_height = int(init_msg["monitor_height"])
        self.monitor_width = int(init_msg["monitor_width"])
        self.NumberOfChannels = int(init_msg["number_of_channels"])

        self.image_shape = tuple(init_msg["image_shape"])
        self.single_channel_shape = (
            self.monitor_height,
            self.monitor_width,
        )

        self.input_shm = shared_memory.SharedMemory(
            name=init_msg["input_shm_name"],
        )

        self.output_shm = shared_memory.SharedMemory(
            name=init_msg["output_shm_name"],
        )

        self.input_arr = np.ndarray(
            self.image_shape,
            dtype=self.dtype,
            buffer=self.input_shm.buf,
        )

        self.output_arr = np.ndarray(
            self.image_shape,
            dtype=self.dtype,
            buffer=self.output_shm.buf,
        )

        print("SLM server ready")
        print(f"Shape: {self.image_shape}")
        print(f"Input SHM: {init_msg['input_shm_name']}")
        print(f"Output SHM: {init_msg['output_shm_name']}")

    def stopProcess(self):
        self.terminateEvent.set()
        self.Doorbell.set()

        if self.Process is not None:
            self.Process.join(timeout=2.0)

            if self.Process.is_alive():
                self.Process.terminate()
                self.Process.join(timeout=1.0)

            self.Process = None

        try:
            if self.input_shm is not None:
                self.input_shm.close()
        except Exception:
            pass

        try:
            if self.output_shm is not None:
                self.output_shm.close()
        except Exception:
            pass

    def WriteImageToSLM(self, NewImage=None, channelIdx=None):
        if NewImage is None:
            raise ValueError("No image sent")

        NewImage = np.asarray(NewImage, dtype=np.uint8)

        if NewImage.shape == self.image_shape:
            if channelIdx is None:
                channelIdx = 0

            if channelIdx < 0 or channelIdx >= self.NumberOfChannels:
                raise ValueError(
                    f"channelIdx {channelIdx} out of range for {self.NumberOfChannels} channels"
                )

            np.copyto(self.input_arr, NewImage)

        elif NewImage.shape == self.single_channel_shape:
            if self.NumberOfChannels == 1:
                channelIdx = 0
                np.copyto(self.input_arr[:, :, 0], NewImage)

            elif self.NumberOfChannels == 3:
                if channelIdx is None:
                    raise ValueError("channelIdx must be specified for multi-channel SLM")

                if channelIdx < 0 or channelIdx >= self.NumberOfChannels:
                    raise ValueError(
                        f"channelIdx {channelIdx} out of range for {self.NumberOfChannels} channels"
                    )

                np.copyto(self.input_arr[:, :, channelIdx], NewImage)

            else:
                raise ValueError(
                    f"Unsupported number of SLM channels: {self.NumberOfChannels}"
                )

        else:
            raise ValueError(
                f"Expected image shape {self.single_channel_shape} or {self.image_shape}, got {NewImage.shape}"
            )

        self.ChannelIdx.value = int(channelIdx)

        self.SLMwriteSuccess.value = 0
        self.DisplayDone.clear()

        self.UpdateDisplay.set()
        self.Doorbell.set()

        if not self.DisplayDone.wait(timeout=self.timeout):
            raise TimeoutError("Timed out waiting for SLM image flip")

        return int(self.SLMwriteSuccess.value)

    def _send_command_and_wait(self, cmd, timeout=2.0):
        command_id = str(uuid.uuid4())
        cmd["command_id"] = command_id

        self.control_queue.put(cmd)
        self.Doorbell.set()

        while True:
            try:
                reply = self.reply_queue.get(timeout=timeout)
            except Exception:
                raise TimeoutError(f"Timed out waiting for command reply: {cmd['cmd']}")

            if reply.get("command_id") == command_id:
                if not reply.get("ok", False):
                    raise RuntimeError(reply.get("error", f"Command failed: {cmd['cmd']}"))

                return reply

    def SetRefreshRate(self, NewRefreshRate):
        reply = self._send_command_and_wait({
            "cmd": "set_refresh_rate",
            "value": float(NewRefreshRate),
        })
        return reply.get("result", None)

    def SetTriggerOutput(self, TriggerOutputEnabled):
        reply = self._send_command_and_wait({
            "cmd": "set_trigger_output",
            "value": int(TriggerOutputEnabled),
        })
        return int(reply["result"])

    def LoadLutFile(self, PathToLut):
        reply = self._send_command_and_wait({
            "cmd": "load_lut",
            "path": PathToLut,
        })
        return int(reply["result"])

    def GetSLMTemperature(self):
        reply = self._send_command_and_wait({
            "cmd": "get_temperature",
        })
        return float(reply["result"])

    def GetProperties(self):
        return {
            "monitor_width": self.monitor_width,
            "monitor_height": self.monitor_height,
            "number_of_channels": self.NumberOfChannels,
            "image_shape": self.image_shape,
            "single_channel_shape": self.single_channel_shape,
            "input_shm_name": self.input_shm.name if self.input_shm is not None else None,
            "output_shm_name": self.output_shm.name if self.output_shm is not None else None,
        }

    
    #####################
    # self can be passed only because everything currently in self is pickleable or multiprocessing-compatible.
    #####################
    def run_forever(self):
        input_shm = None
        output_shm = None

        try:
            import psutil, os
            p = psutil.Process(os.getpid())
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
            print("Set ABOVE_NORMAL priority")
        except Exception as e:
            print(f"Priority set failed: {e}")

        try:
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

            image_shape = (
                monitor_height,
                monitor_width,
                number_of_channels,
            )

            nbytes = int(np.prod(image_shape) * np.dtype(np.uint8).itemsize)

            input_shm = shared_memory.SharedMemory(create=True, size=nbytes)
            output_shm = shared_memory.SharedMemory(create=True, size=nbytes)

            input_arr = np.ndarray(
                image_shape,
                dtype=np.uint8,
                buffer=input_shm.buf,
            )

            output_arr = np.ndarray(
                image_shape,
                dtype=np.uint8,
                buffer=output_shm.buf,
            )

            input_arr.fill(0)
            output_arr.fill(0)

            self.init_queue.put({
                "ok": True,
                "monitor_height": monitor_height,
                "monitor_width": monitor_width,
                "number_of_channels": number_of_channels,
                "image_shape": list(image_shape),
                "input_shm_name": input_shm.name,
                "output_shm_name": output_shm.name,
            })

            print("SLM worker started")
            print(f"Image shape: {image_shape}")
            print(f"Input SHM: {input_shm.name}")
            print(f"Output SHM: {output_shm.name}")

            while not self.terminateEvent.is_set():
                # One wake-up event controls everything:
                # image update, control command, or shutdown.
                self.Doorbell.wait()
                self.Doorbell.clear()

                if self.terminateEvent.is_set():
                    break

                # --------------------------------------------------
                # Handle all queued control commands first
                # --------------------------------------------------
                while not self.control_queue.empty():
                    try:
                        cmd = self.control_queue.get_nowait()
                        command_id = cmd.get("command_id")

                        if cmd["cmd"] == "set_refresh_rate":
                            value = float(cmd["value"])
                            slmOBJ.RefreshRate = value

                            self.reply_queue.put({
                                "ok": True,
                                "command_id": command_id,
                                "result": value,
                            })

                        elif cmd["cmd"] == "set_trigger_output":
                            value = int(cmd["value"])

                            if value not in (0, 1):
                                raise ValueError("Trigger output must be 0 or 1")

                            err = slmOBJ.SetTriggerOutput(value)

                            self.reply_queue.put({
                                "ok": True,
                                "command_id": command_id,
                                "result": int(err),
                            })

                        elif cmd["cmd"] == "load_lut":
                            err = slmOBJ.LoadLutFile(cmd["path"])

                            self.reply_queue.put({
                                "ok": True,
                                "command_id": command_id,
                                "result": int(err),
                            })

                        elif cmd["cmd"] == "get_temperature":
                            temp = float(slmOBJ.GetSLMTemperature())

                            self.reply_queue.put({
                                "ok": True,
                                "command_id": command_id,
                                "result": temp,
                            })

                        else:
                            self.reply_queue.put({
                                "ok": False,
                                "command_id": command_id,
                                "error": f"Unknown command: {cmd['cmd']}",
                            })

                    except Exception as e:
                        self.reply_queue.put({
                            "ok": False,
                            "command_id": cmd.get("command_id", None),
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(),
                        })

                # --------------------------------------------------
                # Handle image update if requested
                # --------------------------------------------------
                if self.UpdateDisplay.is_set():
                    self.UpdateDisplay.clear()

                    try:
                        image_cube = input_arr.copy()
                        channelIdx = int(self.ChannelIdx.value)

                        if channelIdx < 0 or channelIdx >= number_of_channels:
                            raise ValueError(
                                f"channelIdx {channelIdx} out of range for {number_of_channels} channels"
                            )

                        ok = bool(
                            slmOBJ.WriteImageToSLM(image_cube, channelIdx)
                        )

                        self.SLMwriteSuccess.value = int(ok)

                        if ok:
                            np.copyto(output_arr, image_cube)

                    except Exception:
                        self.SLMwriteSuccess.value = 0
                        traceback.print_exc()

                    finally:
                        self.DisplayDone.set()

        except Exception as e:
            self.init_queue.put({
                "ok": False,
                "error": f"{type(e).__name__}: {e}",
                "traceback": traceback.format_exc(),
            })

        finally:
            print("SLM worker shutting down")

            try:
                if input_shm is not None:
                    input_shm.close()
                    input_shm.unlink()
            except Exception:
                pass

            try:
                if output_shm is not None:
                    output_shm.close()
                    output_shm.unlink()
            except Exception:
                pass

    def __del__(self):
        try:
            self.stopProcess()
        except Exception:
            pass


if __name__ == "__main__":
    mp.freeze_support()

    slm = SLMServerObject(
        SLMType="Blink Plus",
        RefreshRate=0,
        LutFile=None,
    )

    img = np.zeros(
        (slm.monitor_height, slm.monitor_width),
        dtype=np.uint8,
    )

    slm.WriteImageToSLM(img)

    print(slm.GetProperties())

    slm.stopProcess()