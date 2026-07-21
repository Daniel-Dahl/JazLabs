import numpy as np

from JazLabs.simulator.HadamardBackward import (
    coeffs_to_density_matrix,
    predict_powers_from_coeffs,
    predict_powers_from_density_matrix,
    transmission_matrix_to_power_operators,
)


def test_power_operators_match_transmission_matrix_powers():
    rng = np.random.default_rng(31)
    T = rng.normal(size=(6, 8)) + 1j * rng.normal(size=(6, 8))
    coeffs = rng.normal(size=8) + 1j * rng.normal(size=8)

    operators = transmission_matrix_to_power_operators(T)
    expected = np.abs(T @ coeffs) ** 2
    predicted = predict_powers_from_coeffs(coeffs, operators)

    assert np.allclose(predicted, expected)


def test_density_matrix_prediction_matches_pure_coeff_prediction():
    rng = np.random.default_rng(32)
    T = rng.normal(size=(6, 8)) + 1j * rng.normal(size=(6, 8))
    coeffs = rng.normal(size=8) + 1j * rng.normal(size=8)
    operators = transmission_matrix_to_power_operators(T)
    density_matrix = coeffs_to_density_matrix(coeffs)

    coeff_powers = predict_powers_from_coeffs(coeffs, operators)
    density_powers = predict_powers_from_density_matrix(density_matrix, operators)

    assert np.allclose(density_powers, coeff_powers)
