import json
import time
import traceback
import uuid

import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMZMQBridgeServer:
    """
    Shared-memory bridge for a remotely hosted SLM server.

    This process owns the network connection to SLM_Server.py, watches a
    2D pymilk requested-image SHM, and publishes every complete SHM update to
    the hardware server. CHANIDX identifies the colour channel. A separate 2D
    confirmed SHM is updated only after the matching physical-server ACK.
    """

    def __init__(
        self,
        client_id=None,
        shm_name="slm_image",
        confirmed_shm_name=None,
        bind_host="127.0.0.1",
        local_command_port=5565,
        server_host="10.196.0.67",
        server_command_port=5555,
        server_image_port=5556,
        server_ack_port=5557,
        image_topic="slm.image",
        ack_topic="slm.ack",
        timeout_ms=5000,
        create_shm=True,
        acquire_control=True,
        poll_timeout_s=0.001,
    ):
        self.client_id = client_id if client_id is not None else f"slm_bridge_{uuid.uuid4()}"
        self.shm_name = str(shm_name)
        self.confirmed_shm_name = (
            str(confirmed_shm_name)
            if confirmed_shm_name is not None
            else f"{self.shm_name}_confirmed"
        )
        self.bind_host = bind_host
        self.local_command_port = int(local_command_port)
        self.server_host = server_host
        self.server_command_port = int(server_command_port)
        self.server_image_port = int(server_image_port)
        self.server_ack_port = int(server_ack_port)
        self.image_topic = str(image_topic)
        self.ack_topic = str(ack_topic)
        self.timeout_ms = int(timeout_ms)
        self.create_shm = bool(create_shm)
        self.acquire_control_on_start = bool(acquire_control)
        self.poll_timeout_s = float(poll_timeout_s)

        self.context = zmq.Context()
        self.running = True

        self.frame_id = 0
        self.last_sent_shm_counter = -1
        self.last_sent_frame_id = 0
        self.last_ack_frame_id = 0
        self.last_ack_shm_counter = -1
        self.last_ack_ok = False
        self.last_display_success = False
        self.last_error = None
        self.skipped_counter_count = 0
        self.last_timing = {}
        self.monitor_width = None
        self.monitor_height = None
        self.NumberOfChannels = None
        self.image_shape = None
        self.single_channel_shape = None
        self.shm = None
        self.confirmed_shm = None
        self.pending_writes = {}

        self.server_command_socket = self.context.socket(zmq.REQ)
        self.server_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.server_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.server_command_socket.connect(
            f"tcp://{self.server_host}:{self.server_command_port}"
        )
   
        self.server_image_socket = self.context.socket(zmq.PUB)
        self.server_image_socket.setsockopt(zmq.SNDHWM, 1)
        self.server_image_socket.connect(
            f"tcp://{self.server_host}:{self.server_image_port}"
        )

        self.server_ack_socket = self.context.socket(zmq.SUB)
        self.server_ack_socket.setsockopt(zmq.RCVHWM, 16)
        self.server_ack_socket.setsockopt_string(zmq.SUBSCRIBE, self.ack_topic)
        self.server_ack_socket.connect(
            f"tcp://{self.server_host}:{self.server_ack_port}"
        )

        self.client_command_socket = self.context.socket(zmq.REP)
        self.client_command_socket.setsockopt(zmq.LINGER, 0)
        self.client_command_socket.setsockopt(zmq.SNDTIMEO, 0)
        self.client_command_socket.bind(f"tcp://{self.bind_host}:{self.local_command_port}")

    def _reset_server_command_socket(self):
        try:
            self.server_command_socket.close(0)
        except Exception:
            pass
        self.server_command_socket = self.context.socket(zmq.REQ)
        self.server_command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.server_command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.server_command_socket.connect(
            f"tcp://{self.server_host}:{self.server_command_port}"
        )

    def _send_server_json(self, msg):
        msg = dict(msg)
        msg["client_id"] = self.client_id

        try:
            self.server_command_socket.send_json(msg)
            reply = self.server_command_socket.recv_json()
        except Exception:
            self._reset_server_command_socket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown SLM server error"))

        return reply

    def _send_server_snapshot_request(self, msg):
        msg = dict(msg)
        msg["client_id"] = self.client_id

        try:
            self.server_command_socket.send_json(msg)
            reply_parts = self.server_command_socket.recv_multipart()
        except Exception:
            self._reset_server_command_socket()
            raise

        if not reply_parts:
            raise RuntimeError("SLM server returned an empty snapshot reply")

        reply = json.loads(reply_parts[0].decode("utf-8"))
        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown SLM server error"))
        return reply_parts

    def _read_stable_requested_image(self, changed_counter):
        expected_counter = int(changed_counter)

        for _ in range(10):
            frame = np.asarray(self.shm.get_data(copy=True), dtype=np.uint8)
            keywords = dict(self.shm.get_keywords())
            counter_after = int(self.shm.get_counter())

            if counter_after != expected_counter:
                self.skipped_counter_count += max(
                    1,
                    counter_after - expected_counter,
                )
                expected_counter = counter_after
                continue

            writing = int(keywords.get("WRITING", 0))
            keyword_counter = int(keywords.get("SHMCNT", counter_after))
            if writing != 0 or keyword_counter != counter_after:
                return None

            if frame.shape != self.single_channel_shape:
                raise ValueError(
                    f"Expected SHM image shape {self.single_channel_shape}, "
                    f"got {frame.shape}"
                )

            channel_index = int(keywords.get("CHANIDX", 0))
            if channel_index < 0 or channel_index >= self.NumberOfChannels:
                raise ValueError(
                    f"channelIdx {channel_index} out of range for "
                    f"{self.NumberOfChannels} channels"
                )

            return np.ascontiguousarray(frame), channel_index, counter_after

        return None

    def _send_latest_shm_image_to_server(self, changed_counter):
        requested_write = self._read_stable_requested_image(changed_counter)
        if requested_write is None:
            return False

        image, channelIdx, counter = requested_write
        if counter == self.last_sent_shm_counter:
            return False

        send_start_ns = time.perf_counter_ns()
        self.frame_id += 1
        frame_id = int(self.frame_id)
        header = {
            "type": "slm_image",
            "client_id": self.client_id,
            "shape": list(self.single_channel_shape),
            "dtype": "uint8",
            "frame_id": frame_id,
            "channelIdx": int(channelIdx),
            "shm_name": self.shm_name,
            "shm_counter": int(counter),
            "publish_time_ns": time.time_ns(),
        }

        try:
            self.server_image_socket.send_multipart(
                [
                    self.image_topic.encode("utf-8"),
                    json.dumps(header).encode("utf-8"),
                    memoryview(image),
                ],
                flags=zmq.NOBLOCK,
            )
        except zmq.Again:
            self.last_error = (
                "SLM server image socket is not ready; "
                f"dropped SHM counter {counter}"
            )
            return False
        send_done_ns = time.perf_counter_ns()

        if self.last_sent_shm_counter >= 0 and counter > self.last_sent_shm_counter + 1:
            self.skipped_counter_count += counter - self.last_sent_shm_counter - 1

        self.last_sent_shm_counter = counter
        self.last_sent_frame_id = frame_id
        self.pending_writes[frame_id] = {
            "image": image,
            "channelIdx": int(channelIdx),
            "shm_counter": int(counter),
        }
        self.last_error = None
        self.last_timing = {
            "frame_id": int(frame_id),
            "shm_counter": int(counter),
            "bridge_send_start_perf_ns": int(send_start_ns),
            "bridge_send_done_perf_ns": int(send_done_ns),
            "bridge_send_ms": (send_done_ns - send_start_ns) / 1e6,
            "image_nbytes": int(image.nbytes),
        }
        return True

    def _commit_acknowledged_image(self, ack):
        acknowledged_frame_id = int(ack.get("frame_id", 0))
        pending_write = self.pending_writes.get(acknowledged_frame_id)

        if bool(ack.get("ok", False)) and pending_write is not None:
            channel_index = int(pending_write["channelIdx"])
            self.confirmed_shm.set_keywords(
                {
                    "WRITING": 1,
                    "CHANIDX": channel_index,
                    "FRAMEID": acknowledged_frame_id,
                }
            )
            self.confirmed_shm.set_data(pending_write["image"])
            confirmed_counter = int(self.confirmed_shm.get_counter())
            self.confirmed_shm.set_keywords(
                {
                    "WRITING": 0,
                    "CHANIDX": channel_index,
                    "FRAMEID": acknowledged_frame_id,
                    "SHMCNT": confirmed_counter,
                }
            )

        completed_frame_ids = [
            frame_id
            for frame_id in self.pending_writes
            if frame_id <= acknowledged_frame_id
        ]
        for frame_id in completed_frame_ids:
            del self.pending_writes[frame_id]

    def _drain_server_ack_socket(self):
        received_ack = False

        while True:
            try:
                parts = self.server_ack_socket.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.Again:
                return received_ack

            try:
                if len(parts) == 2:
                    _, payload = parts
                elif len(parts) == 1:
                    payload = parts[0]
                else:
                    raise ValueError("ACK must be [topic, payload] or [payload]")

                ack = json.loads(payload.decode("utf-8"))
                if ack.get("client_id") != self.client_id:
                    continue

                received_ack = True
                self.last_ack_frame_id = int(ack.get("frame_id", self.last_ack_frame_id))
                self.last_ack_shm_counter = int(
                    ack.get("shm_counter", self.last_ack_shm_counter)
                )
                self.last_ack_ok = bool(ack.get("ok", False))
                self.last_display_success = self.last_ack_ok
                self.last_error = ack.get("error")
                self._commit_acknowledged_image(ack)
                if "timing" in ack:
                    self.last_timing = dict(self.last_timing, server_ack=ack["timing"])
            except Exception as e:
                self.last_error = f"ACK {type(e).__name__}: {e}"

    def _get_local_properties(self, include_server=False):
        result = {
            "client_id": self.client_id,
            "shm_name": self.shm_name,
            "confirmed_shm_name": self.confirmed_shm_name,
            "shm_protocol": {
                "image_shape": list(self.single_channel_shape),
                "channel_keyword": "CHANIDX",
                "counter_keyword": "SHMCNT",
                "writing_keyword": "WRITING",
            },
            "monitor_width": self.monitor_width,
            "monitor_height": self.monitor_height,
            "number_of_channels": self.NumberOfChannels,
            "input_expected_shape": list(self.image_shape),
            "single_channel_shape": list(self.single_channel_shape),
            "local_command_port": self.local_command_port,
            "server_host": self.server_host,
            "server_command_port": self.server_command_port,
            "server_image_port": self.server_image_port,
            "server_ack_port": self.server_ack_port,
            "image_topic": self.image_topic,
            "ack_topic": self.ack_topic,
            "last_frame_id": int(self.frame_id),
            "last_sent_shm_counter": int(self.last_sent_shm_counter),
            "last_sent_frame_id": int(self.last_sent_frame_id),
            "last_ack_frame_id": int(self.last_ack_frame_id),
            "last_ack_shm_counter": int(self.last_ack_shm_counter),
            "last_ack_ok": bool(self.last_ack_ok),
            "last_display_success": bool(self.last_display_success),
            "last_error": self.last_error,
            "skipped_counter_count": int(self.skipped_counter_count),
            "last_timing": self.last_timing,
        }

        if include_server:
            try:
                result["server_properties"] = self._send_server_json(
                    {"cmd": "get_properties"}
                )["result"]
            except Exception as e:
                result["server_properties_error"] = f"{type(e).__name__}: {e}"

        return result

    def _idle_briefly(self):
        if self.poll_timeout_s > 0:
            time.sleep(self.poll_timeout_s)

    def _wait_for_slm_display_ack(self, shm_counter, timeout_ms=None):
        timeout_s = (self.timeout_ms if timeout_ms is None else int(timeout_ms)) / 1000.0
        deadline = time.monotonic() + timeout_s
        target_counter = int(shm_counter)

        while time.monotonic() < deadline:
            self._drain_server_ack_socket()

            try:
                current_shm_counter = int(self.shm.get_counter())
                if current_shm_counter != self.last_sent_shm_counter:
                    self._send_latest_shm_image_to_server(current_shm_counter)
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
                self.last_display_success = False
                print(f"[SLM bridge] SHM send error: {type(e).__name__}: {e}")
                print(traceback.format_exc())

            if self.last_ack_shm_counter >= target_counter:
                return bool(self.last_ack_ok)
            self._idle_briefly()

        raise TimeoutError(
            f"Timed out waiting for SLM server display ACK for SHM counter {target_counter}"
        )

    def _process_client_command(self, msg):
        cmd = msg.get("cmd")

        if cmd == "get_properties":
            return {
                "ok": True,
                "result": self._get_local_properties(
                    include_server=bool(msg.get("include_server", False))
                ),
            }

        if cmd == "wait_for_slm_display_ack":
            ok = self._wait_for_slm_display_ack(
                msg["shm_counter"],
                timeout_ms=msg.get("timeout_ms"),
            )
            return {"ok": True, "result": int(ok)}

        if cmd == "get_confirmed_display_state":
            return self._send_server_snapshot_request(msg)

        if cmd == "shutdown":
            self.running = False
            return {"ok": True, "result": "shutdown_ack"}

        server_commands = {
            "set_refresh_rate",
            "set_trigger_output",
            "load_lut",
            "get_temperature",
            "acquire_control",
            "release_control",
        }
        if cmd in server_commands:
            return self._send_server_json(msg)

        return {"ok": False, "error": f"Unknown command: {cmd}"}

    def run_forever(self):
        print("[SLM bridge] requesting SLM server properties", flush=True)
        props = self._send_server_json({"cmd": "get_properties"})["result"]
        self.monitor_width = int(props["monitor_width"])
        self.monitor_height = int(props["monitor_height"])
        self.NumberOfChannels = int(props["number_of_channels"])
        self.single_channel_shape = (self.monitor_height, self.monitor_width)
        self.image_shape = (
            self.monitor_height,
            self.monitor_width,
        )
        print(f"[SLM bridge] SLM shape = {self.image_shape}", flush=True)

        if self.create_shm:
            initial = np.zeros(self.single_channel_shape, dtype=np.uint8)
            self.shm = SHM(self.shm_name, initial, shared=True, autoSqueeze=False)
            self.shm.set_data(initial)
        else:
            self.shm = SHM(self.shm_name, autoSqueeze=False)

        initial_counter = int(self.shm.get_counter())
        self.shm.set_keywords(
            {
                "WRITING": 0,
                "CHANIDX": 0,
                "SHMCNT": initial_counter,
            }
        )

        confirmed_initial = np.zeros(self.single_channel_shape, dtype=np.uint8)
        self.confirmed_shm = SHM(
            self.confirmed_shm_name,
            confirmed_initial,
            shared=True,
            autoSqueeze=False,
        )
        self.confirmed_shm.set_data(confirmed_initial)
        confirmed_counter = int(self.confirmed_shm.get_counter())
        self.confirmed_shm.set_keywords(
            {
                "WRITING": 0,
                "CHANIDX": 0,
                "FRAMEID": 0,
                "SHMCNT": confirmed_counter,
            }
        )
        print(f"[SLM bridge] SHM ready: {self.shm_name}", flush=True)

        if self.acquire_control_on_start:
            print("[SLM bridge] acquiring SLM control", flush=True)
            self._send_server_json({"cmd": "acquire_control"})
            print("[SLM bridge] SLM control acquired", flush=True)
            
        print(
            "[SLM bridge] entering main loop; client command socket = "
            f"tcp://{self.bind_host}:{self.local_command_port}",
            flush=True,
        )

        try:
            while self.running:
                # 1. Process any display ACKs already waiting from the server.
                ack_received = self._drain_server_ack_socket()

                # 2. Check the SHM counter and send the newest image if it changed.
                shm_frame_sent = False
                try:
                    current_shm_counter = int(self.shm.get_counter())
                    shm_counter_changed = current_shm_counter != self.last_sent_shm_counter

                    if shm_counter_changed:
                        print(
                            "[SLM bridge] SHM counter changed: "
                            f"{self.last_sent_shm_counter} -> {current_shm_counter}",
                            flush=True,
                        )
                        shm_frame_sent = self._send_latest_shm_image_to_server(
                            current_shm_counter
                        )
                        print(
                            "[SLM bridge] SHM image send attempted; "
                            f"sent={shm_frame_sent}",
                            flush=True,
                        )
                except Exception as e:
                    self.last_error = f"{type(e).__name__}: {e}"
                    self.last_display_success = False
                    print(f"[SLM bridge] SHM send error: {type(e).__name__}: {e}")
                    print(traceback.format_exc())

                # 3. Try to receive one client command without blocking.
                command_handled = False

                try:
                    msg = self.client_command_socket.recv_json(flags=zmq.NOBLOCK)
                except zmq.Again:
                    msg = None

                if msg is not None:
                    print(
                        f"[SLM bridge] received client command: {msg.get('cmd')}",
                        flush=True,
                    )
                    try:
                        reply = self._process_client_command(msg)
                    except Exception as e:
                        reply = {
                            "ok": False,
                            "error": f"{type(e).__name__}: {e}",
                            "traceback": traceback.format_exc(),
                        }
                    try:
                        if isinstance(reply, list):
                            self.client_command_socket.send_multipart(
                                reply,
                                flags=zmq.NOBLOCK,
                            )
                        else:
                            self.client_command_socket.send_json(
                                reply,
                                flags=zmq.NOBLOCK,
                            )
                        command_handled = True
                        print(
                            f"[SLM bridge] replied to client command: {msg.get('cmd')}",
                            flush=True,
                        )
                    except zmq.Again:
                        self.last_error = "Client command reply socket is not ready; dropped reply"

                # 4. If nothing happened, sleep briefly so idle CPU use stays sane.
                if not (ack_received or shm_frame_sent or command_handled):
                    self._idle_briefly()

        finally:
            self.running = False
            if self.acquire_control_on_start:
                try:
                    self._send_server_json({"cmd": "release_control"})
                except Exception:
                    pass
            self.close()

    def close(self):
        for socket in (
            getattr(self, "client_command_socket", None),
            getattr(self, "server_command_socket", None),
            getattr(self, "server_image_socket", None),
            getattr(self, "server_ack_socket", None),
        ):
            try:
                if socket is not None:
                    socket.close(0)
            except Exception:
                pass
        try:
            if self.shm is not None:
                self.shm.close()
        except Exception:
            pass
        try:
            if self.confirmed_shm is not None:
                self.confirmed_shm.close()
        except Exception:
            pass
        try:
            self.context.term()
        except Exception:
            pass
