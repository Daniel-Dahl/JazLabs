import multiprocessing as mp
import traceback

import zmq


class OpticalSwitchZMQServer:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50831,
        switch_type="JDS_SC",
        switch_kwargs=None,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.switch_type = switch_type
        self.switch_kwargs = {} if switch_kwargs is None else switch_kwargs
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Optical switch server process already running.")
            return

        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Optical switch server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://{self.host}:{self.command_port}")
            socket.send_json({"cmd": "shutdown", "client_id": "switch_server_controller"})
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
        if self.switch_type == "JDS_SC":
            import JazLabs.hardware.OpticalSwitch.JDS.JDSUniphaseOpticalSwitch as OpticalSwitch_lib 

        elif self.switch_type == "JDS_Pol":
            import JazLabs.hardware.OpticalSwitch.JDS.JDSPolSwitch as OpticalSwitch_lib
        else:
            raise ValueError(f"Unknown switch_type: {self.switch_type}")
        switch_obj = OpticalSwitch_lib.OpticalSwitchObject(**self.switch_kwargs)
        

        context = None
        command_socket = None
        running = True

        try:
            context = zmq.Context()
            command_socket = context.socket(zmq.REP)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")

            print("Optical Switch ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Switch type: {self.switch_type}")

            while running:
                msg = command_socket.recv_json()
                client_id = msg.get("client_id", "unknown_client")
                cmd = msg.get("cmd", "")

                try:
                    if cmd == "shutdown":
                        running = False
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "get_properties":
                        reply = {
                            "ok": True,
                            "result": {
                                "switch_type": self.switch_type,
                                "command_port": self.command_port,
                                "host": self.host,
                            },
                            "client_id": client_id,
                        }

                    elif cmd == "set_channel":
                        channel = int(msg["channel"])
                        wait_settle = bool(msg.get("wait_settle", True))
                        settle_timeout = float(msg.get("settle_timeout", 10.0))
                        result = switch_obj.set_channel(channel, wait_settle=wait_settle, settle_timeout=settle_timeout)
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "get_channel":
                        result = switch_obj.get_channel()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "max_channel":
                        result = switch_obj.max_channel()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "min_channel":
                        result = switch_obj.min_channel()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "get_status_register":
                        result = switch_obj.get_status_register()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "is_settled":
                        result = switch_obj.is_settled()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "set_driver":
                        idx = int(msg["driver_idx"])
                        on = bool(msg["on"])
                        result = switch_obj.set_driver(idx, on)
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "set_drivers_mask":
                        mask = int(msg["mask"])
                        result = switch_obj.set_drivers_mask(mask)
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "get_drivers_mask":
                        result = switch_obj.get_drivers_mask()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "idn":
                        result = switch_obj.idn()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "reset":
                        result = switch_obj.reset()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "close_switch":
                        result = switch_obj.close()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    else:
                        raise ValueError(f"Unknown command: {cmd}")

                except Exception as exc:
                    reply = {
                        "ok": False,
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "client_id": client_id,
                    }

                command_socket.send_json(reply)

        finally:
            try:
                switch_obj.close()
            except Exception:
                pass

            if command_socket is not None:
                command_socket.close(0)
            if context is not None:
                context.term()
