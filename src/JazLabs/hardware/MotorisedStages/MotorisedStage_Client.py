import zmq


class MotorisedStageClient:
    def __init__(self, host="127.0.0.1", command_port=50931, timeout_ms=5000, client_id="motorised_stage_client"):
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
            raise RuntimeError(reply.get("error", "Unknown motorised stage server error") + "\n" + reply.get("traceback", ""))
        return reply.get("result", None)

    def GetProperties(self):
        return self.SendCommand({"cmd": "get_properties"})

    def ShutdownServer(self):
        return self.SendCommand({"cmd": "shutdown"})

    def GetPositions(self):
        return self.SendCommand({"cmd": "get_positions"})

    def MoveAbs(self, axis, value):
        return self.SendCommand({"cmd": "move_abs", "axis": str(axis), "value": float(value)})

    def MoveRel(self, axis, value):
        return self.SendCommand({"cmd": "move_rel", "axis": str(axis), "value": float(value)})

    def HomeAll(self):
        return self.SendCommand({"cmd": "home_all"})

    def SetNominal(self):
        return self.SendCommand({"cmd": "set_nominal"})

    def CloseStage(self):
        return self.SendCommand({"cmd": "close_stage"})
