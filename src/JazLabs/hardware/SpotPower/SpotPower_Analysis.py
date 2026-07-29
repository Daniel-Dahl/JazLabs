import re

import numpy as np

from JazLabs.utils.SpotArrayAnalysis.SpotArrayAnalysis import extract_spot_minimal


def normalise_aperture_radii(aperture_radii):
    """Return elliptical aperture radii as positive ``(ry, rx)`` floats."""
    if np.isscalar(aperture_radii):
        radius_y = radius_x = float(aperture_radii)
    else:
        radii = np.asarray(aperture_radii, dtype=float).reshape(-1)
        if radii.size != 2:
            raise ValueError("Aperture radii must be a scalar or a (ry, rx) pair.")
        radius_y, radius_x = radii

    if not np.isfinite(radius_y) or not np.isfinite(radius_x):
        raise ValueError("Aperture radii must be finite.")
    if radius_y <= 0 or radius_x <= 0:
        raise ValueError("Aperture radii must be greater than zero.")

    return float(radius_y), float(radius_x)


def validate_spot_centres(spot_centres):
    """Validate and return an ``(N, 2)`` float array in ``(y, x)`` order."""
    centres = np.asarray(spot_centres, dtype=float)

    if centres.size == 0:
        return np.empty((0, 2), dtype=float)
    if centres.ndim != 2 or centres.shape[1] != 2:
        raise ValueError("Spot centres must have shape (N, 2) in (y, x) order.")
    if not np.all(np.isfinite(centres)):
        raise ValueError("Spot centres must contain only finite values.")

    return centres.copy()


def parse_spot_centres(text):
    """
    Parse spot centres written one per line in ``y, x`` or ``y x`` form.

    Blank lines and text following ``#`` are ignored.
    """
    centres = []

    for line_number, source_line in enumerate(str(text).splitlines(), start=1):
        line = source_line.split("#", 1)[0].strip()
        if not line:
            continue

        values = [value for value in re.split(r"[\s,;]+", line) if value]
        if len(values) != 2:
            raise ValueError(
                f"Line {line_number} must contain exactly two values: y, x."
            )

        try:
            centres.append((float(values[0]), float(values[1])))
        except ValueError as error:
            raise ValueError(
                f"Line {line_number} contains a non-numeric spot centre."
            ) from error

    return validate_spot_centres(centres)


def prepare_analysis_frame(frame, dark_frame=None, use_dark_frame=False):
    """
    Convert a camera frame to float and optionally subtract a dark frame.

    Negative values are clipped to zero. This conversion before subtraction
    prevents wraparound when the camera supplies an unsigned integer image.
    """
    analysis_frame = np.asarray(frame, dtype=np.float32)

    if analysis_frame.ndim != 2:
        raise ValueError("Spot-power analysis requires a two-dimensional frame.")

    if not use_dark_frame:
        return analysis_frame
    if dark_frame is None:
        raise ValueError("Dark-frame subtraction is enabled but no dark frame is loaded.")

    dark = np.asarray(dark_frame, dtype=np.float32)
    if dark.shape != analysis_frame.shape:
        raise ValueError(
            "Dark-frame shape "
            f"{dark.shape} does not match camera-frame shape {analysis_frame.shape}."
        )

    return np.maximum(analysis_frame - dark, 0.0)


def analyse_spot_powers(frame, spot_centres, aperture_radii):
    """
    Measure absolute and relative powers inside elliptical spot apertures.

    Returns
    -------
    absolute_powers : ndarray
        Sum of the pixels inside each aperture.
    relative_powers : ndarray
        Each aperture power divided by the total. All zeros when total power
        is zero.
    total_power : float
        Sum of all aperture powers.
    aperture_views : list[ndarray]
        Minimal masked crops for display.
    """
    analysis_frame = np.asarray(frame)
    if analysis_frame.ndim != 2:
        raise ValueError("Spot-power analysis requires a two-dimensional frame.")

    centres = validate_spot_centres(spot_centres)
    radii = normalise_aperture_radii(aperture_radii)

    absolute_powers = np.zeros(len(centres), dtype=float)
    aperture_views = []

    for spot_index, centre_yx in enumerate(centres):
        aperture_view, spot_power = extract_spot_minimal(
            analysis_frame,
            centre_yx,
            radii_px=radii,
            bg_value=0,
        )
        aperture_views.append(aperture_view)
        absolute_powers[spot_index] = spot_power

    total_power = float(np.sum(absolute_powers))
    if total_power > 0:
        relative_powers = absolute_powers / total_power
    else:
        relative_powers = np.zeros_like(absolute_powers)

    return absolute_powers, relative_powers, total_power, aperture_views


def average_spot_power_history(absolute_power_history):
    """
    Average matching per-spot power measurements across multiple frames.

    Returns averaged absolute powers, relative powers, and total power.
    """
    history = np.asarray(absolute_power_history, dtype=float)
    if history.ndim != 2:
        raise ValueError("Power history must have shape (frames, spots).")
    if history.shape[0] == 0:
        raise ValueError("Power history must contain at least one frame.")

    absolute_powers = np.mean(history, axis=0)
    total_power = float(np.sum(absolute_powers))
    if total_power > 0:
        relative_powers = absolute_powers / total_power
    else:
        relative_powers = np.zeros_like(absolute_powers)

    return absolute_powers, relative_powers, total_power
