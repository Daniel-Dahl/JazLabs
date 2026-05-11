import multiprocessing as mp
import traceback


def _as_float(text):
    text = str(text).strip()
    if text == "":
        return None
    return float(text)


def _as_int(text):
    text = str(text).strip()
    if text == "":
        return None
    return int(text)


def _format_time_ns(time_ns):
    try:
        if int(time_ns) <= 0:
            return "none"
        return f"{int(time_ns) / 1e9:.6f} s"
    except Exception:
        return "unknown"


class CameraControlWindow:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        timeout_ms=5000,
        refresh_ms=500,
    ):
        import tkinter as tk
        from tkinter import ttk

        from pwi_inst.hardware.Cameras.Camera_Client import CameraClient

        self.tk = tk
        self.ttk = ttk
        self.refresh_ms = int(refresh_ms)
        self.status_after_id = None

        self.cam = CameraClient(
            host=host,
            command_port=command_port,
            frame_pub_port=frame_pub_port,
            timeout_ms=timeout_ms,
            client_id="camera_widget",
        )

        self.root = tk.Tk()
        self.root.title("Camera Control")
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connected")
        self.properties_var = tk.StringVar(value="")
        self.trigger_var = tk.StringVar(value="")

        self.exposure_var = tk.StringVar()
        self.gain_var = tk.StringVar()
        self.fps_var = tk.StringVar()
        self.pixel_format_var = tk.StringVar()

        self.roi_x_var = tk.StringVar()
        self.roi_y_var = tk.StringVar()
        self.roi_w_var = tk.StringVar()
        self.roi_h_var = tk.StringVar()
        self.roi_enable_var = tk.BooleanVar(value=True)
        self.roi_snap_var = tk.BooleanVar(value=True)
        self.roi_mode_var = tk.StringVar(value="nearest")

        self.hardware_line_var = tk.StringVar(value="0")
        self.hardware_edge_var = tk.StringVar(value="Rising")

        self._build_layout()
        self.refresh_all()
        self._schedule_status_refresh()

    def _build_layout(self):
        tk = self.tk
        ttk = self.ttk

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=10)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=1)

        status = ttk.LabelFrame(main, text="Status", padding=8)
        status.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.trigger_var).grid(row=1, column=0, sticky="w")
        ttk.Label(status, textvariable=self.properties_var, justify="left").grid(row=2, column=0, sticky="w")

        acquisition = ttk.LabelFrame(main, text="Acquisition", padding=8)
        acquisition.grid(row=1, column=0, sticky="nsew", padx=(0, 4), pady=4)
        for col in range(3):
            acquisition.columnconfigure(col, weight=1)

        ttk.Button(acquisition, text="Start", command=self._call(self.cam.StartAcquisition)).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(acquisition, text="Stop", command=self._call(self.cam.StopAcquisition)).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(acquisition, text="Pause Pub", command=self._call(self.cam.PauseAcquisition)).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(acquisition, text="Resume Pub", command=self._call(self.cam.ResumeAcquisition)).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(acquisition, text="Reset Camera", command=self._call(self.cam.ResetCamera)).grid(row=2, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(acquisition, text="Reset Buffer", command=self._call(self.cam.ResetBuffer)).grid(row=2, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(acquisition, text="Get Frame", command=self.get_frame).grid(row=0, column=2, rowspan=2, sticky="nsew", padx=2, pady=2)

        trigger = ttk.LabelFrame(main, text="Trigger", padding=8)
        trigger.grid(row=1, column=1, sticky="nsew", padx=(4, 0), pady=4)
        for col in range(3):
            trigger.columnconfigure(col, weight=1)

        ttk.Button(trigger, text="Continuous", command=self.set_continuous).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(trigger, text="Software", command=self.set_software_trigger).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(trigger, text="Fire", command=self.software_trigger).grid(row=0, column=2, sticky="ew", padx=2, pady=2)
        ttk.Label(trigger, text="Line").grid(row=1, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(trigger, textvariable=self.hardware_line_var, width=8).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        ttk.Combobox(
            trigger,
            textvariable=self.hardware_edge_var,
            values=("Rising", "Falling"),
            state="readonly",
            width=10,
        ).grid(row=1, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(trigger, text="Hardware", command=self.set_hardware_trigger).grid(row=2, column=0, columnspan=3, sticky="ew", padx=2, pady=2)

        settings = ttk.LabelFrame(main, text="Camera Settings", padding=8)
        settings.grid(row=2, column=0, sticky="nsew", padx=(0, 4), pady=4)
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(2, weight=1)

        self._add_setting_row(settings, 0, "Exposure", self.exposure_var, self.get_exposure, self.set_exposure)
        self._add_setting_row(settings, 1, "Gain", self.gain_var, self.get_gain, self.set_gain)
        self._add_setting_row(settings, 2, "FPS", self.fps_var, self.get_fps, self.set_fps)

        ttk.Label(settings, text="Pixel Format").grid(row=3, column=0, sticky="w", padx=2, pady=2)
        ttk.Combobox(
            settings,
            textvariable=self.pixel_format_var,
            values=("mono8", "mono10", "mono12", "mono16"),
            width=12,
        ).grid(row=3, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(settings, text="Get", command=self.get_pixel_format).grid(row=3, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(settings, text="Set", command=self.set_pixel_format).grid(row=3, column=3, sticky="ew", padx=2, pady=2)

        roi = ttk.LabelFrame(main, text="ROI", padding=8)
        roi.grid(row=2, column=1, sticky="nsew", padx=(4, 0), pady=4)
        for col in range(4):
            roi.columnconfigure(col, weight=1)

        labels = ("Offset X", "Offset Y", "Width", "Height")
        vars_ = (self.roi_x_var, self.roi_y_var, self.roi_w_var, self.roi_h_var)
        for idx, (label, var) in enumerate(zip(labels, vars_)):
            ttk.Label(roi, text=label).grid(row=idx, column=0, sticky="w", padx=2, pady=2)
            ttk.Entry(roi, textvariable=var, width=10).grid(row=idx, column=1, columnspan=3, sticky="ew", padx=2, pady=2)

        ttk.Checkbutton(roi, text="Enable ROI", variable=self.roi_enable_var).grid(row=4, column=0, columnspan=2, sticky="w", padx=2, pady=2)
        ttk.Checkbutton(roi, text="Snap", variable=self.roi_snap_var).grid(row=4, column=2, sticky="w", padx=2, pady=2)
        ttk.Combobox(
            roi,
            textvariable=self.roi_mode_var,
            values=("nearest", "floor", "ceil"),
            state="readonly",
            width=10,
        ).grid(row=4, column=3, sticky="ew", padx=2, pady=2)
        ttk.Button(roi, text="Get ROI", command=self.get_roi).grid(row=5, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(roi, text="Set ROI", command=self.set_roi).grid(row=5, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(roi, text="Full Frame", command=self.full_frame).grid(row=5, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(roi, text="Refresh All", command=self.refresh_all).grid(row=5, column=3, sticky="ew", padx=2, pady=2)

        server = ttk.LabelFrame(main, text="Server", padding=8)
        server.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        server.columnconfigure(0, weight=1)
        ttk.Button(server, text="Refresh Status", command=self.refresh_status).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(server, text="Shutdown Server", command=self.shutdown_server).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(server, text="Close Window", command=self.close).grid(row=0, column=2, sticky="ew", padx=2, pady=2)

    def _add_setting_row(self, parent, row, label, var, get_command, set_command):
        ttk = self.ttk

        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=2, pady=2)
        ttk.Entry(parent, textvariable=var, width=12).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(parent, text="Get", command=get_command).grid(row=row, column=2, sticky="ew", padx=2, pady=2)
        ttk.Button(parent, text="Set", command=set_command).grid(row=row, column=3, sticky="ew", padx=2, pady=2)

    def _call(self, func):
        def wrapped():
            try:
                result = func()
                self.set_status(f"{func.__name__}: {result}")
                self.refresh_status()
            except Exception as exc:
                self.show_error(exc)

        return wrapped

    def set_status(self, message):
        self.status_var.set(str(message))

    def show_error(self, exc):
        self.status_var.set(f"ERROR: {type(exc).__name__}: {exc}")

    def refresh_status(self):
        try:
            props = self.cam.GetProperties()
            trigger = self.cam.GetTriggerMode()

            self.trigger_var.set(f"Trigger: {trigger}")
            self.properties_var.set(
                "Frame shape: {shape} | dtype: {dtype} | counter: {counter}\n"
                "Layout version: {version} | acquisition: {acq} | alive: {alive} | last write: {last}".format(
                    shape=tuple(props["frame_shape"]),
                    dtype=props["frame_dtype"],
                    counter=props["frame_counter"],
                    version=props["frame_layout_version"],
                    acq=props["acquisition_running"],
                    alive=props["server_alive"],
                    last=_format_time_ns(props["last_write_time_ns"]),
                )
            )
        except Exception as exc:
            self.show_error(exc)

    def refresh_all(self):
        self.refresh_status()
        self.get_exposure()
        self.get_gain()
        self.get_fps()
        self.get_pixel_format()
        self.get_roi()

    def _schedule_status_refresh(self):
        self.refresh_status()
        self.status_after_id = self.root.after(self.refresh_ms, self._schedule_status_refresh)

    def get_frame(self):
        try:
            frame = self.cam.GetFrame()
            self.set_status(
                f"Got frame {frame.shape}, dtype {frame.dtype}, counter {self.cam.GetFrameCounter()}"
            )
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def set_continuous(self):
        try:
            result = self.cam.SetContinuousMode()
            self.set_status(f"Continuous mode: {result}")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def set_software_trigger(self):
        try:
            result = self.cam.SetSoftwareTriggerMode()
            self.set_status(f"Software trigger mode: {result}")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def set_hardware_trigger(self):
        try:
            edge = 1 if self.hardware_edge_var.get().lower().startswith("r") else -1
            result = self.cam.SetHardwareTriggerMode(
                lineNumber=_as_int(self.hardware_line_var.get()) or 0,
                RiseEdgeOrFallEdge=edge,
            )
            self.set_status(f"Hardware trigger mode: {result}")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def software_trigger(self):
        try:
            result = self.cam.SoftwareTrigger()
            self.set_status(f"Software trigger fired: {result}")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def get_exposure(self):
        try:
            self.exposure_var.set(str(self.cam.GetExposureTime()))
        except Exception as exc:
            self.show_error(exc)

    def set_exposure(self):
        try:
            result = self.cam.SetExposureTime(_as_float(self.exposure_var.get()))
            self.exposure_var.set(str(result))
            self.set_status(f"Exposure set: {result}")
        except Exception as exc:
            self.show_error(exc)

    def get_gain(self):
        try:
            self.gain_var.set(str(self.cam.GetGain()))
        except Exception as exc:
            self.show_error(exc)

    def set_gain(self):
        try:
            result = self.cam.SetGain(_as_float(self.gain_var.get()))
            self.gain_var.set(str(result))
            self.set_status(f"Gain set: {result}")
        except Exception as exc:
            self.show_error(exc)

    def get_fps(self):
        try:
            self.fps_var.set(str(self.cam.GetFPS()))
        except Exception as exc:
            self.show_error(exc)

    def set_fps(self):
        try:
            result = self.cam.SetFPS(_as_float(self.fps_var.get()))
            self.fps_var.set(str(result))
            self.set_status(f"FPS set: {result}")
        except Exception as exc:
            self.show_error(exc)

    def get_pixel_format(self):
        try:
            self.pixel_format_var.set(str(self.cam.GetPixelFormat()))
        except Exception as exc:
            self.show_error(exc)

    def set_pixel_format(self):
        try:
            result = self.cam.SetPixelFormat(self.pixel_format_var.get())
            self.pixel_format_var.set(str(result))
            self.set_status(f"Pixel format set: {result}")
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def get_roi(self):
        try:
            offset_x, offset_y, width, height = self.cam.GetROI()
            self.roi_x_var.set(str(offset_x))
            self.roi_y_var.set(str(offset_y))
            self.roi_w_var.set(str(width))
            self.roi_h_var.set(str(height))
        except Exception as exc:
            self.show_error(exc)

    def set_roi(self):
        try:
            result = self.cam.SetROI(
                offset_x=_as_int(self.roi_x_var.get()),
                offset_y=_as_int(self.roi_y_var.get()),
                width=_as_int(self.roi_w_var.get()),
                height=_as_int(self.roi_h_var.get()),
                snap_values=bool(self.roi_snap_var.get()),
                enable=bool(self.roi_enable_var.get()),
                mode=self.roi_mode_var.get(),
            )
            self.set_status(f"ROI set: {result}")
            self.get_roi()
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def full_frame(self):
        try:
            result = self.cam.SetROI(enable=False)
            self.set_status(f"Full frame ROI: {result}")
            self.get_roi()
            self.refresh_status()
        except Exception as exc:
            self.show_error(exc)

    def shutdown_server(self):
        try:
            self.cam.ShutdownServer()
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
            self.cam.close()
        except Exception:
            pass

        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


def CameraWidgetProcess(
    host="127.0.0.1",
    command_port=50731,
    frame_pub_port=50732,
    timeout_ms=5000,
    refresh_ms=500,
):
    try:
        window = CameraControlWindow(
            host=host,
            command_port=command_port,
            frame_pub_port=frame_pub_port,
            timeout_ms=timeout_ms,
            refresh_ms=refresh_ms,
        )
        window.run()
    except Exception:
        print("Camera widget crashed:")
        print(traceback.format_exc())
        raise


class CameraWidget:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        timeout_ms=5000,
        refresh_ms=500,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.frame_pub_port = int(frame_pub_port)
        self.timeout_ms = int(timeout_ms)
        self.refresh_ms = int(refresh_ms)
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Camera widget already running.")
            return

        self.Process = mp.Process(
            target=CameraWidgetProcess,
            kwargs={
                "host": self.host,
                "command_port": self.command_port,
                "frame_pub_port": self.frame_pub_port,
                "timeout_ms": self.timeout_ms,
                "refresh_ms": self.refresh_ms,
            },
            daemon=False,
        )

        self.Process.start()
        print(f"Camera widget started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is None:
            return

        if self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)

        self.Process = None


def launch_camera_widget(**kwargs):
    widget = CameraWidget(**kwargs)
    widget.startProcess()
    return widget


if __name__ == "__main__":
    mp.freeze_support()
    CameraWidgetProcess()
