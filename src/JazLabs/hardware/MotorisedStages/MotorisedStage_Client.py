"""User-facing motor client; synchronous RPCs and optional GUI polling.

Scripts call request(). Widgets call start(), submit() and get_state() on the
same client. Only the client's network thread handles asynchronous RPCs; it
never imports or accesses a hardware driver.
"""
import zmq


class MotorisedStageClient:
    def __init__(self, host="127.0.0.1", command_port=50931, timeout_ms=500):
        import queue
        import threading
        self.endpoint = f"tcp://{host}:{int(command_port)}"
        self.timeout_ms = int(timeout_ms)
        self.context = zmq.Context()
        self.host = host
        self.command_port = command_port
        self.lock = threading.RLock()
        self.commands = queue.Queue(maxsize=1)
        self.stop_requested = threading.Event()
        self.release_requested = threading.Event()
        self.closing = threading.Event()
        self.wake = threading.Event()
        self.held_jog = None
        self.received_at = None
        self.snapshot = {"connected": False, "name": "Connecting…", "capabilities": [],
                         "axes": {}, "stopped": False, "stop_pending": False,
                         "message": "Connecting…", "error": None, "sequence": 0}
        self.thread = threading.Thread(target=self.run, name="motor-network-owner", daemon=True)

    def request(self, command, axis=None, value=None):
        socket = self.context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        try:
            socket.connect(self.endpoint)
            socket.send_json({"command": command, "axis": axis, "value": value})
            response = socket.recv_json()
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "Motion service rejected request"))
            return response.get("state")
        except zmq.Again as exc:
            raise TimeoutError("Motion service did not respond") from exc
        finally:
            socket.close()

    def GetMotionCapabilities(self):
        return self.request("state")["capabilities"]

    def GetAxisState(self, axis):
        return self.request("state")["axes"][axis]

    def GetProperties(self):
        return self.request("state").get("properties", {})

    def MoveTo(self, axis, target):
        return self.request("absolute", axis, target)

    def HomeAxis(self, axis):
        return self.request("home", axis)

    def EnableAxis(self, axis):
        return self.request("enable", axis)

    def StopAll(self):
        return self.request("stop")

    def SetSpeed(self, axis, value):
        return self.request("speed", axis, value)

    def start(self):
        self.thread.start()

    def submit(self, command, axis=None, value=None):
        import queue
        import time
        with self.lock:
            if command == "stop":
                self.held_jog = None
                while not self.commands.empty():
                    self.commands.get_nowait()
                self.snapshot["stop_pending"] = True
                self.stop_requested.set()
            elif command == "release_jog":
                self.held_jog = None
                # A tap's first step must survive an immediate key release.
                # Cancel the lease separately, without erasing that first intent.
                self.release_requested.set()
            elif command == "jog":
                self.held_jog = (axis, value, time.monotonic() + 0.3)
            else:
                try:
                    self.commands.put_nowait((command, axis, value))
                except queue.Full as exc:
                    raise RuntimeError("A motor command is already pending") from exc
        self.wake.set()

    def get_state(self):
        from copy import deepcopy
        import time
        with self.lock:
            state = deepcopy(self.snapshot)
            elapsed = time.monotonic() - self.received_at if self.received_at else 0
            for axis in state["axes"].values():
                axis["age"] = axis.get("age", 0) + elapsed
            return state

    def close(self):
        if self.closing.is_set():
            return
        self.closing.set()
        if self.thread.is_alive():
            self.submit("stop")
        else:
            self.context.term()

    def run(self):
        import time
        try:
            while True:
                self.wake.clear()
                with self.lock:
                    stopping = self.stop_requested.is_set()
                    if stopping:
                        command, axis, value = "stop", None, None
                    elif self.release_requested.is_set():
                        command, axis, value = "release_jog", None, None
                        self.release_requested.clear()
                    elif not self.commands.empty():
                        command, axis, value = self.commands.get_nowait()
                    elif self.held_jog and self.held_jog[2] > time.monotonic():
                        axis, value, expiry = self.held_jog
                        command = "jog"
                    else:
                        self.held_jog = None
                        command, axis, value = "state", None, None
                try:
                    state = self.request(command, axis, value)
                    with self.lock:
                        self.snapshot = state
                        self.received_at = time.monotonic()
                        if stopping:
                            self.stop_requested.clear()
                    if self.closing.is_set() and stopping:
                        break
                except Exception as exc:
                    with self.lock:
                        self.snapshot.update(connected=False, error=str(exc), message="Motion service unavailable")
                        self.held_jog = None
                        while not self.commands.empty():
                            self.commands.get_nowait()
                        # Request a stop before accepting work after reconnection.
                        self.stop_requested.set()
                    if self.closing.is_set():
                        break
                self.wake.wait(0.1)
        finally:
            self.context.term()
