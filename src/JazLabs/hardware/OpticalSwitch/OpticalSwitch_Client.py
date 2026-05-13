import zmq


class OpticalSwitchClient:
    def __init__(self, host="127.0.0.1", command_port=50831, timeout_ms=5000, client_id="optical_switch_client"):
        self.host = host
        self.command_port = int(command_port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = client_id

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.command_port}")

    def SendCommand(self, msg):
        msg["client_id"] = self.client_id
        self.socket.send_json(msg)
        reply = self.socket.recv_json()
        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown optical switch server error") + "\n" + reply.get("traceback", ""))
        return reply.get("result", None)

    def GetProperties(self):
        return self.SendCommand({"cmd": "get_properties"})

    def ShutdownServer(self):
        return self.SendCommand({"cmd": "shutdown"})

    def SetChannel(self, channel, wait_settle=True, settle_timeout=10.0):
        return self.SendCommand({
            "cmd": "set_channel",
            "channel": int(channel),
            "wait_settle": bool(wait_settle),
            "settle_timeout": float(settle_timeout),
        })

    def GetChannel(self):
        return self.SendCommand({"cmd": "get_channel"})

    def MaxChannel(self):
        return self.SendCommand({"cmd": "max_channel"})

    def MinChannel(self):
        return self.SendCommand({"cmd": "min_channel"})

    def GetStatusRegister(self):
        return self.SendCommand({"cmd": "get_status_register"})

    def IsSettled(self):
        return self.SendCommand({"cmd": "is_settled"})

    def SetDriver(self, driver_idx, on):
        return self.SendCommand({"cmd": "set_driver", "driver_idx": int(driver_idx), "on": bool(on)})

    def SetDriversMask(self, mask):
        return self.SendCommand({"cmd": "set_drivers_mask", "mask": int(mask)})

    def GetDriversMask(self):
        return self.SendCommand({"cmd": "get_drivers_mask"})

    def IDN(self):
        return self.SendCommand({"cmd": "idn"})

    def Reset(self):
        return self.SendCommand({"cmd": "reset"})

    def CloseSwitch(self):
        return self.SendCommand({"cmd": "close_switch"})
