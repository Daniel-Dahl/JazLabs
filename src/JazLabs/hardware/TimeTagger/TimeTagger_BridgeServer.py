import multiprocessing as mp
import traceback

import zmq


class TimeTaggerZMQBridgeServer:
    """Expose a remote TimeTaggerZMQServer through a local command endpoint."""

    def __init__(
        self,
        local_host="127.0.0.1",
        local_command_port=50931,
        remote_host="127.0.0.1",
        remote_command_port=50931,
        timeout_ms=120000,
        poll_timeout_ms=100,
    ):
        self.local_host = local_host
        self.local_command_port = int(local_command_port)
        self.remote_host = remote_host
        self.remote_command_port = int(remote_command_port)
        self.timeout_ms = int(timeout_ms)
        self.poll_timeout_ms = int(poll_timeout_ms)
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Time Tagger bridge server process already running.")
            return
        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"Time Tagger bridge server started with PID {self.Process.pid}")

    def stopProcess(self):
        try:
            context = zmq.Context()
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.LINGER, 0)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.SNDTIMEO, 1000)
            socket.connect(f"tcp://{self.local_host}:{self.local_command_port}")
            socket.send_json(
                {"cmd": "shutdown_bridge", "client_id": "bridge_controller"}
            )
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

    def _create_remote_socket(self, context):
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        socket.connect(f"tcp://{self.remote_host}:{self.remote_command_port}")
        return socket

    def run_forever(self):
        context = zmq.Context()
        local_command_socket = context.socket(zmq.REP)
        local_command_socket.setsockopt(zmq.LINGER, 0)
        remote_command_socket = self._create_remote_socket(context)

        try:
            local_command_socket.bind(
                f"tcp://{self.local_host}:{self.local_command_port}"
            )
            print("Time Tagger ZMQ bridge server running.")
            print(
                "Local command socket: "
                f"tcp://{self.local_host}:{self.local_command_port}"
            )
            print(
                "Remote Time Tagger server: "
                f"tcp://{self.remote_host}:{self.remote_command_port}"
            )

            poller = zmq.Poller()
            poller.register(local_command_socket, zmq.POLLIN)
            running = True
            while running:
                events = dict(poller.poll(self.poll_timeout_ms))
                if local_command_socket not in events:
                    continue
                message = local_command_socket.recv_json()
                client_id = message.get("client_id", "unknown_client")

                if message.get("cmd") == "shutdown_bridge":
                    local_command_socket.send_json(
                        {"ok": True, "result": None, "client_id": client_id}
                    )
                    running = False
                    continue

                try:
                    remote_command_socket.send_json(message)
                    reply = remote_command_socket.recv_json()
                    if message.get("cmd") == "get_properties" and reply.get("ok"):
                        properties = dict(reply.get("result", {}))
                        properties.update(
                            {
                                "role": "time_tagger_bridge_server",
                                "command_port": self.local_command_port,
                                "remote_host": self.remote_host,
                                "remote_command_port": self.remote_command_port,
                            }
                        )
                        reply["result"] = properties
                except Exception as exc:
                    remote_command_socket.close(0)
                    remote_command_socket = self._create_remote_socket(context)
                    reply = {
                        "ok": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "traceback": traceback.format_exc(),
                        "client_id": client_id,
                    }

                local_command_socket.send_json(reply)
        finally:
            local_command_socket.close(0)
            remote_command_socket.close(0)
            context.term()
