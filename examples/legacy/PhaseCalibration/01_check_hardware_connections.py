"""Connect to the camera and SLM and verify the starting configuration."""

import pprint

import JazLabs.hardware.Cameras.Camera_Client as CameraClientLib
import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass
from JazLabs.hardware.SLM.SLMStack import SLMClient

import phase_calibration_config as config


def main():
    camera_client = None
    slm_client = None

    try:
        camera_client = CameraClientLib.CameraClient(
            host=config.SERVER_HOST,
            command_port=config.CAMERA_COMMAND_PORT,
            frame_pub_port=config.CAMERA_FRAME_PORT,
            timeout_ms=60000,
            client_id="slm_phase_calibration_connection_check",
        )
        print("Camera connection succeeded:")
        pprint.pprint(camera_client.GetProperties())

        slm_client = SLMClient(
            host=config.SERVER_HOST,
            command_port=config.SLM_COMMAND_PORT,
            display_pub_port=config.SLM_DISPLAY_PORT,
            timeout_ms=5000,
            attach_viewer_shared_memory=False,
        )
        print("SLM connection succeeded:")
        pprint.pprint(slm_client.GetProperties())

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
        print(f"Loaded starting LUT: {config.INITIAL_LUT_FILE}")
        print("Hardware and mask configuration are ready.")
    finally:
        if slm_client is not None:
            slm_client.close()
        if camera_client is not None:
            camera_client.close()


if __name__ == "__main__":
    main()
