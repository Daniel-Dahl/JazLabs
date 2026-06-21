from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from JazLabs.simulator import BeamGenerator


@dataclass(frozen=True)
class HadamardBackwardSolution:
    """Result from fitting Hadamard coefficients to measured lantern powers."""

    coeffs: np.ndarray
    field: np.ndarray
    phase_mask: np.ndarray
    predicted_powers: np.ndarray
    target_powers: np.ndarray
    residual: float
    loss: float
    iterations: int


def make_hadamard_modes(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    radius: float | None = None,
    centre: tuple[float, float] | None = None,
    circular_pupil: bool = True,
) -> np.ndarray:
    """Make the Hadamard mode stack used by the backwards solver."""

    if circular_pupil:
        return BeamGenerator.make_circular_hadamard_phase_profiles(
            shape,
            n_superpixels_x,
            n_superpixels_y,
            radius=radius,
            centre=centre,
        )

    return BeamGenerator.make_hadamard_phase_profiles(
        shape,
        n_superpixels_x,
        n_superpixels_y,
        radius=radius,
        centre=centre,
    )


def transmission_matrix_to_power_operators(T: np.ndarray) -> np.ndarray:
    """Convert a field transmission matrix to power measurement operators.

    If ``a = T @ c`` is the output field amplitude vector, then the measured
    output powers can be written as ``p[k] = c.conj().T @ M[k] @ c``.
    """

    T = np.asarray(T, dtype=complex)
    if T.ndim != 2:
        raise ValueError("T must be a 2D matrix")

    operators = np.empty((T.shape[0], T.shape[1], T.shape[1]), dtype=complex)
    for output_idx, row in enumerate(T):
        operators[output_idx] = np.outer(np.conj(row), row)
    return operators


def coeffs_to_density_matrix(coeffs: np.ndarray) -> np.ndarray:
    """Return the pure-state density matrix ``rho = c c^dagger``."""

    coeffs = np.asarray(coeffs, dtype=complex)
    if coeffs.ndim != 1:
        raise ValueError("coeffs must be a 1D array")
    return np.outer(coeffs, np.conj(coeffs))


def predict_powers_from_coeffs(
    coeffs: np.ndarray,
    power_operators: np.ndarray,
) -> np.ndarray:
    """Predict lantern powers from Hadamard coefficients."""

    coeffs = np.asarray(coeffs, dtype=complex)
    power_operators = _validate_power_operators(power_operators)
    if coeffs.shape != (power_operators.shape[1],):
        raise ValueError(f"coeffs must have shape ({power_operators.shape[1]},)")

    powers = np.einsum("i,kij,j->k", np.conj(coeffs), power_operators, coeffs)
    return np.real_if_close(powers).real


def predict_powers_from_density_matrix(
    density_matrix: np.ndarray,
    power_operators: np.ndarray,
) -> np.ndarray:
    """Predict lantern powers from an input density matrix."""

    density_matrix = np.asarray(density_matrix, dtype=complex)
    power_operators = _validate_power_operators(power_operators)
    if density_matrix.shape != power_operators.shape[1:]:
        raise ValueError(
            f"density_matrix must have shape {power_operators.shape[1:]}"
        )

    powers = np.einsum("kij,ji->k", power_operators, density_matrix)
    return np.real_if_close(powers).real


def reconstruct_field_from_hadamard_coeffs(
    coeffs: np.ndarray,
    hadamard_modes: np.ndarray,
) -> np.ndarray:
    """Superimpose Hadamard fields with complex coefficients."""

    coeffs = np.asarray(coeffs, dtype=complex)
    hadamard_modes = np.asarray(hadamard_modes, dtype=complex)
    if hadamard_modes.ndim != 3:
        raise ValueError("hadamard_modes must have shape (n_modes, height, width)")
    if coeffs.shape != (hadamard_modes.shape[0],):
        raise ValueError(f"coeffs must have shape ({hadamard_modes.shape[0]},)")

    return np.tensordot(coeffs, hadamard_modes, axes=(0, 0))


def phase_mask_from_field(field: np.ndarray) -> np.ndarray:
    """Return the phase-only mask for a complex reconstructed field."""

    return np.angle(np.asarray(field, dtype=complex))


