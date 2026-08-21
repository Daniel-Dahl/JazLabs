"""Connect to a camera and exercise its common client operations."""

from JazLabs.hardware.Cameras.Camera_Client import CameraClient


HOST = "127.0.0.1"
COMMAND_PORT = 50731
FRAME_PORT = 50732
EXPOSURE_US = 1000
ROI = {"offset_x": 0, "offset_y": 0, "width": 256, "height": 256}


camera = CameraClient(
    host=HOST,
    command_port=COMMAND_PORT,
    frame_pub_port=FRAME_PORT,
)

try:
    camera.SetExposureTime(EXPOSURE_US)
    continuous_frame = camera.GetFrame(WaitForNewFrame=True)
    print("Continuous frame shape:", continuous_frame.shape)

    camera.SetSoftwareTriggerMode()
    triggered_frame = camera.GetSoftwareTriggeredFrame()
    print("Triggered frame shape:", triggered_frame.shape)

    camera.SetContinuousMode()
    camera.SetROI(**ROI, snap_values=True)
    print("ROI:", camera.GetROI())
finally:
    camera.SetROI(enable=False)
    camera.close()
