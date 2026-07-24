import zmq


class LaserClient:
    """Laser-like client for a local or remote :class:`LaserZMQServer`."""

    def __init__(
        self,
        host="127.0.0.1",
        command_port=50931,
        timeout_ms=60000,
        client_id="laser_client",
    ):
        self.host = str(host)
        self.command_port = int(command_port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = str(client_id)
        self.context = zmq.Context()
        self.socket = None
        self._connect_command_socket()

        properties = self.get_properties()
        if int(properties["command_port"]) != self.command_port:
            raise RuntimeError(
                f"Connected to command port {self.command_port}, but the server "
                f"reports command port {properties['command_port']}"
            )

    def _connect_command_socket(self):
        if self.socket is not None:
            self.socket.close(0)
        self.socket = self.context.socket(zmq.REQ)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.socket.connect(f"tcp://{self.host}:{self.command_port}")

    def reset_command_socket(self):
        self._connect_command_socket()

    def send_command(self, msg):
        request = dict(msg)
        request["client_id"] = self.client_id
        try:
            self.socket.send_json(request)
            reply = self.socket.recv_json()
        except zmq.Again as exc:
            self.reset_command_socket()
            raise TimeoutError(
                f"No reply from laser server at {self.host}:{self.command_port} "
                f"within {self.timeout_ms} ms. Check that the server is running, "
                "is bound to this computer's LAN interface (not only 127.0.0.1), "
                "and that the command port is allowed through the firewall."
            ) from exc
        except zmq.ZMQError:
            self.reset_command_socket()
            raise

        if not reply.get("ok", False):
            error = reply.get("error", "Unknown laser server error")
            traceback_text = reply.get("traceback", "")
            if traceback_text:
                error += "\n" + traceback_text
            raise RuntimeError(error)
        return reply.get("result")

    def get_properties(self):
        return self.send_command({"cmd": "get_properties"})

    def get_status(self):
        return self.send_command({"cmd": "get_status"})

    def get_limits(self):
        return self.send_command({"cmd": "get_limits"})

    def get_wavelength_nm(self):
        return self.send_command({"cmd": "get_wavelength_nm"})

    def set_wavelength_nm(
        self, wavelength_nm, wait=True, timeout_s=30, poll_interval_s=0.1
    ):
        return self.send_command(
            {
                "cmd": "set_wavelength_nm",
                "wavelength_nm": wavelength_nm,
                "wait": wait,
                "timeout_s": timeout_s,
                "poll_interval_s": poll_interval_s,
            }
        )

    def get_power(self):
        return self.send_command({"cmd": "get_power"})

    def set_power_dbm(self, power_dbm):
        return self.send_command({"cmd": "set_power_dbm", "power_dbm": power_dbm})

    def set_power_mw(self, power_mw):
        return self.send_command({"cmd": "set_power_mw", "power_mw": power_mw})

    def get_laser_output_state(self):
        return self.send_command({"cmd": "get_laser_output_state"})

    def laser_on(self):
        return self.send_command({"cmd": "laser_on"})

    def laser_off(self):
        return self.send_command({"cmd": "laser_off"})

    def reset(self):
        return self.send_command({"cmd": "reset"})

    def shutdown_server(self):
        return self.send_command({"cmd": "shutdown"})

    # Compatibility with the camera client's public naming style.
    GetProperties = get_properties
    GetStatus = get_status
    GetLimits = get_limits
    ResetCommandSocket = reset_command_socket
    ShutdownServer = shutdown_server

    def close(self):
        if self.socket is not None:
            self.socket.close(0)
            self.socket = None
        if self.context is not None:
            self.context.term()
            self.context = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback_value):
        self.close()
