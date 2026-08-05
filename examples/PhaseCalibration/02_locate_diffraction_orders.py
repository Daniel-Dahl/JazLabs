"""Display blank and binary SLM patterns for locating diffraction orders."""

import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass
from JazLabs.hardware.SLM.SLMStack import SLMClient
import JazLabs.procedures.SLM.SLM_PhaseCalibration as PhaseCalibration

import phase_calibration_config as config


def main():
    slm_client = None
    phase_mask = None

    try:
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
        slm_client.LoadLutFile(str(config.INITIAL_LUT_FILE))

        phase_mask.Clear_Display(config.CHANNEL)
        input(
            "The SLM is blank. Record the zeroth-order (x, y) position in "
            "the live camera viewer, then press Enter. "
        )

        PhaseCalibration.DisplayBinaryDiffractionPattern(
            phase_mask,
            config.CHANNEL,
            Direction=config.GRATING_DIRECTION,
            strip_width=config.STRIPE_WIDTH,
            strip_value=config.DIAGNOSTIC_GREY_LEVEL,
        )
        input(
            "The binary grating is displayed. Record the +1 and -1 order "
            "(x, y) positions, then press Enter to clear the SLM. "
        )

        print(
            "Enter the positions in phase_calibration_config.py as "
            "[row, column] = [y, x]."
        )
    finally:
        if phase_mask is not None:
            phase_mask.Clear_Display(config.CHANNEL)
        if slm_client is not None:
            slm_client.close()


if __name__ == "__main__":
    main()
