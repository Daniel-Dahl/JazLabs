from ._xeneth_base import XenethCameraBase


class CameraObject(XenethCameraBase):
    MODEL_NAME = "Xeva"
    CAMERA_NAME = "cam://0"
    PIXEL_SIZE = 30e-6
    # Xeva/older Xeneth examples use IntegrationTime, VideoGain controls, and
    # Window-of-interest properties WoiSX/WoiEX/WoiSY/WoiEY.
    EXPOSURE_PROPERTIES = ("IntegrationTime", "ExposureTime")
    GAIN_PROPERTIES = ("VideoGain", "VideoGainP", "VideoGainI", "LowGain", "Gain")
    ROI_STYLE = "woi"
    TRIGGER_STYLE = "trigger_in"


XevaCameraObject = CameraObject
