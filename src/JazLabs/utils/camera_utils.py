import numpy as np
import cv2
import matplotlib.pyplot as plt


# ============================================================
# ROI / APERTURE
# ============================================================

def get_aperture(
    frame: np.ndarray,
    centre=None,
    x_half_width=None,
    y_half_width=None,
):
    """
    Return ROI (aperture) from frame.

    Parameters
    ----------
    frame : np.ndarray
    centre : (cy, cx)
    x_half_width, y_half_width : int/float

    Returns
    -------
    roi : np.ndarray
    bounds : (y0, y1, x0, x1)
    """

    if centre is None or x_half_width is None or y_half_width is None:
        return frame, (0, frame.shape[0], 0, frame.shape[1])

    cy, cx = centre
    nrows, ncols = frame.shape

    y0 = max(int(cy - y_half_width), 0)
    y1 = min(int(cy + y_half_width), nrows)
    x0 = max(int(cx - x_half_width), 0)
    x1 = min(int(cx + x_half_width), ncols)

    roi = frame[y0:y1, x0:x1]

    return roi, (y0, y1, x0, x1)


# ============================================================
# POWER
# ============================================================

def compute_relative_power(
    frame: np.ndarray,
    centre=None,
    x_half_width=None,
    y_half_width=None,
):
    """
    Compute background-subtracted power in ROI.
    """

    bg = np.nanmedian(frame)

    roi, _ = get_aperture(
        frame,
        centre=centre,
        x_half_width=x_half_width,
        y_half_width=y_half_width,
    )

    return np.nansum(roi - bg)


def get_relative_power(
    cam=None,
    frame=None,
    centre=None,
    x_half_width=None,
    y_half_width=None,
    avg_count=1,
):
    """
    Wrapper for camera + averaging.
    """

    if avg_count < 1:
        raise ValueError("avg_count must be >= 1")

    total = 0.0

    for _ in range(avg_count):
        if frame is None:
            f = cam.GetFrame()
        else:
            f = frame

        total += compute_relative_power(
            f,
            centre=centre,
            x_half_width=x_half_width,
            y_half_width=y_half_width,
        )

    return total / avg_count


# ============================================================
# VISUALISATION
# ============================================================

def draw_roi_box(
    image: np.ndarray,
    centre=None,
    x_half_width=None,
    y_half_width=None,
    colour=(255, 0, 0),
    thickness=2,
    draw_cross=True,
):
    """
    Draw ROI on image (returns new image).
    """

    if image.ndim == 2:
        vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    elif image.ndim == 3:
        vis = image.copy()
    else:
        raise ValueError(f"Unsupported image shape: {image.shape}")

    if centre is None or x_half_width is None or y_half_width is None:
        return vis

    cy, cx = centre
    h, w = vis.shape[:2]

    x0 = max(int(cx - x_half_width), 0)
    x1 = min(int(cx + x_half_width), w - 1)
    y0 = max(int(cy - y_half_width), 0)
    y1 = min(int(cy + y_half_width), h - 1)

    cv2.rectangle(vis, (x0, y0), (x1, y1), colour, thickness)

    if draw_cross:
        cx_i = int(cx)
        cy_i = int(cy)

        if 0 <= cx_i < w and 0 <= cy_i < h:
            cv2.drawMarker(
                vis,
                (cx_i, cy_i),
                colour,
                markerType=cv2.MARKER_CROSS,
                markerSize=12,
                thickness=thickness,
            )

    return vis


def rescale_to_8bit(frame: np.ndarray):
    """
    Simple min/max normalisation for plotting only.
    """
    lo = np.nanmin(frame)
    hi = np.nanmax(frame)

    if hi <= lo:
        return np.zeros_like(frame, dtype=np.uint8)

    norm = (frame - lo) / (hi - lo)
    return (norm * 255).astype(np.uint8)


def show_aperture(
    frame,
    centre=None,
    x_half_width=None,
    y_half_width=None,
):
    """
    Quick debug visualisation.
    """

    img = rescale_to_8bit(frame)

    vis = draw_roi_box(
        img,
        centre=centre,
        x_half_width=x_half_width,
        y_half_width=y_half_width,
    )

    plt.imshow(vis)
    plt.title("ROI Debug View")
    plt.axis("off")
    plt.show()