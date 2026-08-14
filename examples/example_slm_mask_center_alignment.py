"""Coarse and fine alignment of an SLM mask to the incident beam.

Start the camera and SLM servers before running this example.  The camera GUI
can be used to determine the beam centre and measurement-window dimensions.
"""

import matplotlib.pyplot as plt
import numpy as np

import JazLabs.hardware.Cameras.Camera_Client as CameraClientLib
import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass
from JazLabs.hardware.SLM.SLMStack import SLMClient
import JazLabs.procedures.SLM.SLM_CenterAlignment as SLM_CenterAlignment


# Camera measurement window, determined using the camera viewer.
X_BEAM_CENTER_ON_CAMERA = 64
Y_BEAM_CENTER_ON_CAMERA = 64
X_BEAM_WINDOW_WIDTH = 30
Y_BEAM_WINDOW_WIDTH = 30

# Alignment settings.
SLM_CHANNEL = "Red"
POLARISATION = "H"
STRIPE_WIDTH = 15
MASK_SIZE = [600, 600]
COARSE_STEP_COUNT = 100
BEAM_RADIUS_SCAN_FINAL_RADIUS = 256

# Camera and SLM server connections.
SERVER_HOST = "127.0.0.1"
CAMERA_COMMAND_PORT = 50733
CAMERA_FRAME_PORT = 50734
SLM_COMMAND_PORT = 5555
SLM_DISPLAY_PORT = 5556

# SLM configuration.
SLM_PIXEL_SIZE = 17e-6
SLM_WAVELENGTH = 1550e-9
SLM_REFRESH_TIME = 40e-3
# SLM_LUT_FILE = (
#     r"C:\Program Files\Meadowlark Optics\Blink OverDrive Plus\LUT Files"
#     r"\SLM6658_at1550_75c_2.lut"
# )
from pathlib import Path
import JazLabs
JAZLABS_ROOT = Path(JazLabs.__file__).resolve().parents[2]
LUTFOLDER =JAZLABS_ROOT/ "calibrations"/ "SLM"/ "CustomLutFiles"
SLM_LUT_FILE = str(LUTFOLDER / "SLM_PhaseCalibration_New_2.lut")
# SLM_LUT_FILE = (
#     r"C:\Program Files\Meadowlark Optics\Blink OverDrive Plus\LUT Files"
#     r"\SLM6658_at1550_75c_2.lut"
# )
# Output and optional checks.
MASK_PROPERTIES_FILENAME = "SLM_CenterAlignment.npy"
SAVE_MASK_PROPERTIES = True
LOAD_SAVED_PROPERTIES_AFTER_ALIGNMENT = False
RUN_BEAM_RADIUS_SCAN = True


