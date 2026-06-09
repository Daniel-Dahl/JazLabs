import argparse
import multiprocessing as mp
import traceback

import numpy as np

try:
    from .SLM_Client import SLMClient
except ImportError:
    from SLM_Client import SLMClient


def _as_int(text, default=0):
    text = str(text).strip()
    if text == "":
        return int(default)
    return int(text)


def _as_float(text, default=0.0):
    text = str(text).strip()
    if text == "":
        return float(default)
    return float(text)


class SLMControlWindow:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=5555,
        display_pub_port=5556,
        timeout_ms=5000,
    ):
        import tkinter as tk
        from tkinter import filedialog
        from tkinter import ttk

        self.tk = tk
        self.ttk = ttk
        self.filedialog = filedialog

        self.client = SLMClient(
            host=host,
            command_port=command_port,
            display_pub_port=display_pub_port,
            timeout_ms=timeout_ms,
            client_id="slm_widget",
            attach_viewer_shared_memory=True,
        )
        self.properties = self.client.GetProperties()

        self.root = tk.Tk()
        self.root.title("SLM Control")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connected")
        self.host_var = tk.StringVar(value=host)
        self.command_port_var = tk.StringVar(value=str(command_port))
        self.display_port_var = tk.StringVar(value=str(display_pub_port))
        self.channel_var = tk.StringVar(value="0")
        self.refresh_rate_var = tk.StringVar(
            value=str(self.properties.get("refresh_rate", 0))
        )
        self.trigger_output_var = tk.BooleanVar(
            value=bool(self.properties.get("output_pulse_image_flip", 0))
        )
        self.npy_file_var = tk.StringVar(value="")

        self._build_layout()

    def _build_layout(self):
        ttk = self.ttk

        self.root.columnconfigure(0, weight=1)
        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(1, weight=1)

        ttk.Label(main, text="Status").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(main, textvariable=self.status_var).grid(
            row=0, column=1, columnspan=3, sticky="ew", padx=2, pady=2
        )

        ttk.Label(main, text="Host").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(main, textvariable=self.host_var, state="readonly").grid(
            row=1, column=1, sticky="ew", padx=2, pady=2
        )
        ttk.Label(main, text="Command Port").grid(
            row=1, column=2, sticky="w", padx=2, pady=2
        )
        ttk.Entry(main, textvariable=self.command_port_var, state="readonly", width=8).grid(
            row=1, column=3, sticky="ew", padx=2, pady=2
        )

        ttk.Label(main, text="Shape").grid(row=2, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(main, text=str(tuple(self.properties["input_expected_shape"]))).grid(
            row=2, column=1, sticky="w", padx=2, pady=2
        )
        ttk.Label(main, text="Channel").grid(row=2, column=2, sticky="w", padx=2, pady=2)
        ttk.Entry(main, textvariable=self.channel_var, width=8).grid(
            row=2, column=3, sticky="ew", padx=2, pady=2
        )

        ttk.Label(main, text="Refresh Rate").grid(
            row=3, column=0, sticky="w", padx=2, pady=2
        )
        ttk.Entry(main, textvariable=self.refresh_rate_var).grid(
            row=3, column=1, sticky="ew", padx=2, pady=2
        )
        ttk.Button(main, text="Set", command=self._call(self.set_refresh_rate)).grid(
            row=3, column=2, sticky="ew", padx=2, pady=2
        )
        ttk.Checkbutton(
            main,
            text="Trigger Output",
            variable=self.trigger_output_var,
            command=self._call(self.set_trigger_output),
        ).grid(row=3, column=3, sticky="w", padx=2, pady=2)

        ttk.Button(main, text="Clear Display", command=self._call(self.clear_display)).grid(
            row=4, column=0, sticky="ew", padx=2, pady=6
        )
        ttk.Button(main, text="Test Ramp", command=self._call(self.write_test_ramp)).grid(
            row=4, column=1, sticky="ew", padx=2, pady=6
        )
        ttk.Button(main, text="Load .npy", command=self._call(self.pick_npy_file)).grid(
            row=4, column=2, sticky="ew", padx=2, pady=6
        )
        ttk.Button(main, text="Write .npy", command=self._call(self.write_npy_file)).grid(
            row=4, column=3, sticky="ew", padx=2, pady=6
        )

        ttk.Entry(main, textvariable=self.npy_file_var).grid(
            row=5, column=0, columnspan=4, sticky="ew", padx=2, pady=2
        )

    def _call(self, func):
        def wrapped():
            try:
                func()
            except Exception as exc:
                self.status_var.set(f"ERROR: {type(exc).__name__}: {exc}")

        return wrapped

    def set_refresh_rate(self):
        refresh_rate = _as_float(self.refresh_rate_var.get())
        self.client.SetRefreshRate(refresh_rate)
        self.status_var.set(f"Refresh rate set to {refresh_rate}")

    def set_trigger_output(self):
        value = int(bool(self.trigger_output_var.get()))
        self.client.SetTriggerOutput(value)
        self.status_var.set(f"Trigger output set to {value}")

    def clear_display(self):
        image = np.zeros(tuple(self.properties["input_expected_shape"]), dtype=np.uint8)
        result = self.client.WriteToDisplay(image, channelIdx=_as_int(self.channel_var.get()))
        self.status_var.set(f"Clear sent: {result}")

    def write_test_ramp(self):
        single_channel_shape = tuple(self.properties["single_channel_shape"])
        width = int(single_channel_shape[1])
        ramp = np.linspace(0, 255, width, dtype=np.uint8)
        image = np.tile(ramp, (int(single_channel_shape[0]), 1))
        result = self.client.WriteToDisplay(image, channelIdx=_as_int(self.channel_var.get()))
        self.status_var.set(f"Ramp sent: {result}")

    def pick_npy_file(self):
        filename = self.filedialog.askopenfilename(
            title="Select SLM image .npy file",
            filetypes=(("NumPy files", "*.npy"), ("All files", "*.*")),
        )
        if filename:
            self.npy_file_var.set(filename)

    def write_npy_file(self):
        filename = self.npy_file_var.get().strip()
        if not filename:
            raise ValueError("Choose a .npy file first")
        image = np.load(filename)
        result = self.client.WriteToDisplay(image, channelIdx=_as_int(self.channel_var.get()))
        self.status_var.set(f".npy sent: {result}")

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def SLMControlWidgetProcess(
    host="127.0.0.1",
    command_port=5555,
    display_pub_port=5556,
    timeout_ms=5000,
):
    try:
        window = SLMControlWindow(
            host=host,
            command_port=command_port,
            display_pub_port=display_pub_port,
            timeout_ms=timeout_ms,
        )
        window.run()
    except Exception:
        print("SLM control widget crashed:")
        print(traceback.format_exc())
        raise


class SLMControlWidget:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=5555,
        display_pub_port=5556,
        timeout_ms=5000,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.display_pub_port = int(display_pub_port)
        self.timeout_ms = int(timeout_ms)
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM control widget already running.")
            return

        self.Process = mp.Process(
            target=SLMControlWidgetProcess,
            kwargs={
                "host": self.host,
                "command_port": self.command_port,
                "display_pub_port": self.display_pub_port,
                "timeout_ms": self.timeout_ms,
            },
            daemon=False,
        )
        self.Process.start()
        print(f"SLM control widget started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is None:
            return

        if self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)

        self.Process = None


def launch_slm_control_widget(
    host="127.0.0.1",
    command_port=5555,
    display_pub_port=5556,
    timeout_ms=5000,
):
    widget = SLMControlWidget(
        host=host,
        command_port=command_port,
        display_pub_port=display_pub_port,
        timeout_ms=timeout_ms,
    )
    widget.startProcess()
    return widget


if __name__ == "__main__":
    mp.freeze_support()

    parser = argparse.ArgumentParser(description="Open an SLMStack control widget.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--command-port", type=int, default=5555)
    parser.add_argument("--display-pub-port", type=int, default=5556)
    parser.add_argument("--timeout-ms", type=int, default=5000)
    args = parser.parse_args()

    SLMControlWidgetProcess(
        host=args.host,
        command_port=args.command_port,
        display_pub_port=args.display_pub_port,
        timeout_ms=args.timeout_ms,
    )
