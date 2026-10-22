"""Command bridge for motor clients on a computer without the serial hardware."""
import time

import zmq


class MotorisedStageZMQBridgeServer:
    def __init__(self, remote_host, remote_command_port, local_host="127.0.0.1",
                 local_command_port=51941, timeout_ms=500, poll_timeout_ms=50):
        if not remote_host or remote_host in ("0.0.0.0", "::"):
            raise ValueError("remote_host must be the hardware server's reachable address")
        local_addresses = {"127.0.0.1", "localhost", "::1", "0.0.0.0", "::"}
        if (remote_host in local_addresses and local_host in local_addresses
                and int(remote_command_port) == int(local_command_port)):
            raise ValueError("Local and remote bridge endpoints must differ on the same computer")
        if timeout_ms <= 0 or poll_timeout_ms <= 0:
            raise ValueError("Bridge timeouts must be positive")
        self.remote_host = remote_host
        self.remote_command_port = int(remote_command_port)
        self.local_host = local_host
        self.local_command_port = int(local_command_port)
        self.timeout_ms = int(timeout_ms)
        self.poll_timeout_ms = int(poll_timeout_ms)

    def run_forever(self, ready_connection=None):
        context = zmq.Context()
        local_socket = context.socket(zmq.REP)
        local_socket.setsockopt(zmq.LINGER, 0)
        local_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        try:
            if self.local_command_port == 0:
                self.local_command_port = local_socket.bind_to_random_port(f"tcp://{self.local_host}")
            else:
                local_socket.bind(f"tcp://{self.local_host}:{self.local_command_port}")
            if ready_connection is not None:
                ready_connection.send({"command_port": self.local_command_port})
                ready_connection.close()
                ready_connection = None
            print(f"Motor bridge: tcp://{self.local_host}:{self.local_command_port}")
            print(f"Remote motor server: tcp://{self.remote_host}:{self.remote_command_port}")
            running = True
            while running:
                if not local_socket.poll(self.poll_timeout_ms):
                    continue
                remote_socket = None
                try:
                    message = local_socket.recv_json()
                    if not isinstance(message, dict):
                        raise ValueError("Motor request must be a JSON object")
                    if message.get("command") == "shutdown_bridge":
                        # This command stops only this bridge, never the hardware server.
                        response = {"ok": True, "state": None}
                        running = False
                    else:
                        # Each request owns a socket. After a timeout the next
                        # request starts cleanly; a motor command is never retried.
                        remote_socket = context.socket(zmq.REQ)
                        remote_socket.setsockopt(zmq.LINGER, 0)
                        remote_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
                        remote_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
                        remote_socket.connect(f"tcp://{self.remote_host}:{self.remote_command_port}")
                        started = time.monotonic()
                        remote_socket.send_json(message)
                        response = remote_socket.recv_json()
                        if not isinstance(response, dict):
                            raise RuntimeError("Remote server returned an invalid response")
                        state = response.get("state")
                        if response.get("ok") and isinstance(state, dict):
                            # Relaying must not make old position feedback look fresh.
                            elapsed = time.monotonic() - started
                            for axis in state.get("axes", {}).values():
                                axis["age"] = axis.get("age", 0) + elapsed
                            state["bridge"] = {"host": self.local_host, "command_port": self.local_command_port,
                                               "remote_host": self.remote_host,
                                               "remote_command_port": self.remote_command_port}
                except zmq.Again:
                    response = {"ok": False, "error": "Remote motor request timed out; outcome unknown. Command was not retried."}
                except Exception as exc:
                    response = {"ok": False, "error": str(exc)}
                finally:
                    if remote_socket is not None:
                        remote_socket.close()
                try:
                    local_socket.send_json(response)
                except zmq.Again:
                    break
        finally:
            local_socket.close()
            context.term()
            if ready_connection is not None:
                ready_connection.send({"error": "Motor bridge could not bind its local port"})
                ready_connection.close()
