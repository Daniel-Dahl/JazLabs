import numpy as np
import pytest

from JazLabs.simulator.HighDimStokesMeasurement import (
    build_superpixel_focal_coupling,
    compare_matrices,
    generate_physical_stokes_measurements,
    generate_stokes_measurements,
    make_circular_tophat,
    make_gaussian_focal_modes,
    make_hadamard_basis,
    make_matched_focal_modes,
    make_superpixel_map,
    phase_mask_to_pupil_field,
    project_field_onto_modes,
    propagate_pupil_to_focal_plane,
    reconstruct_field_from_mode_coeffs,
    reconstruct_T_from_physical_stokes,
    reconstruct_T_from_stokes,
    simulate_lantern_powers,
    simulate_lantern_powers_from_modal_coeffs,
    simulate_lantern_powers_from_phase_mask,
    solve_input_coeffs_from_output_powers,
)


def test_circular_pupil_shape_and_values():
    pupil = make_circular_tophat((32, 40), radius=10)

    assert pupil.shape == (32, 40)
    assert set(np.unique(pupil)).issubset({0.0, 1.0})
    assert pupil.sum() > 0
    assert pupil[0, 0] == 0


def test_superpixel_indexing_is_compact_inside_pupil():
    pupil = make_circular_tophat((32, 32), radius=13)
    labels = make_superpixel_map((32, 32), 4, 4, pupil)
    valid_labels = np.unique(labels[labels >= 0])

    assert labels.shape == (32, 32)
    assert np.all(labels[pupil == 0] == -1)
    assert np.array_equal(valid_labels, np.arange(valid_labels.size))


def test_simulate_lantern_powers_dimensions():
    T = np.ones((3, 5), dtype=complex)
    coeffs = np.ones(5, dtype=complex) / np.sqrt(5)

    powers = simulate_lantern_powers(T, coeffs)

    assert powers.shape == (3,)


def test_noiseless_stokes_reconstruction_recovers_row_phase_ambiguity():
    rng = np.random.default_rng(11)
    n_outputs = 6
    n_modes = 9
    T_true = (
        rng.normal(size=(n_outputs, n_modes))
        + 1j * rng.normal(size=(n_outputs, n_modes))
    ) / np.sqrt(2 * n_modes)
    T_true[:, 0] += 0.5

    measurements = generate_stokes_measurements(T_true)
    T_est, diagnostics = reconstruct_T_from_stokes(
        measurements,
        n_outputs=n_outputs,
        n_modes=n_modes,
    )
    comparison = compare_matrices(T_true, T_est)

    assert np.all(diagnostics["reference_is_mode_zero"])
    assert comparison.relative_error < 1e-12
    assert comparison.amplitude_error < 1e-12
    assert comparison.phase_error < 1e-12


def test_hadamard_non_power_of_two_raises_clear_error():
    with pytest.raises(ValueError, match="power of two"):
        make_hadamard_basis(6)


def test_fourier_forward_model_shapes_and_projection():
    shape = (32, 32)
    pupil = make_circular_tophat(shape, radius=12)
    phase = np.zeros(shape)
    pupil_field = phase_mask_to_pupil_field(phase, pupil)
    focal_field = propagate_pupil_to_focal_plane(pupil_field)
    modes = make_gaussian_focal_modes(shape, np.array([[16, 16], [16, 20]]), waist=3)
    coeffs = project_field_onto_modes(focal_field, modes)

    assert pupil_field.shape == shape
    assert focal_field.shape == shape
    assert modes.shape == (2, *shape)
    assert coeffs.shape == (2,)


def test_phase_mask_power_matches_manual_projection():
    shape = (32, 32)
    pupil = make_circular_tophat(shape, radius=12)
    phase = np.zeros(shape)
    modes = make_gaussian_focal_modes(shape, np.array([[16, 16], [16, 20]]), waist=3)
    T = np.array([[1.0, 0.5j], [0.2, 1.0]], dtype=complex)

    powers, input_coeffs, focal_field = simulate_lantern_powers_from_phase_mask(
        T,
        phase,
        pupil,
        modes,
    )
    manual_coeffs = project_field_onto_modes(focal_field, modes)
    manual_powers = simulate_lantern_powers(T, manual_coeffs)

    assert np.allclose(input_coeffs, manual_coeffs)
    assert np.allclose(powers, manual_powers)