def solve_hadamard_coeffs_from_powers(
    power_operators: np.ndarray,
    target_powers: np.ndarray,
    hadamard_modes: np.ndarray,
    n_restarts: int = 32,
    n_iterations: int = 1000,
    step_size: float = 0.05,
    normalize_coeffs: bool = True,
    seed: int | None = None,
    initial_coeffs: np.ndarray | None = None,
) -> HadamardBackwardSolution:
    """Fit Hadamard coefficients directly to output powers.

    This solves the pure-state problem
    ``target_powers[k] ~= c.conj().T @ M[k] @ c``. The solution is generally
    not unique, because a small number of output powers cannot uniquely
    determine a high-dimensional input state.
    """

    power_operators = _validate_power_operators(power_operators)
    target_powers = _validate_target_powers(target_powers, power_operators.shape[0])
    hadamard_modes = np.asarray(hadamard_modes, dtype=complex)
    if hadamard_modes.shape[0] != power_operators.shape[1]:
        raise ValueError("hadamard_modes count must match operator input dimension")
    if n_restarts < 1:
        raise ValueError("n_restarts must be positive")
    if n_iterations < 1:
        raise ValueError("n_iterations must be positive")
    if step_size <= 0:
        raise ValueError("step_size must be positive")

    rng = np.random.default_rng(seed)
    initial_vectors = _make_initial_vectors(
        power_operators.shape[1],
        n_restarts,
        rng,
        initial_coeffs,
        normalize_coeffs,
    )

    best_coeffs = None
    best_loss = np.inf
    best_iterations = 0
    for coeffs in initial_vectors:
        coeffs, loss, iterations = _fit_single_restart(
            coeffs,
            power_operators,
            target_powers,
            n_iterations,
            step_size,
            normalize_coeffs,
        )
        if loss < best_loss:
            best_coeffs = coeffs
            best_loss = loss
            best_iterations = iterations

    predicted_powers = predict_powers_from_coeffs(best_coeffs, power_operators)
    field = reconstruct_field_from_hadamard_coeffs(best_coeffs, hadamard_modes)
    phase_mask = phase_mask_from_field(field)
    residual = np.linalg.norm(predicted_powers - target_powers)

    return HadamardBackwardSolution(
        coeffs=best_coeffs,
        field=field,
        phase_mask=phase_mask,
        predicted_powers=predicted_powers,
        target_powers=target_powers,
        residual=float(residual),
        loss=float(best_loss),
        iterations=best_iterations,
    )


def solve_hadamard_coeffs_from_transmission_matrix(
    T: np.ndarray,
    target_powers: np.ndarray,
    hadamard_modes: np.ndarray,
    **kwargs,
) -> HadamardBackwardSolution:
    """Fit Hadamard coefficients using a Hadamard-to-lantern transmission matrix."""

    power_operators = transmission_matrix_to_power_operators(T)
    return solve_hadamard_coeffs_from_powers(
        power_operators,
        target_powers,
        hadamard_modes,
        **kwargs,
    )


def _fit_single_restart(
    coeffs: np.ndarray,
    power_operators: np.ndarray,
    target_powers: np.ndarray,
    n_iterations: int,
    step_size: float,
    normalize_coeffs: bool,
) -> tuple[np.ndarray, float, int]:
    loss = _power_loss(coeffs, power_operators, target_powers)
    step = step_size

    for iteration in range(1, n_iterations + 1):
        powers = predict_powers_from_coeffs(coeffs, power_operators)
        errors = powers - target_powers
        gradient = 2.0 * np.einsum("k,kij,j->i", errors, power_operators, coeffs)
        trial = coeffs - step * gradient
        if normalize_coeffs:
            trial = _normalize(trial)

        trial_loss = _power_loss(trial, power_operators, target_powers)
        if trial_loss <= loss:
            coeffs = trial
            loss = trial_loss
            step *= 1.02
        else:
            step *= 0.5

        if step < 1e-14:
            return coeffs, loss, iteration

    return coeffs, loss, n_iterations


def _power_loss(
    coeffs: np.ndarray,
    power_operators: np.ndarray,
    target_powers: np.ndarray,
) -> float:
    errors = predict_powers_from_coeffs(coeffs, power_operators) - target_powers
    return float(0.5 * np.dot(errors, errors))


def _make_initial_vectors(
    n_modes: int,
    n_restarts: int,
    rng: np.random.Generator,
    initial_coeffs: np.ndarray | None,
    normalize_coeffs: bool,
) -> list[np.ndarray]:
    vectors = []
    if initial_coeffs is not None:
        initial_coeffs = np.asarray(initial_coeffs, dtype=complex)
        if initial_coeffs.shape != (n_modes,):
            raise ValueError(f"initial_coeffs must have shape ({n_modes},)")
        vectors.append(_normalize(initial_coeffs) if normalize_coeffs else initial_coeffs)

    while len(vectors) < n_restarts:
        coeffs = rng.normal(size=n_modes) + 1j * rng.normal(size=n_modes)
        vectors.append(_normalize(coeffs) if normalize_coeffs else coeffs)
    return vectors


def _normalize(coeffs: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(coeffs)
    if norm == 0:
        raise ValueError("cannot normalize a zero coefficient vector")
    return coeffs / norm


def _validate_power_operators(power_operators: np.ndarray) -> np.ndarray:
    power_operators = np.asarray(power_operators, dtype=complex)
    if power_operators.ndim != 3:
        raise ValueError("power_operators must have shape (n_outputs, n_modes, n_modes)")
    if power_operators.shape[1] != power_operators.shape[2]:
        raise ValueError("power_operators must be square in the last two axes")
    return power_operators


def _validate_target_powers(
    target_powers: np.ndarray,
    n_outputs: int,
) -> np.ndarray:
    target_powers = np.asarray(target_powers, dtype=float)
    if target_powers.shape != (n_outputs,):
        raise ValueError(f"target_powers must have shape ({n_outputs},)")
    if np.any(target_powers < 0):
        raise ValueError("target_powers must be non-negative")
    return target_powers
