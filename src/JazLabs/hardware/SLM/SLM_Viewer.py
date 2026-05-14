# SLM_Output_Viewer.py

import sys
import cv2
import zmq
import numpy as np
import multiprocessing as mp
from multiprocessing import shared_memory


class SLMOutputViewer:
    def __init__(
        self,
        shm_name,
        shape,
        dtype=np.uint8,
        window_name="SLM Viewer",
        fps=30,
        zoom=1.0,
    ):
        self.shm_name = shm_name
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

        self.Process = mp.Process(
            target=self.run_forever,
            daemon=False,
        )

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

    def run_forever(self):
        shm = shared_memory.SharedMemory(name=self.shm_name)

        try:
            image_arr = np.ndarray(
                self.shape,
                dtype=self.dtype,
                buffer=shm.buf,
            )

            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)

            delay_ms = max(1, int(1000 / self.fps))

            while not self.terminateEvent.is_set():
                frame = image_arr.copy()

                # Handle server viewer buffer:
                #   Meadowlark PCIe: H x W x 1
                #   HDMI SLM:        H x W x 3
                if frame.ndim == 3 and frame.shape[2] == 1:
                    frame = frame[:, :, 0]

                elif frame.ndim == 3 and frame.shape[2] == 3:
                    # OpenCV displays colour images as BGR.
                    # Server stores channel order as RGB-like channel order.
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                zoom = min(max(float(self.zoom.value), 0.05), 10.0)

                if zoom != 1.0:
                    frame = cv2.resize(
                        frame,
                        None,
                        fx=zoom,
                        fy=zoom,
                        interpolation=cv2.INTER_NEAREST,
                    )

                cv2.imshow(self.window_name, frame)

                key = cv2.waitKey(delay_ms) & 0xFF
                if key == ord("q"):
                    break

        finally:
            shm.close()
            cv2.destroyAllWindows()
            cv2.waitKey(1)

    def __del__(self):
        try:
            self.stopProcess()
        except Exception:
            pass

