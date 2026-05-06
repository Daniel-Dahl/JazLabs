# SLM_ViewerLinux.py

import cv2
import numpy as np
import multiprocessing as mp
from pyMilk.interfacing.isio_shmlib import SHM


class SLMLinuxViewer:
    def __init__(
        self,
        stream_name,
        window_name="SLM Viewer",
        fps=30,
        zoom=1.0,
    ):
        self.stream_name = stream_name
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
        if frame is None:
            return None

        if frame.size == 0:
            return None

        frame = np.asarray(frame)

        # ------------------------------------------------------------
        # pymilk can sometimes return singleton channel dimensions in
        # odd locations, e.g.
        #     H x W
        #     H x W x 1
        #     1 x H x W
        #     H x 1 x W
        # This block converts those into a normal OpenCV display image.
        # ------------------------------------------------------------

        if frame.ndim == 2:
            display_frame = frame

        elif frame.ndim == 3:
            if 1 in frame.shape and frame.shape.count(1) == 1:
                # Single-channel image with singleton axis anywhere.
                singleton_axis = frame.shape.index(1)
                display_frame = np.take(frame, indices=0, axis=singleton_axis)

            elif frame.shape[-1] == 3:
                # Normal H x W x 3 image.
                display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            elif frame.shape[0] == 3:
                # C x H x W image.
                display_frame = np.transpose(frame, (1, 2, 0))
                display_frame = cv2.cvtColor(display_frame, cv2.COLOR_RGB2BGR)

            else:
                raise ValueError(f"Unsupported 3D frame shape for display: {frame.shape}")

        else:
            raise ValueError(f"Unsupported frame shape for display: {frame.shape}")

        # ------------------------------------------------------------
        # Make dtype OpenCV-safe.
        # ------------------------------------------------------------
        if np.iscomplexobj(display_frame):
            display_frame = np.abs(display_frame)

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
        shm = SHM(self.stream_name)
        

        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_AUTOSIZE)
            delay_ms = max(1, int(1000 / self.fps))

            while not self.terminateEvent.is_set():
                try:
                    frame = shm.get_data()
                    display_frame = self.prepare_frame_for_display(frame)

                except Exception as e:
                    print(f"[SLM Viewer] display error: {type(e).__name__}: {e}")
                    cv2.waitKey(delay_ms)
                    continue

                if display_frame is None:
                    cv2.waitKey(delay_ms)
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

                key = cv2.waitKey(delay_ms) & 0xFF
                if key == ord("q"):
                    break

        finally:
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

    viewer = SLMLinuxViewer(
        stream_name="PUT_YOUR_PYMILK_STREAM_NAME_HERE",
        zoom=1.0,
        fps=30,
    )

    viewer.run_forever()