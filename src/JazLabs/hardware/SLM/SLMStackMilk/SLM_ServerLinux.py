import argparse
import json
import time
import traceback
import uuid

import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMLinuxServer:
    """
    Linux bridge for a Windows-hosted SLM.

    This process owns the network connection to SLM_ServerWindows.py, watches a
    pymilk SHM, and publishes every SHM update to the Windows server. Local
    clients can update the SHM directly or call the small command server exposed
    here for the Meadowlark-style control methods.
    """

    def __init__(
        self,
        client_id=None,
        shm_name="slm_image",
        bind_host="127.0.0.1",
        local_command_port=5565,
        windows_host="10.196.0.67",
        windows_command_port=5555,
        windows_image_port=5556,
        windows_ack_port=5557,
        image_topic="slm.image",
        ack_topic="slm.ack",
        timeout_ms=5000,
        create_shm=True,
        acquire_control=True,
        poll_timeout_s=0.001,
    ):
        self.client_id = client_id if client_id is not None else f"slm_linux_server_{uuid.uuid4()}"
        self.shm_name = str(shm_name)
        self.bind_host = bind_host
        self.local_command_port = int(local_command_port)
        self.windows_host = windows_host
        self.windows_command_port = int(windows_command_port)
        self.windows_image_port = int(windows_image_port)
        self.windows_ack_port = int(windows_ack_port)
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

        self.command_socket = self.context.socket(zmq.REQ)
        self.command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.command_socket.connect(f"tcp://{self.windows_host}:{self.windows_command_port}")
   
        self.image_pub_socket = self.context.socket(zmq.PUB)
        self.image_pub_socket.setsockopt(zmq.SNDHWM, 1)
        self.image_pub_socket.connect(f"tcp://{self.windows_host}:{self.windows_image_port}")

        self.ack_sub_socket = self.context.socket(zmq.SUB)
        self.ack_sub_socket.setsockopt(zmq.RCVHWM, 16)
        self.ack_sub_socket.setsockopt_string(zmq.SUBSCRIBE, self.ack_topic)
        self.ack_sub_socket.connect(f"tcp://{self.windows_host}:{self.windows_ack_port}")

        self.client_command_socket = self.context.socket(zmq.REP)
        self.client_command_socket.setsockopt(zmq.LINGER, 0)
        self.client_command_socket.setsockopt(zmq.SNDTIMEO, 0)
        self.client_command_socket.bind(f"tcp://{self.bind_host}:{self.local_command_port}")

    def _reset_windows_command_socket(self):
        try:
            self.command_socket.close(0)
        except Exception:
            pass
        self.command_socket = self.context.socket(zmq.REQ)
        self.command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        self.command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        self.command_socket.connect(f"tcp://{self.windows_host}:{self.windows_command_port}")

    def _send_windows_json(self, msg):
        msg = dict(msg)
        msg["client_id"] = self.client_id

        try:
            self.command_socket.send_json(msg)
            reply = self.command_socket.recv_json()
        except Exception:
            self._reset_windows_command_socket()
            raise

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown Windows SLM server error"))

        return reply

    def _normalise_shm_image(self, frame):
        arr = np.asarray(frame)

        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8, copy=False)

        if arr.shape == self.single_channel_shape:
            image_cube = np.zeros(self.image_shape, dtype=np.uint8)
            image_cube[:, :, 0] = arr
            return image_cube, 0

        if arr.shape == self.image_shape:
            return np.ascontiguousarray(arr), 0

        if (
            arr.ndim == 3
            and arr.shape[0] == self.NumberOfChannels
            and arr.shape[1:] == self.single_channel_shape
        ):
            return np.ascontiguousarray(np.transpose(arr, (1, 2, 0))), 0

        raise ValueError(
            f"Expected SHM image shape {self.single_channel_shape}, "
            f"{self.image_shape}, or channels-first equivalent; got {arr.shape}"
        )

    def _send_latest_shm_image_to_windows_server(self, changed_counter):
        counter_before = int(changed_counter)

        while True:
            frame = self.shm.get_data(copy=True)
            counter_after = int(self.shm.get_counter())
            if counter_after == counter_before:
                break

            self.skipped_counter_count += max(1, counter_after - counter_before)
            counter_before = counter_after

        counter = counter_after
        if counter == self.last_sent_shm_counter:
            return False

        image_cube, channelIdx = self._normalise_shm_image(frame)

        send_start_ns = time.perf_counter_ns()
        self.frame_id += 1
        frame_id = int(self.frame_id)
        header = {
            "type": "slm_image",
            "client_id": self.client_id,
            "shape": list(self.image_shape),
            "dtype": "uint8",
            "frame_id": frame_id,
            "channelIdx": int(channelIdx),
            "shm_name": self.shm_name,
            "shm_counter": int(counter),
            "publish_time_ns": time.time_ns(),
        }

        try:
            self.image_pub_socket.send_multipart(
                [
                    self.image_topic.encode("utf-8"),
                    json.dumps(header).encode("utf-8"),
                    memoryview(image_cube),
                ],
                flags=zmq.NOBLOCK,
            )
        except zmq.Again:
            self.last_error = (
                "Windows image socket is not ready; "
                f"dropped SHM counter {counter}"
            )
            return False
        send_done_ns = time.perf_counter_ns()

        if self.last_sent_shm_counter >= 0 and counter > self.last_sent_shm_counter + 1:
            self.skipped_counter_count += counter - self.last_sent_shm_counter - 1

        self.last_sent_shm_counter = counter
        self.last_sent_frame_id = frame_id
        self.last_error = None
        self.last_timing = {
            "frame_id": int(frame_id),
            "shm_counter": int(counter),
            "linux_send_start_perf_ns": int(send_start_ns),
            "linux_send_done_perf_ns": int(send_done_ns),
            "linux_send_ms": (send_done_ns - send_start_ns) / 1e6,
            "image_nbytes": int(image_cube.nbytes),
        }
        return True

    def _drain_windows_server_ack_socket(self):
        received_ack = False

        while True:
            try:
                parts = self.ack_sub_socket.recv_multipart(flags=zmq.NOBLOCK)
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
                if "timing" in ack:
                    self.last_timing = dict(self.last_timing, windows_ack=ack["timing"])
            except Exception as e:
                self.last_error = f"ACK {type(e).__name__}: {e}"

    def _get_local_properties(self, include_windows=False):
        result = {
            "client_id": self.client_id,
            "shm_name": self.shm_name,
            "monitor_width": self.monitor_width,
            "monitor_height": self.monitor_height,
            "number_of_channels": self.NumberOfChannels,
            "input_expected_shape": list(self.image_shape),
            "single_channel_shape": list(self.single_channel_shape),
            "local_command_port": self.local_command_port,
            "windows_host": self.windows_host,
            "windows_command_port": self.windows_command_port,
            "windows_image_port": self.windows_image_port,
            "windows_ack_port": self.windows_ack_port,
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

        if include_windows:
            try:
                result["windows_properties"] = self._send_windows_json(
                    {"cmd": "get_properties"}
                )["result"]
            except Exception as e:
                result["windows_properties_error"] = f"{type(e).__name__}: {e}"

        return result

    def _idle_briefly(self):
        if self.poll_timeout_s > 0:
            time.sleep(self.poll_timeout_s)

    def _wait_for_slm_display_ack(self, shm_counter, timeout_ms=None):
        timeout_s = (self.timeout_ms if timeout_ms is None else int(timeout_ms)) / 1000.0
        deadline = time.monotonic() + timeout_s
        target_counter = int(shm_counter)

        while time.monotonic() < deadline:
            self._drain_windows_server_ack_socket()

            try:
                current_shm_counter = int(self.shm.get_counter())
                if current_shm_counter != self.last_sent_shm_counter:
                    self._send_latest_shm_image_to_windows_server(current_shm_counter)
            except Exception as e:
                self.last_error = f"{type(e).__name__}: {e}"
                self.last_display_success = False
                print(f"[Linux SLM Server] SHM send error: {type(e).__name__}: {e}")
                print(traceback.format_exc())

            if self.last_ack_shm_counter >= target_counter:
                return bool(self.last_ack_ok)
            self._idle_briefly()

        raise TimeoutError(
            f"Timed out waiting for Windows SLM display ACK for SHM counter {target_counter}"
        )

    def _process_client_command(self, msg):
        cmd = msg.get("cmd")

        if cmd == "get_properties":
            return {
                "ok": True,
                "result": self._get_local_properties(
                    include_windows=bool(msg.get("include_windows", False))
                ),
            }

        if cmd == "wait_for_slm_display_ack":
            ok = self._wait_for_slm_display_ack(
                msg["shm_counter"],
                timeout_ms=msg.get("timeout_ms"),
            )
            return {"ok": True, "result": int(ok)}

        if cmd == "shutdown":
            self.running = False
            return {"ok": True, "result": "shutdown_ack"}

        windows_cmds = {
            "set_refresh_rate",
            "set_trigger_output",
            "load_lut",
            "get_temperature",
            "acquire_control",
            "release_control",
        }
        if cmd in windows_cmds:
            return self._send_windows_json(msg)

        return {"ok": False, "error": f"Unknown command: {cmd}"}

    def run_forever(self):
        print("[Linux SLM Server] requesting Windows SLM properties", flush=True)
        props = self._send_windows_json({"cmd": "get_properties"})["result"]
        self.monitor_width = int(props["monitor_width"])
        self.monitor_height = int(props["monitor_height"])
        self.NumberOfChannels = int(props["number_of_channels"])
        self.single_channel_shape = (self.monitor_height, self.monitor_width)
        self.image_shape = (
            self.monitor_height,
            self.monitor_width,
            self.NumberOfChannels,
        )
        print(f"[Linux SLM Server] Windows SLM shape = {self.image_shape}", flush=True)

        if self.create_shm:
            initial = np.zeros(self.image_shape, dtype=np.uint8)
            self.shm = SHM(self.shm_name, initial, shared=True, autoSqueeze=False)
            self.shm.set_data(initial)
        else:
            self.shm = SHM(self.shm_name, autoSqueeze=False)
        print(f"[Linux SLM Server] SHM ready: {self.shm_name}", flush=True)

        if self.acquire_control_on_start:
            print("[Linux SLM Server] acquiring Windows SLM control", flush=True)
            self._send_windows_json({"cmd": "acquire_control"})
            print("[Linux SLM Server] Windows SLM control acquired", flush=True)
            
        print(
            "[Linux SLM Server] entering main loop; client command socket = "
            f"tcp://{self.bind_host}:{self.local_command_port}",
            flush=True,
        )

        try:
            while self.running:
                # 1. Process any display ACKs already waiting from Windows.
                ack_received = self._drain_windows_server_ack_socket()

                # 2. Check the SHM counter and send the newest image if it changed.
                shm_frame_sent = False
                try:
                    current_shm_counter = int(self.shm.get_counter())
                    shm_counter_changed = current_shm_counter != self.last_sent_shm_counter

                    if shm_counter_changed:
                        print(
                            "[Linux SLM Server] SHM counter changed: "
                            f"{self.last_sent_shm_counter} -> {current_shm_counter}",
                            flush=True,
                        )
                        shm_frame_sent = self._send_latest_shm_image_to_windows_server(
                            current_shm_counter
                        )
                        print(
                            "[Linux SLM Server] SHM image send attempted; "
                            f"sent={shm_frame_sent}",
                            flush=True,
                        )
                except Exception as e:
                    self.last_error = f"{type(e).__name__}: {e}"
                    self.last_display_success = False
                    print(f"[Linux SLM Server] SHM send error: {type(e).__name__}: {e}")
                    print(traceback.format_exc())

                # 3. Try to receive one client command without blocking.
                command_handled = False

                try:
                    msg = self.client_command_socket.recv_json(flags=zmq.NOBLOCK)
                except zmq.Again:
                    msg = None

                if msg is not None:
                    print(
                        f"[Linux SLM Server] received client command: {msg.get('cmd')}",
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
                        self.client_command_socket.send_json(reply, flags=zmq.NOBLOCK)
                        command_handled = True
                        print(
                            f"[Linux SLM Server] replied to client command: {msg.get('cmd')}",
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
                    self._send_windows_json({"cmd": "release_control"})
                except Exception:
                    pass
            self.close()

    def close(self):
        for socket in (
            getattr(self, "client_command_socket", None),
            getattr(self, "command_socket", None),
            getattr(self, "image_pub_socket", None),
            getattr(self, "ack_sub_socket", None),
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
            self.context.term()
        except Exception:
            pass
