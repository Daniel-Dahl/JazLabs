"""Acquire and save the binary-grating grey-level sweep."""

from datetime import datetime

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt

import JazLabs.hardware.Cameras.Camera_Client as CameraClientLib
import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass
from JazLabs.hardware.SLM.SLMStack import SLMClient
import JazLabs.procedures.SLM.SLM_PhaseCalibration as PhaseCalibration

import phase_calibration_config as config


def main():
    camera_client = None
    slm_client = None
    phase_mask = None

    try:
        camera_client = CameraClientLib.CameraClient(
            host=config.SERVER_HOST,
            command_port=config.CAMERA_COMMAND_PORT,
            frame_pub_port=config.CAMERA_FRAME_PORT,
            timeout_ms=60000,
            client_id="slm_phase_calibration_acquisition",
        )
        slm_client = SLMClient(
            host=config.SERVER_HOST,
            command_port=config.SLM_COMMAND_PORT,
            display_pub_port=config.SLM_DISPLAY_PORT,
            timeout_ms=5000,
            attach_viewer_shared_memory=False,
        )
        phase_mask = PhaseMaskClass.PhaseMaskObject(
            SLMObject=slm_client,
            ActiveRGBChannels=[config.CHANNEL],
            pixel_size=config.SLM_PIXEL_SIZE,
            wavelength=config.SLM_WAVELENGTH,
        )
        phase_mask.polProps[config.CHANNEL]["V"].polEnabled = False
        phase_mask.LoadMaskProperties(
            filenamePrefix=config.MASK_PROPERTIES_FILENAME,
            PolSelector=config.POLARISATION,
        )
        slm_client.LoadLutFile(str(config.INITIAL_LUT_FILE))

        zero_order_power, plus_first_power, minus_first_power = (
            PhaseCalibration.PhaseCalibration_BinaryDiffraction_Cam_0thAnd1stOrder(
                slm=phase_mask,
                Cam=camera_client,
                channel=config.CHANNEL,
                Direction=config.GRATING_DIRECTION,
                imask=config.MASK_INDEX,
                pol=config.POLARISATION,
                backgroundLevel=config.BACKGROUND_LEVEL,
                strip_width=config.STRIPE_WIDTH,
                camframeAvg=config.CAMERA_FRAME_AVERAGES,
                ixCamCenter0th=config.DIFFRACTION_ORDER_CENTERS["0th"][0],
                iyCamCenter0th=config.DIFFRACTION_ORDER_CENTERS["0th"][1],
                ixCamCenter_plus1st=config.DIFFRACTION_ORDER_CENTERS["+1st"][0],
                iyCamCenter_plus1st=config.DIFFRACTION_ORDER_CENTERS["+1st"][1],
                ixCamCenter_minus1st=config.DIFFRACTION_ORDER_CENTERS["-1st"][0],
                iyCamCenter_minus1st=config.DIFFRACTION_ORDER_CENTERS["-1st"][1],
                x_half_width=config.APERTURE_HALF_WIDTH_X,
                y_half_width=config.APERTURE_HALF_WIDTH_Y,
                phaseLevels=256,
                Verbose=True,
            )
        )
    finally:
        if phase_mask is not None:
            phase_mask.Clear_Display(config.CHANNEL)
        if slm_client is not None:
            slm_client.close()
        if camera_client is not None:
            camera_client.close()

    acquisition_metadata = {
        "acquired_at": datetime.now().astimezone().isoformat(),
        "channel": config.CHANNEL,
        "polarisation": config.POLARISATION,
        "mask_index": config.MASK_INDEX,
        "slm_wavelength_m": config.SLM_WAVELENGTH,
        "slm_pixel_size_m": config.SLM_PIXEL_SIZE,
        "initial_lut_file": str(config.INITIAL_LUT_FILE),
        "grating_direction": config.GRATING_DIRECTION,
        "stripe_width_px": config.STRIPE_WIDTH,
        "camera_frame_averages": config.CAMERA_FRAME_AVERAGES,
        "aperture_half_width_x_px": config.APERTURE_HALF_WIDTH_X,
        "aperture_half_width_y_px": config.APERTURE_HALF_WIDTH_Y,
        "diffraction_order_centers": config.DIFFRACTION_ORDER_CENTERS,
    }
    saved_path = PhaseCalibration.SavePhaseCalibrationMeasurements(
        str(config.RAW_DATA_FILE),
        zero_order_power,
        plus_first_power,
        minus_first_power,
        metadata=acquisition_metadata,
    )

    config.RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    figure, _ = PhaseCalibration.PlotPhaseCalibrationMeasurements(
        zero_order_power,
        plus_first_power,
        minus_first_power,
        include_reference=False,
    )
    plot_path = config.RESULTS_DIRECTORY / "raw_diffraction_order_power.png"
    figure.savefig(plot_path, dpi=160)
    plt.close(figure)

    print(f"Saved raw calibration: {saved_path}")
    print(f"Saved raw measurement plot: {plot_path}")


if __name__ == "__main__":
    main()