def main():
    plt.style.use("dark_background")

    camera_client = None
    slm_client = None

    try:
        camera_client = CameraClientLib.CameraClient(
            host=SERVER_HOST,
            command_port=CAMERA_COMMAND_PORT,
            frame_pub_port=CAMERA_FRAME_PORT,
            timeout_ms=60000,
            client_id="slm_mask_center_alignment_example",
        )

        slm_client = SLMClient(
            host=SERVER_HOST,
            command_port=SLM_COMMAND_PORT,
            display_pub_port=SLM_DISPLAY_PORT,
            timeout_ms=5000,
            attach_viewer_shared_memory=False,
        )
        phase_mask = PhaseMaskClass.PhaseMaskObject(
            SLMObject=slm_client,
            ActiveRGBChannels=[SLM_CHANNEL],
            pixel_size=SLM_PIXEL_SIZE,
            wavelength=SLM_WAVELENGTH,
        )
        slm_client.LoadLutFile(SLM_LUT_FILE)
        slm_client.SetRefreshRate(SLM_REFRESH_TIME)

        alignment = SLM_CenterAlignment.AlginmentObj(
            slmObjs=[phase_mask],
            CamObjs=[camera_client],
        )

        # Coarse alignment: progressively reveal the full-screen stripe pattern.
        (
            coarse_metric,
            _coarse_metric_log,
            coarse_positions,
        ) = alignment.SweepAcrossSLM_StripProfile(
            ObjIdx=0,
            channel=SLM_CHANNEL,
            stepCount=COARSE_STEP_COUNT,
            StartingSweepPoint=0,
            strip_width=STRIPE_WIDTH,
            avgFrameCount=1,
            ixCamCenter=Y_BEAM_CENTER_ON_CAMERA,
            iyCamCenter=X_BEAM_CENTER_ON_CAMERA,
            x_half_width=X_BEAM_WINDOW_WIDTH // 2,
            y_half_width=Y_BEAM_WINDOW_WIDTH // 2,
            MetricType="POWERMinusHalfRef",
        )

        y_minimum_index = np.nanargmin(coarse_metric[0, :, 0])
        x_minimum_index = np.nanargmin(coarse_metric[1, :, 0])
        coarse_y_center = int(coarse_positions[0, y_minimum_index, 0])
        coarse_x_center = int(coarse_positions[1, x_minimum_index, 0])

        plt.figure(figsize=(8, 5))
        plt.plot(
            coarse_positions[0, :, 0],
            coarse_metric[0, :, 0],
            ".-",
            label="Y sweep",
        )
        plt.plot(
            coarse_y_center,
            coarse_metric[0, y_minimum_index, 0],
            "ro",
            label="Y minimum",
        )
        plt.plot(
            coarse_positions[1, :, 0],
            coarse_metric[1, :, 0],
            ".-",
            label="X sweep",
        )
        plt.plot(
            coarse_x_center,
            coarse_metric[1, x_minimum_index, 0],
            "ro",
            label="X minimum",
        )
        plt.xlabel("SLM stripe curtain edge position [pixels]")
        plt.ylabel("Alignment metric")
        plt.grid(alpha=0.3)
        plt.legend()
        plt.show()

        phase_mask.polProps[SLM_CHANNEL]["V"].polEnabled=False
        phase_mask.AllMaskProperties[SLM_CHANNEL][POLARISATION][0].center[1] = coarse_x_center
        phase_mask.AllMaskProperties[SLM_CHANNEL][POLARISATION][0].center[0] = coarse_y_center
        print(f"Coarse SLM centre: X={coarse_x_center}, Y={coarse_y_center}")

        # Fine alignment around the centre found by the coarse sweep.
        fine_x_center, fine_y_center = alignment.PerformCenterAlignment_GoldenSearch(
            ObjIdx=0,
            channel=SLM_CHANNEL,
            pol=POLARISATION,
            ApplyZernike=False,
            MaskSize=MASK_SIZE,
            PixelsCountFromCenters=COARSE_STEP_COUNT,
            PlotTracking=True,
            BackgroundPhase=0,
            avgFrameCount=1,
            MetricType="POWERMinusHalfRef",
            stripe_width=STRIPE_WIDTH,
            ixCamCenter=Y_BEAM_CENTER_ON_CAMERA,
            iyCamCenter=X_BEAM_CENTER_ON_CAMERA,
            x_half_width=X_BEAM_WINDOW_WIDTH // 2,
            y_half_width=Y_BEAM_WINDOW_WIDTH // 2,
            Verbose=False,
        )
        print(f"Fine SLM centre: X={fine_x_center}, Y={fine_y_center}")

        if SAVE_MASK_PROPERTIES:
            phase_mask.saveMaskProperties(filenamePrefix=MASK_PROPERTIES_FILENAME)

        if LOAD_SAVED_PROPERTIES_AFTER_ALIGNMENT:
            phase_mask.LoadMaskProperties(filenamePrefix=MASK_PROPERTIES_FILENAME)

        if RUN_BEAM_RADIUS_SCAN:
            beam_radius, beam_metric = alignment.Beam_size_scan_on_SLM(
                ObjIdx=0,
                channel=SLM_CHANNEL,
                pol=POLARISATION,
                ApplyZernike=False,
                InitalRadius=1,
                FinalRadius=BEAM_RADIUS_SCAN_FINAL_RADIUS,
                radiusStep=1,
                avgFrameCount=1,
                PlotResults=False,
                MetricType="POWER",
                ixCamCenter=Y_BEAM_CENTER_ON_CAMERA,
                iyCamCenter=X_BEAM_CENTER_ON_CAMERA,
                x_half_width=Y_BEAM_WINDOW_WIDTH // 2,
                y_half_width=X_BEAM_WINDOW_WIDTH // 2,
            )
            SLM_CenterAlignment.FindPlateauStart(
                beam_radius,
                beam_metric,
                smoothing_window=15,
                plateau_tail_fraction=0.20,
                PlotResults=True,
            )
    finally:
        if slm_client is not None:
            slm_client.close()
        if camera_client is not None:
            camera_client.close()


if __name__ == "__main__":
    main()
