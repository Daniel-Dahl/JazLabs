import argparse
import multiprocessing as mp
import time
from multiprocessing import shared_memory

import cv2
import numpy as np


class SLMOutputViewer:
    def __init__(
        self,
        shm_name=None,
        shape=None,
        dtype=np.uint8,
        window_name="SLM Viewer",
        fps=30,
        zoom=1.0,
        max_window_width=1200,
        max_window_height=900,
    ):
        if shm_name is None:
            raise ValueError("shm_name must be provided")
        if shape is None:
            raise ValueError("shape must be provided")

        self.shm_name = str(shm_name)
        self.shape = tuple(shape)
        self.dtype = np.dtype(dtype)
        self.window_name = window_name
        self.fps = int(fps)
        self.initial_zoom = float(zoom)
        self.max_window_width = int(max_window_width)
        self.max_window_height = int(max_window_height)

        if self.initial_zoom <= 0:
            raise ValueError("zoom must be greater than zero")
        if self.max_window_width <= 0 or self.max_window_height <= 0:
            raise ValueError("maximum window dimensions must be greater than zero")

        self.Process = None
        self.terminateEvent = mp.Event()
        self.zoom = mp.Value("d", self.initial_zoom)

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
        zoom = float(zoom)
        if zoom <= 0:
            raise ValueError("zoom must be greater than zero")
        self.zoom.value = zoom

    def prepare_frame_for_display(self, frame):
        frame = np.asarray(frame)

        if frame.ndim == 3 and frame.shape[2] == 1:
            display_frame = frame[:, :, 0]
        elif frame.ndim == 3 and frame.shape[2] == 3:
            display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        elif frame.ndim == 2:
            display_frame = frame
        else:
            raise ValueError(f"Unsupported SLM viewer frame shape: {frame.shape}")

        if display_frame.dtype == np.bool_:
            display_frame = display_frame.astype(np.uint8) * 255
        elif display_frame.dtype != np.uint8:
            display_frame = display_frame.astype(np.float32)
            fmin = np.nanmin(display_frame)
            fmax = np.nanmax(display_frame)
            if np.isfinite(fmin) and np.isfinite(fmax) and fmax > fmin:
                display_frame = (
                    255 * (display_frame - fmin) / (fmax - fmin)
                ).astype(np.uint8)
            else:
                display_frame = np.zeros(display_frame.shape, dtype=np.uint8)

        return np.ascontiguousarray(display_frame)

    def run_forever(self):
        viewer_shm = None

        view_x0 = 0
        view_y0 = 0
        view_width = None
        view_height = None
        applied_zoom = None

        def update_view_for_zoom(
            frame_shape,
            new_zoom,
            anchor_raw_x=None,
            anchor_raw_y=None,
        ):
            nonlocal view_x0, view_y0, view_width, view_height, applied_zoom

            frame_height, frame_width = frame_shape[:2]

            if anchor_raw_x is None:
                anchor_raw_x = view_x0 + (view_width or frame_width) / 2
            if anchor_raw_y is None:
                anchor_raw_y = view_y0 + (view_height or frame_height) / 2

            applied_zoom = min(max(float(new_zoom), 0.05), 50.0)
            self.zoom.value = applied_zoom

            target_display_width = min(
                self.max_window_width,
                max(1, int(round(frame_width * applied_zoom))),
            )
            target_display_height = min(
                self.max_window_height,
                max(1, int(round(frame_height * applied_zoom))),
            )

            view_width = int(
                max(1, min(frame_width, target_display_width / applied_zoom))
            )
            view_height = int(
                max(1, min(frame_height, target_display_height / applied_zoom))
            )

            view_x0 = int(anchor_raw_x - view_width / 2)
            view_y0 = int(anchor_raw_y - view_height / 2)
            view_x0 = max(0, min(view_x0, frame_width - view_width))
            view_y0 = max(0, min(view_y0, frame_height - view_height))

        mouse_position = {"x": None, "y": None, "frame_shape": self.shape}

        def screen_to_raw(x, y):
            zoom = applied_zoom if applied_zoom is not None else self.initial_zoom
            raw_x = int(view_x0 + x / zoom)
            raw_y = int(view_y0 + y / zoom)
            return raw_x, raw_y

        def mouse_callback(event, x, y, flags, param):
            raw_x, raw_y = screen_to_raw(x, y)
            mouse_position["x"] = raw_x
            mouse_position["y"] = raw_y

            if event != cv2.EVENT_MOUSEWHEEL:
                return

            if flags > 0:
                new_zoom = (applied_zoom or self.initial_zoom) * 1.25
            else:
                new_zoom = (applied_zoom or self.initial_zoom) / 1.25

            update_view_for_zoom(
                mouse_position["frame_shape"],
                new_zoom,
                anchor_raw_x=raw_x,
                anchor_raw_y=raw_y,
            )

        try:
            viewer_shm = shared_memory.SharedMemory(name=self.shm_name)
            viewer_arr = np.ndarray(
                self.shape,
                dtype=self.dtype,
                buffer=viewer_shm.buf,
            )

            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(self.window_name, mouse_callback)
            frame_period_s = 1.0 / max(1, self.fps)
            next_frame_time = time.monotonic()

            while not self.terminateEvent.is_set():
                frame = viewer_arr.copy()
                display_frame = self.prepare_frame_for_display(frame)
                mouse_position["frame_shape"] = display_frame.shape

                requested_zoom = min(max(float(self.zoom.value), 0.05), 50.0)
                if applied_zoom is None:
                    update_view_for_zoom(display_frame.shape, requested_zoom)
                elif requested_zoom != applied_zoom:
                    update_view_for_zoom(display_frame.shape, requested_zoom)

                cropped_frame = display_frame[
                    view_y0:view_y0 + view_height,
                    view_x0:view_x0 + view_width,
                ]

                if applied_zoom != 1.0:
                    display_frame = cv2.resize(
                        cropped_frame,
                        (
                            max(1, int(round(view_width * applied_zoom))),
                            max(1, int(round(view_height * applied_zoom))),
                        ),
                        interpolation=(
                            cv2.INTER_AREA
                            if applied_zoom < 1.0
                            else cv2.INTER_NEAREST
                        ),
                    )
                else:
                    display_frame = cropped_frame

                cv2.imshow(self.window_name, display_frame)
                display_height, display_width = display_frame.shape[:2]
                cv2.resizeWindow(
                    self.window_name,
                    display_width,
                    display_height,
                )

                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                elif key in [ord("+"), ord("=")]:
                    update_view_for_zoom(
                        mouse_position["frame_shape"],
                        applied_zoom * 1.25,
                        anchor_raw_x=mouse_position["x"],
                        anchor_raw_y=mouse_position["y"],
                    )
                elif key in [ord("-"), ord("_")]:
                    update_view_for_zoom(
                        mouse_position["frame_shape"],
                        applied_zoom / 1.25,
                        anchor_raw_x=mouse_position["x"],
                        anchor_raw_y=mouse_position["y"],
                    )
                elif key == ord("0"):
                    frame_height, frame_width = mouse_position["frame_shape"][:2]
                    update_view_for_zoom(
                        mouse_position["frame_shape"],
                        self.initial_zoom,
                        anchor_raw_x=frame_width / 2,
                        anchor_raw_y=frame_height / 2,
                    )

                next_frame_time += frame_period_s
                sleep_s = next_frame_time - time.monotonic()
                if sleep_s > 0:
                    time.sleep(sleep_s)
                else:
                    next_frame_time = time.monotonic()

        finally:
            try:
                if viewer_shm is not None:
                    viewer_shm.close()
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

    parser = argparse.ArgumentParser(description="View an SLMStack display buffer.")
    parser.add_argument("--shm-name", required=True)
    parser.add_argument("--shape", type=int, nargs="+", required=True)
    parser.add_argument("--dtype", default="uint8")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--zoom", type=float, default=1.0)
    parser.add_argument("--max-window-width", type=int, default=1200)
    parser.add_argument("--max-window-height", type=int, default=900)
    args = parser.parse_args()

    viewer = SLMOutputViewer(
        shm_name=args.shm_name,
        shape=args.shape,
        dtype=args.dtype,
        fps=args.fps,
        zoom=args.zoom,
        max_window_width=args.max_window_width,
        max_window_height=args.max_window_height,
    )
    viewer.run_forever()