def test_superpixel_focal_coupling_builds_effective_matrix():
    shape = (32, 32)
    pupil = make_circular_tophat(shape, radius=12)
    labels = make_superpixel_map(shape, 3, 2, pupil)
    n_superpixels = int(labels.max() + 1)
    modes = make_gaussian_focal_modes(shape, np.array([[16, 16], [16, 20]]), waist=3)

    coupling = build_superpixel_focal_coupling(labels, pupil, modes)

    assert coupling.shape == (2, n_superpixels)


def test_physical_stokes_recovers_raw_T_with_known_forward_model():
    shape = (32, 32)
    pupil = make_circular_tophat(shape, radius=12)
    labels = make_superpixel_map(shape, 3, 2, pupil)
    n_superpixels = int(labels.max() + 1)
    modes = make_matched_focal_modes(labels, pupil)
    forward_model = build_superpixel_focal_coupling(labels, pupil, modes)
    rng = np.random.default_rng(12)
    T_true = (
        rng.normal(size=(6, 6)) + 1j * rng.normal(size=(6, 6))
    ) / np.sqrt(12)

    powers, physical_input = simulate_lantern_powers_from_modal_coeffs(
        T_true,
        np.eye(n_superpixels, dtype=complex)[0],
        forward_model,
    )
    assert powers.shape == (6,)
    assert physical_input.shape == (6,)

    measurements = generate_physical_stokes_measurements(T_true, forward_model)
    T_est, diagnostics = reconstruct_T_from_physical_stokes(
        measurements,
        n_outputs=6,
        n_lantern_inputs=6,
    )
    comparison = compare_matrices(T_true, T_est)

    assert diagnostics["T_commanded"].shape == (6, n_superpixels)
    assert comparison.relative_error < 1e-12


def test_backward_power_solution_reproduces_target_powers():
    rng = np.random.default_rng(13)
    T = (
        rng.normal(size=(6, 6)) + 1j * rng.normal(size=(6, 6))
    ) / np.sqrt(12)
    true_coeffs = (
        rng.normal(size=6) + 1j * rng.normal(size=6)
    ) / np.sqrt(12)
    target_powers = simulate_lantern_powers(T, true_coeffs)
    target_phases = np.angle(T @ true_coeffs)

    solution = solve_input_coeffs_from_output_powers(
        T,
        target_powers,
        output_phases=target_phases,
    )

    assert np.allclose(solution.predicted_powers, target_powers)
    assert np.allclose(T @ solution.commanded_coeffs, T @ true_coeffs)


def test_backward_power_solution_uses_forward_model():
    rng = np.random.default_rng(14)
    T = (
        rng.normal(size=(6, 6)) + 1j * rng.normal(size=(6, 6))
    ) / np.sqrt(12)
    forward_model = (
        rng.normal(size=(6, 8)) + 1j * rng.normal(size=(6, 8))
    ) / np.sqrt(16)
    commanded_coeffs = (
        rng.normal(size=8) + 1j * rng.normal(size=8)
    ) / np.sqrt(16)
    effective_matrix = T @ forward_model
    target_powers = np.abs(effective_matrix @ commanded_coeffs) ** 2
    target_phases = np.angle(effective_matrix @ commanded_coeffs)

    solution = solve_input_coeffs_from_output_powers(
        T,
        target_powers,
        output_phases=target_phases,
        forward_model=forward_model,
    )

    assert solution.commanded_coeffs.shape == (8,)
    assert np.allclose(solution.predicted_powers, target_powers)


def test_reconstruct_field_from_mode_coeffs_superimposes_modes():
    modes = np.zeros((2, 3, 3), dtype=complex)
    modes[0, 1, 1] = 1.0
    modes[1, 0, 0] = 1.0j
    coeffs = np.array([2.0, -1.0j])

    field = reconstruct_field_from_mode_coeffs(coeffs, modes)

    assert field[1, 1] == 2.0
    assert field[0, 0] == 1.0
