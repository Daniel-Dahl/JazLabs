import multiprocessing as mp
import traceback


def _as_int(text):
    text = str(text).strip()
    if text == "":
        return None
    return int(text)


class OpticalSwitchControlWindow:
    def __init__(self, host="127.0.0.1", command_port=50831, timeout_ms=5000, refresh_ms=1000):
        import tkinter as tk
        from tkinter import ttk

        from JazLabs.hardware.OpticalSwitch.OpticalSwitch_Client import OpticalSwitchClient

        self.tk = tk
        self.ttk = ttk
        self.refresh_ms = int(refresh_ms)
        self.status_after_id = None

        self.switch = OpticalSwitchClient(host=host, command_port=command_port, timeout_ms=timeout_ms, client_id="optical_switch_widget")

        self.root = tk.Tk()
        self.root.title("Optical Switch Control")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connected")
        self.properties_var = tk.StringVar(value="")
        self.channel_var = tk.StringVar(value="")
        self.max_ch_var = tk.StringVar(value="")
        self.min_ch_var = tk.StringVar(value="")
        self.driver_idx_var = tk.StringVar(value="1")
        self.driver_on_var = tk.BooleanVar(value=True)
        self.driver_mask_var = tk.StringVar(value="0")

        self._build_layout()
        self.refresh_all()
        self._schedule_status_refresh()

    def _build_layout(self):
        ttk = self.ttk

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")

        status = ttk.LabelFrame(main, text="Status", padding=8)
        status.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.properties_var).grid(row=1, column=0, sticky="w")

        channel = ttk.LabelFrame(main, text="Channel", padding=8)
        channel.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        ttk.Label(channel, text="Current").grid(row=0, column=0, sticky="w")
        ttk.Entry(channel, textvariable=self.channel_var, width=10).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Button(channel, text="Set", command=self.set_channel).grid(row=0, column=2, sticky="ew", padx=3)
        ttk.Button(channel, text="Get", command=self.get_channel).grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Label(channel, text="Min").grid(row=1, column=0, sticky="w")
        ttk.Entry(channel, textvariable=self.min_ch_var, width=10).grid(row=1, column=1, sticky="ew", padx=3)
        ttk.Button(channel, text="Read Min", command=self.read_min).grid(row=1, column=2, columnspan=2, sticky="ew", padx=3)
        ttk.Label(channel, text="Max").grid(row=2, column=0, sticky="w")
        ttk.Entry(channel, textvariable=self.max_ch_var, width=10).grid(row=2, column=1, sticky="ew", padx=3)
        ttk.Button(channel, text="Read Max", command=self.read_max).grid(row=2, column=2, columnspan=2, sticky="ew", padx=3)

        drivers = ttk.LabelFrame(main, text="Drivers", padding=8)
        drivers.grid(row=1, column=1, sticky="nsew", padx=6)
        ttk.Label(drivers, text="Driver Idx").grid(row=0, column=0, sticky="w")
        ttk.Entry(drivers, textvariable=self.driver_idx_var, width=10).grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Checkbutton(drivers, text="ON", variable=self.driver_on_var).grid(row=0, column=2, sticky="w")
        ttk.Button(drivers, text="Set Driver", command=self.set_driver).grid(row=0, column=3, sticky="ew", padx=3)
        ttk.Label(drivers, text="Mask").grid(row=1, column=0, sticky="w")
        ttk.Entry(drivers, textvariable=self.driver_mask_var, width=10).grid(row=1, column=1, sticky="ew", padx=3)
        ttk.Button(drivers, text="Set Mask", command=self.set_mask).grid(row=1, column=2, sticky="ew", padx=3)
        ttk.Button(drivers, text="Get Mask", command=self.get_mask).grid(row=1, column=3, sticky="ew", padx=3)

        controls = ttk.LabelFrame(main, text="Controls", padding=8)
        controls.grid(row=1, column=2, sticky="nsew", padx=(6, 0))
        ttk.Button(controls, text="Refresh", command=self.refresh_all).grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Button(controls, text="IDN", command=self.idn).grid(row=1, column=0, sticky="ew", pady=2)
        ttk.Button(controls, text="Reset", command=self.reset).grid(row=2, column=0, sticky="ew", pady=2)
        ttk.Button(controls, text="Shutdown Server", command=self.shutdown_server).grid(row=3, column=0, sticky="ew", pady=2)
        ttk.Button(controls, text="Close Window", command=self.close).grid(row=4, column=0, sticky="ew", pady=2)

    def set_status(self, message):
        self.status_var.set(str(message))

    def show_error(self, exc):
        self.status_var.set(f"ERROR: {type(exc).__name__}: {exc}")

    def refresh_status(self):
        try:
            props = self.switch.GetProperties()
            self.properties_var.set(f"type={props['switch_type']} host={props['host']} port={props['command_port']}")
        except Exception as exc:
            self.show_error(exc)

    def refresh_all(self):
        self.refresh_status()
        self.get_channel()
        self.read_min()
        self.read_max()
        self.get_mask()

    def _schedule_status_refresh(self):
        self.refresh_status()
        self.status_after_id = self.root.after(self.refresh_ms, self._schedule_status_refresh)

    def get_channel(self):
        try:
            ch = self.switch.GetChannel()
            self.channel_var.set("" if ch is None else str(ch))
            self.set_status(f"Channel: {ch}")
        except Exception as exc:
            self.show_error(exc)

    def set_channel(self):
        try:
            ch = _as_int(self.channel_var.get())
            if ch is None:
                raise ValueError("Channel is required")
            self.switch.SetChannel(ch)
            self.get_channel()
        except Exception as exc:
            self.show_error(exc)

    def read_min(self):
        try:
            ch = self.switch.MinChannel()
            self.min_ch_var.set("" if ch is None else str(ch))
        except Exception as exc:
            self.show_error(exc)

    def read_max(self):
        try:
            ch = self.switch.MaxChannel()
            self.max_ch_var.set("" if ch is None else str(ch))
        except Exception as exc:
            self.show_error(exc)

    def set_driver(self):
        try:
            idx = _as_int(self.driver_idx_var.get())
            if idx is None:
                raise ValueError("Driver index is required")
            self.switch.SetDriver(idx, bool(self.driver_on_var.get()))
            self.set_status(f"Driver {idx} set to {self.driver_on_var.get()}")
        except Exception as exc:
            self.show_error(exc)

    def set_mask(self):
        try:
            mask = _as_int(self.driver_mask_var.get())
            if mask is None:
                raise ValueError("Mask is required")
            self.switch.SetDriversMask(mask)
            self.get_mask()
        except Exception as exc:
            self.show_error(exc)

    def get_mask(self):
        try:
            mask = self.switch.GetDriversMask()
            self.driver_mask_var.set("" if mask is None else str(mask))
        except Exception as exc:
            self.show_error(exc)

    def idn(self):
        try:
            self.set_status(f"IDN: {self.switch.IDN()}")
        except Exception as exc:
            self.show_error(exc)

    def reset(self):
        try:
            self.switch.Reset()
            self.set_status("Switch reset command sent")
        except Exception as exc:
            self.show_error(exc)

    def shutdown_server(self):
        try:
            self.switch.ShutdownServer()
            self.set_status("Shutdown command sent")
        except Exception as exc:
            self.show_error(exc)

    def close(self):
        if self.status_after_id is not None:
            try:
                self.root.after_cancel(self.status_after_id)
            except Exception:
                pass
            self.status_after_id = None
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def launch_optical_switch_widget(host="127.0.0.1", command_port=50831, timeout_ms=5000, refresh_ms=1000):
    try:
        win = OpticalSwitchControlWindow(host=host, command_port=command_port, timeout_ms=timeout_ms, refresh_ms=refresh_ms)
        win.run()
    except Exception:
        traceback.print_exc()


def launch_optical_switch_widget_process(host="127.0.0.1", command_port=50831, timeout_ms=5000, refresh_ms=1000):
    proc = mp.Process(
        target=launch_optical_switch_widget,
        args=(host, command_port, timeout_ms, refresh_ms),
        daemon=False,
    )
    proc.start()
    return proc
