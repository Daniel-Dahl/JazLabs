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


if __name__ == "__main__":
    mp.freeze_support()

    if len(sys.argv) < 3:
        print("\n[SLM Viewer] ERROR: Server host and port must be provided.\n")
        print("Usage:")
        print("    python SLM_Output_Viewer.py <host> <port>\n")
        print("Example:")
        print("    python SLM_Output_Viewer.py 127.0.0.1 50721\n")
        print("Make sure the SLM server is running first.\n")
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    context = zmq.Context()
    socket = context.socket(zmq.REQ)

    try:
        socket.setsockopt(zmq.RCVTIMEO, 3000)
        socket.setsockopt(zmq.SNDTIMEO, 3000)
        socket.connect(f"tcp://{host}:{port}")

        socket.send_json({
            "cmd": "get_properties",
            "client_id": "slm_viewer",
        })

        reply = socket.recv_json()

        if not reply.get("ok", False):
            raise RuntimeError(reply.get("error", "Server returned an error"))

        props = reply["result"]

        shm_name = props["viewer_shared_memory_name"]
        shape = tuple(props["viewer_shape"])
        dtype = np.dtype(props["viewer_dtype"])

    except Exception as e:
        print("\n[SLM Viewer] ERROR: Could not connect to SLM server.\n")
        print(f"Details: {type(e).__name__}: {e}\n")
        print("Check:")
        print("    - Server is running")
        print("    - Host and port are correct\n")
        sys.exit(1)

    finally:
        try:
            socket.close()
            context.term()
        except Exception:
            pass

    try:
        shm_test = shared_memory.SharedMemory(name=shm_name)
        shm_test.close()

    except FileNotFoundError:
        print(f"\n[SLM Viewer] ERROR: Shared memory '{shm_name}' not found.\n")
        print("The server returned a viewer buffer, but it could not be opened.")
        print("The server may have restarted.\n")
        sys.exit(1)

    print("[SLM Viewer] Connected to server.")
    print(f"[SLM Viewer] shm_name = {shm_name}")
    print(f"[SLM Viewer] shape = {shape}")
    print(f"[SLM Viewer] dtype = {dtype}")

    viewer = SLMOutputViewer(
        shm_name=shm_name,
        shape=shape,
        dtype=dtype,
        zoom=1.0,
        fps=30,
    )

    viewer.run_forever()