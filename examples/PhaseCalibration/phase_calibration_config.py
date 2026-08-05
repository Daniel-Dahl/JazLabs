"""Editable settings shared by the SLM phase-calibration scripts."""

from pathlib import Path

import numpy as np
import JazLabs


JAZLABS_ROOT = Path(JazLabs.__file__).resolve().parents[2]

# Camera and SLM server connections.
SERVER_HOST = "127.0.0.1"
CAMERA_COMMAND_PORT = 50733
CAMERA_FRAME_PORT = 50734
SLM_COMMAND_PORT = 5555
SLM_DISPLAY_PORT = 5556

# SLM and mask settings.
CHANNEL = "Red"
POLARISATION = "H"
MASK_INDEX = 0
MASK_PROPERTIES_FILENAME = "SLM_CenterAlignment.npy"
SLM_PIXEL_SIZE = 17e-6
SLM_WAVELENGTH = 1550e-9

# Binary grating and camera measurement settings.
GRATING_DIRECTION = "y"
STRIPE_WIDTH = 25
DIAGNOSTIC_GREY_LEVEL = 128
BACKGROUND_LEVEL = 0
CAMERA_FRAME_AVERAGES = 1
APERTURE_HALF_WIDTH_X = 10
APERTURE_HALF_WIDTH_Y = 10

# Coordinates are [camera row, camera column], or [y, x] in the viewer.
DIFFRACTION_ORDER_CENTERS = {
    "0th": [64, 64],
    "+1st": [64, 100],
    "-1st": [64, 27],
}

# Input LUT and saved analysis files.
LUT_DIRECTORY = JAZLABS_ROOT / "calibrations" / "SLM" / "CustomLutFiles"
INITIAL_LUT_FILE = LUT_DIRECTORY / "1024x1024_linearVoltage.lut"
RAW_DATA_FILE = LUT_DIRECTORY / "PowerPhaseCalibration.npz"
FIT_DATA_FILE = LUT_DIRECTORY / "PowerPhaseCalibrationFit.npz"
RESULTS_DIRECTORY = LUT_DIRECTORY / "PhaseCalibrationResults"

# Fit settings. Adjust these until the measured and fitted curves agree.
FIT_N_KNOTS = 18
FIT_POLYNOMIAL_DEGREE = 2
FIT_PHASE_MAX_GUESS = 2 * np.pi
FIT_CURVATURE_PENALTY = 0.1
FIT_ROBUST = False

# LUT generation settings. BASE_LUT_FILE must be the LUT used for acquisition.
BASE_LUT_FILE = LUT_DIRECTORY / "1024x1024_linearVoltage.lut"
NEW_LUT_PREFIX = LUT_DIRECTORY / "SLM_PhaseCalibration_New_1"
PHASE_STROKE = 2.0 * np.pi
PHASE_OFFSET = 0.0
