"""One process owns the driver and handles explicit ZMQ commands in one loop."""
import multiprocessing as mp

import time

import zmq

from .USBHub_Driver import USBHubDriver


class USBHubZMQServer:
    def __init__(self, host="127.0.0.1", command_port=50951, binary=None,
                 command_timeout=25.0):
        self.host = host
        self.command_port = int(command_port)
        self.binary = binary
        self.command_timeout = float(command_timeout)
        self.process = None

    def start(self):
        """Launch this same serving loop in a child process for Python callers."""
        if self.process is not None and self.process.is_alive():
            raise RuntimeError("USB hub server is already running")
        parent_ready, child_ready = mp.Pipe(duplex=False)
        self.process = mp.Process(target=_run_usb_hub_server, args=(self.host,
            self.command_port, self.binary, self.command_timeout, child_ready), daemon=False)
        self.process.start()
        child_ready.close()
        try:
            if not parent_ready.poll(5):
                raise TimeoutError("USB hub server did not open its command port")
            reply = parent_ready.recv()
            if "error" in reply:
                raise RuntimeError(reply["error"])
            self.command_port = reply["command_port"]
        except Exception:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=3)
            raise
        finally:
            parent_ready.close()

    def stop(self):
        if self.process is None or not self.process.is_alive():
            return
        from .USBHub_Client import USBHubClient
        host = "127.0.0.1" if self.host == "0.0.0.0" else self.host
        client = USBHubClient(host, self.command_port)
        try:
            client.ShutdownServer()
        finally:
            client.close()
            self.process.join(timeout=3)
        if self.process.is_alive():
            raise RuntimeError("USB hub server did not confirm shutdown")

    def run_forever(self, ready_connection=None):
        context = zmq.Context()
        command_socket = context.socket(zmq.REP)
        command_socket.setsockopt(zmq.LINGER, 1000)
        command_socket.setsockopt(zmq.MAXMSGSIZE, 65536)
        command_socket.setsockopt(zmq.SNDTIMEO, 1000)
        try:
            # Construct the driver only in the hardware owner's process.
            driver = USBHubDriver(self.binary, self.command_timeout)
            if self.command_port == 0:
                self.command_port = command_socket.bind_to_random_port(f"tcp://{self.host}")
            else:
                command_socket.bind(f"tcp://{self.host}:{self.command_port}")
            if ready_connection is not None:
                ready_connection.send({"command_port": self.command_port})
                ready_connection.close()
                ready_connection = None
            print(f"USB hub server: tcp://{self.host}:{self.command_port}", flush=True)
            running = True
            while running:
                if not command_socket.poll(100, zmq.POLLIN):
                    continue
                try:
                    request = command_socket.recv_json()
                    if not isinstance(request, dict):
                        raise ValueError("Request must be a JSON object")
                    command = request.get("cmd")
                    if command == "get_status":
                        result = driver.GetStatus()
                    elif command == "set_power":
                        # A stale GUI mapping must not survive a hardware-owner restart.
                        if request.get("session_id") != driver.session_id:
                            raise ValueError("USB hub owner restarted. Refresh and verify mappings again.")
                        result = driver.SetPower((request.get("location"), request.get("port")),
                            request.get("on"), request.get("expected_identity"), request["session_id"])
                    elif command == "shutdown":
                        running = False
                        result = None
                    else:
                        raise ValueError(f"Unknown USB hub command: {command!r}")
                    response = {"ok": True, "result": result}
                except Exception as error:
                    response = {"ok": False, "error": f"{type(error).__name__}: {error}"}
                # Every received request gets a reply, including malformed JSON.
                command_socket.send_json(response)
                if not running:
                    # ZMQ queues sends in its I/O thread. Let the final reply
                    # leave before closing the owner's TCP connection.
                    time.sleep(0.05)
        except KeyboardInterrupt:
            print("USB hub server stopped; port power states are unchanged.")
        except Exception as error:
            if ready_connection is not None:
                ready_connection.send({"error": str(error)})
            raise
        finally:
            command_socket.close(1000)
            context.term()
            if ready_connection is not None:
                ready_connection.close()


def _run_usb_hub_server(host, command_port, binary, command_timeout, ready_connection):
    server = USBHubZMQServer(host, command_port, binary, command_timeout)
    server.run_forever(ready_connection)


if __name__ == "__main__":
    from JazLabs.launchers.launch_usb_hub_server import main
    main()
