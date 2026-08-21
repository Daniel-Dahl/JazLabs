"""Connect a camera and pass it to the digital holography viewer."""

from JazLabs.hardware.Cameras.Camera_Client import CameraClient
from JazLabs.hardware.digHolo.digHolo_pylibs.digHolo_Veiwer import digholoWindow


HOST = "127.0.0.1"
COMMAND_PORT = 50731
FRAME_PORT = 50732
PIXEL_SIZE_M = 6.9e-6
WAVELENGTH_M = 1550e-9
FFT_RADIUS = 0.4
MAX_MODE_GROUP = 3


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
