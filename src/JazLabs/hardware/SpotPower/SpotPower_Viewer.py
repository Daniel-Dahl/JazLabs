import multiprocessing as mp
import queue
import threading
import time
import traceback
from pathlib import Path

import numpy as np

from JazLabs.hardware.SpotPower.SpotPower_Analysis import (
    analyse_spot_powers,
    normalise_aperture_radii,
    parse_spot_centres,
    prepare_analysis_frame,
    validate_spot_centres,
)


def load_array_file(filename):
    """Load a two-dimensional array from NumPy, text, or common image files."""
    path = Path(filename)
    suffix = path.suffix.lower()

    if suffix == ".npy":
        array = np.load(path, allow_pickle=False)
    elif suffix == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            if not archive.files:
                raise ValueError(f"{path} contains no arrays.")
            array = archive[archive.files[0]]
    elif suffix in {".csv", ".txt"}:
        delimiter = "," if suffix == ".csv" else None
        array = np.loadtxt(path, delimiter=delimiter)
    else:
        import cv2

        array = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if array is None:
            raise ValueError(f"Could not read array or image file: {path}")

    array = np.asarray(array)
    if array.ndim == 3 and array.shape[2] in (3, 4):
        array = np.mean(array[..., :3], axis=2)
    if array.ndim != 2:
        raise ValueError(f"Expected a two-dimensional array, received shape {array.shape}.")

    return array


def load_spot_centres_file(filename):
    """Load ``(y, x)`` spot centres from a NumPy, CSV, or text file."""
    path = Path(filename)
    if path.suffix.lower() == ".npy":
        centres = np.load(path, allow_pickle=False)
    elif path.suffix.lower() == ".npz":
        with np.load(path, allow_pickle=False) as archive:
            if not archive.files:
                raise ValueError(f"{path} contains no arrays.")
            centres = archive[archive.files[0]]
    else:
        centres = parse_spot_centres(path.read_text(encoding="utf-8"))

    return validate_spot_centres(centres)


def save_spot_centres_file(filename, spot_centres):
    """Save ``(y, x)`` spot centres to a NumPy, CSV, or text file."""
    path = Path(filename)
    centres = validate_spot_centres(spot_centres)
    suffix = path.suffix.lower()

    if suffix == ".npy":
        np.save(path, centres)
    elif suffix == ".npz":
        np.savez(path, spot_centres=centres)
    elif suffix == ".csv":
        np.savetxt(
            path,
            centres,
            delimiter=",",
            header="y, x",
            comments="# ",
        )
    elif suffix == ".txt":
        np.savetxt(
            path,
            centres,
            header="y x",
            comments="# ",
        )
    else:
        raise ValueError("Spot centres must be saved as .npy, .npz, .csv, or .txt.")


