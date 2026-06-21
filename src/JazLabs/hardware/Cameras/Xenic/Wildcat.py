from ._xeneth_base import XenethCameraBase


class CameraObject(XenethCameraBase):
    MODEL_NAME = "Wildcat"
    CAMERA_NAME = "cam://0"
    PIXEL_SIZE = 20e-6
    # Wildcat/line-camera trigger examples use TriggerMode and ExposureTime.
    EXPOSURE_PROPERTIES = ("ExposureTime", "ExposureTimeAbs", "IntegrationTime")
    GAIN_PROPERTIES = ("Gain", "AnalogGain", "VideoGain", "LowGain")
    ROI_STYLE = "width_height"
    TRIGGER_STYLE = "trigger_mode"
    SOFTWARE_TRIGGER_MODE = 5
    HARDWARE_TRIGGER_MODE = 1


WildcatCameraObject = CameraObject
