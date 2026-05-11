import time
import traceback
import multiprocessing as mp
from multiprocessing import shared_memory

import numpy as np
import zmq


class CameraZMQServer:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        CameraType="FLIR Point Grey",
        CameraKwargs=None,
        PollSleep=0.0,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.frame_pub_port = int(frame_pub_port)
        self.CameraType = CameraType
        self.CameraKwargs = CameraKwargs or {}
        self.PollSleep = float(PollSleep)

        self.Process = None

        self.frame_shm = None
        self.frame_arr = None
        self.meta_shm = None
        self.meta_arr = None

        self.frame_shape = None
        self.frame_dtype = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Camera server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Camera server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://{self.host}:{self.command_port}")
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

    def run_forever(self):
        # ----------------------------------------------------
        # Camera selection, like the original camera server
        # ----------------------------------------------------
        if self.CameraType == "First Light C-Blue":
            import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCblue2 as cameraobj
        elif self.CameraType == "First Light C-Red3_2Lite":
            import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCred3_2Lite as cameraobj
        elif self.CameraType == "FLIR Point Grey":
            import pwi_inst.hardware.Cameras.FLIRPointGreyCameras.FLIR_PointGrey as cameraobj
        else:
            raise ValueError(f"Unknown CameraType: {self.CameraType}")

        camOBJ = None
        context = None
        command_socket = None
        frame_pub_socket = None

        try:
            camOBJ = cameraobj.CameraObject(**self.CameraKwargs)

            # ----------------------------------------------------
            # Create shared memory from first frame
            # ----------------------------------------------------
            first_frame = np.asarray(camOBJ.GetFrame())
            self.frame_shape = tuple(first_frame.shape)
            self.frame_dtype = np.dtype(first_frame.dtype)
            frame_nbytes = int(np.prod(self.frame_shape) * self.frame_dtype.itemsize)

            self.frame_shm = shared_memory.SharedMemory(
                create=True,
                size=frame_nbytes,
            )

            self.frame_arr = np.ndarray(
                self.frame_shape,
                dtype=self.frame_dtype,
                buffer=self.frame_shm.buf,
            )

            self.meta_shm = shared_memory.SharedMemory(
                create=True,
                size=5 * np.dtype(np.int64).itemsize,
            )

            self.meta_arr = np.ndarray(
                (5,),
                dtype=np.int64,
                buffer=self.meta_shm.buf,
            )

            # meta_arr[0] = writing/resizing flag
            # meta_arr[1] = frame counter
            # meta_arr[2] = last frame write time ns
            # meta_arr[3] = server alive flag
            # meta_arr[4] = frame layout version, incremented after ROI/frame-size changes
            self.meta_arr[:] = 0
            self.meta_arr[3] = 1
            self.meta_arr[4] = 1

            self.frame_arr[:] = first_frame
            self.meta_arr[1] = 1
            self.meta_arr[2] = time.time_ns()

            # ----------------------------------------------------
            # ZMQ sockets
            # ----------------------------------------------------
            context = zmq.Context()

            command_socket = context.socket(zmq.REP)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")

            frame_pub_socket = context.socket(zmq.PUB)
            frame_pub_socket.bind(f"tcp://{self.host}:{self.frame_pub_port}")

            print("Camera ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Frame PUB socket: tcp://{self.host}:{self.frame_pub_port}")
            print(f"CameraType: {self.CameraType}")
            print(f"Frame SHM name: {self.frame_shm.name}")
            print(f"Meta SHM name:  {self.meta_shm.name}")
            print(f"Frame shape:    {self.frame_shape}")
            print(f"Frame dtype:    {self.frame_dtype}")

            acquisition_running = True
            running = True

            # Give already-created subscribers a brief chance to finish connecting.
            time.sleep(0.1)
            self.PublishNewFrame(frame_pub_socket)

            try:
                while running:
                    # ------------------------------------------------
                    # 1. Check for one ZMQ command
                    # ------------------------------------------------
                    try:
                        flags = zmq.NOBLOCK if acquisition_running else 0
                        msg = command_socket.recv_json(flags=flags)
                        got_command = True
                    except zmq.Again:
                        got_command = False

                    if got_command:
                        try:
                            cmd = msg.get("cmd")
                            client_id = msg.get("client_id", "unknown_client")

                            # ----------------------------
                            # Server commands
                            # ----------------------------
                            if cmd == "get_properties":
                                reply = {
                                    "ok": True,
                                    "result": {
                                        "camera_type": self.CameraType,
                                        "command_port": self.command_port,
                                        "frame_pub_port": self.frame_pub_port,
                                        "frame_shared_memory_name": self.frame_shm.name,
                                        "frame_shape": list(self.frame_shape),
                                        "frame_dtype": str(self.frame_dtype),
                                        "meta_shape": [5],
                                        "meta_shared_memory_name": self.meta_shm.name,
                                        "meta_dtype": "int64",
                                        "frame_layout_version": int(self.meta_arr[4]),
                                        "frame_counter": int(self.meta_arr[1]),
                                        "last_write_time_ns": int(self.meta_arr[2]),
                                        "acquisition_running": acquisition_running,
                                        "server_alive": bool(self.meta_arr[3]),
                                    },
                                    "client_id": client_id,
                                }

                            elif cmd == "pause_acquisition":
                                acquisition_running = False
                                reply = {"ok": True, "result": None, "client_id": client_id}

                            elif cmd == "resume_acquisition":
                                acquisition_running = True
                                reply = {"ok": True, "result": None, "client_id": client_id}

                            elif cmd == "shutdown":
                                running = False
                                reply = {"ok": True, "result": None, "client_id": client_id}

                            # ----------------------------
                            # Camera object commands
                            # ----------------------------
                            elif cmd == "start_acquisition":
                                result = camOBJ.StartAcquisition()
                                acquisition_running = True
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "stop_acquisition":
                                result = camOBJ.StopAcquisition()
                                acquisition_running = False
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "reset_camera":
                                result = camOBJ.ResetCamera()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "reset_buffer":
                                result = camOBJ.ResetBuffer()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_buffer_size_in_number_of_frames":
                                n_frames = msg["n_frames"]
                                result = camOBJ.SetBufferSizeInNumberOfFrames(n_frames)
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_buffer_size_in_number_of_frames":
                                result = camOBJ.GetBufferSizeInNumberOfFrames()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_number_of_frames_in_buffer":
                                result = camOBJ.GetNumberOfFramesInBuffer()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_trigger_mode":
                                result = camOBJ.GetTriggerMode()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_continuous_mode":
                                result = camOBJ.SetContinuousMode()
                                acquisition_running = True
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_software_trigger_mode":
                                result = camOBJ.SetSoftwareTriggerMode()
                                acquisition_running = False
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_hardware_trigger_mode":
                                lineNumber = msg.get("lineNumber", 0)
                                RiseEdgeOrFallEdge = msg.get("RiseEdgeOrFallEdge", 1)

                                result = camOBJ.SetHardwareTriggerMode(
                                    lineNumber=lineNumber,
                                    RiseEdgeOrFallEdge=RiseEdgeOrFallEdge,
                                )
                                acquisition_running = True

                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "software_trigger":
                                frame = np.asarray(camOBJ.GetFrame())
                                self.WriteFrameToSharedMemory(frame)
                                self.PublishNewFrame(frame_pub_socket)
                                reply = {
                                    "ok": True,
                                    "result": {
                                        "frame_counter": int(self.meta_arr[1]),
                                        "last_write_time_ns": int(self.meta_arr[2]),
                                        "frame_layout_version": int(self.meta_arr[4]),
                                    },
                                    "client_id": client_id,
                                }

                            elif cmd == "set_exposure_time":
                                exposure_time = msg["exposure_time"]
                                result = camOBJ.SetExposureTime(exposure_time)
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_exposure_time":
                                result = camOBJ.GetExposureTime()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_gain":
                                gain = msg["gain"]
                                result = camOBJ.SetGain(gain)
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_gain":
                                result = camOBJ.GetGain()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_fps":
                                fps = msg["fps"]
                                result = camOBJ.SetFPS(fps)
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_fps":
                                result = camOBJ.GetFPS()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_max_min_fps_exposure_time":
                                result = camOBJ.GetMaxMinFPS_ExposureTime()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_roi":
                                offset_x = msg.get("offset_x", None)
                                offset_y = msg.get("offset_y", None)
                                width = msg.get("width", None)
                                height = msg.get("height", None)
                                snap_values = msg.get("snap_values", True)
                                enable = msg.get("enable", True)
                                mode = msg.get("mode", "nearest")

                                self.meta_arr[0] = 1

                                result = camOBJ.SetROI(
                                    offset_x=offset_x,
                                    offset_y=offset_y,
                                    width=width,
                                    height=height,
                                    snap_values=snap_values,
                                    enable=enable,
                                    mode=mode,
                                )

                                self.RecreateFrameSharedMemory(
                                    camOBJ=camOBJ,
                                )
                                self.PublishNewFrame(frame_pub_socket)

                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_roi":
                                result = camOBJ.GetROI()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_frame_id":
                                result = camOBJ.GetFrameID()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "set_pixel_format":
                                pixel_format = msg["pixel_format"]
                                result = camOBJ.SetPixelFormat(pixel_format)
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            elif cmd == "get_pixel_format":
                                result = camOBJ.GetPixelFormat()
                                reply = {"ok": True, "result": result, "client_id": client_id}

                            else:
                                reply = {
                                    "ok": False,
                                    "error": f"Unknown command: {cmd}",
                                    "client_id": client_id,
                                }

                        except Exception as e:
                            try:
                                if self.meta_arr is not None:
                                    self.meta_arr[0] = 0
                            except Exception:
                                pass

                            reply = {
                                "ok": False,
                                "error": f"{type(e).__name__}: {e}",
                                "traceback": traceback.format_exc(),
                                "client_id": msg.get("client_id", "unknown_client"),
                            }

                        command_socket.send_json(reply)

                    # ------------------------------------------------
                    # 2. Publish latest frame
                    # ------------------------------------------------
                    if acquisition_running:
                        try:
                            # This is intentionally the timing throttle. There is no
                            # artificial polling sleep when PollSleep is 0; the next
                            # loop begins as soon as the camera returns a frame.
                            frame = np.asarray(camOBJ.GetFrame())

                            if frame.shape != self.frame_shape:
                                raise ValueError(
                                    f"Camera frame shape changed from {self.frame_shape} to {frame.shape}. "
                                    "Use set_roi so the server can recreate shared memory."
                                )

                            if frame.dtype != self.frame_dtype:
                                frame = frame.astype(self.frame_dtype, copy=False)

                            self.WriteFrameToSharedMemory(frame)
                            self.PublishNewFrame(frame_pub_socket)

                        except Exception as e:
                            print("Camera frame acquisition error:")
                            print(f"{type(e).__name__}: {e}")
                            print(traceback.format_exc())
                            time.sleep(0.01)

                    if self.PollSleep > 0:
                        time.sleep(self.PollSleep)

            finally:
                print("Closing camera ZMQ server...")

                try:
                    if self.meta_arr is not None:
                        self.meta_arr[3] = 0
                except Exception:
                    pass

                try:
                    if camOBJ is not None:
                        if hasattr(camOBJ, "StopAcquisition"):
                            camOBJ.StopAcquisition()
                        if hasattr(camOBJ, "shutdown"):
                            camOBJ.shutdown()
                except Exception:
                    pass

                try:
                    if command_socket is not None:
                        command_socket.close(0)
                except Exception:
                    pass

                try:
                    if frame_pub_socket is not None:
                        frame_pub_socket.close(0)
                except Exception:
                    pass

                try:
                    if context is not None:
                        context.term()
                except Exception:
                    pass

                try:
                    if self.frame_shm is not None:
                        self.frame_shm.close()
                        self.frame_shm.unlink()
                except Exception:
                    pass

                try:
                    if self.meta_shm is not None:
                        self.meta_shm.close()
                        self.meta_shm.unlink()
                except Exception:
                    pass

                print("Camera ZMQ server closed.")

        except Exception:
            print("Camera server startup error:")
            print(traceback.format_exc())
            raise

    def PublishNewFrame(self, frame_pub_socket):
        frame_pub_socket.send_json(
            {
                "type": "new_frame",
                "frame_counter": int(self.meta_arr[1]),
                "last_write_time_ns": int(self.meta_arr[2]),
                "frame_layout_version": int(self.meta_arr[4]),
            }
        )

    def WriteFrameToSharedMemory(self, frame):
        frame = np.asarray(frame)

        if frame.shape != self.frame_shape:
            raise ValueError(
                f"Camera frame shape changed from {self.frame_shape} to {frame.shape}. "
                "Use set_roi so the server can recreate shared memory."
            )

        if frame.dtype != self.frame_dtype:
            frame = frame.astype(self.frame_dtype, copy=False)

        self.meta_arr[0] = 1
        self.frame_arr[:] = frame
        self.meta_arr[1] += 1
        self.meta_arr[2] = time.time_ns()
        self.meta_arr[0] = 0

    def RecreateFrameSharedMemory(self, camOBJ):
        """
        Recreate frame shared memory after ROI/frame size changes.

        The metadata shared memory stays the same.
        The frame shared memory is recreated with a fresh name. On Windows a
        shared-memory name can remain unavailable while clients still hold an
        open handle to the old segment.
        Clients detect the layout version change via meta_arr[4].
        """

        self.meta_arr[0] = 1

        new_frame = np.asarray(camOBJ.GetFrame())
        new_frame_shape = tuple(new_frame.shape)
        new_frame_dtype = np.dtype(new_frame.dtype)
        new_frame_nbytes = int(np.prod(new_frame_shape) * new_frame_dtype.itemsize)

        try:
            if self.frame_shm is not None:
                self.frame_shm.close()
                self.frame_shm.unlink()
        except FileNotFoundError:
            pass

        self.frame_shm = shared_memory.SharedMemory(
            create=True,
            size=new_frame_nbytes,
        )

        self.frame_arr = np.ndarray(
            new_frame_shape,
            dtype=new_frame_dtype,
            buffer=self.frame_shm.buf,
        )

        self.frame_arr[:] = new_frame
        self.frame_shape = new_frame_shape
        self.frame_dtype = new_frame_dtype

        self.meta_arr[1] += 1
        self.meta_arr[2] = time.time_ns()
        self.meta_arr[4] += 1
        self.meta_arr[0] = 0

        print("Frame shared memory recreated after ROI change.")
        print(f"New frame shape: {new_frame_shape}")
        print(f"New frame dtype: {new_frame_dtype}")
        print(f"Frame SHM name:  {self.frame_shm.name}")


if __name__ == "__main__":
    mp.freeze_support()

    server = CameraZMQServer(
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        CameraType="FLIR Point Grey",
        CameraKwargs={
            "CameraIdx": 0,
            "verbose": True,
        },
        PollSleep=0.0,
    )

    server.run_forever()
