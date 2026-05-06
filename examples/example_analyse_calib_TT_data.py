#!/usr/bin/env python3
"""
Minimal script to run tip/tilt calibration analysis.

All calibration logic, fitting, printing, and plotting is in tiptilt_calibration_core.py.
Edit the configuration section below, then run this script.
"""

from pathlib import Path

import numpy as np

from pwi_inst.procedures.TipTiltMirror.tiptilt_calibration_core import analyse_and_save_calibration, BaseTipTiltCalibration

# ============================================================
# Configuration — edit these
# ============================================================

DATADIR    = Path('/Users/bnorris/DataAnalysis/IRPL_testbed/Data_202603-04/')
VOLTS_FILE = DATADIR / "all_dac_volts_2d_20260407_165839.npy"
XY_FILE    = DATADIR / "all_xyvals_2d_20260407_165839.npy"

# Model to fit: "affine" (linear, analytic inverse) or "quadratic" (nonlinear, numeric inverse)
MODEL_TYPE = "affine"

# If True, also fits the other model type and prints a side-by-side comparison
COMPARE_WITH_OTHER_MODEL = True

# ============================================================
# Fit and save calibration
# ============================================================

cal = analyse_and_save_calibration(
    volts_file=VOLTS_FILE,
    xy_file=XY_FILE,
    output_plot=DATADIR / f"piezo_tiptilt_calibration_plot_{MODEL_TYPE}.png",
    output_json=DATADIR / f"piezo_tiptilt_calibration_{MODEL_TYPE}.json",
    model_type=MODEL_TYPE,
    compare_with_other_model=COMPARE_WITH_OTHER_MODEL,
)

# ============================================================
# Usage examples
# ============================================================

print("\n" + "="*80)
print("USAGE EXAMPLES")
print("="*80)

# --- Example 1: absolute pixel position -> absolute DAC voltages ---
# Use this for positioning: "move the PSF to pixel (x, y)"
print("\n=== Example 1: Absolute pixel position to DAC voltages ===")
x_target, y_target = 512.3, 480.1
V1, V2 = cal.absolute_xy_to_dac(x_target, y_target)
print(f"Target (x,y)=({x_target:.1f},{y_target:.1f}) px  ->  (V1,V2)=({V1:.6f},{V2:.6f}) V")

# --- Example 2: load a saved calibration from JSON and use it ---
print("\n=== Example 2: Load saved calibration from JSON ===")
cal_loaded = BaseTipTiltCalibration.load_json(DATADIR / f"piezo_tiptilt_calibration_{MODEL_TYPE}.json")
print(f"Loaded model type: {cal_loaded.model_type}")
x_target, y_target = 510.0, 482.5
V1, V2 = cal_loaded.absolute_xy_to_dac(x_target, y_target)
print(f"Target (x,y)=({x_target:.1f},{y_target:.1f}) px  ->  (V1,V2)=({V1:.6f},{V2:.6f}) V")

# --- Example 3: pixel offset -> voltage offset (for incremental corrections) ---
# Use this in a control loop: "shift the PSF by (dx, dy) pixels from its current position"
# For quadratic, supply current DAC voltages as the reference operating point.
print("\n=== Example 3: Pixel offset to voltage offset (incremental) ===")
dx, dy = 1.0, 0.5
if MODEL_TYPE == "affine":
    dV1, dV2 = cal.offset_pixels_to_dac(dx, dy)
else:
    current_volts = np.array([0.0, 0.0], dtype=float)  # replace with actual DAC state
    dV1, dV2 = cal.offset_pixels_to_dac(dx, dy, reference_volts=current_volts)
print(f"Offset (dx,dy)=({dx:.3f},{dy:.3f}) px  ->  (dV1,dV2)=({dV1:.6f},{dV2:.6f}) V")
