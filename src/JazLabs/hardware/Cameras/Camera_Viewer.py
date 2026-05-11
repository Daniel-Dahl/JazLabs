import time
import multiprocessing as mp
import numpy as np
import cv2

from pwi_inst.hardware.Cameras.Camera_Client import CameraClient


def GetHardwareRangeFromDtype(frame):
    if frame.dtype == np.uint8:
        return 0, 255
    if frame.dtype == np.uint16:
        return 0, 65535
    if frame.dtype == np.int16:
        return -32768, 32767

    return float(np.nanmin(frame)), float(np.nanmax(frame))


def GetHardwareRangeFromPixelFormat(pixel_format, frame=None):
    """
    Use the camera's real pixel format, not the NumPy dtype.
    Example: SDK returns uint16, but camera format is Mono12.
    """
    if pixel_format is None:
        if frame is not None:
            return GetHardwareRangeFromDtype(frame)
        return 0, 65535

    pf = str(pixel_format).lower()

    if "mono8" in pf or "8" in pf:
        return 0, 255
    if "mono10" in pf or "10" in pf:
        return 0, 1023
    if "mono12" in pf or "12" in pf:
        return 0, 4095
    if "mono14" in pf or "14" in pf:
        return 0, 16383
    if "mono16" in pf or "16" in pf:
        return 0, 65535

    if frame is not None:
        return GetHardwareRangeFromDtype(frame)

    return 0, 65535


def MapFrameToDisplay(
    frame,
    hw_min,
    hw_max,
    use_manual_contrast=False,
    display_min=None,
    display_max=None,
    use_log_scale=False,
):
    if use_manual_contrast:
        disp_min = hw_min if display_min is None else display_min
        disp_max = hw_max if display_max is None else display_max
    else:
        disp_min = hw_min
        disp_max = hw_max

    if disp_max <= disp_min:
        return np.zeros(frame.shape, dtype=np.uint8)

    frame_float = frame.astype(np.float32)
    frame_float = np.clip(frame_float, disp_min, disp_max)
    frame_float = frame_float - disp_min

    if use_log_scale:
        frame_float = np.log1p(frame_float)
        denom = np.log1p(disp_max - disp_min)
    else:
        denom = disp_max - disp_min

    if denom <= 0:
        return np.zeros(frame.shape, dtype=np.uint8)

    frame_float = frame_float / denom

    return (255 * frame_float).clip(0, 255).astype(np.uint8)


def ROIToBox(roi_centre, roi_x_half_width, roi_y_half_width):
    if roi_centre is None or roi_x_half_width is None or roi_y_half_width is None:
        return None

    cy, cx = roi_centre

    return (
        int(cx - roi_x_half_width),
        int(cy - roi_y_half_width),
        int(cx + roi_x_half_width),
        int(cy + roi_y_half_width),
    )


def ClipROIToFrame(roi, frame_shape):
    if roi is None:
        return None

    h, w = frame_shape[:2]
    x0, y0, x1, y1 = roi

    x0, x1 = sorted([int(x0), int(x1)])
    y0, y1 = sorted([int(y0), int(y1)])

    x0 = max(x0, 0)
    y0 = max(y0, 0)
    x1 = min(x1, w - 1)
    y1 = min(y1, h - 1)

    return x0, y0, x1, y1


def DrawROI(image, roi, view_x0, view_y0, scale):
    if roi is None:
        return image

    x0, y0, x1, y1 = roi
    x0, x1 = sorted([int(x0), int(x1)])
    y0, y1 = sorted([int(y0), int(y1)])

    sx0 = int((x0 - view_x0) * scale)
    sy0 = int((y0 - view_y0) * scale)
    sx1 = int((x1 - view_x0) * scale)
    sy1 = int((y1 - view_y0) * scale)

    cv2.rectangle(image, (sx0, sy0), (sx1, sy1), (0, 0, 255), 2)

    cx = int((sx0 + sx1) / 2)
    cy = int((sy0 + sy1) / 2)

    cv2.drawMarker(
        image,
        (cx, cy),
        (0, 0, 255),
        markerType=cv2.MARKER_CROSS,
        markerSize=12,
        thickness=2,
    )

    return image


