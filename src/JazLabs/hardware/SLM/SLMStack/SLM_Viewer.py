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

        try:
            viewer_shm = shared_memory.SharedMemory(name=self.shm_name)
            viewer_arr = np.ndarray(
                self.shape,
                dtype=self.dtype,
                buffer=viewer_shm.buf,
            )

            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
            frame_period_s = 1.0 / max(1, self.fps)
            next_frame_time = time.monotonic()

            while not self.terminateEvent.is_set():
                frame = viewer_arr.copy()
                display_frame = self.prepare_frame_for_display(frame)

                zoom = min(max(float(self.zoom.value), 0.05), 10.0)
                if zoom != 1.0:
                    height, width = display_frame.shape[:2]
                    display_frame = cv2.resize(
                        display_frame,
                        (
                            max(1, int(round(width * zoom))),
                            max(1, int(round(height * zoom))),
                        ),
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
    args = parser.parse_args()

    viewer = SLMOutputViewer(
        shm_name=args.shm_name,
        shape=args.shape,
        dtype=args.dtype,
        fps=args.fps,
        zoom=args.zoom,
    )
    viewer.run_forever()
