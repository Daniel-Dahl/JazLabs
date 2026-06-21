import multiprocessing as mp
import traceback


def _as_float(text):
    text = str(text).strip()
    if text == "":
        return 0.0
    return float(text)


def _as_int(text):
    text = str(text).strip()
    if text == "":
        return 0
    return int(text)


def _process_context():
    try:
        return mp.get_context("fork")
    except ValueError:
        return mp


class SLMPhaseMaskWindow:
    def __init__(self, phase_mask=None, pol="V", imask=0, channel="Red", slm=None):
        import tkinter as tk
        from tkinter import ttk

        if phase_mask is None:
            phase_mask = slm
        if phase_mask is None:
            raise TypeError("SLMPhaseMaskWindow requires a PhaseMaskObject")

        self.tk = tk
        self.ttk = ttk
        self.slm = phase_mask
        self._refreshing = False
        self._pending_update_id = None
        self._updating_mask = False
        self._require_phase_mask_object()

        channels = [
            ch
            for ch in getattr(self.slm, "ActiveRGBChannels", ["Red", "Green", "Blue"])
            if ch in self.slm.polProps
        ]
        if not channels:
            raise ValueError("PhaseMaskObject has no active channels in polProps")

        self.root = tk.Tk()
        self.root.title("SLM Phase Mask Control")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connected")
        self.channel_var = tk.StringVar(value=channel if channel in channels else channels[0])
        self.pol_var = tk.StringVar(value=pol)
        self.plane_var = tk.StringVar(value=str(int(imask)))
        self.mode_h_var = tk.StringVar(value="0")
        self.mode_v_var = tk.StringVar(value="0")
        self.pol_enabled_var = tk.BooleanVar()
        self.mask_enabled_var = tk.BooleanVar()
        self.x_center_var = tk.StringVar()
        self.y_center_var = tk.StringVar()
        self.x_tilt_var = tk.StringVar()
        self.y_tilt_var = tk.StringVar()
        self.piston_var = tk.StringVar()
        self.defocus_var = tk.StringVar()
        self.refresh_ms_var = tk.StringVar()
        self.sweep_step_var = tk.StringVar(value="30")
        self.mask_file_var = tk.StringVar(value=getattr(self.slm, "MasksFilename", ""))

        self._build_layout(channels)
        self._bind_property_traces()

        self.refresh_from_slm()

    def _require_phase_mask_object(self):
        required_attrs = ("AllMaskProperties", "GLobProps", "polProps", "setmask")
        missing = [attr for attr in required_attrs if not hasattr(self.slm, attr)]
        if missing:
            raise TypeError(
                "SLMPhaseMaskWindow expects a PhaseMaskObject-like instance; "
                f"missing: {', '.join(missing)}"
            )

    def current_channel(self):
        return self.channel_var.get()

    def current_pol(self):
        return self.pol_var.get()

    def current_plane(self):
        return _as_int(self.plane_var.get())

    def _valid_channels(self):
        return [
            channel
            for channel in getattr(self.slm, "ActiveRGBChannels", [])
            if channel in self.slm.polProps
        ]

    def _current_mask_props(self):
        return self.slm.AllMaskProperties[
            self.current_channel()
        ][
            self.current_pol()
        ][
            self.current_plane()
        ]

    def _refresh_time_seconds(self, ch):
        glob_props = self.slm.GLobProps[ch]
        if hasattr(glob_props, "RefreshTime"):
            return float(glob_props.RefreshTime)

        refresh_rate = getattr(glob_props, "RefreshRate", None)
        if refresh_rate:
            return 1.0 / float(refresh_rate)

        slm_object = getattr(self.slm, "SLMObject", None)
        refresh_rate = getattr(slm_object, "RefreshRate", 0.0)
        return 0.0 if not refresh_rate else 1.0 / float(refresh_rate)

    def _set_refresh_time_seconds(self, ch, refresh_time):
        if hasattr(self.slm, "SetRefreshTime"):
            self.slm.SetRefreshTime(refresh_time, channel=ch)
            return

        self.slm.GLobProps[ch].RefreshTime = refresh_time

    def set_refresh_time_from_gui(self):
        ch = self.current_channel()
        self._set_refresh_time_seconds(ch, _as_float(self.refresh_ms_var.get()) * 1e-3)
        self.set_status(f"Set {ch} refresh time to {self.refresh_ms_var.get()} ms")

    def _set_mode_limits(self, ch):
        self.mode_h_spin.configure(to=max(0, self.slm.polProps[ch]["H"].modeCount - 1))
        self.mode_v_spin.configure(to=max(0, self.slm.polProps[ch]["V"].modeCount - 1))

    def _set_plane_limits(self, ch, pol):
        self.plane_spin.configure(to=max(0, self.slm.polProps[ch][pol].MaskCount - 1))

    def _apply_widget_values_to_current_mask(self, update_refresh=False):
        ch = self.current_channel()
        pol = self.current_pol()
        props = self._current_mask_props()

        props.center[1] = _as_int(self.x_center_var.get())
        props.center[0] = _as_int(self.y_center_var.get())
        props.zernike.zern_coefs[1] = _as_float(self.x_tilt_var.get())
        props.zernike.zern_coefs[2] = _as_float(self.y_tilt_var.get())
        props.zernike.zern_coefs[0] = _as_float(self.piston_var.get())
        props.zernike.zern_coefs[4] = _as_float(self.defocus_var.get())
        props.maskEnabled = bool(self.mask_enabled_var.get())
        self.slm.polProps[ch][pol].polEnabled = bool(self.pol_enabled_var.get())
        if update_refresh:
            self._set_refresh_time_seconds(ch, _as_float(self.refresh_ms_var.get()) * 1e-3)

    def _bind_property_traces(self):
        for var in (
            self.x_center_var,
            self.y_center_var,
            self.x_tilt_var,
            self.y_tilt_var,
            self.piston_var,
            self.defocus_var,
        ):
            var.trace_add("write", self._schedule_mask_property_update_from_trace)

    def _schedule_mask_property_update_from_trace(self, *_):
        self.schedule_mask_property_update()

    def schedule_mask_property_update(self, delay_ms=80):
        if self._refreshing:
            return

        if self._pending_update_id is not None:
            try:
                self.root.after_cancel(self._pending_update_id)
            except Exception:
                pass

        self._pending_update_id = self.root.after(delay_ms, self.apply_mask_property_update)

    def apply_mask_property_update(self):
        self._pending_update_id = None
        if self._refreshing or self._updating_mask:
            return

        self._updating_mask = True
        try:
            self._apply_widget_values_to_current_mask(update_refresh=False)
            self.update_mask()
        finally:
            self._updating_mask = False

    def nudge_mask_center(self, dx=0, dy=0):
        if self._refreshing:
            return

        self.x_center_var.set(str(_as_int(self.x_center_var.get()) + int(dx)))
        self.y_center_var.set(str(_as_int(self.y_center_var.get()) + int(dy)))
        self.schedule_mask_property_update(delay_ms=20)

    def _on_center_arrow_key(self, event):
        if event.keysym == "Left":
            self.nudge_mask_center(dx=-1)
        elif event.keysym == "Right":
            self.nudge_mask_center(dx=1)
        elif event.keysym == "Up":
            self.nudge_mask_center(dy=-1)
        elif event.keysym == "Down":
            self.nudge_mask_center(dy=1)
        return "break"

    def _call(self, func):
        def wrapped():
            try:
                func()
            except Exception as exc:
                self.show_error(exc)

        return wrapped

    def _build_layout(self, channels):
        ttk = self.ttk

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        for col in range(4):
            main.columnconfigure(col, weight=1)

        status = ttk.LabelFrame(main, text="Status", padding=8)
        status.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        select = ttk.LabelFrame(main, text="Selection", padding=8)
        select.grid(row=1, column=0, columnspan=4, sticky="ew", pady=4)
        for col in range(8):
            select.columnconfigure(col, weight=1)

        ttk.Label(select, text="Channel").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.channel_combo = ttk.Combobox(select, textvariable=self.channel_var, values=channels, state="readonly", width=10)
        self.channel_combo.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.channel_combo.bind("<<ComboboxSelected>>", self._call_event(self.on_channel_or_pol_change))

        ttk.Label(select, text="Pol").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        self.pol_combo = ttk.Combobox(select, textvariable=self.pol_var, values=("H", "V"), state="readonly", width=8)
        self.pol_combo.grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        self.pol_combo.bind("<<ComboboxSelected>>", self._call_event(self.on_channel_or_pol_change))

        ttk.Label(select, text="Plane").grid(row=0, column=4, sticky="w", padx=2, pady=2)
        self.plane_spin = ttk.Spinbox(select, textvariable=self.plane_var, from_=0, to=9999, width=8, command=self._call(self.on_plane_change))
        self.plane_spin.grid(row=0, column=5, sticky="ew", padx=2, pady=2)
        self.plane_spin.bind("<Return>", self._call_event(self.on_plane_change))

        self.pol_check = ttk.Checkbutton(select, text="Enable Pol", variable=self.pol_enabled_var, command=self._call(self.on_pol_enable_change))
        self.pol_check.grid(row=0, column=6, sticky="w", padx=2, pady=2)
        self.mask_check = ttk.Checkbutton(select, text="Enable Mask", variable=self.mask_enabled_var, command=self._call(self.on_mask_enable_change))
        self.mask_check.grid(row=0, column=7, sticky="w", padx=2, pady=2)

        modes = ttk.LabelFrame(main, text="Modes", padding=8)
        modes.grid(row=2, column=0, columnspan=4, sticky="ew", pady=4)
        for col in range(4):
            modes.columnconfigure(col, weight=1)
        ttk.Label(modes, text="Mode H").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        self.mode_h_spin = ttk.Spinbox(modes, textvariable=self.mode_h_var, from_=0, to=9999, width=10, command=self._call(self.update_mask))
        self.mode_h_spin.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.mode_h_spin.bind("<Return>", self._call_event(self.update_mask))
        ttk.Label(modes, text="Mode V").grid(row=0, column=2, sticky="w", padx=2, pady=2)
        self.mode_v_spin = ttk.Spinbox(modes, textvariable=self.mode_v_var, from_=0, to=9999, width=10, command=self._call(self.update_mask))
        self.mode_v_spin.grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        self.mode_v_spin.bind("<Return>", self._call_event(self.update_mask))

        props = ttk.LabelFrame(main, text="Mask Properties", padding=8)
        props.grid(row=3, column=0, columnspan=4, sticky="ew", pady=4)
        for col in range(5):
            props.columnconfigure(col, weight=1)

        self.x_center_spin, self.y_center_spin = self._add_spinbox_row(
            props, 0, "X Center", self.x_center_var, "Y Center", self.y_center_var,
            from_=-100000, to=100000, increment=1,
        )
        self.x_tilt_spin, self.y_tilt_spin = self._add_spinbox_row(
            props, 1, "X Tilt", self.x_tilt_var, "Y Tilt", self.y_tilt_var,
            from_=-1e6, to=1e6, increment=0.001,
        )
        self.piston_spin, self.defocus_spin = self._add_spinbox_row(
            props, 2, "Piston", self.piston_var, "Defocus", self.defocus_var,
            from_=-1e6, to=1e6, increment=2 * 3.141592653589793 / 256,
        )
        self._add_entry_row(props, 3, "Refresh ms", self.refresh_ms_var, "Sweep Step", self.sweep_step_var)
        ttk.Button(props, text="Set Refresh", command=self._call(self.set_refresh_time_from_gui)).grid(row=3, column=4, sticky="ew", padx=2, pady=2)

        for spin in (self.x_center_spin, self.y_center_spin):
            spin.bind("<Left>", self._on_center_arrow_key)
            spin.bind("<Right>", self._on_center_arrow_key)
            spin.bind("<Up>", self._on_center_arrow_key)
            spin.bind("<Down>", self._on_center_arrow_key)

        ttk.Button(props, text="Apply Current", command=self._call(self.update_current_slm)).grid(row=4, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(props, text="Apply All Channels", command=self._call(self.update_all_slm)).grid(row=4, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(props, text="Refresh From Object", command=self._call(self.refresh_from_slm)).grid(row=4, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(props, text="Clear SLM", command=self._call(self.clear_slm)).grid(row=4, column=3, sticky="ew", padx=2, pady=2)

        operations = ttk.LabelFrame(main, text="Operations", padding=8)
        operations.grid(row=4, column=0, columnspan=4, sticky="ew", pady=4)
        for col in range(4):
            operations.columnconfigure(col, weight=1)
        ttk.Button(operations, text="Zero Zernikes", command=self._call(self.zero_zernikes)).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(operations, text="Equal Spacing", command=self._call(self.equal_spacing)).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(operations, text="Reverse Plane Order", command=self._call(self.reverse_order)).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(operations, text="Start Sweep", command=self._call(self.start_sweep)).grid(row=0, column=3, sticky="ew", padx=2, pady=2)

        files = ttk.LabelFrame(main, text="Masks", padding=8)
        files.grid(row=5, column=0, columnspan=4, sticky="ew", pady=4)
        files.columnconfigure(1, weight=1)
        ttk.Label(files, text="Mask File").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(files, textvariable=self.mask_file_var).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(files, text="Load Mask File", command=self._call(self.load_mask_files)).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(files, text="Load PI Flip", command=self._call(self.load_pi_flip_masks)).grid(row=0, column=3, sticky="ew", padx=2, pady=2)
        ttk.Button(files, text="Save Mask Props", command=self._call(self.save_mask_props)).grid(row=0, column=4, sticky="ew", padx=2, pady=2)

        server = ttk.LabelFrame(main, text="Window", padding=8)
        server.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        server.columnconfigure(0, weight=1)
        ttk.Button(server, text="Close Window", command=self.close).grid(row=0, column=0, sticky="ew", padx=2, pady=2)

    def _add_entry_row(self, parent, row, label_a, var_a, label_b, var_b):
        ttk = self.ttk
        ttk.Label(parent, text=label_a).grid(row=row, column=0, sticky="w", padx=2, pady=2)
        entry_a = ttk.Entry(parent, textvariable=var_a, width=12)
        entry_a.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        entry_a.bind("<Return>", self._call_event(self.on_value_change))
        ttk.Label(parent, text=label_b).grid(row=row, column=2, sticky="w", padx=2, pady=2)
        entry_b = ttk.Entry(parent, textvariable=var_b, width=12)
        entry_b.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        entry_b.bind("<Return>", self._call_event(self.on_value_change))

    def _add_spinbox_row(self, parent, row, label_a, var_a, label_b, var_b, from_, to, increment):
        ttk = self.ttk
        ttk.Label(parent, text=label_a).grid(row=row, column=0, sticky="w", padx=2, pady=2)
        spin_a = ttk.Spinbox(
            parent,
            textvariable=var_a,
            from_=from_,
            to=to,
            increment=increment,
            width=12,
            command=self.schedule_mask_property_update,
        )
        spin_a.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        spin_a.bind("<Return>", self._call_event(self.apply_mask_property_update))
        spin_a.bind("<FocusOut>", self._call_event(self.apply_mask_property_update))

        ttk.Label(parent, text=label_b).grid(row=row, column=2, sticky="w", padx=2, pady=2)
        spin_b = ttk.Spinbox(
            parent,
            textvariable=var_b,
            from_=from_,
            to=to,
            increment=increment,
            width=12,
            command=self.schedule_mask_property_update,
        )
        spin_b.grid(row=row, column=3, sticky="ew", padx=2, pady=2)
        spin_b.bind("<Return>", self._call_event(self.apply_mask_property_update))
        spin_b.bind("<FocusOut>", self._call_event(self.apply_mask_property_update))

        return spin_a, spin_b

    def _call_event(self, func):
        def wrapped(_event=None):
            try:
                func()
            except Exception as exc:
                self.show_error(exc)

        return wrapped

    def set_status(self, message):
        self.status_var.set(str(message))

    def show_error(self, exc):
        self.status_var.set(f"ERROR: {type(exc).__name__}: {exc}")

    def refresh_from_slm(self):
        self._require_phase_mask_object()
        ch = self.current_channel()
        pol = self.current_pol()
        imask = self.current_plane()

        self._refreshing = True
        self._set_mode_limits(ch)
        self._set_plane_limits(ch, pol)

        max_plane = int(float(self.plane_spin.cget("to")))
        if imask > max_plane:
            self.plane_var.set("0")
            imask = 0

        props = self.slm.AllMaskProperties[ch][pol][imask]

        self.x_center_var.set(str(int(props.center[1])))
        self.y_center_var.set(str(int(props.center[0])))
        self.piston_var.set(str(float(props.zernike.zern_coefs[0])))
        self.x_tilt_var.set(str(float(props.zernike.zern_coefs[1])))
        self.y_tilt_var.set(str(float(props.zernike.zern_coefs[2])))
        self.defocus_var.set(str(float(props.zernike.zern_coefs[4])))

        self.pol_enabled_var.set(bool(self.slm.polProps[ch][pol].polEnabled))
        self.mask_enabled_var.set(bool(props.maskEnabled))
        self.refresh_ms_var.set(str(float(self._refresh_time_seconds(ch) * 1e3)))

        self._refreshing = False
        self.set_status(f"Loaded {ch} {pol} plane {imask}")

    def on_channel_or_pol_change(self):
        self.refresh_from_slm()

    def on_plane_change(self):
        ch = self.current_channel()
        pol = self.current_pol()

        if self.current_plane() > self.slm.polProps[ch][pol].MaskCount - 1:
            self.plane_var.set("0")
            return

        self.refresh_from_slm()

    def on_value_change(self):
        if self._refreshing:
            return
        self.apply_mask_property_update()

    def on_pol_enable_change(self):
        ch = self.current_channel()
        pol = self.current_pol()
        self.slm.polProps[ch][pol].polEnabled = bool(self.pol_enabled_var.get())
        self.update_mask()

    def on_mask_enable_change(self):
        ch = self.current_channel()
        pol = self.current_pol()
        imask = self.current_plane()
        self.slm.AllMaskProperties[ch][pol][imask].maskEnabled = bool(self.mask_enabled_var.get())
        self.update_mask()

    def update_mask(self):
        if self._refreshing:
            return

        ch = self.current_channel()

        max_h = self.slm.polProps[ch]["H"].modeCount - 1
        max_v = self.slm.polProps[ch]["V"].modeCount - 1

        mode_h = _as_int(self.mode_h_var.get())
        mode_v = _as_int(self.mode_v_var.get())

        if mode_h > max_h:
            mode_h = 0
            self.mode_h_var.set("0")

        if mode_v > max_v:
            mode_v = 0
            self.mode_v_var.set("0")

        self.slm.setmask(
            ch,
            imode_H=mode_h,
            imode_V=mode_v,
        )
        self.set_status(f"Updated {ch}: H mode {mode_h}, V mode {mode_v}")

    def update_current_slm(self):
        self._apply_widget_values_to_current_mask(update_refresh=False)
        self.update_mask()

    def update_all_slm(self):
        self._apply_widget_values_to_current_mask(update_refresh=False)
        for ch in self._valid_channels():
            self.slm.setmask(
                ch,
                imode_H=min(_as_int(self.mode_h_var.get()), self.slm.polProps[ch]["H"].modeCount - 1),
                imode_V=min(_as_int(self.mode_v_var.get()), self.slm.polProps[ch]["V"].modeCount - 1),
            )
        self.set_status("Updated all active SLM channels")

    def clear_slm(self):
        for ch in self._valid_channels():
            self.slm.Clear_Display(ch)
        self.set_status("Cleared SLM")

    def zero_zernikes(self):
        self.slm.ResetAllZernikesToZero(self.current_channel())
        self.refresh_from_slm()
        self.update_mask()

    def equal_spacing(self):
        self.slm.setCentersToEqualSpacing(self.current_channel())
        self.refresh_from_slm()

    def reverse_order(self):
        self.slm.mplc_reverse_order_mask_x_centers(
            channel=self.current_channel(),
            pol=self.current_pol(),
        )
        self.refresh_from_slm()

    def start_sweep(self):
        self.slm.CourseSweepAcrossSLM(
            self.current_channel(),
            _as_int(self.sweep_step_var.get()),
        )
        self.set_status("Sweep complete")

    def save_mask_props(self):
        self.slm.saveMaskProperties(channel=self.current_channel())
        self.set_status("Saved mask properties")

    def load_pi_flip_masks(self):
        self.slm.LoadPiFlipMasks(channel=self.current_channel())
        self.mask_file_var.set(getattr(self.slm, "MasksFilename", ""))
        self.refresh_from_slm()

    def load_mask_files(self):
        self.slm.LoadMasksFromFile(
            Filename=self.mask_file_var.get(),
            channel=self.current_channel(),
        )
        self.refresh_from_slm()

    def close(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def SLMWidgetProcess(phase_mask, pol="V", imask=0, channel="Red"):
    try:
        window = SLMPhaseMaskWindow(
            phase_mask=phase_mask,
            pol=pol,
            imask=imask,
            channel=channel,
        )
        window.run()
    except Exception:
        print("SLM widget crashed:")
        print(traceback.format_exc())
        raise


class SLMWidget:
    def __init__(self, phase_mask=None, pol="V", imask=0, channel="Red", slm=None):
        if phase_mask is None:
            phase_mask = slm
        if phase_mask is None:
            raise TypeError("SLMWidget requires a PhaseMaskObject")

        self.phase_mask = phase_mask
        self.pol = pol
        self.imask = int(imask)
        self.channel = channel
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("SLM widget already running.")
            return

        ctx = _process_context()
        self.Process = ctx.Process(
            target=SLMWidgetProcess,
            kwargs={
                "phase_mask": self.phase_mask,
                "pol": self.pol,
                "imask": self.imask,
                "channel": self.channel,
            },
            daemon=False,
        )

        self.Process.start()
        print(f"SLM widget started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is None:
            return

        if self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)

        self.Process = None


def launch_slm_phase_mask_widget(phase_mask=None, pol="V", imask=0, channel="Red", slm=None):
    widget = SLMWidget(
        phase_mask=phase_mask,
        slm=slm,
        pol=pol,
        imask=imask,
        channel=channel,
    )
    widget.startProcess()
    return widget


launch_slm_widget = launch_slm_phase_mask_widget


def show_slm_phase_mask_window(phase_mask=None, pol="V", imask=0, channel="Red", slm=None):
    window = SLMPhaseMaskWindow(
        phase_mask=phase_mask,
        slm=slm,
        pol=pol,
        imask=imask,
        channel=channel,
    )
    window.run()
    return window


if __name__ == "__main__":
    mp.freeze_support()
    print("Create a PhaseMaskObject and call launch_slm_phase_mask_widget(phase_mask).")


# import matplotlib.pyplot as plt
# import ipywidgets as widgets
# from IPython.display import display
# import cv2
# import numpy as np
# import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass


# def create_slm_widget(slm:PhaseMaskClass.PhaseMaskObject, pol="V", imask=0, channel="Red"):
#     # Create widgets
#     #####################################
#     # Drop down  boxes
#     ####################################
#     widget_channel = widgets.Dropdown(
#         options=[('Red SLM', "Red"), ('Green SLM', "Green"),('Blue SLM', "Blue")],
#         value=channel, description='Channel',
#         layout=widgets.Layout(width='200px')
#     )
#     widget_pol = widgets.Dropdown(
#         options=[('H', "H"), ('V', "V")],
#         value=pol, description='pol',
#         layout=widgets.Layout(width='140px')
#     )
#     #####################################
#     # Check boxes
#     ####################################
#     widget_PolEnableChecBox = widgets.Checkbox(
#     value=True,
#     description='Enable Pol',
#     disabled=False,indent=False,
#     layout=widgets.Layout(width='150px')
    
    
# )
#     widget_MaskEnableChecBox = widgets.Checkbox(
#     value=True,
#     description='Enable Mask',
#     disabled=False,indent=False,
#     layout=widgets.Layout(width='150px'))

#     #####################################
#     # Value boxes
#     ####################################
#     widget_Plane = widgets.IntText(value=0, 
#         description='Plane', 
#         layout=widgets.Layout(width='140px'))
#     widget_Mode_H = widgets.IntText(value=0, 
#         description='Mode_H', 
#         layout=widgets.Layout(width='140px'))
#     widget_Mode_V = widgets.IntText(value=0, 
#         description='Mode_V', 
#         layout=widgets.Layout(width='140px'))
    
#     widget_XCenter = widgets.IntText(
#         value=slm.AllMaskProperties[channel][pol][imask].center[1],
#         description='X Center', layout=widgets.Layout(width='160px')
#     )
#     widget_YCenter = widgets.IntText(
#         value=slm.AllMaskProperties[channel][pol][imask].center[0],
#         description='Y Center', layout=widgets.Layout(width='160px')
#     )
#     widget_XTilt = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[1],
#         step=0.001,
#         description='X Tilt', layout=widgets.Layout(width='160px')
#     )
#     widget_YTilt = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[2],
#         step=0.001,
#         description='Y Tilt', layout=widgets.Layout(width='160px')
#     )
#     widget_Piston = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[0],
#         step=2*np.pi/256,
#         description='Piston', layout=widgets.Layout(width='160px')
#     )
#     widget_Defocus = widgets.FloatText(
#         value=slm.AllMaskProperties[channel][pol][imask].zernike.zern_coefs[4],
#         step=1,
#         description='Defocus', layout=widgets.Layout(width='160px')
#     )
#     widget_RefreshTime = widgets.FloatText(
#         value=slm.GLobProps[channel].RefreshTime*1e3,
#         description='Refresh Rate (ms)', layout=widgets.Layout(width='180px')
#     )
    
#     widget_SweepStep = widgets.IntText(
#         value=30,
#         description='Sweep Step', layout=widgets.Layout(width='160px')
#     )
#     #######################################
#     # text box
#     ####################################
#     widget_MaskFilename = widgets.Text(
#         value=slm.MasksFilename,
#         description="Mask File Name",
#         layout=widgets.Layout(width='250px')
#     )


#     #####################################
#     # Buttons
#     ####################################
#     update_button_currentSLM = widgets.Button(description='Update Current SLM', layout=widgets.Layout(width='150px'))
#     update_button_AllSLM = widgets.Button(description='Update All SLM', layout=widgets.Layout(width='150px'))
#     update_button_ClearSLM = widgets.Button(description='Clear SLM', layout=widgets.Layout(width='150px'))
#     update_button_SetZernikeToZero = widgets.Button(description='Set All Zernike To Zero', layout=widgets.Layout(width='170px'))
#     update_button_SetPlanesToEqualSpacing = widgets.Button(description='Set PlaneTo Equal Spacing', layout=widgets.Layout(width='170px'))
#     update_button_ReversePlaneOrder = widgets.Button(description='Reverse Plane Order', layout=widgets.Layout(width='170px'))
#     update_button_ViewDisplay = widgets.Button(description='View SLM Image', layout=widgets.Layout(width='170px'))
#     Init_button_PiSweep = widgets.Button(description='Start Sweep', layout=widgets.Layout(width='170px'))
    
#     Save_MaskProp_button = widgets.Button(description='Save Mask Props', layout=widgets.Layout(width='170px'))
#     LoadPiFlipMasks_button =  widgets.Button(description='Load PI flip masks', layout=widgets.Layout(width='170px'))
#     LoadMaskFile_button =  widgets.Button(description='Load mask files', layout=widgets.Layout(width='170px'))
   

#     # Define event handlers (using closures to capture widget variables)
#     def on_value_change(change):
#         # Determine which widget changed and update accordingly.
        
#         desc = change['owner'].description
#         if desc == 'Mode_H':
#             if widget_Mode_H.value > slm.polProps[widget_channel.value]['H'].modeCount - 1:
#                 widget_Mode_H.value = 0
#             if widget_Mode_H.value < 0:
#                 widget_Mode_H.value = slm.polProps[widget_channel.value]['H'].modeCount - 1
#         elif desc == 'Mode_V':
#             if widget_Mode_V.value > slm.polProps[widget_channel.value]['V'].modeCount - 1:
#                 widget_Mode_V.value = 0
#             if widget_Mode_V.value < 0:
#                 widget_Mode_V.value = slm.polProps[widget_channel.value]['V'].modeCount - 1
#             # slm.setmask(widget_channel.value, widget_Mode.value)
#         elif desc == 'X Center':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].center[1] = change['new']
#         elif desc == 'Y Center':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].center[0] = change['new']
#         elif desc == 'X Tilt':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[1] = change['new']
#         elif desc == 'Y Tilt':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[2] = change['new']
#         elif desc == 'Piston':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[0] = change['new']
#         elif desc == 'Defocus':
#             slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].zernike.zern_coefs[4] = change['new']
#         elif desc == 'Refresh Rate (ms)':
#            slm.GLobProps[widget_channel.value].RefreshTime = change['new']*1e-3
        
#         slm.setmask(widget_channel.value,imode_H=widget_Mode_H.value,imode_V=widget_Mode_V.value)

#     def on_button_click(event, update_all=False):
#         if update_all:
#             for ch in slm.ActiveRGBChannels:
#                 for ipol in ["H","V"]:

#                     update_slm_properties(ch, ipol, widget_Plane.value)
#         else:
#             update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_button_click_clearSLM(event):
#         for ch in slm.ActiveRGBChannels:
#             slm.LCOS_Clean(ch)

#     def on_button_click_SetAllZernikeToZero(event):
#         slm.ResetAllZernikesToZero(widget_channel.value)
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)
    
#     def on_button_click_SetPlanesToEqualSpacing(event):
#         slm.setCentersToEqualSpacing(widget_channel.value)
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_button_click_ReversePlaneOrder(event):
#         # slm.setCentersToEqualSpacing(widget_channel.value)
#         slm.mplc_reverse_order_mask_x_centers(channel=widget_channel.value,pol=widget_pol.value)
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)
        
#     fig, ax = plt.subplots()
#     fig.canvas.header_visible = False
#     rgbimage=np.zeros((slm.slmHeigth, slm.slmWidth, 3), dtype=np.uint8)
#     channelIdx=slm.GLobProps[widget_channel.value].rgbChannelIdx
#     np.copyto(rgbimage[:,:,channelIdx],slm.FullScreenBuffer_int)
#     rgb_image = cv2.cvtColor(rgbimage, cv2.COLOR_BGR2RGB)
#     image_display = ax.imshow(rgb_image,aspect='auto')
#     plt.axis("off")  # Hide axes
#     fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
#     # Function to update the plot when button is clicked
#     def update_displayWidget(_):
#         # rgb_image = cv2.cvtColor(slm.FullScreenBuffer_int, cv2.COLOR_BGR2RGB)
#         channelIdx=slm.GLobProps[widget_channel.value].rgbChannelIdx
#         np.copyto(rgbimage[:,:,channelIdx],slm.FullScreenBuffer_int)
#         rgb_image = cv2.cvtColor(rgbimage, cv2.COLOR_BGR2RGB)
#         image_display.set_data(rgb_image)
#         fig.canvas.draw_idle()  # Redraw figure without clearing widgets

#     # Observer callback for widget_Plane changes.
#     def on_plane_change(change):
#         # change['new'] is the new value of widget_Plane
#         new_plane = change['new']
#         # Sanity check for plane value
        
#         if new_plane > slm.polProps[widget_channel.value][widget_pol.value].MaskCount - 1:
#             widget_Plane.value = 0
#         elif new_plane < 0:
#             widget_Plane.value =  slm.polProps[widget_channel.value][widget_pol.value].MaskCount - 1
#         # Now update the center widgets based on the new plane value.
#         update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_channel_change(change):  
#          Channel = change['new']
#          update_slm_properties(widget_channel.value, widget_pol.value, widget_Plane.value)
    
#     def on_pol_change(change):
#         pol = change['new']
#         update_slm_properties( widget_channel.value, widget_pol.value, widget_Plane.value)

#     def on_pol_Enable_change(change):
#         if change['new']:
#             if(widget_pol.value=="H"):# Turn the Vertical pol side of SLM off
#                 slm.polProps[widget_channel.value]['H'].polEnabled=True
#             else:# Turn the Horizontial pol side of SLM off
#                 slm.polProps[widget_channel.value]['V'].polEnabled=True
#         else:
#             if(widget_pol.value=="H"):# Turn the Vertical pol side of SLM off
#                 slm.polProps[widget_channel.value]['H'].polEnabled=False
#             else:# Turn the Horizontial pol side of SLM off
#                 slm.polProps[widget_channel.value]['V'].polEnabled=False

#         update_slm_properties( widget_channel.value, widget_pol.value, widget_Plane.value)
    
#     def on_Mask_Enable_change(change):
#         slm.AllMaskProperties[widget_channel.value][widget_pol.value][widget_Plane.value].maskEnabled=widget_MaskEnableChecBox.value
#         slm.setmask(widget_channel.value, imode_H=widget_Mode_H.value,imode_V=widget_Mode_V.value)


#     def update_slm_properties(Channel, pol="V", imask=0):
#         widget_XCenter.value = slm.AllMaskProperties[Channel][pol][imask].center[1]
#         widget_YCenter.value = slm.AllMaskProperties[Channel][pol][imask].center[0]
#         widget_Piston.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[0]
#         widget_XTilt.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[1]
#         widget_YTilt.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[2]
#         widget_Defocus.value = slm.AllMaskProperties[Channel][pol][imask].zernike.zern_coefs[4]
#         if(pol=="H"):# Turn the Vertical pol side of SLM off
#                 widget_PolEnableChecBox.value=slm.polProps[Channel]['H'].polEnabled
#         else:# Turn the Horizontial pol side of SLM off
#                 widget_PolEnableChecBox.value=slm.polProps[Channel]['V'].polEnabled
#         widget_MaskEnableChecBox.value= slm.AllMaskProperties[Channel][pol][imask].maskEnabled
#         slm.setmask(widget_channel.value, imode_H=widget_Mode_H.value,imode_V=widget_Mode_V.value)
    
#     def InitialPiSweep(_):
#         slm.CourseSweepAcrossSLM(widget_channel.value,widget_SweepStep.value)

#     def SaveMaskProps(_):
#         slm.saveMaskProperties(channel=widget_channel.value)

#     def LoadPiFlipAlignmentMasks(_):
#         slm.LoadPiFlipMasks(channel=widget_channel.value) 
#     def LoadMaskFiles(_):
#         slm.LoadMasksFromFile(Filename=widget_MaskFilename.value,channel=widget_channel.value,)


        
#     # Attach the observer to widget_Plane.
#     widget_Plane.observe(on_plane_change, names='value')
#     widget_channel.observe(on_channel_change, names='value')
#     widget_pol.observe(on_pol_change, names='value')
#     widget_PolEnableChecBox.observe(on_pol_Enable_change, names='value')
#     widget_MaskEnableChecBox.observe(on_Mask_Enable_change, names='value')
    
    
    

#     # Register observers for the widgets
#     for w in [widget_Mode_H,widget_Mode_V, widget_XCenter, widget_YCenter, widget_XTilt,
#               widget_YTilt, widget_Piston, widget_Defocus,widget_RefreshTime]:
#         w.observe(on_value_change, names='value')

#     update_button_currentSLM.on_click(lambda event: on_button_click(event, update_all=False))
#     update_button_AllSLM.on_click(lambda event: on_button_click(event, update_all=True))
#     update_button_ClearSLM.on_click(on_button_click_clearSLM)
#     update_button_SetZernikeToZero.on_click(on_button_click_SetAllZernikeToZero)
#     update_button_SetPlanesToEqualSpacing.on_click(on_button_click_SetPlanesToEqualSpacing)
#     update_button_ReversePlaneOrder.on_click(on_button_click_ReversePlaneOrder)
#     update_button_ViewDisplay.on_click(update_displayWidget)
#     Init_button_PiSweep.on_click(InitialPiSweep)
#     Save_MaskProp_button.on_click(SaveMaskProps)
#     LoadPiFlipMasks_button.on_click(LoadPiFlipAlignmentMasks)
#     LoadMaskFile_button.on_click(LoadMaskFiles)
    
#     # Organize the widgets using layout containers
#     grid = widgets.GridBox(
#         children=[
#             widget_channel, widget_pol,widget_PolEnableChecBox,widget_Plane,widget_MaskEnableChecBox,
#             widget_Mode_H, widget_Mode_V,
#             widget_XCenter, widget_YCenter, widget_XTilt,
#             widget_YTilt, widget_Piston, widget_Defocus,widget_RefreshTime,
#             update_button_currentSLM, update_button_AllSLM, 
#             LoadPiFlipMasks_button,
#             update_button_ClearSLM,update_button_SetZernikeToZero,
#             update_button_SetPlanesToEqualSpacing,update_button_ReversePlaneOrder,update_button_ViewDisplay,
#             Save_MaskProp_button,
#             widget_SweepStep,Init_button_PiSweep,
#             widget_MaskFilename,LoadMaskFile_button],
#          layout=widgets.Layout(
#         grid_template_columns="repeat(5, 1fr)",
#         grid_template_rows="repeat(5, auto)",
#         grid_gap="10px"
#     )
#         # layout=widgets.Layout(
#         #     grid_template_columns="repeat(5, 1fr)",
#         #     grid_gap="10px"
#         # )
#     )
#     return grid