def CropAndScaleImage(display, view_x0, view_y0, view_w, view_h, scale):
    h, w = display.shape[:2]

    view_x0 = int(max(0, min(view_x0, w - 1)))
    view_y0 = int(max(0, min(view_y0, h - 1)))
    view_w = int(max(1, min(view_w, w - view_x0)))
    view_h = int(max(1, min(view_h, h - view_y0)))

    cropped = display[view_y0:view_y0 + view_h, view_x0:view_x0 + view_w]

    if scale != 1.0:
        cropped = cv2.resize(
            cropped,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_NEAREST,
        )

    return cropped


def AddInfoPanel(
    image,
    raw_frame,
    hw_min,
    hw_max,
    pixel_format=None,
    mouse_x=None,
    mouse_y=None,
    roi=None,
    scale=1.0,
    use_manual_contrast=False,
    display_min=None,
    display_max=None,
    frame_counter=None,
    use_log_scale=False,
    view_x0=0,
    view_y0=0,
    view_w=None,
    view_h=None,
):
    h, w = raw_frame.shape[:2]

    raw_min = np.min(raw_frame)
    raw_max = np.max(raw_frame)

    saturated_pixels = int(np.sum(raw_frame >= hw_max))
    saturated_fraction = saturated_pixels / raw_frame.size

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1
    margin = 8
    line_height = 18

    if view_w is None:
        view_w = w
    if view_h is None:
        view_h = h

    lines = []
    lines.append(f"Frame: {raw_frame.shape} | counter: {frame_counter}")
    lines.append(f"PixelFormat: {pixel_format} | dtype: {raw_frame.dtype}")
    lines.append(f"Range: {hw_min} to {hw_max} | Raw min/max: {raw_min} / {raw_max}")

    if saturated_pixels > 0:
        lines.append(
            f"SATURATION: YES | pixels: {saturated_pixels} "
            f"({100 * saturated_fraction:.4f}%)"
        )
    else:
        lines.append("SATURATION: no")

    if use_manual_contrast:
        lines.append(f"Contrast: MANUAL | {display_min} to {display_max}")
    else:
        lines.append("Contrast: PIXELFORMAT RANGE")

    lines.append(
        f"Display: {'LOG' if use_log_scale else 'LINEAR'} | "
        f"Scale: {scale:.2f} | "
        f"View: x={view_x0}:{view_x0 + view_w}, y={view_y0}:{view_y0 + view_h}"
    )

    if mouse_x is not None and mouse_y is not None:
        if 0 <= mouse_x < w and 0 <= mouse_y < h:
            value = raw_frame[mouse_y, mouse_x]
            lines.append(f"Cursor: ({mouse_x},{mouse_y}) = {value}")

    if roi is not None:
        roi_clipped = ClipROIToFrame(roi, raw_frame.shape)

        if roi_clipped is not None:
            x0, y0, x1, y1 = roi_clipped

            roi_cx = int((x0 + x1) / 2)
            roi_cy = int((y0 + y1) / 2)
            roi_width = int(abs(x1 - x0) + 1)
            roi_height = int(abs(y1 - y0) + 1)

            roi_frame = raw_frame[y0:y1 + 1, x0:x1 + 1]

            lines.append(
                f"ROI centre: ({roi_cx},{roi_cy}) | "
                f"size: {roi_width} x {roi_height}"
            )

            if roi_frame.size > 0:
                roi_sat = int(np.sum(roi_frame >= hw_max))
                roi_sat_frac = roi_sat / roi_frame.size

                lines.append(
                    f"ROI x={x0}:{x1}, y={y0}:{y1} | "
                    f"mean={np.mean(roi_frame):.2f}, "
                    f"max={np.max(roi_frame)}, "
                    f"sat={100 * roi_sat_frac:.4f}%"
                )

    lines.append("q quit | +/- zoom | 0 reset | l log | a contrast | r reset contrast")
    lines.append("[/] min cap | ;/' max cap | c clear ROI")
    lines.append("arrows move ROI | i/o x-size | y/u y-size | drag mouse ROI")

    panel_height = margin * 2 + line_height * len(lines)
    panel = np.zeros((panel_height, image.shape[1], 3), dtype=np.uint8)
    panel[:] = (30, 30, 30)

    for i, line in enumerate(lines):
        y = margin + (i + 1) * line_height - 4

        colour = (255, 255, 255)
        if "SATURATION: YES" in line:
            colour = (0, 0, 255)

        cv2.putText(
            panel,
            line,
            (margin, y),
            font,
            font_scale,
            colour,
            thickness,
            cv2.LINE_AA,
        )

    return np.vstack([image, panel])


