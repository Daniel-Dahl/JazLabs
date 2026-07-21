"""Hadamard and Stokes tomography for superpixel photonic-lantern simulations.

The tomography basis is the superpixel basis. This module also includes a
simple Fourier-optics forward model so a rendered pupil field can be focused
onto lantern input modes before the lantern transfer matrix is applied.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

import numpy as np


@dataclass(frozen=True)
class NoiseModel:
    """Optional detector noise model for simulated power measurements.

    Parameters
    ----------
    shot_scale:
        If given, powers are converted to Poisson counts using this scale and
        converted back to powers. Larger values mean lower relative shot noise.
    gaussian_std:
        Additive Gaussian read-noise standard deviation in power units.
    seed:
        Seed for deterministic noise.
    clip:
        If true, negative noisy powers are clipped to zero.
    """

    shot_scale: float | None = None
    gaussian_std: float = 0.0
    seed: int | None = None
    clip: bool = True


@dataclass(frozen=True)
class StokesMeasurements:
    """Structured power-only measurements for Stokes reconstruction."""

    input_vectors: np.ndarray
    powers: np.ndarray
    single_indices: np.ndarray
    real_pairs: np.ndarray
    imag_pairs: np.ndarray
    single_measurement_indices: np.ndarray
    real_measurement_indices: np.ndarray
    imag_measurement_indices: np.ndarray


@dataclass(frozen=True)
class PhysicalStokesMeasurements:
    """Stokes measurements taken through a known optical forward model.

    ``forward_model`` maps commanded superpixel modal coefficients to the input
    coefficients seen by the lantern matrix.
    """

    stokes: StokesMeasurements
    forward_model: np.ndarray
    lantern_input_vectors: np.ndarray


@dataclass(frozen=True)
class MatrixComparison:
    """Row-phase-aligned comparison between a true and reconstructed matrix."""

    relative_error: float
    amplitude_error: float
    phase_error: float
    row_phases: np.ndarray
    aligned_estimate: np.ndarray


@dataclass(frozen=True)
class BackwardPowerSolution:
    """Input coefficients that reproduce a chosen lantern output power vector."""

    commanded_coeffs: np.ndarray
    output_amplitudes: np.ndarray
    predicted_powers: np.ndarray
    target_powers: np.ndarray
    residual: float
    coeff_norm: float
    effective_matrix: np.ndarray


def make_superpixel_map(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    pupil_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Divide a pupil into rectangular labelled superpixels.

    Pixels outside the pupil are labelled ``-1``. A superpixel receives a compact
    index only if at least one of its pixels overlaps the pupil.
    """

    height, width = _validate_shape(shape)
    if n_superpixels_x < 1 or n_superpixels_y < 1:
        raise ValueError("superpixel counts must be positive")

    if pupil_mask is None:
        valid = np.ones((height, width), dtype=bool)
    else:
        if pupil_mask.shape != (height, width):
            raise ValueError("pupil_mask shape must match shape")
        valid = np.asarray(pupil_mask) > 0

    labels = np.full((height, width), -1, dtype=int)
    y_edges = np.linspace(0, height, n_superpixels_y + 1, dtype=int)
    x_edges = np.linspace(0, width, n_superpixels_x + 1, dtype=int)

    mode_idx = 0
    for iy in range(n_superpixels_y):
        y0, y1 = y_edges[iy], y_edges[iy + 1]
        for ix in range(n_superpixels_x):
            x0, x1 = x_edges[ix], x_edges[ix + 1]
            cell_valid = valid[y0:y1, x0:x1]
            if np.any(cell_valid):
                block = labels[y0:y1, x0:x1]
                block[cell_valid] = mode_idx
                mode_idx += 1

    return labels


def make_hadamard_basis(n_modes: int) -> tuple[np.ndarray, np.ndarray]:
    """Return unnormalised and unit-norm Hadamard bases with entries +-1.

    ``n_modes`` must be a positive power of two. Padding can be added later when
    needed, but raising here keeps the measurement dimension explicit.
    """

    if n_modes < 1:
        raise ValueError("n_modes must be positive")
    if n_modes & (n_modes - 1):
        raise ValueError("n_modes must be a power of two for Hadamard modes")

    basis = np.array([[1]], dtype=int)
    while basis.shape[0] < n_modes:
        basis = np.block([[basis, basis], [basis, -basis]])
    return basis, basis.astype(float) / np.sqrt(n_modes)


