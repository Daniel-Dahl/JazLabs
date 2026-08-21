import json
import multiprocessing as mp
import time

import cv2
import numpy as np
import zmq
from pyMilk.interfacing.isio_shmlib import SHM


class SLMViewer:
    def __init__(
        self,
        stream_name,
        window_name="SLM Viewer",
        fps=30,
        zoom=1.0,
        number_of_channels=1,
        bridge_host=None,
        bridge_command_port=None,
        timeout_ms=5000,
    ):
        self.stream_name = stream_name
        self.window_name = window_name
        self.fps = int(fps)
        self.number_of_channels = int(number_of_channels)
        self.bridge_host = bridge_host
        self.bridge_command_port = bridge_command_port
        self.timeout_ms = int(timeout_ms)

        self.Process = None
        self.terminateEvent = mp.Event()
        self.zoom = mp.Value("d", float(zoom))

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM viewer is already running.")
            return

        self.terminateEvent.clear()
        self.Process = mp.Process(target=self.run_forever, daemon=False)
        self.Process.start()
        print(f"SLM viewer process started with PID {self.Process.pid}")

    def stopProcess(self):
        self.terminateEvent.set()

        if self.Process is not None:
            self.Process.join(timeout=2.0)

            if self.Process.is_alive():
                self.Process.terminate()
                self.Process.join(timeout=1.0)

            self.Process = None

    def set_zoom(self, zoom):
        self.zoom.value = float(zoom)

    def prepare_frame_for_display(self, frame):
        if frame is None or frame.size == 0:
            return None

        frame = np.asarray(frame)

        if frame.ndim == 2:
            display_frame = frame

        elif frame.ndim == 3:
            if 1 in frame.shape and frame.shape.count(1) == 1:
                singleton_axis = frame.shape.index(1)
                display_frame = np.take(frame, indices=0, axis=singleton_axis)

            elif frame.shape[-1] == 3:
                display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            elif frame.shape[0] == 3:
                display_frame = np.transpose(frame, (1, 2, 0))
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_RGB2BGR)

            else:
                raise ValueError(f"Unsupported 3D frame shape for display: {frame.shape}")

        else:
            raise ValueError(f"Unsupported frame shape for display: {frame.shape}")

        if np.iscomplexobj(display_frame):
            display_frame = np.abs(display_frame)

        if display_frame.dtype == np.bool_:
            display_frame = display_frame.astype(np.uint8) * 255

        elif display_frame.dtype != np.uint8:
            display_frame = display_frame.astype(np.float32)
            fmin = np.nanmin(display_frame)
            fmax = np.nanmax(display_frame)

            if np.isfinite(fmin) and np.isfinite(fmax) and fmax > fmin:
                display_frame = (255 * (display_frame - fmin) / (fmax - fmin)).astype(np.uint8)
            else:
                display_frame = np.zeros(display_frame.shape, dtype=np.uint8)

        return np.ascontiguousarray(display_frame)

    @staticmethod
    def apply_confirmed_channel_image(
        accumulated_rgb_frame,
        confirmed_image,
        channel_index,
    ):
        if accumulated_rgb_frame is None:
            return confirmed_image.copy()

        rgb_channel_index = 2 - int(channel_index)
        accumulated_rgb_frame[:, :, rgb_channel_index] = confirmed_image
        return accumulated_rgb_frame.copy()

    def _request_confirmed_display_state(self):
        if self.bridge_host is None or self.bridge_command_port is None:
            return []

        context = zmq.Context()
        command_socket = context.socket(zmq.REQ)
        command_socket.setsockopt(zmq.LINGER, 0)
        command_socket.setsockopt(zmq.RCVTIMEO, self.timeout_ms)
        command_socket.setsockopt(zmq.SNDTIMEO, self.timeout_ms)
        command_socket.connect(
            f"tcp://{self.bridge_host}:{int(self.bridge_command_port)}"
        )

        try:
            command_socket.send_json(
                {
                    "cmd": "get_confirmed_display_state",
                    "client_id": "slm_milk_viewer",
                }
            )
            reply_parts = command_socket.recv_multipart()
        finally:
            command_socket.close(0)
            context.term()

        if not reply_parts:
            raise RuntimeError("SLM bridge returned an empty snapshot reply")

        reply = json.loads(reply_parts[0].decode("utf-8"))
        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Unknown SLM bridge error"))

        channel_states = []
        for channel_header in reply.get("result", {}).get("channels", []):
            part_index = int(channel_header["part_index"])
            shape = tuple(channel_header["shape"])
            dtype = np.dtype(channel_header["dtype"])
            channel_state = dict(channel_header)
            channel_state["image"] = np.frombuffer(
                reply_parts[part_index],
                dtype=dtype,
            ).reshape(shape).copy()
            channel_states.append(channel_state)
        return channel_states

    def run_forever(self):
        shm = SHM(self.stream_name)
        frame_period_s = 1.0 / max(1, self.fps)
        next_frame_time = time.monotonic()

        initial_frame = np.asarray(shm.get_data(copy=True), dtype=np.uint8)
        accumulated_rgb_frame = None
        if self.number_of_channels == 3:
            accumulated_rgb_frame = np.zeros(
                initial_frame.shape + (3,),
                dtype=np.uint8,
            )

        latest_display_frame = initial_frame
        last_seen_frame_id = 0

        def load_confirmed_state_snapshot():
            nonlocal latest_display_frame, last_seen_frame_id

            channel_states = self._request_confirmed_display_state()
            last_seen_frame_id = 0
            if accumulated_rgb_frame is not None:
                accumulated_rgb_frame.fill(0)
                latest_display_frame = accumulated_rgb_frame.copy()
            else:
                latest_display_frame = np.zeros_like(initial_frame)

            for channel_state in channel_states:
                if not bool(channel_state.get("confirmed", False)):
                    continue

                latest_display_frame = self.apply_confirmed_channel_image(
                    accumulated_rgb_frame,
                    channel_state["image"],
                    int(channel_state["channelIdx"]),
                )
                last_seen_frame_id = max(
                    last_seen_frame_id,
                    int(channel_state.get("frame_id", 0)),
                )

        load_confirmed_state_snapshot()
        last_counter = -1

        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)

            while not self.terminateEvent.is_set():
                try:
                    counter_before = int(shm.get_counter())
                    if counter_before != last_counter:
                        confirmed_image = np.asarray(
                            shm.get_data(copy=True),
                            dtype=np.uint8,
                        )
                        keywords = dict(shm.get_keywords())
                        counter_after = int(shm.get_counter())

                        writing = int(keywords.get("WRITING", 0))
                        keyword_counter = int(
                            keywords.get("SHMCNT", counter_after)
                        )
                        if (
                            counter_before == counter_after
                            and writing == 0
                            and keyword_counter == counter_after
                        ):
                            confirmed_frame_id = int(keywords.get("FRAMEID", 0))
                            confirmed_channel_index = int(
                                keywords.get("CHANIDX", 0)
                            )
                            if (
                                last_seen_frame_id > 0
                                and confirmed_frame_id != last_seen_frame_id + 1
                            ):
                                load_confirmed_state_snapshot()
                            elif confirmed_frame_id > 0:
                                latest_display_frame = (
                                    self.apply_confirmed_channel_image(
                                        accumulated_rgb_frame,
                                        confirmed_image,
                                        confirmed_channel_index,
                                    )
                                )
                                last_seen_frame_id = confirmed_frame_id
                            last_counter = counter_after

                    display_frame = self.prepare_frame_for_display(
                        latest_display_frame
                    )
                except Exception as e:
                    print(f"[SLM Viewer] display error: {type(e).__name__}: {e}")
                    cv2.waitKey(1)
                    continue

                if display_frame is None:
                    cv2.waitKey(1)
                    continue

                zoom = min(max(float(self.zoom.value), 0.05), 10.0)

                if zoom != 1.0:
                    h, w = display_frame.shape[:2]
                    new_w = max(1, int(round(w * zoom)))
                    new_h = max(1, int(round(h * zoom)))
                    display_frame = cv2.resize(
                        display_frame,
                        (new_w, new_h),
                        interpolation=cv2.INTER_NEAREST,
                    )

                cv2.imshow(self.window_name, display_frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break

                next_frame_time += frame_period_s
                sleep_s = next_frame_time - time.monotonic()
                if sleep_s > 0:
                    time.sleep(sleep_s)
                else:
                    next_frame_time = time.monotonic()

        finally:
            try:
                shm.close()
            except Exception:
                pass
            try:
                cv2.destroyAllWindows()
                cv2.waitKey(1)
            except Exception:
                pass

    def __del__(self):
        try:
            self.stopProcess()
        except Exception:
            pass


if __name__ == "__main__":
    mp.freeze_support()

    viewer = SLMViewer(
        stream_name="PUT_YOUR_PYMILK_STREAM_NAME_HERE",
        zoom=1.0,
        fps=30,
    )

    viewer.run_forever()
