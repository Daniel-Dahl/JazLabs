"""Forward commands to a USB hub owner without importing its driver."""
import time

import zmq


class USBHubZMQBridgeServer:
    def __init__(self, remote_host, remote_command_port=50951, local_host="127.0.0.1",
                 local_command_port=51951, timeout_ms=90000):
        if not remote_host or remote_host in ("0.0.0.0", "::"):
            raise ValueError("remote_host must be the hardware computer's reachable address")
        local_addresses = {"127.0.0.1", "localhost", "0.0.0.0"}
        if (remote_host in local_addresses and local_host in local_addresses
                and int(remote_command_port) == int(local_command_port)):
            raise ValueError("Local and remote bridge endpoints must differ")
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        self.remote_host = remote_host
        self.remote_command_port = int(remote_command_port)
        self.local_host = local_host
        self.local_command_port = int(local_command_port)
        self.timeout_ms = int(timeout_ms)

    def run_forever(self, ready_connection=None):
        context = zmq.Context()
        local_socket = context.socket(zmq.REP)
        local_socket.setsockopt(zmq.LINGER, 1000)
        local_socket.setsockopt(zmq.MAXMSGSIZE, 65536)
        local_socket.setsockopt(zmq.SNDTIMEO, 1000)
        try:
            if self.local_command_port == 0:
                self.local_command_port = local_socket.bind_to_random_port(f"tcp://{self.local_host}")
            else:
                local_socket.bind(f"tcp://{self.local_host}:{self.local_command_port}")
            if ready_connection is not None:
                ready_connection.send({"command_port": self.local_command_port})
                ready_connection.close()
                ready_connection = None
            print(f"USB hub bridge: tcp://{self.local_host}:{self.local_command_port}", flush=True)
            running = True
            while running:
                if not local_socket.poll(100, zmq.POLLIN):
                    continue
                remote_socket = None
                try:
                    request = local_socket.recv_json()
                    if not isinstance(request, dict):
                        raise ValueError("USB hub request must be a JSON object")
                    if request.get("cmd") == "shutdown_bridge":
                        running = False
                        response = {"ok": True, "result": None}
                    else:
                        # A fresh remote socket recovers after a timeout without
                        # replaying an on/off request whose outcome is unknown.
                        remote_socket = context.socket(zmq.REQ)
                        remote_socket.setsockopt(zmq.LINGER, 0)
                        remote_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
                        remote_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
                        remote_socket.setsockopt(zmq.MAXMSGSIZE, 1048576)
                        remote_socket.connect(f"tcp://{self.remote_host}:{self.remote_command_port}")
                        remote_socket.send_json(request)
                        response = remote_socket.recv_json()
                        if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                            raise RuntimeError("Invalid reply from USB hub server")
                except zmq.Again:
                    response = {"ok": False, "error": "USB hub request timed out; outcome unknown. Command was not retried."}
                except Exception as error:
                    response = {"ok": False, "error": str(error)}
                finally:
                    if remote_socket is not None:
                        remote_socket.close(0)
                local_socket.send_json(response)
                if not running:
                    # ZMQ queues sends in its I/O thread. Let the final reply
                    # leave before closing the owner's TCP connection.
                    time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        except Exception as error:
            if ready_connection is not None:
                ready_connection.send({"error": str(error)})
            raise
        finally:
            local_socket.close(1000)
            context.term()
            if ready_connection is not None:
                ready_connection.close()


if __name__ == "__main__":
    from JazLabs.launchers.launch_usb_hub_bridge import main
    main()
