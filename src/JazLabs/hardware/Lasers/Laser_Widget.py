import multiprocessing as mp


class LaserControlWindow:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50931,
        timeout_ms=5000,
        refresh_ms=1000,
        window_name="Laser Control",
    ):
        import tkinter as tk
        from tkinter import messagebox, ttk

        from JazLabs.hardware.Lasers.Laser_Client import LaserClient

        self.tk = tk
        self.ttk = ttk
        self.messagebox = messagebox
        self.refresh_ms = int(refresh_ms)
        self.refresh_after_id = None
        self.closed = False

        self.laser = LaserClient(
            host=host,
            command_port=command_port,
            timeout_ms=timeout_ms,
            client_id="laser_widget",
        )

        self.root = tk.Tk()
        self.root.title(window_name)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.connection_var = tk.StringVar(value="Connected")
        self.output_var = tk.StringVar(value="Output: unknown")
        self.wavelength_readback_var = tk.StringVar(value="-- nm")
        self.power_readback_var = tk.StringVar(value="--")
        self.wavelength_set_var = tk.StringVar()
        self.power_set_var = tk.StringVar()
        self.power_units_var = tk.StringVar(value="dBm")
        self.wavelength_limits_var = tk.StringVar(value="Range: unknown")

        self._build_layout()
        self._load_properties_and_limits()
        self.refresh_status()

    def _build_layout(self):
        ttk = self.ttk

        self.root.columnconfigure(0, weight=1)
        main = ttk.Frame(self.root, padding=12)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)

        status = ttk.LabelFrame(main, text="Laser status", padding=8)
        status.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.connection_var).grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        ttk.Label(status, textvariable=self.output_var).grid(
            row=1, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Button(status, text="Refresh", command=self.refresh_status).grid(
            row=1, column=1, sticky="e", padx=(8, 0)
        )

        wavelength = ttk.LabelFrame(main, text="Wavelength", padding=8)
        wavelength.grid(row=1, column=0, sticky="ew", pady=4)
        wavelength.columnconfigure(1, weight=1)
        ttk.Label(wavelength, text="Current").grid(row=0, column=0, sticky="w")
        ttk.Label(wavelength, textvariable=self.wavelength_readback_var).grid(
            row=0, column=1, sticky="w", padx=8
        )
        ttk.Label(wavelength, text="Setpoint (nm)").grid(row=1, column=0, sticky="w")
        wavelength_entry = ttk.Entry(
            wavelength, textvariable=self.wavelength_set_var, width=18
        )
        wavelength_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        wavelength_entry.bind("<Return>", lambda event: self.set_wavelength())
        ttk.Button(wavelength, text="Set", command=self.set_wavelength).grid(
            row=1, column=2, sticky="ew"
        )
        ttk.Label(wavelength, textvariable=self.wavelength_limits_var).grid(
            row=2, column=0, columnspan=3, sticky="w"
        )

        power = ttk.LabelFrame(main, text="Power", padding=8)
        power.grid(row=2, column=0, sticky="ew", pady=4)
        power.columnconfigure(1, weight=1)
        ttk.Label(power, text="Current").grid(row=0, column=0, sticky="w")
        ttk.Label(power, textvariable=self.power_readback_var).grid(
            row=0, column=1, columnspan=2, sticky="w", padx=8
        )
        ttk.Label(power, text="Setpoint").grid(row=1, column=0, sticky="w")
        power_entry = ttk.Entry(power, textvariable=self.power_set_var, width=18)
        power_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        power_entry.bind("<Return>", lambda event: self.set_power())
        ttk.Combobox(
            power,
            textvariable=self.power_units_var,
            values=("dBm", "mW"),
            state="readonly",
            width=7,
        ).grid(row=1, column=2, sticky="ew", padx=(0, 8))
        ttk.Button(power, text="Set", command=self.set_power).grid(
            row=1, column=3, sticky="ew"
        )

        output = ttk.LabelFrame(main, text="Emission", padding=8)
        output.grid(row=3, column=0, sticky="ew", pady=4)
        output.columnconfigure(0, weight=1)
        output.columnconfigure(1, weight=1)
        ttk.Button(output, text="Enable output", command=self.enable_output).grid(
            row=0, column=0, sticky="ew", padx=(0, 4)
        )
        ttk.Button(output, text="Disable output", command=self.disable_output).grid(
            row=0, column=1, sticky="ew", padx=(4, 0)
        )

        ttk.Button(main, text="Close", command=self.close).grid(
            row=4, column=0, sticky="ew", pady=(8, 0)
        )

    def _load_properties_and_limits(self):
        try:
            properties = self.laser.get_properties()
            self.root.title(f"Laser Control - {properties['laser_type']}")
            limits = self.laser.get_limits()
            minimum = limits.get("min_wavelength_nm")
            maximum = limits.get("max_wavelength_nm")
            if minimum is not None and maximum is not None:
                self.wavelength_limits_var.set(
                    f"Range: {minimum:g} to {maximum:g} nm"
                )
        except Exception as exc:
            self._show_error(exc)

    def _show_error(self, exc):
        self.connection_var.set(f"ERROR: {type(exc).__name__}: {exc}")
        try:
            self.laser.reset_command_socket()
        except Exception:
            pass

    def refresh_status(self):
        if self.closed:
            return
        try:
            status = self.laser.get_status()
            wavelength_nm = status.get("wavelength_nm")
            power = status.get("power")
            units = status.get("power_units", self.power_units_var.get())
            output_enabled = status.get("output_enabled")

            self.connection_var.set("Connected")
            self.wavelength_readback_var.set(
                "-- nm" if wavelength_nm is None else f"{wavelength_nm:.6f} nm"
            )
            self.power_readback_var.set(
                f"-- {units}" if power is None else f"{power:.6f} {units}"
            )
            if units in ("dBm", "mW"):
                self.power_units_var.set(units)
            if output_enabled is None:
                self.output_var.set("Output: unknown")
            elif output_enabled:
                self.output_var.set("Output: ENABLED")
            else:
                self.output_var.set("Output: disabled")

            errors = status.get("errors", {})
            if errors:
                self.connection_var.set(
                    "Connected; some readbacks unavailable: " + ", ".join(errors)
                )
        except Exception as exc:
            self._show_error(exc)
        finally:
            if not self.closed:
                self.refresh_after_id = self.root.after(
                    self.refresh_ms, self.refresh_status
                )

    def set_wavelength(self):
        try:
            wavelength_nm = float(self.wavelength_set_var.get())
            self.laser.set_wavelength_nm(wavelength_nm, wait=False)
            self.connection_var.set(f"Wavelength setpoint sent: {wavelength_nm:g} nm")
            self.refresh_status()
        except Exception as exc:
            self._show_error(exc)

    def set_power(self):
        try:
            power = float(self.power_set_var.get())
            units = self.power_units_var.get()
            if units == "dBm":
                self.laser.set_power_dbm(power)
            else:
                self.laser.set_power_mw(power)
            self.connection_var.set(f"Power setpoint sent: {power:g} {units}")
            self.refresh_status()
        except Exception as exc:
            self._show_error(exc)

    def enable_output(self):
        confirmed = self.messagebox.askyesno(
            "Enable laser output",
            "Confirm that the optical path is safe and enable laser emission?",
            icon="warning",
        )
        if not confirmed:
            return
        try:
            self.laser.laser_on()
            self.refresh_status()
        except Exception as exc:
            self._show_error(exc)

    def disable_output(self):
        try:
            self.laser.laser_off()
            self.refresh_status()
        except Exception as exc:
            self._show_error(exc)

    def run(self):
        self.root.mainloop()

    def close(self):
        if self.closed:
            return
        self.closed = True
        if self.refresh_after_id is not None:
            try:
                self.root.after_cancel(self.refresh_after_id)
            except Exception:
                pass
        self.laser.close()
        self.root.destroy()


def LaserWidgetProcess(**kwargs):
    LaserControlWindow(**kwargs).run()


class LaserWidget:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50931,
        timeout_ms=5000,
        refresh_ms=1000,
        window_name="Laser Control",
    ):
        self.kwargs = {
            "host": host,
            "command_port": int(command_port),
            "timeout_ms": int(timeout_ms),
            "refresh_ms": int(refresh_ms),
            "window_name": window_name,
        }
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Laser widget already running.")
            return
        self.Process = mp.Process(
            target=LaserWidgetProcess, kwargs=self.kwargs, daemon=False
        )
        self.Process.start()
        print(f"Laser widget started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is not None and self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)
        self.Process = None


if __name__ == "__main__":
    mp.freeze_support()
    LaserWidgetProcess()
