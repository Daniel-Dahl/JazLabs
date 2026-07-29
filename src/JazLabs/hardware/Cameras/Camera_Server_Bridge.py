import json
import time
import traceback
import multiprocessing as mp
from multiprocessing import shared_memory

import numpy as np
import zmq


class CameraZMQBridgeServer:
    """
    Local compatibility bridge for a remote CameraZMQServer.

    The remote camera server must be started with PublishFramesOverZMQ=True.
    This bridge receives those network frames, writes them into local shared
    memory, and exposes the same command and frame-notification interface that
    Camera_Client.py already expects.
    """

    def __init__(
        self,
        local_host="127.0.0.1",
        local_command_port=50731,
        local_frame_pub_port=50732,
        remote_host="127.0.0.1",
        remote_command_port=50731,
        remote_frame_pub_port=50732,
        frame_topic="camera.frame",
        timeout_ms=5000,
        PollSleep=0.0,
    ):
        self.local_host = local_host
        self.local_command_port = int(local_command_port)
        self.local_frame_pub_port = int(local_frame_pub_port)
        self.remote_host = remote_host
        self.remote_command_port = int(remote_command_port)
        self.remote_frame_pub_port = int(remote_frame_pub_port)
        self.frame_topic = str(frame_topic)
        self.timeout_ms = int(timeout_ms)
        self.PollSleep = float(PollSleep)

        self.Process = None

        self.frame_shm = None
        self.frame_arr = None
        self.meta_shm = None
        self.meta_arr = None

        self.frame_shape = None
        self.frame_dtype = None
        self.remote_properties = {}

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Camera bridge server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Camera bridge server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://{self.local_host}:{self.local_command_port}")
            socket.send_json({"cmd": "shutdown_bridge", "client_id": "bridge_controller"})
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

    def _reset_remote_command_socket(self, context, remote_command_socket):
        try:
            if remote_command_socket is not None:
                remote_command_socket.close(0)
        except Exception:
            pass

        remote_command_socket = context.socket(zmq.REQ)
        remote_command_socket.setsockopt(zmq.LINGER, 0)
        remote_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        remote_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        remote_command_socket.connect(
            f"tcp://{self.remote_host}:{self.remote_command_port}"
        )
        return remote_command_socket

    def _send_remote_command(self, context, remote_command_socket, msg):
        msg = dict(msg)

        try:
            remote_command_socket.send_json(msg)
            reply = remote_command_socket.recv_json()
        except Exception:
            try:
                remote_command_socket.close(0)
            except Exception:
                pass
            raise

        if not reply.get("ok", False):
            error = reply.get("error", "Unknown remote camera server error")
            traceback_text = reply.get("traceback", "")
            if traceback_text:
                error = error + "\n" + traceback_text
            raise RuntimeError(error)

        return reply, remote_command_socket

    def _create_shared_memory_from_remote_properties(self, properties):
        self.frame_shape = tuple(properties["frame_shape"])
        self.frame_dtype = np.dtype(properties["frame_dtype"])
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

        self.frame_arr[:] = 0
        self.meta_arr[:] = 0
        self.meta_arr[3] = 1
        self.meta_arr[4] = int(properties.get("frame_layout_version", 1))

    def _get_local_properties(self):
        acquisition_running = self.remote_properties.get("acquisition_running", None)
        camera_type = self.remote_properties.get("camera_type", "remote_camera")

        return {
            "camera_type": camera_type,
            "command_port": self.local_command_port,
            "frame_pub_port": self.local_frame_pub_port,
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
            "continuous_publish_fps": self.remote_properties.get(
                "continuous_publish_fps",
                None,
            ),
            "remote_host": self.remote_host,
            "remote_command_port": self.remote_command_port,
            "remote_frame_pub_port": self.remote_frame_pub_port,
        }

    def _publish_local_frame_notification(self, local_frame_pub_socket):
        local_frame_pub_socket.send_json(
            {
                "type": "new_frame",
                "frame_counter": int(self.meta_arr[1]),
                "last_write_time_ns": int(self.meta_arr[2]),
                "frame_layout_version": int(self.meta_arr[4]),
            }
        )

    def _recreate_local_frame_shared_memory(self, new_frame_shape, new_frame_dtype):
        self.meta_arr[0] = 1

        try:
            if self.frame_shm is not None:
                self.frame_shm.close()
                self.frame_shm.unlink()
        except FileNotFoundError:
            pass

        frame_nbytes = int(np.prod(new_frame_shape) * new_frame_dtype.itemsize)
        self.frame_shm = shared_memory.SharedMemory(
            create=True,
            size=frame_nbytes,
        )
        self.frame_arr = np.ndarray(
            new_frame_shape,
            dtype=new_frame_dtype,
            buffer=self.frame_shm.buf,
        )

        self.frame_shape = tuple(new_frame_shape)
        self.frame_dtype = np.dtype(new_frame_dtype)
        self.meta_arr[4] += 1
        self.meta_arr[0] = 0

        print("Camera bridge recreated local frame shared memory.")
        print(f"New frame shape: {self.frame_shape}")
        print(f"New frame dtype: {self.frame_dtype}")
        print(f"Frame SHM name:  {self.frame_shm.name}")

    def _write_remote_frame_to_local_shared_memory(self, header, frame_bytes):
        remote_shape = tuple(header["shape"])
        remote_dtype = np.dtype(header["dtype"])

        if remote_shape != self.frame_shape or remote_dtype != self.frame_dtype:
            self._recreate_local_frame_shared_memory(remote_shape, remote_dtype)

        frame = np.frombuffer(frame_bytes, dtype=remote_dtype).reshape(remote_shape)

        self.meta_arr[0] = 1
        self.frame_arr[:] = frame
        self.meta_arr[1] = int(header.get("frame_counter", int(self.meta_arr[1]) + 1))
        self.meta_arr[2] = int(header.get("last_write_time_ns", time.time_ns()))
        remote_layout_version = int(
            header.get("frame_layout_version", int(self.meta_arr[4]))
        )
        if remote_layout_version > int(self.meta_arr[4]):
            self.meta_arr[4] = remote_layout_version
        self.meta_arr[0] = 0

    def _receive_latest_remote_frame(self, remote_frame_sub_socket):
        latest_parts = None

        while True:
            try:
                latest_parts = remote_frame_sub_socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                return latest_parts

    def run_forever(self):
        context = None
        local_command_socket = None
        local_frame_pub_socket = None
        remote_frame_sub_socket = None
        remote_command_socket = None

        try:
            context = zmq.Context()
            remote_command_socket = self._reset_remote_command_socket(context, None)

            properties_reply, remote_command_socket = self._send_remote_command(
                context,
                remote_command_socket,
                {
                    "cmd": "get_properties",
                    "client_id": "camera_bridge_startup",
                },
            )
            self.remote_properties = dict(properties_reply.get("result", {}))
            self._create_shared_memory_from_remote_properties(self.remote_properties)

            local_command_socket = context.socket(zmq.REP)
            local_command_socket.bind(
                f"tcp://{self.local_host}:{self.local_command_port}"
            )

            local_frame_pub_socket = context.socket(zmq.PUB)
            local_frame_pub_socket.bind(
                f"tcp://{self.local_host}:{self.local_frame_pub_port}"
            )

            remote_frame_sub_socket = context.socket(zmq.SUB)
            remote_frame_sub_socket.setsockopt(zmq.RCVHWM, 1)
            remote_frame_sub_socket.setsockopt_string(zmq.SUBSCRIBE, self.frame_topic)
            remote_frame_sub_socket.connect(
                f"tcp://{self.remote_host}:{self.remote_frame_pub_port}"
            )

            poller = zmq.Poller()
            poller.register(local_command_socket, zmq.POLLIN)
            poller.register(remote_frame_sub_socket, zmq.POLLIN)

            running = True

            print("Camera ZMQ bridge server running.")
            print(f"Local command socket: tcp://{self.local_host}:{self.local_command_port}")
            print(f"Local frame PUB socket: tcp://{self.local_host}:{self.local_frame_pub_port}")
            print(f"Remote command socket: tcp://{self.remote_host}:{self.remote_command_port}")
            print(f"Remote frame SUB socket: tcp://{self.remote_host}:{self.remote_frame_pub_port}")
            print(f"Frame topic: {self.frame_topic}")
            print(f"Local frame SHM name: {self.frame_shm.name}")
            print(f"Local meta SHM name:  {self.meta_shm.name}")
            print(f"Frame shape:          {self.frame_shape}")
            print(f"Frame dtype:          {self.frame_dtype}")

            while running:
                events = dict(poller.poll(timeout=1000))

                if remote_frame_sub_socket in events:
                    try:
                        latest_parts = self._receive_latest_remote_frame(
                            remote_frame_sub_socket
                        )

                        if latest_parts is not None:
                            if len(latest_parts) != 3:
                                raise ValueError(
                                    "Remote camera frame must be multipart "
                                    "[topic, header, frame]"
                                )

                            _, header_bytes, frame_bytes = latest_parts
                            header = json.loads(header_bytes.decode("utf-8"))
                            if header.get("type") != "new_frame":
                                continue

                            self._write_remote_frame_to_local_shared_memory(
                                header,
                                frame_bytes,
                            )
                            self._publish_local_frame_notification(local_frame_pub_socket)

                    except Exception as e:
                        print("Camera bridge frame receive error:")
                        print(f"{type(e).__name__}: {e}")
                        print(traceback.format_exc())
                        time.sleep(0.01)

                if local_command_socket in events:
                    msg = {}
                    try:
                        msg = local_command_socket.recv_json()
                        cmd = msg.get("cmd")
                        client_id = msg.get("client_id", "unknown_client")

                        if cmd == "get_properties":
                            properties_reply, remote_command_socket = (
                                self._send_remote_command(
                                    context,
                                    remote_command_socket,
                                    {
                                        "cmd": "get_properties",
                                        "client_id": "camera_bridge_properties",
                                    },
                                )
                            )
                            self.remote_properties = dict(
                                properties_reply.get("result", {})
                            )
                            reply = {
                                "ok": True,
                                "result": self._get_local_properties(),
                                "client_id": client_id,
                            }

                        elif cmd == "shutdown_bridge":
                            running = False
                            reply = {"ok": True, "result": None, "client_id": client_id}

                        else:
                            remote_reply, remote_command_socket = self._send_remote_command(
                                context,
                                remote_command_socket,
                                msg,
                            )
                            remote_result = remote_reply.get("result", None)

                            if cmd == "shutdown":
                                running = False

                            if cmd in ("set_roi", "fire_software_trigger", "software_trigger"):
                                try:
                                    properties_reply, remote_command_socket = (
                                        self._send_remote_command(
                                            context,
                                            remote_command_socket,
                                            {
                                                "cmd": "get_properties",
                                                "client_id": "camera_bridge_refresh",
                                            },
                                        )
                                    )
                                    self.remote_properties = dict(
                                        properties_reply.get("result", {})
                                    )
                                except Exception:
                                    pass

                            reply = {
                                "ok": True,
                                "result": remote_result,
                                "client_id": client_id,
                            }

                    except Exception as e:
                        try:
                            remote_command_socket = self._reset_remote_command_socket(
                                context,
                                remote_command_socket,
                            )
                        except Exception:
                            pass

                        reply = {
                            "ok": False,
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(),
                            "client_id": msg.get("client_id", "unknown_client"),
                        }

                    local_command_socket.send_json(reply)

                if self.PollSleep > 0:
                    time.sleep(self.PollSleep)

        finally:
            print("Closing camera ZMQ bridge server...")

            try:
                if self.meta_arr is not None:
                    self.meta_arr[3] = 0
            except Exception:
                pass

            for socket in (
                local_command_socket,
                local_frame_pub_socket,
                remote_frame_sub_socket,
                remote_command_socket,
            ):
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

            print("Camera ZMQ bridge server closed.")


if __name__ == "__main__":
    mp.freeze_support()

    bridge = CameraZMQBridgeServer(
        local_host="127.0.0.1",
        local_command_port=50731,
        local_frame_pub_port=50732,
        remote_host="127.0.0.1",
        remote_command_port=50731,
        remote_frame_pub_port=50732,
        frame_topic="camera.frame",
    )

    bridge.run_forever()
