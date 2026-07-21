"""Example 6-output superpixel Stokes tomography simulation."""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import matplotlib.pyplot as plt

SRC_ROOT = Path(__file__).resolve().parents[3]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from JazLabs.simulator.HighDimStokesMeasurement import (
    build_superpixel_focal_coupling,
    coeffs_to_phase_mask,
    compare_matrices,
    generate_physical_stokes_measurements,
    generate_stokes_measurements,
    make_circular_tophat,
    make_matched_focal_modes,
    make_superpixel_map,
    reconstruct_T_from_physical_stokes,
    reconstruct_T_from_stokes,
    simulate_lantern_powers_from_phase_mask,
)


def main() -> None:
    shape = (256, 256)
    pupil = make_circular_tophat(shape, radius=112)
    superpixels = make_superpixel_map(
        shape,
        n_superpixels_x=3,
        n_superpixels_y=2,
        pupil_mask=pupil,
    )
    n_modes = int(superpixels.max() + 1)
    n_outputs = 6
    n_lantern_inputs = 6

    rng = np.random.default_rng(3)
    lantern_input_modes = make_matched_focal_modes(superpixels, pupil)

    T_true = (
        rng.normal(size=(n_outputs, n_lantern_inputs))
        + 1j * rng.normal(size=(n_outputs, n_lantern_inputs))
    ) / np.sqrt(2 * n_lantern_inputs)
    forward_model = build_superpixel_focal_coupling(
        superpixels,
        pupil,
        lantern_input_modes,
    )
    T_commanded = T_true @ forward_model

    physical_measurements = generate_physical_stokes_measurements(
        T_true,
        forward_model,
    )
    T_est, diagnostics = reconstruct_T_from_physical_stokes(
        physical_measurements,
        n_outputs=n_outputs,
        n_lantern_inputs=n_lantern_inputs,
    )
    T_commanded_est, _ = reconstruct_T_from_stokes(
        physical_measurements.stokes,
        n_outputs=n_outputs,
        n_modes=n_modes,
    )
    comparison = compare_matrices(T_true, T_est)
    commanded_comparison = compare_matrices(T_commanded, T_commanded_est)

    print(f"valid superpixel modes: {n_modes}")
    print(f"lantern input modes: {n_lantern_inputs}")
    print(f"measurements: {len(physical_measurements.stokes.input_vectors)}")
    print(f"T_true relative error: {comparison.relative_error:.3e}")
    print(f"T_true amplitude error: {comparison.amplitude_error:.3e}")
    print(f"T_true phase rms error: {comparison.phase_error:.3e} rad")
    print(f"T_commanded relative error: {commanded_comparison.relative_error:.3e}")
    print(f"forward model condition: {diagnostics['forward_model_condition']:.3e}")
    print(f"reference modes: {diagnostics['reference_modes']}")

    single_mode = np.zeros(n_modes, dtype=complex)
    single_mode[0] = 1.0
    binary_phase = np.ones(n_modes, dtype=complex)
    binary_phase[1::2] = -1.0

    phase_mask = coeffs_to_phase_mask(single_mode, superpixels)
    powers, input_coeffs, _ = simulate_lantern_powers_from_phase_mask(
        T_true,
        phase_mask,
        pupil,
        lantern_input_modes,
    )
    print(f"single phase-mask powers: {powers}")
    print(f"projected lantern input amplitudes: {input_coeffs}")

    fig, axes = plt.subplots(1, 3, figsize=(10, 3), constrained_layout=True)
    axes[0].imshow(pupil, cmap="gray")
    axes[0].set_title("Circular pupil")
    axes[1].imshow(coeffs_to_phase_mask(single_mode, superpixels), cmap="twilight")
    axes[1].set_title("Superpixel mode 0")
    axes[2].imshow(coeffs_to_phase_mask(binary_phase, superpixels), cmap="twilight")
    axes[2].set_title("Binary phase")
    for ax in axes:
        ax.set_axis_off()
    plt.show()


if __name__ == "__main__":
    main()
