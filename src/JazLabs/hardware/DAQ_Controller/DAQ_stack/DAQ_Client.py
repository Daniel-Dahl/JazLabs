import inspect
import json
import time
from multiprocessing import shared_memory

import numpy as np
import zmq


_SHARED_MEMORY_SUPPORTS_TRACK = (
    "track" in inspect.signature(shared_memory.SharedMemory).parameters
)


def _attach_shared_memory(name):
    if _SHARED_MEMORY_SUPPORTS_TRACK:
        return shared_memory.SharedMemory(name=name, track=False)

    return shared_memory.SharedMemory(name=name)


class DAQClient:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50831,
        voltage_pub_port=50832,
        timeout_ms=5000,
        client_id="daq_client",
    ):
        self.host = host
        self.command_port = int(command_port)
        self.voltage_pub_port = int(voltage_pub_port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = client_id

        self.context = zmq.Context()
        self.socket = None
        self.voltage_sub_socket = self.context.socket(zmq.SUB)

        self._connect_command_socket()

        self.voltage_sub_socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self.voltage_sub_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.voltage_sub_socket.connect(f"tcp://{self.host}:{self.voltage_pub_port}")

        properties = self.GetProperties()
        self.ChannelCount = int(properties["channel_count"])
        self.voltage_min = float(properties["voltage_min"])
        self.voltage_max = float(properties["voltage_max"])

        self.voltage_shm = _attach_shared_memory(
            properties["voltage_shared_memory_name"]
        )
        self.meta_shm = _attach_shared_memory(
            properties["meta_shared_memory_name"]
        )

        self.voltage_arr = np.ndarray(
            tuple(properties["voltage_shape"]),
            dtype=np.dtype(properties["voltage_dtype"]),
            buffer=self.voltage_shm.buf,
        )
        self.meta_arr = np.ndarray(
            tuple(properties["meta_shape"]),
            dtype=np.dtype(properties["meta_dtype"]),
            buffer=self.meta_shm.buf,
        )

        self._drain_voltage_notifications()

    def _connect_command_socket(self):
        if self.socket is not None:
            try:
                self.socket.close(0)
            except Exception:
                pass

        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.command_port}")

    def ResetCommandSocket(self):
        self._connect_command_socket()

    def SendCommand(self, msg):
        msg["client_id"] = self.client_id

        try:
            self.socket.send_json(msg)
            reply = self.socket.recv_json()
        except zmq.ZMQError:
            self.ResetCommandSocket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(
                reply.get("error", "Unknown DAQ server error")
                + "\n"
                + reply.get("traceback", "")
            )

        return reply.get("result", None)

    def _receive_voltage_notification(self, flags=0):
        parts = self.voltage_sub_socket.recv_multipart(flags=flags)

        if len(parts) == 1:
            return json.loads(parts[0].decode("utf-8"))

        if len(parts) >= 2:
            return json.loads(parts[1].decode("utf-8"))

        return None

    def _drain_voltage_notifications(self):
        latest = None
        while True:
            try:
                latest = self._receive_voltage_notification(flags=zmq.NOBLOCK)
            except zmq.Again:
                return latest

    def WaitForVoltageNotification(self, LastVoltageCounter=None, timeout_ms=None):
        timeout_s = self.timeout_ms / 1000 if timeout_ms is None else timeout_ms / 1000
        deadline = time.monotonic() + timeout_s if timeout_s >= 0 else None

        while True:
            if LastVoltageCounter is not None and self.GetVoltageCounter() != LastVoltageCounter:
                self._drain_voltage_notifications()
                return True

            if deadline is not None:
                remaining_ms = int((deadline - time.monotonic()) * 1000)
                if remaining_ms <= 0:
                    return False
                self.voltage_sub_socket.setsockopt(zmq.RCVTIMEO, remaining_ms)

            try:
                msg = self._receive_voltage_notification()
            except zmq.Again:
                if not self.IsServerAlive():
                    raise RuntimeError("DAQ server is no longer alive")
                return False
            finally:
                self.voltage_sub_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)

            if msg is None:
                continue
            if msg.get("type") != "voltage_update":
                continue

            if LastVoltageCounter is None:
                return True

            if int(msg.get("voltage_counter", -1)) != int(LastVoltageCounter):
                return True

    def GetVoltages(self):
        while True:
            counter_before = int(self.meta_arr[1])
            writing_before = int(self.meta_arr[0])

            if writing_before:
                time.sleep(0.0001)
                continue

            voltages = self.voltage_arr.copy()

            counter_after = int(self.meta_arr[1])
            writing_after = int(self.meta_arr[0])

            if counter_before == counter_after and not writing_after:
                return voltages

    def GetVoltage(self, channel):
        if not 0 <= channel < self.ChannelCount:
            raise ValueError(
                f"Channel {channel} does not exist (max {self.ChannelCount - 1})."
            )

        return float(self.GetVoltages()[channel])

    def SetVoltage(self, channel, voltage):
        return self.SendCommand({
            "cmd": "set_voltage",
            "channel": int(channel),
            "voltage": float(voltage),
        })

    def SetVoltages(self, voltages):
        return self.SendCommand({
            "cmd": "set_voltages",
            "voltages": [float(voltage) for voltage in voltages],
        })

    def Zero(self):
        return self.SendCommand({"cmd": "zero"})

    def SetRefreshTime(self, NewRefreshTime):
        return self.SendCommand({
            "cmd": "set_refresh_time",
            "refresh_time": float(NewRefreshTime),
        })

    def GetProperties(self):
        return self.SendCommand({"cmd": "get_properties"})

    def ShutdownServer(self):
        return self.SendCommand({"cmd": "shutdown"})

    def GetVoltageCounter(self):
        return int(self.meta_arr[1])

    def GetLastWriteTimeNS(self):
        return int(self.meta_arr[2])

    def IsServerAlive(self):
        return bool(self.meta_arr[3])

    def close(self):
        self.voltage_arr = None
        self.meta_arr = None

        for shm in (self.voltage_shm, self.meta_shm):
            try:
                if shm is not None:
                    shm.close()
            except Exception:
                pass

        for socket in (self.voltage_sub_socket, self.socket):
            try:
                if socket is not None:
                    socket.close(0)
            except Exception:
                pass

        try:
            self.context.term()
        except Exception:
            pass

