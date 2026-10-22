"""New motor console: capability-driven layouts and leased hold-to-jog.

Start the configured server before launching this widget. All I/O belongs to the
motor client; Tk only submits intents and draws the client's cached state.
"""
import math
import time


class MotorisedStageControlWindow:
    def __init__(self, client, layout="alignment"):
        import tkinter as tk
        from tkinter import ttk
        self.tk, self.ttk = tk, ttk
        self.client = client
        self.root = tk.Tk()
        self.root.title("JazLabs · Motion")
        self.root.geometry("1050x760")
        self.root.minsize(720, 540)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.closed = False
        self.after_id = None
        self.focus_after_id = None
        self.release_after_id = None
        self.held_key = None
        self.held_axis = None
        self.held_distance = None
        self.held_started = 0
        self.capabilities = {}
        self.axis_widgets = {}
        self.state = {"connected": False, "axes": {}, "stopped": False, "stop_pending": False}
        self.layout = tk.StringVar(value=layout)
        self.keyboard = tk.BooleanVar(value=False)
        self.step = tk.StringVar(value="0.01")
        self.selected_axis = tk.StringVar()
        self.name = tk.StringVar(value="Connecting…")
        self.connection = tk.StringVar(value="Connecting…")
        self.message = tk.StringVar(value="Connecting…")
        self.keyboard_hint = tk.StringVar(value="Keyboard off · Escape stops all axes")
        self.local_error = None
        self._configure_style()
        self._build_shell()
        self.root.bind("<KeyPress>", self.key_pressed)
        self.root.bind("<KeyRelease>", self.key_released)
        self.root.bind("<FocusOut>", self.focus_left)
        self.root.bind("<FocusIn>", self.focus_entered)
        self.root.bind("<Unmap>", self.window_hidden)
        self.client.start()
        self.tick()

    def _configure_style(self):
        style = self.ttk.Style(self.root)
        style.theme_use("clam")
        self.colors = {"background": "#08090b", "panel": "#14171b", "ink": "#edf1f5",
                       "muted": "#a7b0be", "line": "#363e49", "blue": "#89baff",
                       "green": "#83d4a5", "amber": "#f0c981", "red": "#ff9c9c",
                       "field": "#0c0e11", "control": "#252a32", "active": "#333d4b"}
        c = self.colors
        self.root.configure(background=c["background"])
        style.configure(".", background=c["background"], foreground=c["ink"], bordercolor=c["line"])
        self.root.option_add("*TCombobox*Listbox.background", c["field"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["ink"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["active"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["ink"])
        style.configure("TEntry", fieldbackground=c["field"], foreground=c["ink"],
                        insertcolor=c["ink"], bordercolor=c["line"], padding=6)
        style.configure("TCombobox", fieldbackground=c["field"], background=c["control"],
                        foreground=c["ink"], arrowcolor=c["ink"], bordercolor=c["line"], padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", c["field"])],
                  foreground=[("readonly", c["ink"])], selectbackground=[("readonly", c["active"])])
        style.configure("Horizontal.TScale", background=c["blue"], troughcolor=c["field"],
                        bordercolor=c["line"], lightcolor=c["line"], darkcolor=c["line"])
        style.map("Horizontal.TScale", background=[("disabled", c["line"])])
        style.configure("Vertical.TScrollbar", background=c["control"], troughcolor=c["background"],
                        arrowcolor=c["ink"], bordercolor=c["line"])
        style.map("Vertical.TScrollbar", background=[("active", c["active"])])
        style.configure("TFrame", background=c["background"])
        style.configure("Panel.TFrame", background=c["panel"])
        style.configure("TLabel", background=c["background"], foreground=c["ink"], font=("Arial", 11))
        style.configure("Panel.TLabel", background=c["panel"])
        style.configure("Heading.TLabel", background=c["panel"], font=("Arial", 12, "bold"))
        style.configure("Position.TLabel", background=c["panel"], font=("Courier", 22))
        style.configure("Good.TLabel", background=c["panel"], foreground=c["green"], font=("Arial", 10))
        style.configure("Warning.TLabel", background=c["panel"], foreground=c["amber"], font=("Arial", 10))
        style.configure("Muted.TLabel", background=c["panel"], foreground=c["muted"], font=("Arial", 10))
        style.configure("TButton", padding=(12, 9), font=("Arial", 11),
                        background=c["control"], foreground=c["ink"], bordercolor=c["line"])
        style.map("TButton", background=[("active", c["active"]), ("disabled", c["panel"])],
                  foreground=[("disabled", c["muted"])])
        style.configure("Stop.TButton", background="#401a20", foreground=c["red"], font=("Arial", 12, "bold"))
        style.map("Stop.TButton", background=[("active", "#622530")])
        style.configure("TCheckbutton", background=c["panel"], foreground=c["ink"],
                        indicatorbackground=c["field"], indicatorforeground=c["ink"], font=("Arial", 11))
        style.map("TCheckbutton", background=[("active", c["panel"])],
                  indicatorbackground=[("selected", c["blue"]), ("!selected", c["field"])])

    def _build_shell(self):
        ttk = self.ttk
        shell = ttk.Frame(self.root, padding=18)
        shell.pack(fill="both", expand=True)
        chrome = ttk.Frame(shell)
        chrome.pack(fill="x", pady=(0, 14))
        ttk.Label(chrome, text="JazLabs / Motion", font=("Arial", 13, "bold")).pack(side="left")
        ttk.Label(chrome, textvariable=self.name).pack(side="left", padx=18)
        picker = ttk.Combobox(chrome, values=("alignment", "console"), textvariable=self.layout,
                              state="readonly", width=12)
        picker.pack(side="right")
        picker.bind("<<ComboboxSelected>>", lambda event: self.rebuild_layout())
        self.connection_label = ttk.Label(shell, textvariable=self.connection)
        self.connection_label.pack(anchor="w", pady=(0, 10))
        viewport = ttk.Frame(shell)
        viewport.pack(fill="both", expand=True)
        canvas = self.tk.Canvas(viewport, background=self.colors["background"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        self.content = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content_window, width=event.width))
        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(14, 0))
        self.stop_button = ttk.Button(footer, text="■ STOP ALL AXES · Esc", style="Stop.TButton", command=self.stop)
        self.stop_button.pack(side="right")
        self.resume_button = ttk.Button(footer, text="Re-enable motion", command=lambda: self.send("resume"))
        self.resume_button.pack(side="right", padx=8)
        ttk.Label(footer, textvariable=self.message, wraplength=460).pack(anchor="w")
        ttk.Label(footer, textvariable=self.keyboard_hint, foreground=self.colors["muted"]).pack(anchor="w")

    def _panel(self, parent):
        return self.ttk.Frame(parent, style="Panel.TFrame", padding=16)

    def _axis_readout(self, parent, axis):
        ttk = self.ttk
        spec = self.capabilities[axis]
        panel = self._panel(parent)
        ttk.Label(panel, text=spec["label"], style="Heading.TLabel").pack(anchor="w")
        value = self.tk.StringVar(value="—")
        status = self.tk.StringVar(value="Awaiting feedback")
        ttk.Label(panel, textvariable=value, style="Position.TLabel").pack(anchor="w", pady=6)
        indicator = ttk.Label(panel, textvariable=status, style="Warning.TLabel")
        indicator.pack(anchor="w")
        actions = ttk.Frame(panel, style="Panel.TFrame")
        actions.pack(anchor="w", pady=(8, 0))
        home = ttk.Button(actions, text="Home", command=lambda: self.send("home", axis)) if spec["home"] else None
        if home:
            home.pack(side="left")
        enable = ttk.Button(actions, text="Enable axis", command=lambda: self.send("enable", axis))
        self.axis_widgets[axis] = {"position": value, "status": status, "indicator": indicator,
                                   "home": home, "enable": enable, "move_controls": []}
        return panel

    def _position_controls(self, parent, axis):
        ttk = self.ttk
        spec = self.capabilities[axis]
        widgets = self.axis_widgets[axis]
        ttk.Label(parent, text=f"Absolute target ({spec['units']})", style="Panel.TLabel").pack(anchor="w")
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=(6, 12))
        target = self.tk.StringVar(value="")
        entry = ttk.Entry(row, textvariable=target, width=14)
        entry.pack(side="left", fill="x", expand=True)
        go = ttk.Button(row, text="Go", command=lambda: self.absolute_move(axis))
        go.pack(side="left", padx=(8, 0))
        entry.bind("<Return>", lambda event: self.absolute_move(axis))
        widgets.update(target=target, entry=entry, target_initialized=False)
        widgets["move_controls"].append(go)
        jog_row = ttk.Frame(parent, style="Panel.TFrame")
        jog_row.pack(fill="x", pady=(0, 12))
        for sign, text in ((-1, "−"), (1, "+")):
            button = ttk.Button(jog_row, text=f"{text} {spec['label']}", command=lambda sign=sign: self.jog_once(axis, sign))
            button.pack(side="left", expand=True, fill="x", padx=(0, 5))
            widgets["move_controls"].append(button)
        if spec["minimum"] is not None and spec["maximum"] is not None:
            preview = self.tk.StringVar(value="Slider target")
            ttk.Label(parent, textvariable=preview, style="Panel.TLabel").pack(anchor="w")
            slider = ttk.Scale(parent, from_=spec["minimum"], to=spec["maximum"],
                               command=lambda value: preview.set(f"Slider target · {self.number(axis, float(value))} {spec['units']}"))
            slider.pack(fill="x", pady=8)
            slider.bind("<ButtonPress-1>", lambda event: widgets.update(dragging=True))
            slider.bind("<ButtonRelease-1>", lambda event: self.slider_released(axis))
            # Keyboard arrow adjustments commit on key release too.
            slider.bind("<KeyRelease>", lambda event: self.slider_released(axis) if event.keysym in ("Left", "Right", "Up", "Down", "Home", "End") else None)
            widgets.update(slider=slider, dragging=False, slider_initialized=False)
            widgets["move_controls"].append(slider)
            ttk.Label(parent, text="Drag to preview · release to move", style="Muted.TLabel").pack(anchor="w")
            ttk.Label(parent, text=f"Range {spec['minimum']:g} to {spec['maximum']:g} {spec['units']}", style="Muted.TLabel").pack(anchor="w")
        else:
            ttk.Label(parent, text="Slider unavailable · configure travel limits", style="Muted.TLabel", wraplength=260).pack(anchor="w")
        speed_panel = ttk.Frame(parent, style="Panel.TFrame")
        speed_panel.pack(fill="x", pady=(16, 0))
        ttk.Label(speed_panel, text="Motion speed", style="Heading.TLabel").pack(anchor="w")
        if spec["speed"]:
            speed = self.tk.StringVar(value="")
            speed_row = ttk.Frame(speed_panel, style="Panel.TFrame")
            speed_row.pack(fill="x", pady=(6, 0))
            ttk.Entry(speed_row, textvariable=speed, width=9).pack(side="left")
            apply = ttk.Button(speed_row, text="Apply", command=lambda: self.speed_changed(axis))
            apply.pack(side="left", padx=6)
            ttk.Label(speed_row, text=spec["speed_units"], style="Panel.TLabel").pack(side="left")
            widgets.update(speed=speed, speed_initialized=False, speed_button=apply)
        else:
            ttk.Label(speed_panel, text="Unavailable in this driver", style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

    def rebuild_layout(self):
        self.release_jog(disarm=True)
        for child in self.content.winfo_children():
            child.destroy()
        self.axis_widgets = {}
        if not self.capabilities:
            return
        ttk = self.ttk
        axes = list(self.capabilities)
        self.root.minsize(960 if self.layout.get() == "alignment" and len(axes) > 1 else 740, 540)
        tools = self._panel(self.content)
        tools.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Checkbutton(tools, text="Keyboard control", variable=self.keyboard, command=self.keyboard_changed).pack(side="left")
        ttk.Label(tools, text="Relative step", style="Panel.TLabel").pack(side="left", padx=(22, 8))
        ttk.Entry(tools, textvariable=self.step, width=10).pack(side="left")
        units = {spec["units"] for spec in self.capabilities.values()}
        ttk.Label(tools, text=next(iter(units)) if len(units) == 1 else "selected axis units", style="Panel.TLabel").pack(side="left", padx=6)
        ttk.Label(tools, text="Tap = one step · hold to repeat", style="Muted.TLabel").pack(side="right")
        if self.layout.get() == "console":
            for index, axis in enumerate(axes):
                row = ttk.Frame(self.content)
                row.pack(fill="both", expand=True, pady=(0, 10))
                readout = self._axis_readout(row, axis)
                readout.pack(side="left", fill="both", padx=(0, 10))
                controls = self._panel(row)
                controls.pack(side="left", fill="both", expand=True)
                self._position_controls(controls, axis)
        else:
            left = ttk.Frame(self.content)
            left.pack(side="left", fill="both", expand=True, padx=(0, 12))
            readouts = ttk.Frame(left)
            readouts.pack(fill="x")
            for index, axis in enumerate(axes):
                panel = self._axis_readout(readouts, axis)
                column = index % 2
                panel.grid(row=index // 2, column=column, sticky="nsew", padx=(0, 8), pady=(0, 8))
                readouts.columnconfigure(column, weight=1)
            pad_panel = self._panel(left)
            pad_panel.pack(fill="both", expand=True, pady=(12, 0))
            ttk.Label(pad_panel, text="Mount alignment" if len(axes) > 1 else "Axis jog", style="Heading.TLabel").pack(anchor="w")
            pad = ttk.Frame(pad_panel, style="Panel.TFrame")
            pad.pack(expand=True, pady=18)
            directions = [(0, -1, "A  ←", 1, 0), (0, 1, "D  →", 1, 2)]
            if len(axes) > 1:
                directions += [(1, 1, "W  ↑", 0, 1), (1, -1, "S  ↓", 2, 1)]
            for axis_index, sign, label, row, column in directions:
                axis = axes[axis_index]
                button = ttk.Button(pad, text=label, command=lambda axis=axis, sign=sign: self.jog_once(axis, sign), width=8)
                button.grid(row=row, column=column, padx=5, pady=5)
                self.axis_widgets[axis]["move_controls"].append(button)
            ttk.Label(pad, text=" / ".join(axes[:2]), style="Muted.TLabel").grid(row=1, column=1, padx=10)
            if len(axes) > 2:
                axis = axes[2]
                for column, sign, label in ((0, -1, f"Q / −{axis}"), (2, 1, f"E / +{axis}")):
                    button = ttk.Button(pad, text=label, command=lambda sign=sign: self.jog_once(axis, sign))
                    button.grid(row=3, column=column, padx=5, pady=10)
                    self.axis_widgets[axis]["move_controls"].append(button)
            right = self._panel(self.content)
            right.pack(side="right", fill="both")
            ttk.Label(right, text="Precise positioning", style="Heading.TLabel").pack(anchor="w", pady=(0, 12))
            if self.selected_axis.get() not in axes:
                self.selected_axis.set(axes[0])
            if len(axes) > 1:
                selector = ttk.Combobox(right, textvariable=self.selected_axis, values=axes, state="readonly", width=18)
                selector.pack(fill="x", pady=(0, 14))
                selector.bind("<<ComboboxSelected>>", lambda event: self.rebuild_layout())
            self._position_controls(right, self.selected_axis.get())
        self.draw_state()

    def number(self, axis, value):
        resolution = self.capabilities[axis]["resolution"]
        decimals = 0 if resolution >= 1 else min(6, max(3, math.ceil(-math.log10(resolution))))
        return f"{value:.{decimals}f}"

    def send(self, command, axis=None, value=None):
        try:
            self.client.submit(command, axis, value)
            self.local_error = None
        except Exception as exc:
            self.local_error = str(exc)
            self.message.set(str(exc))
            return False
        return True

    def absolute_move(self, axis):
        self.release_jog(disarm=True)
        try:
            target = float(self.axis_widgets[axis]["target"].get())
            if not math.isfinite(target):
                raise ValueError("Enter a finite absolute target")
            self.send("absolute", axis, target)
        except ValueError:
            self.local_error = "Enter a finite absolute target"
            self.message.set(self.local_error)

    def jog_once(self, axis, sign):
        try:
            distance = float(self.step.get())
            if not math.isfinite(distance) or distance <= 0:
                raise ValueError("Relative step must be positive and finite")
            return self.send("relative", axis, sign * distance)
        except ValueError:
            self.local_error = "Relative step must be positive and finite"
            self.message.set(self.local_error)
            return False

    def slider_released(self, axis):
        widgets = self.axis_widgets[axis]
        widgets["dragging"] = False
        if "disabled" not in widgets["slider"].state():
            self.release_jog(disarm=True)
            widgets["target"].set(self.number(axis, widgets["slider"].get()))
            self.absolute_move(axis)

    def speed_changed(self, axis):
        try:
            self.send("speed", axis, float(self.axis_widgets[axis]["speed"].get()))
        except ValueError:
            self.local_error = "Enter a valid speed"
            self.message.set(self.local_error)

    def keyboard_changed(self):
        self.release_jog(disarm=not self.keyboard.get())
        self.keyboard_hint.set("Keyboard armed · A/D first axis · W/S second · Q/E third" if self.keyboard.get() else "Keyboard off · Escape stops all axes")

    def key_pressed(self, event):
        if event.keysym == "Escape":
            self.stop()
            return "break"
        key = event.keysym.lower()
        bindings = {"a": (0, -1), "d": (0, 1), "w": (1, 1), "s": (1, -1), "q": (2, -1), "e": (2, 1)}
        if not self.keyboard.get() or key not in bindings:
            return
        if event.widget.winfo_class() in ("Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text"):
            return
        if event.state & (0x4 | 0x8 | 0x40):
            return  # Leave Ctrl/Alt/Command shortcuts to the desktop.
        if self.held_key:
            if self.held_key == key and self.release_after_id:
                self.root.after_cancel(self.release_after_id)
                self.release_after_id = None
            return "break"
        index, sign = bindings[key]
        axes = list(self.capabilities)
        if index >= len(axes):
            return "break"
        axis = axes[index]
        if not self.can_move(axis):
            return "break"
        if self.jog_once(axis, sign):
            self.held_key, self.held_axis = key, axis
            self.held_distance = sign * float(self.step.get())
            self.held_started = time.monotonic()
        return "break"

    def key_released(self, event):
        if self.held_key == event.keysym.lower():
            # X11 can emit synthetic release/press pairs during auto repeat.
            # Deferring cancellation lets the matching press suppress that pair.
            if self.release_after_id:
                self.root.after_cancel(self.release_after_id)
            self.release_after_id = self.root.after(25, self.release_jog)
            return "break"

    def release_jog(self, disarm=False):
        if self.release_after_id:
            self.root.after_cancel(self.release_after_id)
            self.release_after_id = None
        was_held = self.held_key is not None
        self.held_key = self.held_axis = self.held_distance = None
        if was_held:
            self.send("release_jog")
        if disarm:
            self.keyboard.set(False)
            self.keyboard_hint.set("Keyboard off · Escape stops all axes")

    def focus_left(self, event):
        if self.focus_after_id:
            self.root.after_cancel(self.focus_after_id)
        self.focus_after_id = self.root.after(30, self.check_application_focus)

    def check_application_focus(self):
        self.focus_after_id = None
        if self.root.focus_displayof() is None:
            self.release_jog(disarm=True)

    def focus_entered(self, event):
        if event.widget.winfo_class() in ("Entry", "TEntry", "TCombobox", "Spinbox", "TSpinbox", "Text"):
            self.release_jog(disarm=True)

    def window_hidden(self, event):
        if event.widget is self.root:
            self.release_jog(disarm=True)

    def stop(self):
        self.release_jog(disarm=True)
        self.send("stop")
        self.message.set("Stop requested…")

    def can_move(self, axis):
        state = self.state
        current = state["axes"].get(axis, {})
        busy = any(a.get("moving") or a.get("homing") or a.get("commanded") for a in state["axes"].values())
        return bool(state["connected"] and not state["stopped"] and not state["stop_pending"]
                    and current.get("age", 999) < 1 and not busy and current.get("enabled")
                    and not current.get("fault") and (not self.capabilities[axis]["home"] or current.get("homed")))

    def draw_state(self):
        state = self.state
        busy = any(a.get("moving") or a.get("homing") or a.get("commanded") for a in state["axes"].values())
        available = state["connected"] and not state["stopped"] and not state["stop_pending"]
        stale = not state["connected"] or any(a.get("age", 999) >= 1 for a in state["axes"].values())
        self.name.set(state.get("name", "Motion"))
        self.connection.set("Feedback unavailable / stale" if stale else "Connected · live feedback")
        self.connection_label.configure(foreground=self.colors["amber"] if stale else self.colors["green"])
        self.message.set(self.local_error or state.get("error") or state.get("message", ""))
        self.resume_button.state(["!disabled"] if state["stopped"] and state["connected"] and not state["stop_pending"] and not busy else ["disabled"])
        for axis, widgets in self.axis_widgets.items():
            spec = self.capabilities[axis]
            current = state["axes"].get(axis)
            if not current:
                continue
            widgets["position"].set(f"{self.number(axis, current['position'])} {spec['units']}")
            if stale:
                text = "Feedback stale · motion disabled"
            elif current.get("fault"):
                text = current["fault"]
            elif current["homing"]:
                text = "Homing…"
            elif not current["enabled"]:
                text = "Axis disabled"
            elif current["moving"] or current.get("commanded"):
                text = "Moving…"
            elif not spec["home"]:
                text = "Absolute sensor · no homing"
            else:
                text = "Homed" if current["homed"] else "Needs homing"
            widgets["status"].set(text)
            good = available and not stale and (not spec["home"] or current["homed"]) and current["enabled"] and not current["fault"]
            widgets["indicator"].configure(style="Good.TLabel" if good else "Warning.TLabel")
            for control in widgets["move_controls"]:
                control.state(["!disabled"] if self.can_move(axis) else ["disabled"])
            if widgets["home"]:
                widgets["home"].state(["!disabled"] if available and not stale and not busy and current["enabled"] else ["disabled"])
            if not current["enabled"]:
                widgets["enable"].pack(side="left", padx=5)
                widgets["enable"].state(["!disabled"] if available and not stale and not busy else ["disabled"])
            else:
                widgets["enable"].pack_forget()
            if "target" in widgets and not widgets["target_initialized"]:
                widgets["target"].set(self.number(axis, current["position"]))
                widgets["target_initialized"] = True
            if "slider" in widgets and not widgets["slider_initialized"]:
                widgets["slider"].set(current["position"])
                widgets["slider_initialized"] = True
            if "speed" in widgets:
                if not widgets["speed_initialized"] and current["speed"] is not None:
                    widgets["speed"].set(f"{current['speed']:g}")
                    widgets["speed_initialized"] = True
                widgets["speed_button"].state(["!disabled"] if available and not busy and not stale else ["disabled"])
        if stale or state["stopped"] or state["stop_pending"] or state.get("error"):
            self.release_jog(disarm=True)

    def tick(self):
        if self.closed:
            return
        self.state = self.client.get_state()
        capabilities = {axis["id"]: axis for axis in self.state.get("capabilities", [])}
        if capabilities != self.capabilities:
            self.capabilities = capabilities
            if capabilities:
                self.step.set(str(next(iter(capabilities.values()))["step"]))
            self.rebuild_layout()
        self.draw_state()
        if self.held_key and not self.release_after_id and time.monotonic() - self.held_started >= 0.35:
            self.send("jog", self.held_axis, self.held_distance)
        self.after_id = self.root.after(80, self.tick)

    def close(self):
        if self.closed:
            return
        self.release_jog(disarm=True)
        self.closed = True
        for callback in (self.after_id, self.focus_after_id, self.release_after_id):
            if callback:
                self.root.after_cancel(callback)
        self.client.close()
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.client.close()
            # Keep the process alive long enough for the hardware owner to send
            # stop and close the port after the window has been destroyed.
            self.client.thread.join(timeout=3)
            if self.client.thread.is_alive():
                raise RuntimeError("Motion connection did not close within 3 seconds; stop is unconfirmed")


if __name__ == "__main__":
    from JazLabs.launchers.launch_motorised_stage_widget import main
    main()