def modal_coeffs_to_field(
    coeffs: np.ndarray,
    superpixel_map: np.ndarray,
    pupil_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Render complex superpixel coefficients as a 2D complex pupil field."""

    coeffs = np.asarray(coeffs, dtype=complex)
    labels = np.asarray(superpixel_map)
    if labels.ndim != 2:
        raise ValueError("superpixel_map must be 2D")

    n_modes = _n_modes_from_map(labels)
    if coeffs.shape != (n_modes,):
        raise ValueError(f"coeffs must have shape ({n_modes},)")

    field = np.zeros(labels.shape, dtype=complex)
    valid = labels >= 0
    if pupil_mask is not None:
        if pupil_mask.shape != labels.shape:
            raise ValueError("pupil_mask shape must match superpixel_map")
        valid &= np.asarray(pupil_mask) > 0

    field[valid] = coeffs[labels[valid]]
    return field


def coeffs_to_phase_mask(
    coeffs: np.ndarray,
    superpixel_map: np.ndarray,
    phase_only: bool = True,
) -> np.ndarray:
    """Render modal coefficients as an SLM phase mask in radians.

    For phase-only use, complex amplitudes are represented by their phase. Thus
    Hadamard entries +1 and -1 become phases 0 and pi.
    """

    coeffs = np.asarray(coeffs, dtype=complex)
    labels = np.asarray(superpixel_map)
    n_modes = _n_modes_from_map(labels)
    if coeffs.shape != (n_modes,):
        raise ValueError(f"coeffs must have shape ({n_modes},)")

    phase = np.zeros(labels.shape, dtype=float)
    valid = labels >= 0
    if phase_only:
        phase[valid] = np.mod(np.angle(coeffs[labels[valid]]), 2 * np.pi)
    else:
        phase[valid] = np.mod(np.real(coeffs[labels[valid]]), 2 * np.pi)
    return phase


def phase_mask_to_pupil_field(
    phase_mask: np.ndarray,
    pupil_mask: np.ndarray,
    amplitude: float | np.ndarray = 1.0,
) -> np.ndarray:
    """Apply an SLM phase mask to a tophat pupil field.

    The returned field is ``amplitude * pupil_mask * exp(1j * phase_mask)``.
    """

    phase_mask = np.asarray(phase_mask, dtype=float)
    pupil_mask = np.asarray(pupil_mask, dtype=float)
    if phase_mask.shape != pupil_mask.shape:
        raise ValueError("phase_mask and pupil_mask must have the same shape")

    return np.asarray(amplitude) * pupil_mask * np.exp(1j * phase_mask)


def propagate_pupil_to_focal_plane(
    pupil_field: np.ndarray,
    normalize: bool = True,
) -> np.ndarray:
    """Propagate a pupil field to a focal plane with a centred 2D FFT."""

    pupil_field = np.asarray(pupil_field, dtype=complex)
    if pupil_field.ndim != 2:
        raise ValueError("pupil_field must be 2D")

    norm = "ortho" if normalize else None
    return np.fft.fftshift(
        np.fft.fft2(np.fft.ifftshift(pupil_field), norm=norm)
    )


def make_gaussian_focal_modes(
    shape: tuple[int, int],
    centres: np.ndarray,
    waist: float,
    normalize: bool = True,
) -> np.ndarray:
    """Create Gaussian lantern input modes in the focal plane.

    Parameters
    ----------
    shape:
        Focal-plane array shape.
    centres:
        Array-like of ``(y, x)`` centre coordinates, one per mode.
    waist:
        Gaussian 1/e field-radius in pixels.
    normalize:
        If true, each mode is normalised to unit discrete power.
    """

    height, width = _validate_shape(shape)
    centres = np.asarray(centres, dtype=float)
    if centres.ndim != 2 or centres.shape[1] != 2:
        raise ValueError("centres must have shape (n_modes, 2)")
    if waist <= 0:
        raise ValueError("waist must be positive")

    yy, xx = np.indices((height, width), dtype=float)
    modes = np.empty((centres.shape[0], height, width), dtype=complex)
    for mode_idx, (cy, cx) in enumerate(centres):
        rr2 = (yy - cy) ** 2 + (xx - cx) ** 2
        mode = np.exp(-rr2 / (waist**2))
        if normalize:
            mode_norm = np.linalg.norm(mode.ravel())
            if mode_norm > 0:
                mode = mode / mode_norm
        modes[mode_idx] = mode
    return modes


def project_field_onto_modes(field: np.ndarray, modes: np.ndarray) -> np.ndarray:
    """Project a 2D complex field onto a stack of lantern input modes."""

    field = np.asarray(field, dtype=complex)
    modes = np.asarray(modes, dtype=complex)
    if field.ndim != 2:
        raise ValueError("field must be 2D")
    if modes.ndim != 3:
        raise ValueError("modes must have shape (n_modes, height, width)")
    if modes.shape[1:] != field.shape:
        raise ValueError("mode shapes must match field shape")

    return np.tensordot(np.conj(modes), field, axes=([1, 2], [0, 1]))


def build_superpixel_focal_coupling(
    superpixel_map: np.ndarray,
    pupil_mask: np.ndarray,
    lantern_input_modes: np.ndarray,
    normalize_fft: bool = True,
) -> np.ndarray:
    """Build the linear coupling from superpixel pistons to lantern input modes.

    The returned matrix ``C`` has shape ``(n_lantern_input_modes,
    n_superpixels)``. Column ``j`` is the focal-plane projection generated by
    setting superpixel ``j`` to unit complex amplitude in the pupil.
    """

    labels = np.asarray(superpixel_map)
    pupil_mask = np.asarray(pupil_mask, dtype=float)
    if labels.shape != pupil_mask.shape:
        raise ValueError("superpixel_map and pupil_mask must have the same shape")

    n_superpixels = _n_modes_from_map(labels)
    n_lantern_modes = np.asarray(lantern_input_modes).shape[0]
    coupling = np.zeros((n_lantern_modes, n_superpixels), dtype=complex)

    for mode_idx in range(n_superpixels):
        coeffs = np.zeros(n_superpixels, dtype=complex)
        coeffs[mode_idx] = 1.0
        pupil_field = modal_coeffs_to_field(coeffs, labels, pupil_mask)
        focal_field = propagate_pupil_to_focal_plane(
            pupil_field,
            normalize=normalize_fft,
        )
        coupling[:, mode_idx] = project_field_onto_modes(
            focal_field,
            lantern_input_modes,
        )

    return coupling


def make_matched_focal_modes(
    superpixel_map: np.ndarray,
    pupil_mask: np.ndarray,
    normalize_fft: bool = True,
) -> np.ndarray:
    """Create orthonormal focal modes matched to superpixel diffraction fields.

    This is useful for ideal simulations where the lantern input basis should
    span the same subspace as the Fourier-transformed superpixel basis without
    introducing an ill-conditioned projection.
    """

    labels = np.asarray(superpixel_map)
    pupil_mask = np.asarray(pupil_mask, dtype=float)
    if labels.shape != pupil_mask.shape:
        raise ValueError("superpixel_map and pupil_mask must have the same shape")

    n_superpixels = _n_modes_from_map(labels)
    focal_columns = []
    for mode_idx in range(n_superpixels):
        coeffs = np.zeros(n_superpixels, dtype=complex)
        coeffs[mode_idx] = 1.0
        pupil_field = modal_coeffs_to_field(coeffs, labels, pupil_mask)
        focal_field = propagate_pupil_to_focal_plane(
            pupil_field,
            normalize=normalize_fft,
        )
        focal_columns.append(focal_field.ravel())

    focal_matrix = np.column_stack(focal_columns)
    q, _ = np.linalg.qr(focal_matrix)
    return q[:, :n_superpixels].T.reshape((n_superpixels, *labels.shape))


def simulate_lantern_powers_from_phase_mask(
    T: np.ndarray,
    phase_mask: np.ndarray,
    pupil_mask: np.ndarray,
    lantern_input_modes: np.ndarray,
    noise: NoiseModel | dict[str, Any] | None = None,
    normalize_fft: bool = True,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Simulate powers from a phase mask focused onto lantern input modes.

    ``T`` maps from projected lantern input-mode coefficients to output
    amplitudes. The returned tuple is ``(powers, input_coeffs, focal_field)``.
    """

    T = np.asarray(T, dtype=complex)
    lantern_input_modes = np.asarray(lantern_input_modes, dtype=complex)
    if T.ndim != 2:
        raise ValueError("T must be a 2D matrix")
    if lantern_input_modes.ndim != 3:
        raise ValueError("lantern_input_modes must be a 3D mode stack")
    if T.shape[1] != lantern_input_modes.shape[0]:
        raise ValueError("T columns must match number of lantern input modes")

    pupil_field = phase_mask_to_pupil_field(phase_mask, pupil_mask)
    focal_field = propagate_pupil_to_focal_plane(
        pupil_field,
        normalize=normalize_fft,
    )
    input_coeffs = project_field_onto_modes(focal_field, lantern_input_modes)
    powers = simulate_lantern_powers(T, input_coeffs, noise=noise)
    return powers, input_coeffs, focal_field


def simulate_lantern_powers_from_modal_coeffs(
    T: np.ndarray,
    commanded_coeffs: np.ndarray,
    forward_model: np.ndarray,
    noise: NoiseModel | dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply a known optical model before the lantern matrix.

    ``commanded_coeffs`` are the superpixel mask coefficients. ``forward_model``
    maps those coefficients to the lantern input-mode amplitudes. ``T`` is the
    actual lantern coupling matrix.
    """

    T = np.asarray(T, dtype=complex)
    commanded_coeffs = np.asarray(commanded_coeffs, dtype=complex)
    forward_model = np.asarray(forward_model, dtype=complex)
    if forward_model.ndim != 2:
        raise ValueError("forward_model must be a 2D matrix")
    if commanded_coeffs.shape != (forward_model.shape[1],):
        raise ValueError(
            f"commanded_coeffs must have shape ({forward_model.shape[1]},)"
        )
    if T.shape[1] != forward_model.shape[0]:
        raise ValueError("T columns must match forward_model rows")

    lantern_input_coeffs = forward_model @ commanded_coeffs
    powers = simulate_lantern_powers(T, lantern_input_coeffs, noise=noise)
    return powers, lantern_input_coeffs


def simulate_lantern_powers(
    T: np.ndarray,
    input_coeffs: np.ndarray,
    noise: NoiseModel | dict[str, Any] | None = None,
) -> np.ndarray:
    """Return output powers ``abs(T @ input_coeffs)**2``."""

    T = np.asarray(T, dtype=complex)
    input_coeffs = np.asarray(input_coeffs, dtype=complex)
    if T.ndim != 2:
        raise ValueError("T must be a 2D matrix")
    if input_coeffs.shape != (T.shape[1],):
        raise ValueError(f"input_coeffs must have shape ({T.shape[1]},)")

    powers = np.abs(T @ input_coeffs) ** 2
    return _apply_noise(powers, noise)


def solve_input_coeffs_from_output_powers(
    T: np.ndarray,
    target_powers: np.ndarray,
    output_phases: np.ndarray | None = None,
    forward_model: np.ndarray | None = None,
    phase_trials: int = 0,
    seed: int | None = None,
    rcond: float | None = None,
) -> BackwardPowerSolution:
    """Find commanded mode coefficients for a desired lantern power vector.

    Power measurements only give output amplitudes up to unknown phases. If
    ``output_phases`` is given, those phases are used directly. Otherwise zero
    output phases are used, with optional random phase trials to find a
    lower-norm coefficient vector that still matches the powers.

    ``T`` should map lantern input coefficients to output amplitudes. If
    ``forward_model`` is supplied, commanded coefficients are solved through the
    effective matrix ``T @ forward_model``.
    """

    target_powers = _validate_power_vector(target_powers)
    effective_matrix = _make_effective_matrix(T, forward_model)
    if effective_matrix.shape[0] != target_powers.shape[0]:
        raise ValueError("target_powers length must match number of outputs")
    if phase_trials < 0:
        raise ValueError("phase_trials must be non-negative")

    candidate_phases = _candidate_output_phases(
        target_powers.shape[0],
        output_phases,
        phase_trials,
        seed,
    )
    pinv_kwargs = {}
    if rcond is not None:
        pinv_kwargs["rcond"] = rcond
    effective_inverse = np.linalg.pinv(effective_matrix, **pinv_kwargs)

    best_solution = None
    for phases in candidate_phases:
        output_amplitudes = np.sqrt(target_powers) * np.exp(1j * phases)
        coeffs = effective_inverse @ output_amplitudes
        predicted_powers = np.abs(effective_matrix @ coeffs) ** 2
        residual = np.linalg.norm(predicted_powers - target_powers)
        coeff_norm = np.linalg.norm(coeffs)
        score = (residual, coeff_norm)

        if best_solution is None or score < best_solution[0]:
            best_solution = (
                score,
                BackwardPowerSolution(
                    commanded_coeffs=coeffs,
                    output_amplitudes=output_amplitudes,
                    predicted_powers=predicted_powers,
                    target_powers=target_powers,
                    residual=float(residual),
                    coeff_norm=float(coeff_norm),
                    effective_matrix=effective_matrix,
                ),
            )

    return best_solution[1]


def reconstruct_field_from_mode_coeffs(
    coeffs: np.ndarray,
    mode_fields: np.ndarray,
) -> np.ndarray:
    """Superimpose a stack of fields using complex mode coefficients."""

    coeffs = np.asarray(coeffs, dtype=complex)
    mode_fields = np.asarray(mode_fields, dtype=complex)
    if mode_fields.ndim != 3:
        raise ValueError("mode_fields must have shape (n_modes, height, width)")
    if coeffs.shape != (mode_fields.shape[0],):
        raise ValueError(f"coeffs must have shape ({mode_fields.shape[0]},)")

    return np.tensordot(coeffs, mode_fields, axes=(0, 0))


def generate_stokes_measurements(
    T: np.ndarray,
    noise: NoiseModel | dict[str, Any] | None = None,
) -> StokesMeasurements:
    """Generate power-only Stokes measurements for a coupling matrix.

    The measurement set contains all single-mode powers and all pairwise
    0-phase and pi/2-phase interferences needed to recover each row of ``T`` up
    to one arbitrary global phase.
    """

    T = np.asarray(T, dtype=complex)
    if T.ndim != 2:
        raise ValueError("T must be a 2D matrix")
    n_outputs, n_modes = T.shape

    input_vectors: list[np.ndarray] = []
    powers: list[np.ndarray] = []
    single_indices: list[int] = []
    real_pairs: list[tuple[int, int]] = []
    imag_pairs: list[tuple[int, int]] = []
    single_measurement_indices: list[int] = []
    real_measurement_indices: list[int] = []
    imag_measurement_indices: list[int] = []

    for mode_idx in range(n_modes):
        coeffs = np.zeros(n_modes, dtype=complex)
        coeffs[mode_idx] = 1.0
        single_indices.append(mode_idx)
        single_measurement_indices.append(len(input_vectors))
        input_vectors.append(coeffs)
        powers.append(simulate_lantern_powers(T, coeffs, noise=noise))

    for i, j in combinations(range(n_modes), 2):
        coeffs = np.zeros(n_modes, dtype=complex)
        coeffs[i] = 1.0 / np.sqrt(2.0)
        coeffs[j] = 1.0 / np.sqrt(2.0)
        real_pairs.append((i, j))
        real_measurement_indices.append(len(input_vectors))
        input_vectors.append(coeffs)
        powers.append(simulate_lantern_powers(T, coeffs, noise=noise))

        coeffs = np.zeros(n_modes, dtype=complex)
        coeffs[i] = 1.0 / np.sqrt(2.0)
        coeffs[j] = 1.0j / np.sqrt(2.0)
        imag_pairs.append((i, j))
        imag_measurement_indices.append(len(input_vectors))
        input_vectors.append(coeffs)
        powers.append(simulate_lantern_powers(T, coeffs, noise=noise))

    return StokesMeasurements(
        input_vectors=np.asarray(input_vectors, dtype=complex),
        powers=np.asarray(powers, dtype=float).reshape(-1, n_outputs),
        single_indices=np.asarray(single_indices, dtype=int),
        real_pairs=np.asarray(real_pairs, dtype=int).reshape(-1, 2),
        imag_pairs=np.asarray(imag_pairs, dtype=int).reshape(-1, 2),
        single_measurement_indices=np.asarray(single_measurement_indices, dtype=int),
        real_measurement_indices=np.asarray(real_measurement_indices, dtype=int),
        imag_measurement_indices=np.asarray(imag_measurement_indices, dtype=int),
    )


def generate_physical_stokes_measurements(
    T: np.ndarray,
    forward_model: np.ndarray,
    noise: NoiseModel | dict[str, Any] | None = None,
) -> PhysicalStokesMeasurements:
    """Generate Stokes measurements through a known Fourier/projection model.

    The commanded vectors are still the usual single and pairwise Stokes vectors
    in the superpixel basis. The measured powers are produced by first applying
    ``forward_model`` and then the raw lantern matrix ``T``.
    """

    T = np.asarray(T, dtype=complex)
    forward_model = np.asarray(forward_model, dtype=complex)
    if T.ndim != 2:
        raise ValueError("T must be a 2D matrix")
    if forward_model.ndim != 2:
        raise ValueError("forward_model must be a 2D matrix")
    if T.shape[1] != forward_model.shape[0]:
        raise ValueError("T columns must match forward_model rows")

    n_commanded_modes = forward_model.shape[1]
    template = generate_stokes_measurements(np.eye(n_commanded_modes, dtype=complex))
    powers = []
    lantern_input_vectors = []
    for commanded_coeffs in template.input_vectors:
        power, lantern_input = simulate_lantern_powers_from_modal_coeffs(
            T,
            commanded_coeffs,
            forward_model,
            noise=noise,
        )
        powers.append(power)
        lantern_input_vectors.append(lantern_input)

    stokes = StokesMeasurements(
        input_vectors=template.input_vectors,
        powers=np.asarray(powers, dtype=float),
        single_indices=template.single_indices,
        real_pairs=template.real_pairs,
        imag_pairs=template.imag_pairs,
        single_measurement_indices=template.single_measurement_indices,
        real_measurement_indices=template.real_measurement_indices,
        imag_measurement_indices=template.imag_measurement_indices,
    )
    return PhysicalStokesMeasurements(
        stokes=stokes,
        forward_model=forward_model,
        lantern_input_vectors=np.asarray(lantern_input_vectors, dtype=complex),
    )


def reconstruct_T_from_stokes(
    measurements: StokesMeasurements,
    n_outputs: int,
    n_modes: int,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Reconstruct ``T`` from Stokes measurements up to row-wise global phase."""

    powers = np.asarray(measurements.powers, dtype=float)
    if powers.shape[1] != n_outputs:
        raise ValueError(f"measurements.powers must have {n_outputs} columns")
    if len(measurements.single_measurement_indices) != n_modes:
        raise ValueError("single-mode measurement count does not match n_modes")

    single_powers = powers[measurements.single_measurement_indices].T
    gram = np.zeros((n_outputs, n_modes, n_modes), dtype=complex)
    for output_idx in range(n_outputs):
        gram[output_idx].flat[:: n_modes + 1] = single_powers[output_idx]

    for meas_idx, (i, j) in zip(
        measurements.real_measurement_indices,
        measurements.real_pairs,
    ):
        real_part = powers[meas_idx] - 0.5 * (
            single_powers[:, i] + single_powers[:, j]
        )
        gram[:, i, j] = real_part + 1j * gram[:, i, j].imag
        gram[:, j, i] = np.conj(gram[:, i, j])

    for meas_idx, (i, j) in zip(
        measurements.imag_measurement_indices,
        measurements.imag_pairs,
    ):
        imag_part = powers[meas_idx] - 0.5 * (
            single_powers[:, i] + single_powers[:, j]
        )
        gram[:, i, j] = gram[:, i, j].real + 1j * imag_part
        gram[:, j, i] = np.conj(gram[:, i, j])

    T_est = np.zeros((n_outputs, n_modes), dtype=complex)
    reference_modes = np.zeros(n_outputs, dtype=int)
    reference_amplitudes = np.zeros(n_outputs, dtype=float)
    reference_is_mode_zero = np.ones(n_outputs, dtype=bool)

    for output_idx in range(n_outputs):
        row_power = single_powers[output_idx]
        ref_idx = 0
        if row_power[ref_idx] <= 0:
            positive = np.flatnonzero(row_power > 0)
            if len(positive) == 0:
                continue
            ref_idx = int(positive[0])
            reference_is_mode_zero[output_idx] = False

        ref_amp = np.sqrt(row_power[ref_idx])
        reference_modes[output_idx] = ref_idx
        reference_amplitudes[output_idx] = ref_amp
        T_est[output_idx, ref_idx] = ref_amp

        for mode_idx in range(n_modes):
            if mode_idx == ref_idx:
                continue
            T_est[output_idx, mode_idx] = np.conj(
                gram[output_idx, ref_idx, mode_idx] / ref_amp
            )

    diagnostics = {
        "single_powers": single_powers,
        "gram_matrices": gram,
        "reference_modes": reference_modes,
        "reference_amplitudes": reference_amplitudes,
        "reference_is_mode_zero": reference_is_mode_zero,
    }
    return T_est, diagnostics


def reconstruct_T_from_physical_stokes(
    measurements: PhysicalStokesMeasurements,
    n_outputs: int,
    n_lantern_inputs: int,
    rcond: float | None = None,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Recover the raw lantern matrix from physical Stokes measurements.

    Power measurements first recover the effective commanded-basis matrix
    ``T_commanded = T @ forward_model``. Because the forward model is known, the
    raw lantern matrix is then estimated as ``T_commanded @ pinv(forward_model)``.
    Each output row still has the usual power-only global phase ambiguity.
    """

    forward_model = np.asarray(measurements.forward_model, dtype=complex)
    if forward_model.shape[0] != n_lantern_inputs:
        raise ValueError("n_lantern_inputs must match forward_model rows")

    T_commanded, diagnostics = reconstruct_T_from_stokes(
        measurements.stokes,
        n_outputs=n_outputs,
        n_modes=forward_model.shape[1],
    )
    pinv_kwargs = {}
    if rcond is not None:
        pinv_kwargs["rcond"] = rcond
    T_est = T_commanded @ np.linalg.pinv(forward_model, **pinv_kwargs)
    diagnostics = dict(diagnostics)
    diagnostics["T_commanded"] = T_commanded
    diagnostics["forward_model_condition"] = np.array(
        np.linalg.cond(forward_model),
        dtype=float,
    )
    return T_est[:, :n_lantern_inputs], diagnostics


def compare_matrices(T_true: np.ndarray, T_est: np.ndarray) -> MatrixComparison:
    """Compare matrices after removing each output row's global phase."""

    T_true = np.asarray(T_true, dtype=complex)
    T_est = np.asarray(T_est, dtype=complex)
    if T_true.shape != T_est.shape:
        raise ValueError("T_true and T_est must have the same shape")

    aligned = np.zeros_like(T_est)
    row_phases = np.zeros(T_true.shape[0], dtype=complex)
    for row_idx, (true_row, est_row) in enumerate(zip(T_true, T_est)):
        overlap = np.vdot(est_row, true_row)
        if np.abs(overlap) > 0:
            phase = overlap / np.abs(overlap)
        else:
            phase = 1.0 + 0.0j
        row_phases[row_idx] = phase
        aligned[row_idx] = est_row * phase

    denom = np.linalg.norm(T_true)
    if denom == 0:
        relative_error = np.linalg.norm(aligned - T_true)
    else:
        relative_error = np.linalg.norm(aligned - T_true) / denom

    amplitude_error = np.linalg.norm(np.abs(aligned) - np.abs(T_true)) / max(
        np.linalg.norm(np.abs(T_true)),
        np.finfo(float).eps,
    )

    nonzero = (np.abs(T_true) > 1e-12) & (np.abs(aligned) > 1e-12)
    if np.any(nonzero):
        phase_delta = np.angle(aligned[nonzero] * np.conj(T_true[nonzero]))
        phase_error = float(np.sqrt(np.mean(phase_delta**2)))
    else:
        phase_error = 0.0

    return MatrixComparison(
        relative_error=float(relative_error),
        amplitude_error=float(amplitude_error),
        phase_error=phase_error,
        row_phases=row_phases,
        aligned_estimate=aligned,
    )


def _apply_noise(
    powers: np.ndarray,
    noise: NoiseModel | dict[str, Any] | None,
) -> np.ndarray:
    if noise is None:
        return powers
    if isinstance(noise, dict):
        noise = NoiseModel(**noise)
    if not isinstance(noise, NoiseModel):
        raise TypeError("noise must be None, a NoiseModel, or a NoiseModel dict")

    rng = np.random.default_rng(noise.seed)
    noisy = np.asarray(powers, dtype=float).copy()
    if noise.shot_scale is not None:
        if noise.shot_scale <= 0:
            raise ValueError("shot_scale must be positive")
        counts = rng.poisson(np.clip(noisy, 0, None) * noise.shot_scale)
        noisy = counts / noise.shot_scale
    if noise.gaussian_std:
        if noise.gaussian_std < 0:
            raise ValueError("gaussian_std must be non-negative")
        noisy += rng.normal(0.0, noise.gaussian_std, size=noisy.shape)
    if noise.clip:
        noisy = np.clip(noisy, 0, None)
    return noisy


def _validate_power_vector(powers: np.ndarray) -> np.ndarray:
    powers = np.asarray(powers, dtype=float)
    if powers.ndim != 1:
        raise ValueError("target_powers must be a 1D array")
    if np.any(powers < 0):
        raise ValueError("target_powers must be non-negative")
    return powers


def _make_effective_matrix(
    T: np.ndarray,
    forward_model: np.ndarray | None,
) -> np.ndarray:
    T = np.asarray(T, dtype=complex)
    if T.ndim != 2:
        raise ValueError("T must be a 2D matrix")
    if forward_model is None:
        return T

    forward_model = np.asarray(forward_model, dtype=complex)
    if forward_model.ndim != 2:
        raise ValueError("forward_model must be a 2D matrix")
    if T.shape[1] != forward_model.shape[0]:
        raise ValueError("T columns must match forward_model rows")
    return T @ forward_model


def _candidate_output_phases(
    n_outputs: int,
    output_phases: np.ndarray | None,
    phase_trials: int,
    seed: int | None,
) -> np.ndarray:
    if output_phases is not None:
        output_phases = np.asarray(output_phases, dtype=float)
        if output_phases.shape != (n_outputs,):
            raise ValueError(f"output_phases must have shape ({n_outputs},)")
        return output_phases[None, :]

    phases = [np.zeros(n_outputs, dtype=float)]
    if phase_trials == 0:
        return np.asarray(phases)

    rng = np.random.default_rng(seed)
    random_phases = rng.uniform(-np.pi, np.pi, size=(phase_trials, n_outputs))
    phases.extend(random_phases)
    return np.asarray(phases)


def _n_modes_from_map(superpixel_map: np.ndarray) -> int:
    valid = superpixel_map[superpixel_map >= 0]
    if valid.size == 0:
        return 0
    unique = np.unique(valid)
    expected = np.arange(unique[-1] + 1)
    if not np.array_equal(unique, expected):
        raise ValueError("superpixel_map labels must be compact from 0 to N-1")
    return int(unique[-1] + 1)


def _validate_shape(shape: tuple[int, int]) -> tuple[int, int]:
    if len(shape) != 2:
        raise ValueError("shape must be a 2-tuple")
    height, width = int(shape[0]), int(shape[1])
    if height < 1 or width < 1:
        raise ValueError("shape dimensions must be positive")
    return height, width
