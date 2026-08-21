"""Fit the saved diffraction powers and save the recovered SLM phase."""

import json

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

import JazLabs.procedures.SLM.SLM_PhaseCalibration as PhaseCalibration
import JazLabs.procedures.SLM.SLMPhaseCalibrationFunctions as PhaseAnalysis

import phase_calibration_config as config


def main():
    measurements, acquisition_metadata = (
        PhaseCalibration.LoadPhaseCalibrationMeasurements(str(config.RAW_DATA_FILE))
    )
    zero_order_power = measurements["PowerValues_0th"]
    plus_first_power = measurements["PowerValues_plus1st"]
    minus_first_power = measurements["PowerValues_minus1st"]
    grey_levels = np.arange(zero_order_power.size - 1)

    phase_fit = PhaseAnalysis.fit_slm_phase_I0_Ipm1(
        grey_levels,
        zero_order_power[:-1],
        plus_first_power[:-1],
        minus_first_power[:-1],
        n_knots=config.FIT_N_KNOTS,
        poly_deg=config.FIT_POLYNOMIAL_DEGREE,
        phi_max_guess=config.FIT_PHASE_MAX_GUESS,
        lam_curv=config.FIT_CURVATURE_PENALTY,
        robust=config.FIT_ROBUST,
    )

    fit_metadata = {
        "raw_data_file": str(config.RAW_DATA_FILE),
        "acquisition_metadata": acquisition_metadata,
        "n_knots": config.FIT_N_KNOTS,
        "polynomial_degree": config.FIT_POLYNOMIAL_DEGREE,
        "phase_max_guess_rad": float(config.FIT_PHASE_MAX_GUESS),
        "curvature_penalty": config.FIT_CURVATURE_PENALTY,
        "robust": config.FIT_ROBUST,
        "fit_success": bool(phase_fit["scipy_result"].success),
        "fit_message": str(phase_fit["scipy_result"].message),
        "recovered_phase_stroke_rad": float(phase_fit["phi_end"]),
    }
    config.FIT_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        config.FIT_DATA_FILE,
        grey_levels=phase_fit["g"],
        recovered_phase=phase_fit["phi"],
        phase_knots=phase_fit["phi_knots"],
        grey_level_knots=phase_fit["g_knots"],
        zero_order_fit=phase_fit["I0_fit"],
        summed_first_order_fit=phase_fit["I1_fit"],
        metadata_json=np.asarray(json.dumps(fit_metadata, indent=2)),
    )

    config.RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    figure, _ = PhaseCalibration.PlotPhaseCalibrationFit(
        phase_fit,
        zero_order_power,
        plus_first_power,
        minus_first_power,
    )
    plot_path = config.RESULTS_DIRECTORY / "phase_response_fit.png"
    figure.savefig(plot_path, dpi=160)
    plt.close(figure)

    print(f"Recovered phase stroke: {phase_fit['phi_end'] / np.pi:.4f} pi")
    print(f"Fit success: {phase_fit['scipy_result'].success}")
    print(f"Fit message: {phase_fit['scipy_result'].message}")
    print(f"Saved fit data: {config.FIT_DATA_FILE}")
    print(f"Saved fit plot: {plot_path}")
    print("Inspect the plot before approving LUT generation.")


if __name__ == "__main__":
    main()
