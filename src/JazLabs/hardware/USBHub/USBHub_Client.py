"""Synchronous notebook/script API. No worker thread, queue, or status cache."""
import uuid

import zmq


class USBHubClient:
    def __init__(self, host="127.0.0.1", command_port=50951,
                 timeout_ms=100000, client_id=None):
        if not host or host in ("0.0.0.0", "::"):
            raise ValueError("Connect to the hardware server or bridge's reachable address")
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        self.host = host
        self.command_port = int(command_port)
        self.timeout_ms = int(timeout_ms)
        self.client_id = client_id or f"usb_hub_{uuid.uuid4().hex[:8]}"
        self._closed = False

    def request(self, command, **arguments):
        if self._closed:
            raise RuntimeError("USB hub client is closed")
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.MAXMSGSIZE, 1048576)
        socket.setsockopt(zmq.IMMEDIATE, 1)
        try:
            socket.connect(f"tcp://{self.host}:{self.command_port}")
            socket.send_json({"cmd": command, "client_id": self.client_id, **arguments})
            reply = socket.recv_json()
            if not isinstance(reply, dict) or type(reply.get("ok")) is not bool:
                raise RuntimeError("Invalid USB hub server reply")
            if not reply["ok"]:
                raise RuntimeError(reply.get("error", "USB hub command failed"))
            result = reply.get("result")
            if isinstance(result, dict) and "hubs" in result:
                # JSON stringifies integer dictionary keys. Keep the public
                # status shape identical to the direct driver's dictionary.
                for hub in result["hubs"].values():
                    hub["ports"] = {int(port): state for port, state in hub["ports"].items()}
                result["trees"] = {root: [tuple(endpoint) for endpoint in endpoints]
                                   for root, endpoints in result["trees"].items()}
            return result
        except zmq.Again:
            raise TimeoutError(
                f"No USB hub reply from {self.host}:{self.command_port}. "
                "Outcome unknown; refresh before another power request. Command was not retried."
            ) from None
        finally:
            # A fresh REQ socket makes the next explicit call usable after a
            # timeout without replaying a possibly completed power command.
            socket.close(0)
            context.term()

    def GetStatus(self):
        return self.request("get_status")

    def SetPower(self, endpoint, on, expected_identity, session_id=None):
        if not isinstance(endpoint, (tuple, list)) or len(endpoint) != 2:
            raise ValueError("endpoint must be a (location, port) pair")
        if session_id is None:
            session_id = self.GetStatus()["session_id"]
        return self.request("set_power", location=endpoint[0], port=endpoint[1],
                            on=on, expected_identity=expected_identity, session_id=session_id)

    def ShutdownServer(self):
        """Explicitly stop the hardware owner, leaving power states unchanged."""
        return self.request("shutdown")

    def close(self):
        self._closed = True
