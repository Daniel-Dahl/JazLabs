import argparse
import json
import multiprocessing as mp
from multiprocessing import shared_memory
import time
import traceback

import numpy as np
import zmq


VIEWER_METADATA_LENGTH = 4
VIEWER_SEQUENCE_INDEX = 0
VIEWER_FRAME_ID_INDEX = 1
VIEWER_CHANNEL_INDEX = 2
VIEWER_CHANNEL_COUNT_INDEX = 3


class SLMZMQBridgeServer:
    """
    Local bridge for a remote SLMZMQServer.

    The bridge exposes the same command interface as the physical SLM server.
    It forwards WriteToDisplay commands to the remote server and commits the
    retained image to local display state only after the remote server confirms
    that the write succeeded.
    """

    def __init__(
        self,
        local_host="127.0.0.1",
        local_command_port=5565,
        local_display_pub_port=5566,
        remote_host="127.0.0.1",
        remote_command_port=5555,
        remote_display_pub_port=5556,
        display_topic="slm.display",
        timeout_ms=5000,
        PollSleep=0.0,
    ):
        self.local_host = local_host
        self.local_command_port = int(local_command_port)
        self.local_display_pub_port = int(local_display_pub_port)
        self.remote_host = remote_host
        self.remote_command_port = int(remote_command_port)
        self.remote_display_pub_port = int(remote_display_pub_port)
        self.display_topic = str(display_topic)
        self.timeout_ms = int(timeout_ms)
        self.PollSleep = float(PollSleep)

        self.Process = None
        self.viewer_shm = None
        self.viewer_arr = None
        self.viewer_metadata = None
        self.viewer_shape = None
        self.viewer_dtype = None
        self.remote_properties = {}
        self.last_frame_id = 0
        self.last_write_time_ns = 0
        self.last_display_success = False
        self.last_timing = {}
        self.next_write_id = 1

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM bridge server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"SLM bridge server process started with PID {self.Process.pid}")

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

    def _send_remote_json_command(self, remote_command_socket, msg):
        remote_command_socket.send_json(dict(msg))
        reply = remote_command_socket.recv_json()
        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown remote SLM server error")
                + "\n"
                + reply.get("traceback", "")
            )
        return reply

    def _send_remote_image_command(self, remote_command_socket, header, image_bytes):
        remote_command_socket.send_multipart(
            [
                json.dumps(dict(header)).encode("utf-8"),
                image_bytes,
            ]
        )
        reply = remote_command_socket.recv_json()
        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown remote SLM server error")
                + "\n"
                + reply.get("traceback", "")
            )
        return reply

    def _send_remote_snapshot_command(self, remote_command_socket, msg):
        remote_command_socket.send_json(dict(msg))
        reply_parts = remote_command_socket.recv_multipart()
        if not reply_parts:
            raise RuntimeError("Remote SLM server returned an empty snapshot reply")

        reply = json.loads(reply_parts[0].decode("utf-8"))
        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown remote SLM server error")
                + "\n"
                + reply.get("traceback", "")
            )
        return reply_parts

    def _create_local_viewer_shared_memory(self, properties):
        self.viewer_shape = tuple(properties["input_expected_shape"])
        self.viewer_dtype = np.dtype(np.uint8)
        nbytes = int(np.prod(self.viewer_shape) * self.viewer_dtype.itemsize)
        metadata_itemsize = np.dtype(np.int64).itemsize
        metadata_offset = (
            (nbytes + metadata_itemsize - 1) // metadata_itemsize
        ) * metadata_itemsize
        metadata_nbytes = VIEWER_METADATA_LENGTH * metadata_itemsize

        self.viewer_shm = shared_memory.SharedMemory(
            create=True,
            size=metadata_offset + metadata_nbytes,
        )
        self.viewer_arr = np.ndarray(
            self.viewer_shape,
            dtype=self.viewer_dtype,
            buffer=self.viewer_shm.buf,
        )
        self.viewer_arr.fill(0)
        self.viewer_metadata = np.ndarray(
            (VIEWER_METADATA_LENGTH,),
            dtype=np.int64,
            buffer=self.viewer_shm.buf,
            offset=metadata_offset,
        )
        self.viewer_metadata.fill(0)
        self.viewer_metadata[VIEWER_CHANNEL_COUNT_INDEX] = int(
            properties["number_of_channels"]
        )

    def _get_local_properties(self):
        properties = dict(self.remote_properties)
        properties["command_port"] = self.local_command_port
        properties["display_pub_port"] = self.local_display_pub_port
        properties["display_topic"] = self.display_topic
        properties["viewer_shared_memory_name"] = self.viewer_shm.name
        properties["viewer_shape"] = list(self.viewer_shape)
        properties["viewer_dtype"] = str(self.viewer_dtype)
        properties["viewer_metadata_offset"] = int(
            self.viewer_metadata.ctypes.data - self.viewer_arr.ctypes.data
        )
        properties["viewer_metadata_length"] = VIEWER_METADATA_LENGTH
        properties["remote_host"] = self.remote_host
        properties["remote_command_port"] = self.remote_command_port
        properties["remote_display_pub_port"] = self.remote_display_pub_port
        properties["last_frame_id"] = int(self.last_frame_id)
        properties["last_write_time_ns"] = int(self.last_write_time_ns)
        properties["last_display_success"] = bool(self.last_display_success)
        properties["last_timing"] = self.last_timing
        return properties

    def _image_from_command(self, header, image_bytes):
        shape = tuple(header["shape"])
        dtype = np.dtype(header.get("dtype", "uint8"))

        if shape != self.viewer_shape:
            raise ValueError(
                f"Expected image shape {self.viewer_shape}, got {shape}"
            )
        if dtype != self.viewer_dtype:
            raise ValueError(
                f"Expected image dtype {self.viewer_dtype}, got {dtype}"
            )

        return np.frombuffer(image_bytes, dtype=dtype).reshape(shape)

    def _publish_local_display(self, local_display_pub_socket, header):
        local_header = dict(header)
        local_header["type"] = "slm_display"
        local_header["frame_id"] = int(self.last_frame_id)
        local_header["last_write_time_ns"] = int(self.last_write_time_ns)
        local_header["ok"] = bool(self.last_display_success)
        local_header["shape"] = list(self.viewer_shape)
        local_header["dtype"] = str(self.viewer_dtype)
        local_header["timing"] = self.last_timing

        local_display_pub_socket.send_multipart(
            [
                self.display_topic.encode("utf-8"),
                json.dumps(local_header).encode("utf-8"),
                memoryview(self.viewer_arr),
            ]
        )

    def _submit_display_write(
        self,
        remote_command_socket,
        local_display_pub_socket,
        header,
        image_bytes,
    ):
        pending_image = self._image_from_command(header, image_bytes)

        remote_header = dict(header)
        if "write_id" not in remote_header:
            remote_header["write_id"] = int(self.next_write_id)
            self.next_write_id += 1

        expected_write_id = int(remote_header["write_id"])
        expected_client_id = remote_header.get("client_id", "unknown_client")
        remote_reply = self._send_remote_image_command(
            remote_command_socket,
            remote_header,
            image_bytes,
        )
        result = remote_reply.get("result", {})

        acknowledged_write_id = int(result.get("write_id", -1))
        acknowledged_client_id = remote_reply.get("client_id")
        if acknowledged_write_id != expected_write_id:
            raise RuntimeError(
                "Remote SLM acknowledgement write_id "
                f"{acknowledged_write_id} does not match {expected_write_id}"
            )
        if acknowledged_client_id != expected_client_id:
            raise RuntimeError(
                "Remote SLM acknowledgement client_id "
                f"{acknowledged_client_id!r} does not match {expected_client_id!r}"
            )

        if not bool(result.get("display_ok", False)):
            self.last_display_success = False
            return remote_reply

        self.last_frame_id = int(result["frame_id"])
        self.last_write_time_ns = int(
            result.get("last_write_time_ns", time.time_ns())
        )
        self.last_display_success = True
        self.last_timing = dict(result.get("timing", {}))

        self.viewer_metadata[VIEWER_SEQUENCE_INDEX] += 1
        try:
            np.copyto(self.viewer_arr, pending_image)
            self.viewer_metadata[VIEWER_FRAME_ID_INDEX] = self.last_frame_id
            self.viewer_metadata[VIEWER_CHANNEL_INDEX] = int(
                remote_header.get("channelIdx", 0)
            )
        finally:
            self.viewer_metadata[VIEWER_SEQUENCE_INDEX] += 1

        confirmed_header = {
            "client_id": expected_client_id,
            "write_id": expected_write_id,
            "channelIdx": int(remote_header.get("channelIdx", 0)),
        }
        self._publish_local_display(local_display_pub_socket, confirmed_header)
        return remote_reply

    def run_forever(self):
        context = None
        local_command_socket = None
        local_display_pub_socket = None
        remote_command_socket = None

        try:
            context = zmq.Context()
            remote_command_socket = self._reset_remote_command_socket(context, None)
            properties_reply = self._send_remote_json_command(
                remote_command_socket,
                {"cmd": "get_properties", "client_id": "slm_bridge_startup"},
            )
            self.remote_properties = dict(properties_reply.get("result", {}))
            self._create_local_viewer_shared_memory(self.remote_properties)

            local_command_socket = context.socket(zmq.REP)
            local_command_socket.bind(
                f"tcp://{self.local_host}:{self.local_command_port}"
            )

            local_display_pub_socket = context.socket(zmq.PUB)
            local_display_pub_socket.setsockopt(zmq.SNDHWM, 4)
            local_display_pub_socket.bind(
                f"tcp://{self.local_host}:{self.local_display_pub_port}"
            )

            poller = zmq.Poller()
            poller.register(local_command_socket, zmq.POLLIN)

            print("SLM ZMQ bridge server running.")
            print(f"Local command socket: tcp://{self.local_host}:{self.local_command_port}")
            print(f"Local display PUB socket: tcp://{self.local_host}:{self.local_display_pub_port}")
            print(f"Remote command socket: tcp://{self.remote_host}:{self.remote_command_port}")
            print(f"Display topic: {self.display_topic}")
            print(f"Local viewer SHM name: {self.viewer_shm.name}")
            print(f"Viewer shape: {self.viewer_shape}")

            running = True

            while running:
                events = dict(poller.poll(timeout=1000))

                if local_command_socket in events:
                    msg = {}
                    reply_parts = None
                    try:
                        parts = local_command_socket.recv_multipart()
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
                            properties_reply = self._send_remote_json_command(
                                remote_command_socket,
                                {
                                    "cmd": "get_properties",
                                    "client_id": "slm_bridge_properties",
                                },
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

                        elif cmd == "get_confirmed_display_state":
                            reply_parts = self._send_remote_snapshot_command(
                                remote_command_socket,
                                msg,
                            )

                        elif len(parts) == 2 and cmd == "write_to_display":
                            remote_reply = self._submit_display_write(
                                remote_command_socket,
                                local_display_pub_socket,
                                msg,
                                parts[1],
                            )
                            reply = {
                                "ok": True,
                                "result": remote_reply.get("result", None),
                                "client_id": client_id,
                            }

                        elif len(parts) == 2:
                            remote_reply = self._send_remote_image_command(
                                remote_command_socket,
                                msg,
                                parts[1],
                            )
                            reply = {
                                "ok": True,
                                "result": remote_reply.get("result", None),
                                "client_id": client_id,
                            }

                        else:
                            remote_reply = self._send_remote_json_command(
                                remote_command_socket,
                                msg,
                            )
                            if cmd == "shutdown":
                                running = False
                            reply = {
                                "ok": True,
                                "result": remote_reply.get("result", None),
                                "client_id": client_id,
                            }

                    except Exception as exc:
                        reply_parts = None
                        try:
                            remote_command_socket = self._reset_remote_command_socket(
                                context,
                                remote_command_socket,
                            )
                        except Exception:
                            pass
                        reply = {
                            "ok": False,
                            "error": f"{type(exc).__name__}: {exc}",
                            "traceback": traceback.format_exc(),
                            "client_id": msg.get("client_id", "unknown_client"),
                        }

                    if reply_parts is not None:
                        local_command_socket.send_multipart(reply_parts)
                    else:
                        local_command_socket.send_json(reply)

                if self.PollSleep > 0:
                    time.sleep(self.PollSleep)

        finally:
            print("Closing SLM ZMQ bridge server...")

            for socket in (
                local_command_socket,
                local_display_pub_socket,
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
                if self.viewer_shm is not None:
                    self.viewer_shm.close()
                    self.viewer_shm.unlink()
            except Exception:
                pass

            print("SLM ZMQ bridge server closed.")


if __name__ == "__main__":
    mp.freeze_support()

    parser = argparse.ArgumentParser(description="Run an SLMStack bridge server.")
    parser.add_argument("--local-host", default="127.0.0.1")
    parser.add_argument("--local-command-port", type=int, default=5565)
    parser.add_argument("--local-display-pub-port", type=int, default=5566)
    parser.add_argument("--remote-host", default="127.0.0.1")
    parser.add_argument("--remote-command-port", type=int, default=5555)
    parser.add_argument("--remote-display-pub-port", type=int, default=5556)
    parser.add_argument("--display-topic", default="slm.display")
    args = parser.parse_args()

    bridge = SLMZMQBridgeServer(
        local_host=args.local_host,
        local_command_port=args.local_command_port,
        local_display_pub_port=args.local_display_pub_port,
        remote_host=args.remote_host,
        remote_command_port=args.remote_command_port,
        remote_display_pub_port=args.remote_display_pub_port,
        display_topic=args.display_topic,
    )
    bridge.run_forever()
