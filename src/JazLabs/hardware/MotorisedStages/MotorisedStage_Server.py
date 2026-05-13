import multiprocessing as mp
import traceback

import zmq


class MotorisedStageZMQServer:
    def __init__(self, host="127.0.0.1", command_port=50931, stage_type="Luminos", stage_kwargs=None):
        self.host = host
        self.command_port = int(command_port)
        self.stage_type = stage_type
        self.stage_kwargs = {} if stage_kwargs is None else stage_kwargs
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Motorised stage server process already running.")
            return
        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Motorised stage server process started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://{self.host}:{self.command_port}")
            socket.send_json({"cmd": "shutdown", "client_id": "motor_stage_server_controller"})
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
        axis_map = None

        if self.stage_type == "Luminos":
            from JazLabs.hardware.MotorisedStages.Luminos.LuminosStage import LuminosStage, Axes

            stage_obj = LuminosStage(**self.stage_kwargs)
            axis_map = {
                "Z": Axes.Z,
                "X": Axes.X,
                "Y": Axes.Y,
                "ROLL": Axes.ROLL,
                "YAW": Axes.YAW,
                "PITCH": Axes.PITCH,
            }
        elif self.stage_type == "NewportM100D":
            from JazLabs.hardware.MotorisedStages.Newport.NewportMounts import NewportM100D_VISA

            stage_obj = NewportM100D_VISA(**self.stage_kwargs)
        else:
            raise ValueError(f"Unknown stage_type: {self.stage_type}")

        context = None
        command_socket = None
        running = True

        try:
            context = zmq.Context()
            command_socket = context.socket(zmq.REP)
            command_socket.bind(f"tcp://{self.host}:{self.command_port}")

            print("Motorised Stage ZMQ server running.")
            print(f"Command socket: tcp://{self.host}:{self.command_port}")
            print(f"Stage type: {self.stage_type}")

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
                                "stage_type": self.stage_type,
                                "command_port": self.command_port,
                                "host": self.host,
                            },
                            "client_id": client_id,
                        }

                    elif cmd == "get_positions":
                        if self.stage_type == "Luminos":
                            result = stage_obj.Get_all_stage_Positions().tolist()
                        else:
                            result = {"U": stage_obj.get_position("U"), "V": stage_obj.get_position("V")}
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "move_abs":
                        axis = str(msg["axis"])
                        value = float(msg["value"])
                        if self.stage_type == "Luminos":
                            if axis.upper() not in axis_map:
                                raise ValueError(f"Invalid Luminos axis '{axis}'. Valid: {list(axis_map.keys())}")
                            stage_obj.Set_Single_Stage_State_abs(axis_map[axis.upper()], value)
                        else:
                            if axis.upper() not in ("U", "V"):
                                raise ValueError("Invalid Newport axis. Valid: ['U', 'V']")
                            stage_obj.move_abs(value, axis.upper())
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "move_rel":
                        axis = str(msg["axis"])
                        value = float(msg["value"])
                        if self.stage_type == "Luminos":
                            if axis.upper() not in axis_map:
                                raise ValueError(f"Invalid Luminos axis '{axis}'. Valid: {list(axis_map.keys())}")
                            stage_obj.Set_Single_Stage_State_rel(axis_map[axis.upper()], value)
                        else:
                            if axis.upper() not in ("U", "V"):
                                raise ValueError("Invalid Newport axis. Valid: ['U', 'V']")
                            stage_obj.move_rel(value, axis.upper())
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "home_all":
                        if self.stage_type == "Luminos":
                            stage_obj.home_all()
                        else:
                            raise NotImplementedError("home_all is only implemented for Luminos in this server.")
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "set_nominal":
                        if self.stage_type == "Luminos":
                            stage_obj.Set_all_stage_Position_Nominal()
                        else:
                            raise NotImplementedError("set_nominal is only implemented for Luminos in this server.")
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "close_stage":
                        result = stage_obj.close() if hasattr(stage_obj, "close") else None
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
                if hasattr(stage_obj, "close"):
                    stage_obj.close()
            except Exception:
                pass
            if command_socket is not None:
                command_socket.close(0)
            if context is not None:
                context.term()
