import multiprocessing as mp
import traceback


def _as_float(text):
    text = str(text).strip()
    if text == "":
        return None
    return float(text)


class MotorisedStageControlWindow:
    def __init__(self, host="127.0.0.1", command_port=50931, timeout_ms=5000, refresh_ms=1000):
        import tkinter as tk
        from tkinter import ttk

        from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import (
            MotorisedStageClient,
        )

        self.tk = tk
        self.ttk = ttk
        self.refresh_ms = int(refresh_ms)
        self.status_after_id = None

        self.stage = MotorisedStageClient(host=host, command_port=command_port, timeout_ms=timeout_ms, client_id="motorised_stage_widget")

        self.root = tk.Tk()
        self.root.title("Motorised Stage Control")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connected")
        self.properties_var = tk.StringVar(value="")
        self.axis_var = tk.StringVar(value="X")
        self.units_var = tk.StringVar(value="Steps")
        self.value_var = tk.StringVar(value="0")
        self.jog_size_var = tk.StringVar(value="1")
        self.positions_var = tk.StringVar(value="")
        self.stage_type = None
        self.supports_mm = False
        self.native_units_label = "Steps"

        self._build_layout()
        self._configure_by_stage_type()
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
        ttk.Label(status, textvariable=self.positions_var).grid(row=2, column=0, sticky="w")

        move = ttk.LabelFrame(main, text="Move", padding=8)
        move.grid(row=1, column=0, sticky="nsew", padx=(0, 8))

        ttk.Label(move, text="Axis").grid(row=0, column=0, sticky="w")
        self.axis_combo = ttk.Combobox(
            move,
            textvariable=self.axis_var,
            values=("X", "Y", "Z", "ROLL", "YAW", "PITCH"),
            width=10,
            state="readonly",
        )
        self.axis_combo.grid(row=0, column=1, sticky="ew", padx=3)
        ttk.Label(move, text="Units").grid(row=1, column=0, sticky="w")
        self.units_combo = ttk.Combobox(
            move,
            textvariable=self.units_var,
            values=("Steps",),
            width=10,
            state="readonly",
        )
        self.units_combo.grid(row=1, column=1, sticky="ew", padx=3)
        self.units_combo.bind("<<ComboboxSelected>>", lambda _event: self.get_positions())

        ttk.Label(move, text="Target / delta").grid(row=2, column=0, sticky="w")
        ttk.Entry(move, textvariable=self.value_var, width=12).grid(row=2, column=1, sticky="ew", padx=3)
        ttk.Button(move, text="Move Abs", command=self.move_abs).grid(row=3, column=0, sticky="ew", padx=3, pady=2)
        ttk.Button(move, text="Move Rel", command=self.move_rel).grid(row=3, column=1, sticky="ew", padx=3, pady=2)

        ttk.Separator(move, orient="horizontal").grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=6
        )
        ttk.Label(move, text="Jog size").grid(row=5, column=0, sticky="w")
        ttk.Entry(move, textvariable=self.jog_size_var, width=12).grid(
            row=5, column=1, sticky="ew", padx=3
        )
        ttk.Button(move, text="− Backward", command=self.jog_backward).grid(
            row=6, column=0, sticky="ew", padx=3, pady=2
        )
        ttk.Button(move, text="+ Forward", command=self.jog_forward).grid(
            row=6, column=1, sticky="ew", padx=3, pady=2
        )

        controls = ttk.LabelFrame(main, text="Controls", padding=8)
        controls.grid(row=1, column=1, sticky="nsew", padx=8)

        ttk.Button(controls, text="Get Positions", command=self.get_positions).grid(row=0, column=0, sticky="ew", pady=2)
        self.home_btn = ttk.Button(controls, text="Home All", command=self.home_all)
        self.home_btn.grid(row=1, column=0, sticky="ew", pady=2)
        self.nominal_btn = ttk.Button(controls, text="Set Nominal", command=self.set_nominal)
        self.nominal_btn.grid(row=2, column=0, sticky="ew", pady=2)
        ttk.Button(controls, text="Refresh", command=self.refresh_all).grid(row=3, column=0, sticky="ew", pady=2)

        server = ttk.LabelFrame(main, text="Server", padding=8)
        server.grid(row=1, column=2, sticky="nsew", padx=(8, 0))
        ttk.Button(server, text="Shutdown Server", command=self.shutdown_server).grid(row=0, column=0, sticky="ew", pady=2)
        ttk.Button(server, text="Close Window", command=self.close).grid(row=1, column=0, sticky="ew", pady=2)

    def set_status(self, message):
        self.status_var.set(str(message))

    def show_error(self, exc):
        self.status_var.set(f"ERROR: {type(exc).__name__}: {exc}")

    def refresh_status(self):
        try:
            props = self.stage.GetProperties()
            if props.get("stage_type") != self.stage_type:
                self.stage_type = props.get("stage_type")
                self._configure_by_stage_type()
            self.properties_var.set(f"type={props['stage_type']} host={props['host']} port={props['command_port']}")
        except Exception as exc:
            self.show_error(exc)

    def _configure_by_stage_type(self):
        props = {}
        try:
            props = self.stage.GetProperties()
            stage_type = props.get("stage_type", "Luminos")
        except Exception:
            stage_type = "Luminos"

        self.stage_type = stage_type
        self.supports_mm = bool(props.get("supports_mm", False))
        native_units = props.get("units", "steps")
        if native_units in (
            "controller_counts",
            "controller_microsteps",
            "steps",
            "steps_from_zero",
        ):
            self.native_units_label = "Steps"
        elif native_units == "deg":
            self.native_units_label = "deg"
        else:
            self.native_units_label = str(native_units)
        if self.supports_mm:
            self.units_combo.configure(values=(self.native_units_label, "mm"))
            if self.units_var.get() not in (self.native_units_label, "mm"):
                self.units_var.set(self.native_units_label)
        else:
            self.units_combo.configure(values=(self.native_units_label,))
            self.units_var.set(self.native_units_label)

        if stage_type == "Luminos":
            self.axis_combo.configure(values=("X", "Y", "Z", "ROLL", "YAW", "PITCH"))
            self.axis_var.set("X")
            self.home_btn.state(["!disabled"])
            self.nominal_btn.state(["!disabled"])
        elif stage_type == "NewportM100D":
            self.axis_combo.configure(values=("U", "V"))
            self.axis_var.set("U")
            self.home_btn.state(["disabled"])
            self.nominal_btn.state(["disabled"])
        elif stage_type == "BSC203Serial":
            slots = props.get("slots", [0, 1, 2])
            axes = ("Z", "X", "Y")[:len(slots)]
            self.axis_combo.configure(values=axes)
            self.axis_var.set(axes[0])
            self.home_btn.state(["!disabled"])
            self.nominal_btn.state(["!disabled"])
        elif stage_type == "KDC101Serial":
            self.axis_combo.configure(values=("X",))
            self.axis_var.set("X")
            self.home_btn.state(["!disabled"])
            self.nominal_btn.state(["!disabled"])
        elif stage_type == "KST201Serial":
            axis = props.get("mount_axis") or "X"
            self.axis_combo.configure(values=(axis,))
            self.axis_var.set(axis)
            self.home_btn.state(["!disabled"])
            self.nominal_btn.state(["!disabled"])
        else:
            self.axis_combo.configure(values=("X",))
            self.axis_var.set("X")
            self.home_btn.state(["disabled"])
            self.nominal_btn.state(["disabled"])

    def refresh_all(self):
        self.refresh_status()
        self.get_positions()

    def _schedule_status_refresh(self):
        self.refresh_status()
        self.status_after_id = self.root.after(self.refresh_ms, self._schedule_status_refresh)

    def get_positions(self):
        try:
            step_positions = self.stage.GetPositions()
            if self.supports_mm:
                mm_positions = self.stage.GetPositionsMM()
                self.positions_var.set(
                    f"{self.native_units_label}={step_positions}  mm={mm_positions}"
                )
            else:
                self.positions_var.set(
                    f"{self.native_units_label}={step_positions}"
                )
        except Exception as exc:
            self.show_error(exc)

    def move_abs(self):
        try:
            axis = self.axis_var.get().strip()
            value = _as_float(self.value_var.get())
            if value is None:
                raise ValueError("Value is required")
            if self.units_var.get() == "mm":
                self.stage.MoveAbsMM(axis, value)
            else:
                self.stage.MoveAbs(axis, value)
            self.get_positions()
        except Exception as exc:
            self.show_error(exc)

    def move_rel(self):
        try:
            axis = self.axis_var.get().strip()
            value = _as_float(self.value_var.get())
            if value is None:
                raise ValueError("Value is required")
            if self.units_var.get() == "mm":
                self.stage.MoveRelMM(axis, value)
            else:
                self.stage.MoveRel(axis, value)
            self.get_positions()
        except Exception as exc:
            self.show_error(exc)

    def jog_backward(self):
        self.jog(-1.0)

    def jog_forward(self):
        self.jog(1.0)

    def jog(self, direction):
        try:
            axis = self.axis_var.get().strip()
            jog_size = _as_float(self.jog_size_var.get())
            if jog_size is None:
                raise ValueError("Jog size is required")
            if jog_size < 0:
                raise ValueError("Jog size must be non-negative")

            signed_distance = float(direction) * jog_size
            if self.units_var.get() == "mm":
                self.stage.MoveRelMM(axis, signed_distance)
            else:
                self.stage.MoveRel(axis, signed_distance)
            self.get_positions()
        except Exception as exc:
            self.show_error(exc)

    def home_all(self):
        try:
            self.stage.HomeAll()
            self.get_positions()
        except Exception as exc:
            self.show_error(exc)

    def set_nominal(self):
        try:
            self.stage.SetNominal()
            self.get_positions()
        except Exception as exc:
            self.show_error(exc)

    def shutdown_server(self):
        try:
            self.stage.ShutdownServer()
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


def launch_motorised_stage_widget(host="127.0.0.1", command_port=50931, timeout_ms=5000, refresh_ms=1000):
    try:
        win = MotorisedStageControlWindow(host=host, command_port=command_port, timeout_ms=timeout_ms, refresh_ms=refresh_ms)
        win.run()
    except Exception:
        traceback.print_exc()


def launch_motorised_stage_widget_process(host="127.0.0.1", command_port=50931, timeout_ms=5000, refresh_ms=1000):
    proc = mp.Process(
        target=launch_motorised_stage_widget,
        args=(host, command_port, timeout_ms, refresh_ms),
        daemon=False,
    )
    proc.start()
    return proc
