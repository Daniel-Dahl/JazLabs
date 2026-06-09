import json
import multiprocessing as mp
import time
import traceback
from multiprocessing import shared_memory

import numpy as np
import zmq


class DAQZMQServer:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50831,
        voltage_pub_port=50832,
        DAQType="ni_daq",
        DAQKwargs=None,
        ChannelCount=1,
        voltage_min=0.0,
        voltage_max=5.0,
        PublishVoltagesOverZMQ=False,
        voltage_topic="daq.voltages",
    ):
        self.host = host
        self.command_port = int(command_port)
        self.voltage_pub_port = int(voltage_pub_port)
        self.DAQType = DAQType
        self.DAQKwargs = DAQKwargs or {}
        self.ChannelCount = int(ChannelCount)
        self.voltage_min = float(voltage_min)
        self.voltage_max = float(voltage_max)
        self.PublishVoltagesOverZMQ = bool(PublishVoltagesOverZMQ)
        self.voltage_topic = str(voltage_topic)

        self.Process = None
        self.voltage_shm = None
        self.voltage_arr = None
        self.meta_shm = None
        self.meta_arr = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("DAQ server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"DAQ server process started with PID {self.Process.pid}")

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

    def _import_daq_module(self):
        if self.DAQType == "mcc_daq":
            import JazLabs.hardware.DAQ_Controller.MCC.mcc_daq as daq_module
        elif self.DAQType == "ni_daq":
            import JazLabs.hardware.DAQ_Controller.NI.NI_DAQ as daq_module
        elif self.DAQType == "coremorrow_daq":
            import JazLabs.hardware.DAQ_Controller.Coremorrow.coremorrow_daq as daq_module
        else:
            raise ValueError(f"Unknown DAQType: {self.DAQType}")

        return daq_module

    def run_forever(self):
        daq_module = self._import_daq_module()
        daq_object = None
        context = None
        command_socket = None
        voltage_pub_socket = None

        try:
            daq_kwargs = dict(self.DAQKwargs)
            daq_kwargs.setdefault("ChannelCount", self.ChannelCount)
            daq_object = daq_module.DAQObject(**daq_kwargs)

            self.voltage_shm = shared_memory.SharedMemory(
                create=True,
                size=self.ChannelCount * np.dtype(np.float64).itemsize,
            )
            self.voltage_arr = np.ndarray(
                (self.ChannelCount,),
                dtype=np.float64,
                buffer=self.voltage_shm.buf,
            )

            self.meta_shm = shared_memory.SharedMemory(
                create=True,
                size=4 * np.dtype(np.int64).itemsize,
            )
            self.meta_arr = np.ndarray((4,), dtype=np.int64, buffer=self.meta_shm.buf)

            # meta_arr[0] = writing flag
            # meta_arr[1] = voltage update counter
            # meta_arr[2] = last voltage write time ns
            # meta_arr[3] = server alive flag
            self.voltage_arr[:] = 0.0
            self.meta_arr[:] = 0
            self.meta_arr[3] = 1

            context = zmq.Context()
            command_socket = context.socket(zmq.REP)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")

            voltage_pub_socket = context.socket(zmq.PUB)
            voltage_pub_socket.bind(f"tcp://{self.host}:{self.voltage_pub_port}")

            print("DAQ ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Voltage PUB socket: tcp://{self.host}:{self.voltage_pub_port}")
            print(f"DAQType: {self.DAQType}")
            print(f"Voltage SHM name: {self.voltage_shm.name}")
            print(f"Meta SHM name:    {self.meta_shm.name}")
            print(f"Channel count:    {self.ChannelCount}")

            running = True
            time.sleep(0.1)
            self.PublishVoltages(voltage_pub_socket)

            while running:
                msg = command_socket.recv_json()
                reply = None

                try:
                    cmd = msg.get("cmd")
                    client_id = msg.get("client_id", "unknown_client")

                    if cmd == "get_properties":
                        reply = {
                            "ok": True,
                            "result": self.GetProperties(),
                            "client_id": client_id,
                        }

                    elif cmd == "set_voltage":
                        channel = int(msg["channel"])
                        voltage = float(msg["voltage"])
                        self.SetHardwareVoltage(daq_object, channel, voltage)
                        self.PublishVoltages(voltage_pub_socket)
                        reply = {
                            "ok": True,
                            "result": float(self.voltage_arr[channel]),
                            "client_id": client_id,
                        }

                    elif cmd == "set_voltages":
                        voltages = list(msg["voltages"])
                        if len(voltages) != self.ChannelCount:
                            raise ValueError(
                                f"Expected {self.ChannelCount} voltages, got {len(voltages)}."
                            )
                        for channel, voltage in enumerate(voltages):
                            self.SetHardwareVoltage(daq_object, channel, float(voltage))
                        self.PublishVoltages(voltage_pub_socket)
                        reply = {
                            "ok": True,
                            "result": self.voltage_arr.tolist(),
                            "client_id": client_id,
                        }

                    elif cmd == "get_voltage":
                        channel = int(msg["channel"])
                        if not 0 <= channel < self.ChannelCount:
                            raise ValueError(
                                f"Channel {channel} does not exist (max {self.ChannelCount - 1})."
                            )
                        reply = {
                            "ok": True,
                            "result": float(self.voltage_arr[channel]),
                            "client_id": client_id,
                        }

                    elif cmd == "get_voltages":
                        reply = {
                            "ok": True,
                            "result": self.voltage_arr.tolist(),
                            "client_id": client_id,
                        }

                    elif cmd == "zero":
                        for channel in range(self.ChannelCount):
                            self.SetHardwareVoltage(daq_object, channel, 0.0)
                        self.PublishVoltages(voltage_pub_socket)
                        reply = {
                            "ok": True,
                            "result": self.voltage_arr.tolist(),
                            "client_id": client_id,
                        }

                    elif cmd == "set_refresh_time":
                        result = daq_object.SetRefreshTime(float(msg["refresh_time"]))
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "shutdown":
                        running = False
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    else:
                        reply = {
                            "ok": False,
                            "error": f"Unknown command: {cmd}",
                            "client_id": client_id,
                        }

                except Exception as exc:
                    try:
                        if self.meta_arr is not None:
                            self.meta_arr[0] = 0
                    except Exception:
                        pass

                    reply = {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "client_id": msg.get("client_id", "unknown_client"),
                    }

                command_socket.send_json(reply)

        finally:
            print("Closing DAQ ZMQ server...")

            try:
                if self.meta_arr is not None:
                    self.meta_arr[3] = 0
            except Exception:
                pass

            try:
                if daq_object is not None and hasattr(daq_object, "shutdown"):
                    daq_object.shutdown(zero=True)
            except Exception:
                pass

            for socket in (command_socket, voltage_pub_socket):
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
                if self.voltage_shm is not None:
                    self.voltage_shm.close()
                    self.voltage_shm.unlink()
            except Exception:
                pass

            try:
                if self.meta_shm is not None:
                    self.meta_shm.close()
                    self.meta_shm.unlink()
            except Exception:
                pass

            print("DAQ ZMQ server closed.")

    def GetProperties(self):
        return {
            "daq_type": self.DAQType,
            "command_port": self.command_port,
            "voltage_pub_port": self.voltage_pub_port,
            "channel_count": self.ChannelCount,
            "voltage_min": self.voltage_min,
            "voltage_max": self.voltage_max,
            "voltage_shared_memory_name": self.voltage_shm.name,
            "voltage_shape": [self.ChannelCount],
            "voltage_dtype": "float64",
            "meta_shared_memory_name": self.meta_shm.name,
            "meta_shape": [4],
            "meta_dtype": "int64",
            "voltage_counter": int(self.meta_arr[1]),
            "last_write_time_ns": int(self.meta_arr[2]),
            "server_alive": bool(self.meta_arr[3]),
        }

    def SetHardwareVoltage(self, daq_object, channel, voltage):
        if not 0 <= channel < self.ChannelCount:
            raise ValueError(
                f"Channel {channel} does not exist (max {self.ChannelCount - 1})."
            )
        if voltage < self.voltage_min or voltage > self.voltage_max:
            raise ValueError(
                f"Voltage {voltage} V is outside configured limits "
                f"({self.voltage_min} V to {self.voltage_max} V)."
            )

        daq_object.SetVoltage(channel, voltage)

        self.meta_arr[0] = 1
        self.voltage_arr[channel] = float(voltage)
        self.meta_arr[1] += 1
        self.meta_arr[2] = time.time_ns()
        self.meta_arr[0] = 0

    def PublishVoltages(self, voltage_pub_socket):
        msg = {
            "type": "voltage_update",
            "voltage_counter": int(self.meta_arr[1]),
            "last_write_time_ns": int(self.meta_arr[2]),
            "channel_count": self.ChannelCount,
        }

        if self.PublishVoltagesOverZMQ:
            voltages = np.ascontiguousarray(self.voltage_arr)
            msg["shape"] = list(voltages.shape)
            msg["dtype"] = str(voltages.dtype)
            msg["nbytes"] = int(voltages.nbytes)
            voltage_pub_socket.send_multipart(
                [
                    self.voltage_topic.encode("utf-8"),
                    json.dumps(msg).encode("utf-8"),
                    memoryview(voltages),
                ]
            )
            return

        voltage_pub_socket.send_json(msg)


if __name__ == "__main__":
    mp.freeze_support()
    server = DAQZMQServer()
    server.run_forever()