def CameraViewerProcess(
    host="127.0.0.1",
    command_port=50731,
    frame_pub_port=50732,
    window_name="Camera Viewer",
    initial_scale=1.0,
    wait_for_new_frame=True,
    update_pixel_format_every_frame=False,
    max_window_width=1200,
    max_window_height=900,
    roi_move_step=1,
    roi_size_step=1,
):
    cam = CameraClient(
        host=host,
        command_port=command_port,
        frame_pub_port=frame_pub_port,
        client_id="opencv_viewer",
    )

    scale = float(initial_scale)
    use_log_scale = False

    use_manual_contrast = False
    display_min = None
    display_max = None

    roi_centre = None          # (cy, cx)
    roi_x_half_width = None
    roi_y_half_width = None

    drawing_roi = False
    roi_start = None
    roi_current = None

    mouse_x = None
    mouse_y = None

    view_x0 = 0
    view_y0 = 0
    view_w = None
    view_h = None

    last_frame_counter = None

    try:
        pixel_format = cam.GetPixelFormat()
    except Exception:
        pixel_format = None

    def ScreenToRaw(x, y):
        raw_x = int(view_x0 + x / scale)
        raw_y = int(view_y0 + y / scale)
        return raw_x, raw_y

    def UpdateViewForScale(frame_shape, old_scale, new_scale, anchor_raw_x=None, anchor_raw_y=None):
        nonlocal view_x0, view_y0, view_w, view_h, scale

        frame_h, frame_w = frame_shape[:2]

        if anchor_raw_x is None:
            anchor_raw_x = view_x0 + (view_w or frame_w) / 2
        if anchor_raw_y is None:
            anchor_raw_y = view_y0 + (view_h or frame_h) / 2

        scale = new_scale

        target_display_w = min(max_window_width, int(frame_w * scale))
        target_display_h = min(max_window_height, int(frame_h * scale))

        view_w = int(max(1, min(frame_w, target_display_w / scale)))
        view_h = int(max(1, min(frame_h, target_display_h / scale)))

        view_x0 = int(anchor_raw_x - view_w / 2)
        view_y0 = int(anchor_raw_y - view_h / 2)

        view_x0 = max(0, min(view_x0, frame_w - view_w))
        view_y0 = max(0, min(view_y0, frame_h - view_h))

    def ResetView(frame_shape):
        nonlocal view_x0, view_y0, view_w, view_h, scale

        frame_h, frame_w = frame_shape[:2]
        scale = float(initial_scale)

        target_display_w = min(max_window_width, int(frame_w * scale))
        target_display_h = min(max_window_height, int(frame_h * scale))

        view_w = int(max(1, min(frame_w, target_display_w / scale)))
        view_h = int(max(1, min(frame_h, target_display_h / scale)))

        view_x0 = int((frame_w - view_w) / 2)
        view_y0 = int((frame_h - view_h) / 2)

    def mouse_callback(event, x, y, flags, param):
        nonlocal mouse_x, mouse_y
        nonlocal drawing_roi, roi_start, roi_current
        nonlocal roi_centre, roi_x_half_width, roi_y_half_width
        nonlocal scale

        raw_x, raw_y = ScreenToRaw(x, y)
        mouse_x = raw_x
        mouse_y = raw_y

        if event == cv2.EVENT_LBUTTONDOWN:
            drawing_roi = True
            roi_start = (raw_x, raw_y)
            roi_current = (raw_x, raw_y)

        elif event == cv2.EVENT_MOUSEMOVE:
            if drawing_roi:
                roi_current = (raw_x, raw_y)

        elif event == cv2.EVENT_LBUTTONUP:
            drawing_roi = False
            roi_current = (raw_x, raw_y)

            if roi_start is not None and roi_current is not None:
                x0, y0 = roi_start
                x1, y1 = roi_current

                if abs(x1 - x0) > 2 and abs(y1 - y0) > 2:
                    roi_cx = int((x0 + x1) / 2)
                    roi_cy = int((y0 + y1) / 2)

                    roi_centre = (roi_cy, roi_cx)
                    roi_x_half_width = max(1, int(abs(x1 - x0) / 2))
                    roi_y_half_width = max(1, int(abs(y1 - y0) / 2))

        elif event == cv2.EVENT_MOUSEWHEEL:
            old_scale = scale

            if flags > 0:
                new_scale = scale * 1.25
            else:
                new_scale = scale / 1.25

            new_scale = max(0.05, min(new_scale, 50.0))

            UpdateViewForScale(
                param["frame_shape"],
                old_scale=old_scale,
                new_scale=new_scale,
                anchor_raw_x=raw_x,
                anchor_raw_y=raw_y,
            )

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    mouse_param = {"frame_shape": (1, 1)}
    cv2.setMouseCallback(window_name, mouse_callback, mouse_param)

    try:
        while True:
            frame = cam.GetFrame(
                WaitForNewFrame=wait_for_new_frame,
                LastFrameCounter=last_frame_counter,
            )

            frame_counter = cam.GetFrameCounter()
            last_frame_counter = frame_counter

            frame_h, frame_w = frame.shape[:2]

            mouse_param["frame_shape"] = frame.shape

            if view_w is None or view_h is None:
                ResetView(frame.shape)

            if update_pixel_format_every_frame:
                try:
                    pixel_format = cam.GetPixelFormat()
                except Exception:
                    pass

            hw_min, hw_max = GetHardwareRangeFromPixelFormat(
                pixel_format,
                frame=frame,
            )

            if display_min is None:
                display_min = hw_min

            if display_max is None:
                display_max = hw_max

            full_display = MapFrameToDisplay(
                frame,
                hw_min=hw_min,
                hw_max=hw_max,
                use_manual_contrast=use_manual_contrast,
                display_min=display_min,
                display_max=display_max,
                use_log_scale=use_log_scale,
            )

            full_display = cv2.cvtColor(full_display, cv2.COLOR_GRAY2BGR)

            display = CropAndScaleImage(
                full_display,
                view_x0=view_x0,
                view_y0=view_y0,
                view_w=view_w,
                view_h=view_h,
                scale=scale,
            )

            active_roi = ROIToBox(
                roi_centre,
                roi_x_half_width,
                roi_y_half_width,
            )

            if drawing_roi and roi_start is not None and roi_current is not None:
                active_roi = (
                    roi_start[0],
                    roi_start[1],
                    roi_current[0],
                    roi_current[1],
                )

            display = DrawROI(
                display,
                active_roi,
                view_x0=view_x0,
                view_y0=view_y0,
                scale=scale,
            )

            display = AddInfoPanel(
                display,
                frame,
                hw_min=hw_min,
                hw_max=hw_max,
                pixel_format=pixel_format,
                mouse_x=mouse_x,
                mouse_y=mouse_y,
                roi=active_roi,
                scale=scale,
                use_manual_contrast=use_manual_contrast,
                display_min=display_min,
                display_max=display_max,
                frame_counter=frame_counter,
                use_log_scale=use_log_scale,
                view_x0=view_x0,
                view_y0=view_y0,
                view_w=view_w,
                view_h=view_h,
            )

            cv2.imshow(window_name, display)

            h, w = display.shape[:2]
            cv2.resizeWindow(window_name, w, h)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key in [ord("+"), ord("=")]:
                old_scale = scale
                new_scale = min(scale * 1.25, 50.0)
                UpdateViewForScale(
                    frame.shape,
                    old_scale=old_scale,
                    new_scale=new_scale,
                    anchor_raw_x=mouse_x,
                    anchor_raw_y=mouse_y,
                )

            elif key in [ord("-"), ord("_")]:
                old_scale = scale
                new_scale = max(scale / 1.25, 0.05)
                UpdateViewForScale(
                    frame.shape,
                    old_scale=old_scale,
                    new_scale=new_scale,
                    anchor_raw_x=mouse_x,
                    anchor_raw_y=mouse_y,
                )

            elif key == ord("0"):
                ResetView(frame.shape)

            elif key == ord("l"):
                use_log_scale = not use_log_scale

            elif key == ord("a"):
                use_manual_contrast = not use_manual_contrast

            elif key == ord("r"):
                use_manual_contrast = False
                display_min = hw_min
                display_max = hw_max

            elif key == ord("c"):
                roi_centre = None
                roi_x_half_width = None
                roi_y_half_width = None
                roi_start = None
                roi_current = None

            elif key == ord("p"):
                try:
                    pixel_format = cam.GetPixelFormat()
                    display_min = hw_min
                    display_max = hw_max
                except Exception:
                    pass
                
            elif key == ord("i"):
                if roi_x_half_width is not None:
                    roi_x_half_width = max(1, roi_x_half_width - roi_size_step)
            elif key == ord("o"):
                if roi_x_half_width is not None:
                    roi_x_half_width += roi_size_step
            elif key == ord("y"):
                if roi_y_half_width is not None:
                    roi_y_half_width = max(1, roi_y_half_width - roi_size_step)
            elif key == ord("u"):
                if roi_y_half_width is not None:
                    roi_y_half_width += roi_size_step

            

            elif key == ord("["):
                use_manual_contrast = True
                contrast_range = display_max - display_min
                display_min -= 0.05 * contrast_range

            elif key == ord("]"):
                use_manual_contrast = True
                contrast_range = display_max - display_min
                display_min += 0.05 * contrast_range

            elif key == ord(";"):
                use_manual_contrast = True
                contrast_range = display_max - display_min
                display_max -= 0.05 * contrast_range

            elif key == ord("'"):
                use_manual_contrast = True
                contrast_range = display_max - display_min
                display_max += 0.05 * contrast_range

            # Arrow keys.
            # These key codes work on many Linux/OpenCV builds.
            # Some systems may return different codes.
            elif key in [81, 2424832]:  # left
                if roi_centre is not None:
                    cy, cx = roi_centre
                    roi_centre = (cy, max(0, cx - roi_move_step))

            elif key in [83, 2555904]:  # right
                if roi_centre is not None:
                    cy, cx = roi_centre
                    roi_centre = (cy, min(frame_w - 1, cx + roi_move_step))

            elif key in [82, 2490368]:  # up
                if roi_centre is not None:
                    cy, cx = roi_centre
                    roi_centre = (max(0, cy - roi_move_step), cx)

            elif key in [84, 2621440]:  # down
                if roi_centre is not None:
                    cy, cx = roi_centre
                    roi_centre = (min(frame_h - 1, cy + roi_move_step), cx)

            display_min = max(display_min, hw_min)
            display_max = min(display_max, hw_max)

            if display_max <= display_min:
                display_min = hw_min
                display_max = hw_max

            if roi_centre is not None:
                cy, cx = roi_centre
                roi_centre = (
                    max(0, min(frame_h - 1, cy)),
                    max(0, min(frame_w - 1, cx)),
                )

    finally:
        cam.close()
        cv2.destroyWindow(window_name)


