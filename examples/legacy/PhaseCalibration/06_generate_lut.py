"""Generate LUT files from an explicitly accepted phase-response fit."""

import argparse
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

import JazLabs.procedures.SLM.SLMPhaseCalibrationFunctions as PhaseAnalysis

import phase_calibration_config as config


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate a new SLM LUT from the saved phase fit."
    )
    parser.add_argument(
        "--accept-fit",
        action="store_true",
        help="Confirm that phase_response_fit.png has been inspected and accepted.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not args.accept_fit:
        raise SystemExit(
            "LUT generation was not approved. Inspect phase_response_fit.png, "
            "then rerun with --accept-fit."
        )

    output_lut_path = Path(f"{config.NEW_LUT_PREFIX}.lut")
    output_blt_path = Path(f"{config.NEW_LUT_PREFIX}.blt")
    existing_outputs = [
        path for path in (output_lut_path, output_blt_path) if path.exists()
    ]
    if existing_outputs:
        raise FileExistsError(
            "Refusing to overwrite an existing LUT. Set a new NEW_LUT_PREFIX: "
            + ", ".join(str(path) for path in existing_outputs)
        )

    with np.load(config.FIT_DATA_FILE, allow_pickle=False) as fit_data:
        recovered_phase = np.copy(fit_data["recovered_phase"])

    phase_count = recovered_phase.size
    overlap_signal_reference = np.exp(1j * recovered_phase)
    overlap_reference_reference = recovered_phase
    overlap_signal_signal = recovered_phase

    config.NEW_LUT_PREFIX.parent.mkdir(parents=True, exist_ok=True)
    config.RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    plt.close("all")

    original_directory = Path.cwd()
    try:
        # CalculatePhaseAndVoltageLevels also writes SLM_CAL.mat to the current
        # directory, so keep that diagnostic beside the other result files.
        os.chdir(config.RESULTS_DIRECTORY)
        lut_results = PhaseAnalysis.CalculatePhaseAndVoltageLevels(
            True,
            str(config.BASE_LUT_FILE),
            str(config.NEW_LUT_PREFIX),
            phase_count,
            config.PHASE_STROKE,
            config.PHASE_OFFSET,
            overlap_signal_reference,
            overlap_reference_reference,
            overlap_signal_signal,
        )
    finally:
        os.chdir(original_directory)

    for plot_index, figure_number in enumerate(plt.get_fignums(), start=1):
        figure = plt.figure(figure_number)
        plot_path = config.RESULTS_DIRECTORY / f"lut_generation_{plot_index:02d}.png"
        figure.savefig(plot_path, dpi=160)
    plt.close("all")

    diagnostics_path = config.RESULTS_DIRECTORY / "lut_generation_data.npz"
    np.savez(
        diagnostics_path,
        measured_phase=lut_results.PhaseShiftUnwrap,
        fitted_phase=lut_results.Fited_PhaseShiftUnwrap,
        old_voltage_lut=lut_results.OldVoltageLutVal,
        new_voltage_lut=lut_results.NewVoltageLutVal,
        new_phase_lut=lut_results.NewPhaseLut,
    )

    print(f"Generated LUT: {output_lut_path}")
    print(f"Generated BLT: {output_blt_path}")
    print(f"Saved LUT diagnostics: {diagnostics_path}")
    print("Copy the LUT to the SLM server machine before validation if required.")


if __name__ == "__main__":
    main()
