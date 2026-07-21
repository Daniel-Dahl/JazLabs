from __future__ import annotations

import numpy as np


def make_circular_tophat(
    shape: tuple[int, int],
    radius: float | None = None,
    centre: tuple[float, float] | None = None,
) -> np.ndarray:
    """Return a 2D circular pupil mask with ones inside the aperture."""

    height, width = _validate_shape(shape)
    if radius is None:
        radius = min(height, width) / 2.0
    if radius <= 0:
        raise ValueError("radius must be positive")

    if centre is None:
        cy = (height - 1) / 2.0
        cx = (width - 1) / 2.0
    else:
        cy, cx = centre

    yy, xx = np.indices((height, width), dtype=float)
    rr = np.hypot(yy - cy, xx - cx)
    return (rr <= radius).astype(float)


def make_hadamard_phase_profiles(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    radius: float | None = None,
    centre: tuple[float, float] | None = None,
) -> np.ndarray:
    """Return Hadamard phase profiles as uniform-intensity complex fields.

    The output has shape ``(n_profiles, height, width)``. Inside the circular
    pupil each pixel has unit amplitude and a phase of either 0 or pi. Outside
    the pupil the field is zero.
    """

    height, width = _validate_shape(shape)
    n_modes = int(n_superpixels_x) * int(n_superpixels_y)
    if n_modes < 1:
        raise ValueError("number of superpixels must be positive")
    if n_modes & (n_modes - 1):
        raise ValueError("number of superpixels must be a power of two")

    pupil = make_circular_tophat((height, width), radius=radius, centre=centre)
    labels = _make_rectangular_superpixel_labels(
        (height, width),
        n_superpixels_x,
        n_superpixels_y,
    )
    hadamard = _make_hadamard(n_modes)

    fields = np.zeros((n_modes, height, width), dtype=complex)
    inside_pupil = pupil > 0
    for profile_idx, signs in enumerate(hadamard):
        field = np.zeros((height, width), dtype=complex)
        field[inside_pupil] = signs[labels[inside_pupil]]
        fields[profile_idx] = field

    return fields


def make_equal_area_circular_superpixel_labels(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    radius: float | None = None,
    centre: tuple[float, float] | None = None,
) -> np.ndarray:
    """Return equal-area superpixel labels inside a circular pupil.

    Pixels outside the usable pupil are labelled ``-1``. Each labelled
    superpixel has the same number of pixels, so Hadamard signs applied to
    these labels are orthogonal under the discrete pupil inner product.
    """

    height, width = _validate_shape(shape)
    n_modes = _validate_superpixel_counts(n_superpixels_x, n_superpixels_y)
    pupil = make_circular_tophat((height, width), radius=radius, centre=centre)
    coords = np.column_stack(np.nonzero(pupil > 0))
    pixels_per_region = coords.shape[0] // n_modes
    if pixels_per_region < 1:
        raise ValueError("circular pupil has fewer pixels than superpixels")

    usable_count = pixels_per_region * n_modes
    coords = _keep_central_pixels(coords, usable_count, (height, width), centre)
    coords = _sort_coords_by_y_then_x(coords)

    labels = np.full((height, width), -1, dtype=int)
    pixels_per_band = pixels_per_region * n_superpixels_x
    label = 0
    for iy in range(n_superpixels_y):
        band_start = iy * pixels_per_band
        band_stop = band_start + pixels_per_band
        band = _sort_coords_by_x_then_y(coords[band_start:band_stop])

        for ix in range(n_superpixels_x):
            region_start = ix * pixels_per_region
            region_stop = region_start + pixels_per_region
            region = band[region_start:region_stop]
            labels[region[:, 0], region[:, 1]] = label
            label += 1

    return labels