class SpotPowerWindow:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        spot_centres=None,
        aperture_radii=(3, 3),
        dark_frame_filename=None,
        refresh_ms=100,
        window_name="Spot Power Viewer",
    ):
        import tkinter as tk
        from tkinter import ttk

        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self.tk = tk
        self.ttk = ttk
        self.FigureCanvasTkAgg = FigureCanvasTkAgg

        self.host = host
        self.command_port = int(command_port)
        self.frame_pub_port = int(frame_pub_port)
        self.refresh_ms = max(20, int(refresh_ms))

        if spot_centres is None:
            spot_centres = np.empty((0, 2), dtype=float)
        self.spot_centres = validate_spot_centres(spot_centres)
        self.aperture_radii = normalise_aperture_radii(aperture_radii)
        self.dark_frame = None
        self.dark_frame_filename = None
        self.latest_frame = None
        self.latest_frame_counter = None
        self.selected_spot_index = 0
        self.last_error_message = None

        self.frame_queue = queue.Queue(maxsize=1)
        self.error_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.camera_thread = None
        self.refresh_after_id = None

        self.root = tk.Tk()
        self.root.title(window_name)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.status_var = tk.StringVar(value="Connecting to camera server...")
        self.total_power_var = tk.StringVar(value="Total spot power: --")
        self.aperture_y_var = tk.StringVar(value=f"{self.aperture_radii[0]:g}")
        self.aperture_x_var = tk.StringVar(value=f"{self.aperture_radii[1]:g}")
        self.use_dark_frame_var = tk.BooleanVar(value=False)
        self.normalise_bars_var = tk.BooleanVar(value=True)
        self.selected_spot_var = tk.IntVar(value=1)

        self.figure = Figure(figsize=(12, 6))
        grid = self.figure.add_gridspec(2, 2, width_ratios=(1.7, 1.0))
        self.frame_axis = self.figure.add_subplot(grid[:, 0])
        self.aperture_axis = self.figure.add_subplot(grid[0, 1])
        self.power_axis = self.figure.add_subplot(grid[1, 1])
        self.figure.subplots_adjust(
            left=0.06,
            right=0.98,
            bottom=0.10,
            top=0.92,
            wspace=0.25,
            hspace=0.38,
        )

        self.frame_image_artist = None
        self.aperture_image_artist = None
        self.spot_ellipse_artists = []
        self.spot_label_artists = []
        self.power_bar_artists = []
        self.plot_configuration_dirty = True

        self._build_layout()
        self._write_centres_to_editor()
        self._draw_empty_plots()

        if dark_frame_filename:
            self._load_dark_frame(dark_frame_filename)

        self.camera_thread = threading.Thread(
            target=self._read_camera_frames,
            name="spot-power-camera-reader",
            daemon=True,
        )
        self.camera_thread.start()
        self._schedule_refresh()

    def _build_layout(self):
        tk = self.tk
        ttk = self.ttk

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        self.canvas = self.FigureCanvasTkAgg(self.figure, master=main)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.canvas.mpl_connect("button_press_event", self._on_plot_click)

        controls = ttk.Frame(main, padding=(10, 0, 0, 0))
        controls.grid(row=0, column=1, sticky="ns")

        centres_group = ttk.LabelFrame(
            controls,
            text="Spot centres (one y, x pair per line)",
            padding=8,
        )
        centres_group.grid(row=0, column=0, sticky="ew")
        self.centres_text = tk.Text(centres_group, width=25, height=12, wrap="none")
        self.centres_text.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(
            centres_group,
            text="Apply centres",
            command=self.apply_centres,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(
            centres_group,
            text="Load centres...",
            command=self.choose_centres_file,
        ).grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(
            centres_group,
            text="Save centres...",
            command=self.choose_save_centres_file,
        ).grid(row=2, column=1, sticky="ew", pady=(6, 0))

        aperture_group = ttk.LabelFrame(
            controls,
            text="Spot aperture / ROI",
            padding=8,
        )
        aperture_group.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(aperture_group, text="Y radius (pixels)").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(aperture_group, textvariable=self.aperture_y_var, width=10).grid(
            row=0, column=1, sticky="ew"
        )
        ttk.Label(aperture_group, text="X radius (pixels)").grid(
            row=1, column=0, sticky="w"
        )
        ttk.Entry(aperture_group, textvariable=self.aperture_x_var, width=10).grid(
            row=1, column=1, sticky="ew"
        )
        ttk.Button(
            aperture_group,
            text="Apply aperture",
            command=self.apply_aperture,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        selection_group = ttk.LabelFrame(controls, text="Display", padding=8)
        selection_group.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(selection_group, text="Selected spot").grid(
            row=0, column=0, sticky="w"
        )
        self.selected_spot_spinbox = ttk.Spinbox(
            selection_group,
            from_=1,
            to=max(1, len(self.spot_centres)),
            textvariable=self.selected_spot_var,
            width=8,
            command=self._apply_selected_spot,
        )
        self.selected_spot_spinbox.grid(row=0, column=1, sticky="ew")
        self.selected_spot_spinbox.bind("<Return>", self._apply_selected_spot)
        self.selected_spot_spinbox.bind("<FocusOut>", self._apply_selected_spot)
        ttk.Checkbutton(
            selection_group,
            text="Show relative powers",
            variable=self.normalise_bars_var,
            command=self._redraw_current_frame,
        ).grid(row=1, column=0, columnspan=2, sticky="w")

        dark_group = ttk.LabelFrame(controls, text="Dark frame", padding=8)
        dark_group.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(
            dark_group,
            text="Load dark frame...",
            command=self.choose_dark_frame_file,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Checkbutton(
            dark_group,
            text="Subtract loaded dark frame",
            variable=self.use_dark_frame_var,
            command=self._redraw_current_frame,
        ).grid(row=1, column=0, sticky="w")

        ttk.Label(
            controls,
            textvariable=self.total_power_var,
            font=("TkDefaultFont", 11, "bold"),
        ).grid(row=4, column=0, sticky="w", pady=(12, 0))
        ttk.Label(
            controls,
            textvariable=self.status_var,
            wraplength=260,
        ).grid(row=5, column=0, sticky="w", pady=(6, 0))

    def _write_centres_to_editor(self):
        self.centres_text.delete("1.0", self.tk.END)
        for centre_y, centre_x in self.spot_centres:
            self.centres_text.insert(self.tk.END, f"{centre_y:g}, {centre_x:g}\n")

    def _draw_empty_plots(self):
        self.frame_axis.set_title("Waiting for camera frame")
        self.frame_axis.set_axis_off()
        self.aperture_axis.set_title("Selected aperture")
        self.aperture_axis.set_axis_off()
        self.power_axis.set_title("Spot powers")
        self.power_axis.set_xlabel("Spot index")
        self.canvas.draw_idle()

    def _read_camera_frames(self):
        from JazLabs.hardware.Cameras.Camera_Client import CameraClient

        camera = None
        last_frame_counter = None

        try:
            camera = CameraClient(
                host=self.host,
                command_port=self.command_port,
                frame_pub_port=self.frame_pub_port,
                timeout_ms=1000,
                client_id="spot_power_viewer",
            )

            while not self.stop_event.is_set():
                software_trigger_mode = camera.IsSoftwareTriggerMode()

                if software_trigger_mode:
                    current_counter = camera.GetFrameCounter()
                    if current_counter == last_frame_counter:
                        time.sleep(0.01)
                        continue
                    frame = camera.GetFrame(WaitForNewFrame=False)
                else:
                    frame = camera.GetFrame(
                        WaitForNewFrame=True,
                        LastFrameCounter=last_frame_counter,
                    )

                last_frame_counter = camera.GetFrameCounter()
                frame_item = (last_frame_counter, frame)

                try:
                    self.frame_queue.put_nowait(frame_item)
                except queue.Full:
                    try:
                        self.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    self.frame_queue.put_nowait(frame_item)
        except Exception:
            self.error_queue.put(traceback.format_exc())
        finally:
            if camera is not None:
                camera.close()

    def _schedule_refresh(self):
        self.refresh_after_id = self.root.after(self.refresh_ms, self._refresh_display)

    def _refresh_display(self):
        self.refresh_after_id = None

        try:
            error_message = self.error_queue.get_nowait()
        except queue.Empty:
            error_message = None

        if error_message is not None:
            self.last_error_message = error_message
            final_line = error_message.strip().splitlines()[-1]
            self.status_var.set(f"Camera error: {final_line}")

        newest_item = None
        while True:
            try:
                newest_item = self.frame_queue.get_nowait()
            except queue.Empty:
                break

        if newest_item is not None:
            self.latest_frame_counter, self.latest_frame = newest_item
            self._analyse_and_draw_latest_frame()

        if not self.stop_event.is_set():
            self._schedule_refresh()

    def _analyse_and_draw_latest_frame(self):
        try:
            analysis_frame = prepare_analysis_frame(
                self.latest_frame,
                dark_frame=self.dark_frame,
                use_dark_frame=self.use_dark_frame_var.get(),
            )
            (
                absolute_powers,
                relative_powers,
                total_power,
                aperture_views,
            ) = analyse_spot_powers(
                analysis_frame,
                self.spot_centres,
                self.aperture_radii,
            )
        except Exception as error:
            error_text = str(error)
            if error_text != self.last_error_message:
                self.status_var.set(f"Analysis error: {error_text}")
                self.last_error_message = error_text
            return

        self.last_error_message = None
        dark_state = "on" if self.use_dark_frame_var.get() else "off"
        self.status_var.set(
            f"Frame {self.latest_frame_counter} | "
            f"{len(self.spot_centres)} spots | dark subtraction {dark_state}"
        )
        self.total_power_var.set(f"Total spot power: {total_power:.6g}")

        frame_height, frame_width = analysis_frame.shape
        frame_minimum = float(np.nanmin(analysis_frame))
        frame_maximum = float(np.nanmax(analysis_frame))
        if frame_maximum <= frame_minimum:
            frame_maximum = frame_minimum + 1.0

        if self.frame_image_artist is None:
            self.frame_axis.set_axis_on()
            self.frame_image_artist = self.frame_axis.imshow(
                analysis_frame,
                cmap="gray",
                vmin=frame_minimum,
                vmax=frame_maximum,
            )
            self.frame_axis.set_title("Live camera frame")
            self.frame_axis.set_xlabel("x (pixels)")
            self.frame_axis.set_ylabel("y (pixels)")
        else:
            self.frame_image_artist.set_data(analysis_frame)
            self.frame_image_artist.set_clim(frame_minimum, frame_maximum)
            self.frame_image_artist.set_extent(
                (-0.5, frame_width - 0.5, frame_height - 0.5, -0.5)
            )
            self.frame_axis.set_xlim(-0.5, frame_width - 0.5)
            self.frame_axis.set_ylim(frame_height - 0.5, -0.5)

        from matplotlib.patches import Ellipse

        radius_y, radius_x = self.aperture_radii
        if self.plot_configuration_dirty:
            for ellipse_artist in self.spot_ellipse_artists:
                ellipse_artist.remove()
            for label_artist in self.spot_label_artists:
                label_artist.remove()

            self.spot_ellipse_artists = []
            self.spot_label_artists = []

            for spot_index, (centre_y, centre_x) in enumerate(self.spot_centres):
                is_selected = spot_index == self.selected_spot_index
                colour = "red" if is_selected else "lime"
                linewidth = 2.0 if is_selected else 1.0
                aperture = Ellipse(
                    (centre_x, centre_y),
                    width=2 * radius_x,
                    height=2 * radius_y,
                    fill=False,
                    edgecolor=colour,
                    linewidth=linewidth,
                )
                self.frame_axis.add_patch(aperture)
                self.spot_ellipse_artists.append(aperture)

                label = self.frame_axis.text(
                    centre_x + radius_x,
                    centre_y - radius_y,
                    str(spot_index + 1),
                    color=colour,
                    fontsize=8,
                )
                self.spot_label_artists.append(label)

        if aperture_views:
            selected_index = min(self.selected_spot_index, len(aperture_views) - 1)
            selected_aperture_view = aperture_views[selected_index]
            aperture_minimum = float(np.nanmin(selected_aperture_view))
            aperture_maximum = float(np.nanmax(selected_aperture_view))
            if aperture_maximum <= aperture_minimum:
                aperture_maximum = aperture_minimum + 1.0

            if self.aperture_image_artist is None:
                self.aperture_image_artist = self.aperture_axis.imshow(
                    selected_aperture_view,
                    cmap="gray",
                    vmin=aperture_minimum,
                    vmax=aperture_maximum,
                )
            else:
                aperture_height, aperture_width = selected_aperture_view.shape
                self.aperture_image_artist.set_visible(True)
                self.aperture_image_artist.set_data(selected_aperture_view)
                self.aperture_image_artist.set_clim(
                    aperture_minimum,
                    aperture_maximum,
                )
                self.aperture_image_artist.set_extent(
                    (
                        -0.5,
                        aperture_width - 0.5,
                        aperture_height - 0.5,
                        -0.5,
                    )
                )
                self.aperture_axis.set_xlim(-0.5, aperture_width - 0.5)
                self.aperture_axis.set_ylim(aperture_height - 0.5, -0.5)

            self.aperture_axis.set_title(f"Spot {selected_index + 1} aperture")
        else:
            if self.aperture_image_artist is not None:
                self.aperture_image_artist.set_visible(False)
            self.aperture_axis.set_title("No spot centres configured")
        self.aperture_axis.set_axis_off()

        displayed_powers = (
            relative_powers if self.normalise_bars_var.get() else absolute_powers
        )
        spot_numbers = np.arange(1, len(displayed_powers) + 1)
        bar_colours = [
            "tab:red" if index == self.selected_spot_index else "tab:blue"
            for index in range(len(displayed_powers))
        ]

        if len(self.power_bar_artists) != len(displayed_powers):
            for bar_artist in self.power_bar_artists:
                bar_artist.remove()
            self.power_bar_artists = list(
                self.power_axis.bar(
                    spot_numbers,
                    displayed_powers,
                    color=bar_colours,
                )
            )
            self.power_axis.set_xticks(spot_numbers)
        else:
            for spot_index, bar_artist in enumerate(self.power_bar_artists):
                bar_artist.set_height(displayed_powers[spot_index])
                bar_artist.set_color(bar_colours[spot_index])

        self.power_axis.set_ylabel(
            "Relative power" if self.normalise_bars_var.get() else "Power (camera counts)"
        )
        maximum_displayed_power = (
            float(np.max(displayed_powers)) if len(displayed_powers) else 0.0
        )
        if self.normalise_bars_var.get():
            self.power_axis.set_ylim(0.0, max(1.0, 1.05 * maximum_displayed_power))
        else:
            self.power_axis.set_ylim(0.0, max(1.0, 1.05 * maximum_displayed_power))

        self.plot_configuration_dirty = False
        self.canvas.draw_idle()

    def _redraw_current_frame(self):
        if self.latest_frame is not None:
            self._analyse_and_draw_latest_frame()

    def apply_centres(self):
        try:
            centres = parse_spot_centres(self.centres_text.get("1.0", self.tk.END))
        except Exception as error:
            self.status_var.set(f"Centre error: {error}")
            return

        self.spot_centres = centres
        self.selected_spot_index = min(
            self.selected_spot_index,
            max(0, len(self.spot_centres) - 1),
        )
        self.selected_spot_var.set(self.selected_spot_index + 1)
        self.selected_spot_spinbox.configure(to=max(1, len(self.spot_centres)))
        self.plot_configuration_dirty = True
        self.status_var.set(f"Applied {len(self.spot_centres)} spot centres.")
        self._redraw_current_frame()

    def apply_aperture(self):
        try:
            self.aperture_radii = normalise_aperture_radii(
                (float(self.aperture_y_var.get()), float(self.aperture_x_var.get()))
            )
        except Exception as error:
            self.status_var.set(f"Aperture error: {error}")
            return

        self.status_var.set(
            "Applied aperture radii "
            f"(y={self.aperture_radii[0]:g}, x={self.aperture_radii[1]:g})."
        )
        self.plot_configuration_dirty = True
        self._redraw_current_frame()

    def _apply_selected_spot(self, event=None):
        del event
        try:
            requested_index = int(self.selected_spot_var.get()) - 1
        except (TypeError, ValueError):
            requested_index = self.selected_spot_index

        if self.spot_centres.size:
            requested_index = max(0, min(requested_index, len(self.spot_centres) - 1))
        else:
            requested_index = 0

        self.selected_spot_index = requested_index
        self.selected_spot_var.set(requested_index + 1)
        self.plot_configuration_dirty = True
        self._redraw_current_frame()

    def _on_plot_click(self, event):
        if event.inaxes is not self.frame_axis:
            return
        if event.xdata is None or event.ydata is None:
            return

        if self.spot_centres.size:
            offsets = self.spot_centres - np.array([event.ydata, event.xdata])
            nearest_index = int(np.argmin(np.sum(offsets**2, axis=1)))
            radius_y, radius_x = self.aperture_radii
            normalised_distance = (
                (offsets[nearest_index, 0] / radius_y) ** 2
                + (offsets[nearest_index, 1] / radius_x) ** 2
            )

            if normalised_distance <= 4.0:
                self.selected_spot_index = nearest_index
                self.selected_spot_var.set(nearest_index + 1)
                self.plot_configuration_dirty = True
                self._redraw_current_frame()
                return

        self.spot_centres = np.vstack(
            [self.spot_centres, [float(event.ydata), float(event.xdata)]]
        )
        self.selected_spot_index = len(self.spot_centres) - 1
        self.selected_spot_var.set(self.selected_spot_index + 1)
        self.selected_spot_spinbox.configure(to=len(self.spot_centres))
        self._write_centres_to_editor()
        self.plot_configuration_dirty = True
        self._redraw_current_frame()

    def choose_centres_file(self):
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            title="Load spot centres",
            filetypes=[
                ("Supported arrays", "*.npy *.npz *.csv *.txt"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return

        try:
            self.spot_centres = load_spot_centres_file(filename)
        except Exception as error:
            self.status_var.set(f"Could not load centres: {error}")
            return

        self.selected_spot_index = 0
        self.selected_spot_var.set(1)
        self.selected_spot_spinbox.configure(to=max(1, len(self.spot_centres)))
        self._write_centres_to_editor()
        self.plot_configuration_dirty = True
        self.status_var.set(f"Loaded {len(self.spot_centres)} centres from {filename}.")
        self._redraw_current_frame()

    def choose_save_centres_file(self):
        from tkinter import filedialog

        filename = filedialog.asksaveasfilename(
            title="Save spot centres",
            defaultextension=".npy",
            filetypes=[
                ("NumPy array", "*.npy"),
                ("Compressed NumPy array", "*.npz"),
                ("Comma-separated values", "*.csv"),
                ("Text file", "*.txt"),
            ],
        )
        if not filename:
            return

        try:
            centres = parse_spot_centres(
                self.centres_text.get("1.0", self.tk.END)
            )
            save_spot_centres_file(filename, centres)
        except Exception as error:
            self.status_var.set(f"Could not save centres: {error}")
            return

        self.spot_centres = centres
        self.selected_spot_index = min(
            self.selected_spot_index,
            max(0, len(self.spot_centres) - 1),
        )
        self.selected_spot_var.set(self.selected_spot_index + 1)
        self.selected_spot_spinbox.configure(to=max(1, len(self.spot_centres)))
        self.plot_configuration_dirty = True
        self.status_var.set(
            f"Saved {len(self.spot_centres)} spot centres to {filename}."
        )
        self._redraw_current_frame()

    def choose_dark_frame_file(self):
        from tkinter import filedialog

        filename = filedialog.askopenfilename(
            title="Load dark frame",
            filetypes=[
                ("Supported arrays/images", "*.npy *.npz *.csv *.txt *.tif *.tiff *.png"),
                ("All files", "*.*"),
            ],
        )
        if filename:
            self._load_dark_frame(filename)

    def _load_dark_frame(self, filename):
        try:
            dark_frame = load_array_file(filename)
        except Exception as error:
            self.status_var.set(f"Could not load dark frame: {error}")
            return

        if self.latest_frame is not None and dark_frame.shape != self.latest_frame.shape:
            self.status_var.set(
                f"Dark frame shape {dark_frame.shape} does not match "
                f"camera frame shape {self.latest_frame.shape}."
            )
            return

        self.dark_frame = dark_frame
        self.dark_frame_filename = str(filename)
        self.use_dark_frame_var.set(True)
        self.status_var.set(f"Loaded dark frame: {filename}")
        self._redraw_current_frame()

    def run(self):
        self.root.mainloop()

    def close(self):
        self.stop_event.set()

        if self.refresh_after_id is not None:
            try:
                self.root.after_cancel(self.refresh_after_id)
            except Exception:
                pass
            self.refresh_after_id = None

        if self.camera_thread is not None:
            self.camera_thread.join(timeout=1.5)

        self.root.destroy()


def SpotPowerViewerProcess(
    host="127.0.0.1",
    command_port=50731,
    frame_pub_port=50732,
    spot_centres=None,
    aperture_radii=(3, 3),
    dark_frame_filename=None,
    refresh_ms=100,
    window_name="Spot Power Viewer",
):
    window = SpotPowerWindow(
        host=host,
        command_port=command_port,
        frame_pub_port=frame_pub_port,
        spot_centres=spot_centres,
        aperture_radii=aperture_radii,
        dark_frame_filename=dark_frame_filename,
        refresh_ms=refresh_ms,
        window_name=window_name,
    )
    window.run()


class SpotPowerViewer:
    """Launch and manage a live spot-power window in a separate process."""

    def __init__(
        self,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        spot_centres=None,
        aperture_radii=(3, 3),
        dark_frame_filename=None,
        refresh_ms=100,
        window_name="Spot Power Viewer",
    ):
        self.host = host
        self.command_port = int(command_port)
        self.frame_pub_port = int(frame_pub_port)
        self.spot_centres = validate_spot_centres(
            np.empty((0, 2)) if spot_centres is None else spot_centres
        )
        self.aperture_radii = normalise_aperture_radii(aperture_radii)
        self.dark_frame_filename = dark_frame_filename
        self.refresh_ms = int(refresh_ms)
        self.window_name = window_name
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Spot-power viewer already running.")
            return

        self.Process = mp.Process(
            target=SpotPowerViewerProcess,
            kwargs={
                "host": self.host,
                "command_port": self.command_port,
                "frame_pub_port": self.frame_pub_port,
                "spot_centres": self.spot_centres,
                "aperture_radii": self.aperture_radii,
                "dark_frame_filename": self.dark_frame_filename,
                "refresh_ms": self.refresh_ms,
                "window_name": self.window_name,
            },
            daemon=False,
        )
        self.Process.start()
        print(f"Spot-power viewer started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is None:
            return

        if self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)

        self.Process = None


if __name__ == "__main__":
    mp.freeze_support()
    viewer = SpotPowerViewer()
    viewer.startProcess()
    viewer.Process.join()