class CameraViewer:
    def __init__(
        self,
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        window_name="Camera Viewer",
        initial_scale=1.0,
        wait_for_new_frame=True,
        update_pixel_format_every_frame=False,
        max_window_width=1200,
        max_window_height=900,
        roi_move_step=1,
        roi_size_step=1,
    ):
        self.host = host
        self.command_port = int(command_port)
        self.frame_pub_port = int(frame_pub_port)
        self.window_name = window_name
        self.initial_scale = float(initial_scale)
        self.wait_for_new_frame = wait_for_new_frame
        self.update_pixel_format_every_frame = update_pixel_format_every_frame
        self.max_window_width = int(max_window_width)
        self.max_window_height = int(max_window_height)
        self.roi_move_step = int(roi_move_step)
        self.roi_size_step = int(roi_size_step)
        self.Process = None

    def startProcess(self):
        if self.Process is not None and self.Process.is_alive():
            print("Camera viewer already running.")
            return

        self.Process = mp.Process(
            target=CameraViewerProcess,
            kwargs={
                "host": self.host,
                "command_port": self.command_port,
                "frame_pub_port": self.frame_pub_port,
                "window_name": self.window_name,
                "initial_scale": self.initial_scale,
                "wait_for_new_frame": self.wait_for_new_frame,
                "update_pixel_format_every_frame": self.update_pixel_format_every_frame,
                "max_window_width": self.max_window_width,
                "max_window_height": self.max_window_height,
                "roi_move_step": self.roi_move_step,
                "roi_size_step": self.roi_size_step,
            },
            daemon=False,
        )

        self.Process.start()
        print(f"Camera viewer started with PID {self.Process.pid}")

    def stopProcess(self):
        if self.Process is None:
            return

        if self.Process.is_alive():
            self.Process.terminate()
            self.Process.join(timeout=1)

        self.Process = None


if __name__ == "__main__":
    mp.freeze_support()

    viewer = CameraViewer(
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        initial_scale=1.0,
    )

    viewer.startProcess()
