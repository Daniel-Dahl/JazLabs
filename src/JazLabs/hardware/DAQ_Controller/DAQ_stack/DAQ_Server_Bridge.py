import json
import multiprocessing as mp
import time
import traceback
from multiprocessing import shared_memory

import numpy as np
import zmq


class DAQZMQBridgeServer:
    """
    Local compatibility bridge for a remote DAQZMQServer.

    Start the remote DAQZMQServer with PublishVoltagesOverZMQ=True so the bridge
    can mirror the remote voltage array into local shared memory.
    """

    def __init__(
        self,
        local_host="127.0.0.1",
        local_command_port=50831,
        local_voltage_pub_port=50832,
        remote_host="10.196.0.67",
        remote_command_port=50831,
        remote_voltage_pub_port=50832,
        voltage_topic="daq.voltages",
        timeout_ms=5000,
        PollSleep=0.0,
    ):
        self.local_host = local_host
        self.local_command_port = int(local_command_port)
        self.local_voltage_pub_port = int(local_voltage_pub_port)
        self.remote_host = remote_host
        self.remote_command_port = int(remote_command_port)
        self.remote_voltage_pub_port = int(remote_voltage_pub_port)
        self.voltage_topic = str(voltage_topic)
        self.timeout_ms = int(timeout_ms)
        self.PollSleep = float(PollSleep)

        self.Process = None
        self.voltage_shm = None
        self.voltage_arr = None
        self.meta_shm = None
        self.meta_arr = None
        self.remote_properties = {}

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("DAQ bridge server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"DAQ bridge server process started with PID {self.Process.pid}")

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
        remote_command_socket.send_json(msg)
        reply = remote_command_socket.recv_json()

        if not reply.get("ok", False):
            error = reply.get("error", "Unknown remote DAQ server error")
            traceback_text = reply.get("traceback", "")
            if traceback_text:
                error = error + "\n" + traceback_text
            raise RuntimeError(error)

        return reply, remote_command_socket

    def _create_shared_memory_from_remote_properties(self, properties):
        channel_count = int(properties["channel_count"])

        self.voltage_shm = shared_memory.SharedMemory(
            create=True,
            size=channel_count * np.dtype(np.float64).itemsize,
        )
        self.voltage_arr = np.ndarray(
            (channel_count,),
            dtype=np.float64,
            buffer=self.voltage_shm.buf,
        )

        self.meta_shm = shared_memory.SharedMemory(
            create=True,
            size=4 * np.dtype(np.int64).itemsize,
        )
        self.meta_arr = np.ndarray((4,), dtype=np.int64, buffer=self.meta_shm.buf)

        self.voltage_arr[:] = 0.0
        self.meta_arr[:] = 0
        self.meta_arr[3] = 1

    def _get_local_properties(self):
        return {
            "daq_type": self.remote_properties.get("daq_type", "remote_daq"),
            "command_port": self.local_command_port,
            "voltage_pub_port": self.local_voltage_pub_port,
            "channel_count": int(self.remote_properties["channel_count"]),
            "voltage_min": float(self.remote_properties["voltage_min"]),
            "voltage_max": float(self.remote_properties["voltage_max"]),
            "voltage_shared_memory_name": self.voltage_shm.name,
            "voltage_shape": list(self.voltage_arr.shape),
            "voltage_dtype": str(self.voltage_arr.dtype),
            "meta_shared_memory_name": self.meta_shm.name,
            "meta_shape": [4],
            "meta_dtype": "int64",
            "voltage_counter": int(self.meta_arr[1]),
            "last_write_time_ns": int(self.meta_arr[2]),
            "server_alive": bool(self.meta_arr[3]),
            "remote_host": self.remote_host,
            "remote_command_port": self.remote_command_port,
            "remote_voltage_pub_port": self.remote_voltage_pub_port,
        }

    def _publish_local_voltage_notification(self, local_voltage_pub_socket):
        local_voltage_pub_socket.send_json(
            {
                "type": "voltage_update",
                "voltage_counter": int(self.meta_arr[1]),
                "last_write_time_ns": int(self.meta_arr[2]),
                "channel_count": int(self.voltage_arr.shape[0]),
            }
        )

    def _write_remote_voltages_to_local_shared_memory(self, header, voltage_bytes):
        remote_shape = tuple(header["shape"])
        remote_dtype = np.dtype(header["dtype"])
        voltages = np.frombuffer(voltage_bytes, dtype=remote_dtype).reshape(remote_shape)

        if voltages.shape != self.voltage_arr.shape:
            raise ValueError(
                f"Remote voltage shape changed from {self.voltage_arr.shape} to {voltages.shape}."
            )

        self.meta_arr[0] = 1
        self.voltage_arr[:] = voltages.astype(np.float64, copy=False)
        self.meta_arr[1] = int(header.get("voltage_counter", int(self.meta_arr[1]) + 1))
        self.meta_arr[2] = int(header.get("last_write_time_ns", time.time_ns()))
        self.meta_arr[0] = 0

    def _receive_latest_remote_voltages(self, remote_voltage_sub_socket):
        latest_parts = None

        while True:
            try:
                latest_parts = remote_voltage_sub_socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                return latest_parts

    def run_forever(self):
        context = None
        local_command_socket = None
        local_voltage_pub_socket = None
        remote_voltage_sub_socket = None
        remote_command_socket = None

        try:
            context = zmq.Context()
            remote_command_socket = self._reset_remote_command_socket(context, None)
            properties_reply, remote_command_socket = self._send_remote_command(
                context,
                remote_command_socket,
                {"cmd": "get_properties", "client_id": "daq_bridge_startup"},
            )
            self.remote_properties = dict(properties_reply.get("result", {}))
            self._create_shared_memory_from_remote_properties(self.remote_properties)

            local_command_socket = context.socket(zmq.REP)
            local_command_socket.bind(f"tcp://{self.local_host}:{self.local_command_port}")

            local_voltage_pub_socket = context.socket(zmq.PUB)
            local_voltage_pub_socket.bind(f"tcp://{self.local_host}:{self.local_voltage_pub_port}")

            remote_voltage_sub_socket = context.socket(zmq.SUB)
            remote_voltage_sub_socket.setsockopt(zmq.RCVHWM, 1)
            remote_voltage_sub_socket.setsockopt_string(zmq.SUBSCRIBE, self.voltage_topic)
            remote_voltage_sub_socket.connect(
                f"tcp://{self.remote_host}:{self.remote_voltage_pub_port}"
            )

            poller = zmq.Poller()
            poller.register(local_command_socket, zmq.POLLIN)
            poller.register(remote_voltage_sub_socket, zmq.POLLIN)

            running = True
            print("DAQ ZMQ bridge server running.")

            while running:
                events = dict(poller.poll(timeout=1000))

                if remote_voltage_sub_socket in events:
                    try:
                        latest_parts = self._receive_latest_remote_voltages(
                            remote_voltage_sub_socket
                        )
                        if latest_parts is not None:
                            if len(latest_parts) != 3:
                                raise ValueError(
                                    "Remote DAQ voltages must be multipart "
                                    "[topic, header, voltages]"
                                )
                            _, header_bytes, voltage_bytes = latest_parts
                            header = json.loads(header_bytes.decode("utf-8"))
                            if header.get("type") == "voltage_update":
                                self._write_remote_voltages_to_local_shared_memory(
                                    header,
                                    voltage_bytes,
                                )
                                self._publish_local_voltage_notification(
                                    local_voltage_pub_socket
                                )
                    except Exception as exc:
                        print("DAQ bridge voltage receive error:")
                        print(f"{type(exc).__name__}: {exc}")
                        print(traceback.format_exc())
                        time.sleep(0.01)

                if local_command_socket in events:
                    msg = {}
                    try:
                        msg = local_command_socket.recv_json()
                        cmd = msg.get("cmd")
                        client_id = msg.get("client_id", "unknown_client")

                        if cmd == "get_properties":
                            properties_reply, remote_command_socket = self._send_remote_command(
                                context,
                                remote_command_socket,
                                {"cmd": "get_properties", "client_id": "daq_bridge_properties"},
                            )
                            self.remote_properties = dict(properties_reply.get("result", {}))
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
                            if cmd == "shutdown":
                                running = False
                            reply = {
                                "ok": True,
                                "result": remote_reply.get("result", None),
                                "client_id": client_id,
                            }

                    except Exception as exc:
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

                    local_command_socket.send_json(reply)

                if self.PollSleep > 0:
                    time.sleep(self.PollSleep)

        finally:
            print("Closing DAQ ZMQ bridge server...")

            try:
                if self.meta_arr is not None:
                    self.meta_arr[3] = 0
            except Exception:
                pass

            for socket in (
                local_command_socket,
                local_voltage_pub_socket,
                remote_voltage_sub_socket,
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

            for shm in (self.voltage_shm, self.meta_shm):
                try:
                    if shm is not None:
                        shm.close()
                        shm.unlink()
                except Exception:
                    pass

            print("DAQ ZMQ bridge server closed.")


if __name__ == "__main__":
    mp.freeze_support()
    bridge = DAQZMQBridgeServer()
    bridge.run_forever()
