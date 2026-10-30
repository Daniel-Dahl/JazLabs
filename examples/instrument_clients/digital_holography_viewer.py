"""Connect a camera and pass it to the digital holography viewer."""

from JazLabs.hardware.Cameras.Camera_Client import CameraClient
from JazLabs.hardware.digHolo.digHolo_pylibs.digHolo_Veiwer import digholoWindow
from JazLabs.launchers.config import get_named_config, load_config


config = load_config("default_lab")
settings = config["DIGITAL_HOLOGRAPHY_CONFIG"]
camera_settings = get_named_config(config, "CAMERA_SERVERS", settings["camera_name"])
HOST = config["CAMERA_HOST"]
COMMAND_PORT = camera_settings["command_port"]
FRAME_PORT = camera_settings["frame_pub_port"]
PIXEL_SIZE_M = settings["pixel_size_m"]
WAVELENGTH_M = settings["wavelength_m"]
FFT_RADIUS = settings["fft_radius"]
MAX_MODE_GROUP = settings["max_mode_group"]


camera = CameraClient(
    host=HOST,
    command_port=COMMAND_PORT,
    frame_pub_port=FRAME_PORT,
)

viewer = digholoWindow(
    CamObj=camera,
    host=HOST,
    command_port=COMMAND_PORT,
    frame_pub_port=FRAME_PORT,
    PixelSize=PIXEL_SIZE_M,
    Wavelength=WAVELENGTH_M,
)

viewer.Set_digholoWindowProps(
    {
        "FFTRadius": FFT_RADIUS,
        "maxMG": MAX_MODE_GROUP,
    }
)
viewer.digholoWindowAutoAlgin()

try:
    input("The digHolo viewer is running. Press Enter to close it. ")
finally:
    viewer.close()
    camera.close()
