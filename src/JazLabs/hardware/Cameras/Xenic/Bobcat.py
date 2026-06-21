from ._xeneth_base import XenethCameraBase


class CameraObject(XenethCameraBase):
    MODEL_NAME = "Bobcat"
    CAMERA_NAME = "cam://0"
    PIXEL_SIZE = 20e-6
    # Bobcat/self-calibrating area-camera examples use ExposureTimeAbs plus
    # Width/Height and TriggerIn* properties.
    EXPOSURE_PROPERTIES = ("ExposureTimeAbs", "ExposureTime", "IntegrationTime")
    GAIN_PROPERTIES = ("Gain", "AnalogGain", "LowGain")
    ROI_STYLE = "width_height"
    TRIGGER_STYLE = "trigger_in"


BobcatCameraObject = CameraObject
