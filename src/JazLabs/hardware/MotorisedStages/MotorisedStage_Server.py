import multiprocessing as mp
import traceback

import zmq


SUPPORTED_STAGE_TYPES = (
    "NewportM100D",
    "BSC203Serial",
    "KDC101Serial",
    "KST201Serial",
)


def create_motorised_stage(stage_type, stage_kwargs=None):
    """Construct the configured hardware driver without opening unused drivers."""
    stage_kwargs = {} if stage_kwargs is None else dict(stage_kwargs)

    if stage_type == "NewportM100D":
        from JazLabs.hardware.MotorisedStages.Newport.newport_m100d_visa import (
            NewportM100D_VISA,
        )

        return NewportM100D_VISA(**stage_kwargs)

    if stage_type == "BSC203Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.BSC203SerialStage import (
            BSC203SerialStage,
        )

        return BSC203SerialStage(**stage_kwargs)

    if stage_type == "KDC101Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.KDC101SerialStage import (
            KDC101SerialStage,
        )

        return KDC101SerialStage(**stage_kwargs)

    if stage_type == "KST201Serial":
        from JazLabs.hardware.MotorisedStages.Thorlabs.KST201SerialStage import (
            KST201SerialStage,
        )

        return KST201SerialStage(**stage_kwargs)

    supported_types = ", ".join(SUPPORTED_STAGE_TYPES)
    raise ValueError(
        f"Unknown stage_type: {stage_type}. Supported stage types: {supported_types}"
    )


class MotorisedStageZMQServer:
    def __init__(self, host="127.0.0.1", command_port=50931, stage_type="NewportM100D", stage_kwargs=None):
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
        stage_obj = create_motorised_stage(self.stage_type, self.stage_kwargs)

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
                        stage_properties = {}
                        if hasattr(stage_obj, "GetProperties"):
                            stage_properties = dict(stage_obj.GetProperties())
                        stage_properties.update(
                            {
                                "stage_type": self.stage_type,
                                "command_port": self.command_port,
                                "host": self.host,
                                "supports_mm": all(
                                    hasattr(stage_obj, method_name)
                                    for method_name in (
                                        "GetPositionsMM",
                                        "MoveAbsMM",
                                        "MoveRelMM",
                                    )
                                ),
                            }
                        )
                        reply = {
                            "ok": True,
                            "result": stage_properties,
                            "client_id": client_id,
                        }

                    elif cmd == "get_positions":
                        result = stage_obj.GetPositions()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "get_positions_mm":
                        if not hasattr(stage_obj, "GetPositionsMM"):
                            raise NotImplementedError(
                                f"{self.stage_type} does not provide calibrated mm positions."
                            )
                        result = stage_obj.GetPositionsMM()
                        reply = {"ok": True, "result": result, "client_id": client_id}

                    elif cmd == "move_abs":
                        axis = str(msg["axis"])
                        value = float(msg["value"])
                        stage_obj.MoveAbs(axis.upper(), value)
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "move_rel":
                        axis = str(msg["axis"])
                        value = float(msg["value"])
                        stage_obj.MoveRel(axis.upper(), value)
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "move_abs_mm":
                        if not hasattr(stage_obj, "MoveAbsMM"):
                            raise NotImplementedError(
                                f"{self.stage_type} does not provide calibrated mm moves."
                            )
                        axis = str(msg["axis"])
                        value_mm = float(msg["value_mm"])
                        stage_obj.MoveAbsMM(axis.upper(), value_mm)
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "move_rel_mm":
                        if not hasattr(stage_obj, "MoveRelMM"):
                            raise NotImplementedError(
                                f"{self.stage_type} does not provide calibrated mm moves."
                            )
                        axis = str(msg["axis"])
                        value_mm = float(msg["value_mm"])
                        stage_obj.MoveRelMM(axis.upper(), value_mm)
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "home_all":
                        stage_obj.HomeAll()
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "set_nominal":
                        stage_obj.SetNominal()
                        reply = {"ok": True, "result": None, "client_id": client_id}

                    elif cmd == "close_stage":
                        result = stage_obj.CloseStage() if hasattr(stage_obj, "CloseStage") else None
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
                if hasattr(stage_obj, "CloseStage"):
                    stage_obj.CloseStage()
                elif hasattr(stage_obj, "close"):
                    stage_obj.close()
            except Exception:
                pass
            if command_socket is not None:
                command_socket.close(0)
            if context is not None:
                context.term()