def make_circular_hadamard_phase_profiles(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    radius: float | None = None,
    centre: tuple[float, float] | None = None,
) -> np.ndarray:
    """Return orthogonal Hadamard phase profiles on a circular pupil.

    The circular pupil is divided into equal-pixel-count superpixels before the
    Hadamard signs are applied. Any leftover pixels that cannot be evenly split
    across the superpixels are left at zero amplitude.
    """

    height, width = _validate_shape(shape)
    n_modes = _validate_superpixel_counts(n_superpixels_x, n_superpixels_y)
    if n_modes & (n_modes - 1):
        raise ValueError("number of superpixels must be a power of two")

    labels = make_equal_area_circular_superpixel_labels(
        (height, width),
        n_superpixels_x,
        n_superpixels_y,
        radius=radius,
        centre=centre,
    )
    hadamard = _make_hadamard(n_modes)

    fields = np.zeros((n_modes, height, width), dtype=complex)
    valid = labels >= 0
    for profile_idx, signs in enumerate(hadamard):
        field = np.zeros((height, width), dtype=complex)
        field[valid] = signs[labels[valid]]
        fields[profile_idx] = field

    return fields


def make_equal_area_circular_pupil(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    radius: float | None = None,
    centre: tuple[float, float] | None = None,
) -> np.ndarray:
    """Return the exact circular pupil used by the equal-area Hadamard modes."""

    labels = make_equal_area_circular_superpixel_labels(
        shape,
        n_superpixels_x,
        n_superpixels_y,
        radius=radius,
        centre=centre,
    )
    return (labels >= 0).astype(float)


def _make_hadamard(n_modes: int) -> np.ndarray:
    hadamard = np.array([[1]], dtype=int)
    while hadamard.shape[0] < n_modes:
        hadamard = np.block([[hadamard, hadamard], [hadamard, -hadamard]])
    return hadamard


def _make_rectangular_superpixel_labels(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
) -> np.ndarray:
    height, width = _validate_shape(shape)
    if n_superpixels_x < 1 or n_superpixels_y < 1:
        raise ValueError("superpixel counts must be positive")

    labels = np.empty((height, width), dtype=int)
    y_edges = np.linspace(0, height, n_superpixels_y + 1, dtype=int)
    x_edges = np.linspace(0, width, n_superpixels_x + 1, dtype=int)

    mode_idx = 0
    for iy in range(n_superpixels_y):
        y0, y1 = y_edges[iy], y_edges[iy + 1]
        for ix in range(n_superpixels_x):
            x0, x1 = x_edges[ix], x_edges[ix + 1]
            labels[y0:y1, x0:x1] = mode_idx
            mode_idx += 1

    return labels


def _validate_shape(shape: tuple[int, int]) -> tuple[int, int]:
    if len(shape) != 2:
        raise ValueError("shape must be a 2-tuple")
    height, width = int(shape[0]), int(shape[1])
    if height < 1 or width < 1:
        raise ValueError("shape dimensions must be positive")
    return height, width


def _validate_superpixel_counts(n_superpixels_x: int, n_superpixels_y: int) -> int:
    n_superpixels_x = int(n_superpixels_x)
    n_superpixels_y = int(n_superpixels_y)
    if n_superpixels_x < 1 or n_superpixels_y < 1:
        raise ValueError("superpixel counts must be positive")
    return n_superpixels_x * n_superpixels_y


def _keep_central_pixels(
    coords: np.ndarray,
    n_keep: int,
    shape: tuple[int, int],
    centre: tuple[float, float] | None,
) -> np.ndarray:
    if coords.shape[0] == n_keep:
        return coords

    height, width = shape
    if centre is None:
        cy = (height - 1) / 2.0
        cx = (width - 1) / 2.0
    else:
        cy, cx = centre

    radius_sq = (coords[:, 0] - cy) ** 2 + (coords[:, 1] - cx) ** 2
    order = np.argsort(radius_sq)
    return coords[order[:n_keep]]


def _sort_coords_by_y_then_x(coords: np.ndarray) -> np.ndarray:
    order = np.lexsort((coords[:, 1], coords[:, 0]))
    return coords[order]


def _sort_coords_by_x_then_y(coords: np.ndarray) -> np.ndarray:
    order = np.lexsort((coords[:, 0], coords[:, 1]))
    return coords[order]
