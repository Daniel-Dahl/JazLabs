import multiprocessing as mp
import traceback


def _as_float(text):
    text = str(text).strip()
    if text == "":
        return None
    return float(text)


def _format_time_ns(time_ns):
    try:
        if int(time_ns) <= 0:
            return "none"
        return f"{int(time_ns) / 1e9:.6f} s"
    except Exception:
        return "unknown"


class DAQControlWindow:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50831,
        voltage_pub_port=50832,
        timeout_ms=5000,
        refresh_ms=500,
    ):
        import tkinter as tk
        from tkinter import ttk

        from JazLabs.hardware.DAQ_Controller.DAQ_stack.DAQ_Client import DAQClient

        self.tk = tk
        self.ttk = ttk
        self.refresh_ms = int(refresh_ms)
        self.status_after_id = None

        self.daq = DAQClient(
            host=host,
            command_port=command_port,
            voltage_pub_port=voltage_pub_port,
            timeout_ms=timeout_ms,
            client_id="daq_widget",
        )

        self.root = tk.Tk()
        self.root.title("DAQ Voltage Control")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connected")
        self.properties_var = tk.StringVar(value="")
        self.voltage_vars = []

        self._build_layout()
        self.refresh_status()
        self._schedule_status_refresh()

    def _build_layout(self):
        tk = self.tk
        ttk = self.ttk

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)

        status = ttk.LabelFrame(main, text="Status", padding=8)
        status.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.properties_var, justify="left").grid(row=1, column=0, sticky="w")

        channels = ttk.LabelFrame(main, text="Channels", padding=8)
        channels.grid(row=1, column=0, sticky="ew", pady=4)
        channels.columnconfigure(1, weight=1)

        for channel in range(self.daq.ChannelCount):
            voltage_var = tk.StringVar(value="0.0")
            self.voltage_vars.append(voltage_var)

            ttk.Label(channels, text=f"Channel {channel}").grid(row=channel, column=0, sticky="w", padx=2, pady=2)
            ttk.Entry(channels, textvariable=voltage_var, width=12).grid(row=channel, column=1, sticky="ew", padx=2, pady=2)
            ttk.Button(
                channels,
                text="Set",
                command=lambda ch=channel: self.set_voltage(ch),
            ).grid(row=channel, column=2, sticky="ew", padx=2, pady=2)

        server = ttk.LabelFrame(main, text="Server", padding=8)
        server.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        for column in range(4):
            server.columnconfigure(column, weight=1)

        ttk.Button(server, text="Refresh", command=self.refresh_status).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(server, text="Zero", command=self.zero).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(server, text="Shutdown Server", command=self.shutdown_server).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(server, text="Close Window", command=self.close).grid(row=0, column=3, sticky="ew", padx=2, pady=2)

    def set_status(self, message):
        self.status_var.set(str(message))

    def show_error(self, exc):
        self.status_var.set(f"ERROR: {type(exc).__name__}: {exc}")
        try:
            self.daq.ResetCommandSocket()
        except Exception:
            pass

    def refresh_status(self):
        try:
            props = self.daq.GetProperties()
            voltages = self.daq.GetVoltages()

            for channel, voltage in enumerate(voltages):
                if channel < len(self.voltage_vars):
                    self.voltage_vars[channel].set(f"{float(voltage):.6f}")

            self.properties_var.set(
                "DAQ: {daq_type} | channels: {channels} | counter: {counter}\n"
                "Limits: {vmin} V to {vmax} V | alive: {alive} | last write: {last}".format(
                    daq_type=props["daq_type"],
                    channels=props["channel_count"],
                    counter=props["voltage_counter"],
                    vmin=props["voltage_min"],
                    vmax=props["voltage_max"],
                    alive=props["server_alive"],
                    last=_format_time_ns(props["last_write_time_ns"]),
                )
            )
        except Exception as exc:
            self.show_error(exc)

    def _schedule_status_refresh(self):
        self.refresh_status()
        self.status_after_id = self.root.after(self.refresh_ms, self._schedule_status_refresh)

    def set_voltage(self, channel):
        try:
            voltage = _as_float(self.voltage_vars[channel].get())
            result = self.daq.SetVoltage(channel, voltage)
            self.set_status(f"Channel {channel} set to {result} V")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def zero(self):
        try:
            result = self.daq.Zero()
            self.set_status(f"Zeroed: {result}")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def shutdown_server(self):
        try:
            self.daq.ShutdownServer()
            self.set_status("Shutdown command sent")
        except Exception as exc:
            self.show_error(exc)

    def close(self):
        try:
            if self.status_after_id is not None:
                self.root.after_cancel(self.status_after_id)
        except Exception:
            pass

        try:
            self.daq.close()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def DAQWidgetProcess(
    host="127.0.0.1",
    command_port=50831,
    voltage_pub_port=50832,
    timeout_ms=5000,
    refresh_ms=500,
):
    try:
        window = DAQControlWindow(
            host=host,
            command_port=command_port,
            voltage_pub_port=voltage_pub_port,
            timeout_ms=timeout_ms,
            refresh_ms=refresh_ms,
        )
        window.run()
    except Exception:
        print("DAQ widget crashed:")
        print(traceback.format_exc())
        raise


class DAQWidget:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50831,
        voltage_pub_port=50832,
        timeout_ms=5000,
        refresh_ms=500,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.voltage_pub_port = int(voltage_pub_port)
        self.timeout_ms = int(timeout_ms)
        self.refresh_ms = int(refresh_ms)
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("DAQ widget already running.")
            return

        self.Process = mp.Process(
            target=DAQWidgetProcess,
            kwargs={
                "host": self.host,
                "command_port": self.command_port,
                "voltage_pub_port": self.voltage_pub_port,
                "timeout_ms": self.timeout_ms,
                "refresh_ms": self.refresh_ms,
            },
            daemon=False,
        )
        self.Process.start()
        print(f"DAQ widget started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is None:
            return

        if self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)

        self.Process = None


def launch_daq_widget(**kwargs):
    widget = DAQWidget(**kwargs)
    widget.startProcess()
    return widget


if __name__ == "__main__":
    mp.freeze_support()
    DAQWidgetProcess()

