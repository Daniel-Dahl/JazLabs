import time
import traceback
import multiprocessing as mp
from multiprocessing import shared_memory

import numpy as np
import zmq

import pwi_inst.hardware.Cameras.Camera_Client as CamClient

class CameraServer:
    def __init__(
        self,
        host="127.0.0.1",
        port=50731,
        CameraType="FLIR Point Grey",
        CameraKwargs=None,
        PollSleep=0.001,
    ):
        self.host = host
        self.port = int(port)
        self.CameraType = CameraType
        self.CameraKwargs = CameraKwargs or {}
        self.PollSleep = float(PollSleep)

        self.Process = None

        self.frame_shm = None
        self.frame_arr = None
        self.meta_shm = None
        self.meta_arr = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Camera server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Camera server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            client = CamClient.CameraClient(host=self.host, port=self.port)
            client.ShutdownServer()
            client.close()
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
        # Camera selection, like your SLM server
        # ----------------------------------------------------
        if self.CameraType == "First Light C-Blue":
            import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCblue2 as cameraobj
        elif self.CameraType == "First Light C-Red3_2Lite":
            import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCred3_2Lite as cameraobj
        elif self.CameraType == "FLIR Point Grey":
            import pwi_inst.hardware.Cameras.FLIRPointGreyCameras.FLIR_PointGrey as cameraobj
        else:
            raise ValueError(f"Unknown CameraType: {self.CameraType}")

        # Note all cameras objects should have a consistent set of methods that the server calls, 
        # like StartAcquisition, GetFrame, SetROI, etc. The server explicitly calls these methods 
        # on the camera object based on client commands.
        camOBJ = cameraobj.CameraObject(**self.CameraKwargs)
        

        # if hasattr(camOBJ, "StartAcquisition"):
        #     camOBJ.StartAcquisition()

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
        buffer=self.frame_shm.buf,)

        self.meta_shm = shared_memory.SharedMemory(
            create=True,
            size=5 * np.dtype(np.int64).itemsize,
        )

        self.meta_arr = np.ndarray(
            (5,),
            dtype=np.int64,
            buffer=self.meta_shm.buf,
        )

        self.meta_arr[:] = 0
        self.meta_arr[3] = 1
        self.meta_arr[4] = 1

        self.frame_arr[:] = first_frame
        self.meta_arr[1] = 1
        self.meta_arr[2] = time.time_ns()

        # ----------------------------------------------------
        # ZMQ server
        # ----------------------------------------------------
        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind(f"tcp://{self.host}:{self.port}")

        print(f"Camera ZMQ server running on tcp://{self.host}:{self.port}")
        print(f"CameraType: {self.CameraType}")
        print(f"Frame SHM name: {self.frame_shm.name}")
        print(f"Meta SHM name:  {self.meta_shm.name}")
        print(f"Frame shape:    {self.frame_shape}")
        print(f"Frame dtype:    {self.frame_dtype}")

        acquisition_running = True
        running = True

        try:
            while running:
                # ------------------------------------------------
                # 1. Check for ZMQ command
                # ------------------------------------------------
                try:
                    msg = socket.recv_json(flags=zmq.NOBLOCK)
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
                        # Explicitly call camOBJ methods
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
                            reply = {"ok": True, "result": result, "client_id": client_id}

                        elif cmd == "set_software_trigger_mode":
                            result = camOBJ.SetSoftwareTriggerMode()
                            reply = {"ok": True, "result": result, "client_id": client_id}

                        elif cmd == "set_hardware_trigger_mode":
                            lineNumber = msg.get("lineNumber", 0)
                            RiseEdgeOrFallEdge = msg.get("RiseEdgeOrFallEdge", 1)

                            result = camOBJ.SetHardwareTriggerMode(
                                lineNumber=lineNumber,
                                RiseEdgeOrFallEdge=RiseEdgeOrFallEdge,
                            )

                            reply = {"ok": True, "result": result, "client_id": client_id}

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

                            old_frame_shm_name = self.frame_shm.name

                            # Stop publishing while ROI changes.
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

                            # Recreate frame shared memory for the new ROI size.
                            self.RecreateFrameSharedMemory(
                                camOBJ=camOBJ,
                                old_frame_shm_name=old_frame_shm_name,
                            )

                            reply = {
                                "ok": True,
                                "result": result,
                                "client_id": client_id,
                            }

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
                        reply = {
                            "ok": False,
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(),
                            "client_id": msg.get("client_id", "unknown_client"),
                        }

                    socket.send_json(reply)

                # ------------------------------------------------
                # 2. Publish latest frame
                # ------------------------------------------------
                if acquisition_running:
                    try:
                        frame = np.asarray(camOBJ.GetFrame())

                        if frame.shape != self.frame_shape:
                            raise ValueError(
                                f"Camera frame shape changed from {self.frame_shape} to {frame.shape}. "
                                "Restart the camera server after changing ROI."
                            )

                        if frame.dtype != self.frame_dtype:
                            frame = frame.astype(self.frame_dtype, copy=False)

                        self.meta_arr[0] = 1
                        self.frame_arr[:] = frame
                        self.meta_arr[1] += 1
                        self.meta_arr[2] = time.time_ns()
                        self.meta_arr[0] = 0

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
                socket.close(0)
            except Exception:
                pass

            try:
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
            
    def RecreateFrameSharedMemory(self, camOBJ, old_frame_shm_name):
        """
        Recreate frame shared memory after ROI/frame size changes.

        The metadata shared memory stays the same.
        The frame shared memory is recreated using the same name.
        Clients detect the layout version change and reattach.
        """

        # Mark shared memory as unstable.
        self.meta_arr[0] = 1

        # Get a frame with the new ROI.
        new_frame = np.asarray(camOBJ.GetFrame())
        new_frame_shape = tuple(new_frame.shape)
        new_frame_dtype = np.dtype(new_frame.dtype)
        new_frame_nbytes = int(np.prod(new_frame_shape) * new_frame_dtype.itemsize)

        # Close and unlink old frame shared memory.
        try:
            if self.frame_shm is not None:
                self.frame_shm.close()
                self.frame_shm.unlink()
        except FileNotFoundError:
            pass

        # Recreate using the same shared memory name.
        self.frame_shm = shared_memory.SharedMemory(
            name=old_frame_shm_name,
            create=True,
            size=new_frame_nbytes,
        )

        self.frame_arr = np.ndarray(
            new_frame_shape,
            dtype=new_frame_dtype,
            buffer=self.frame_shm.buf,
        )

        self.frame_arr[:] = new_frame

        # Update server-side frame information.
        self.frame_shape = new_frame_shape
        self.frame_dtype = new_frame_dtype

        self.meta_arr[1] += 1
        self.meta_arr[2] = time.time_ns()

        # Increment layout version so clients know to reattach.
        self.meta_arr[4] += 1

        # Mark stable again.
        self.meta_arr[0] = 0

        print("Frame shared memory recreated after ROI change.")
        print(f"New frame shape: {new_frame_shape}")
        print(f"New frame dtype: {new_frame_dtype}")
        print(f"Frame SHM name:  {self.frame_shm.name}")



if __name__ == "__main__":
    mp.freeze_support()

    server = CameraServer(
        host="127.0.0.1",
        port=50731,
        CameraType="FLIR Point Grey",
        CameraKwargs={
            "CameraIdx": 0,
            "verbose": True,
        },
        PollSleep=0.001,
    )

    server.run_forever()