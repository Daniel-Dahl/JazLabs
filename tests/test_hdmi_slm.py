import sys
from types import SimpleNamespace

import numpy as np


class RecordingEvent:
    def __init__(self):
        self.set_calls = 0

    def set(self):
        self.set_calls += 1


def make_hdmi_slm(monkeypatch):
    try:
        import cv2  # noqa: F401
    except ImportError:
        monkeypatch.setitem(sys.modules, "cv2", SimpleNamespace())
    monkeypatch.setitem(
        sys.modules,
        "screeninfo",
        SimpleNamespace(get_monitors=lambda: []),
    )
    from JazLabs.hardware.SLM.HDMI_SLM.HDMIFullDisplayObject import SLMObject

    slm = object.__new__(SLMObject)
    slm._shutdown_complete = True
    slm.monitor_height = 2
    slm.monitor_width = 3
    slm.DisplayBuffer_arr_shm = np.zeros((2, 3), dtype=np.uint8)
    slm.channel = SimpleNamespace(value=0)
    slm.UpdateDisplay = RecordingEvent()
    slm.Doorbell = RecordingEvent()
    slm.RefreshRate = 0
    return slm


def test_hdmi_write_returns_one_after_accepting_image(monkeypatch):
    slm = make_hdmi_slm(monkeypatch)
    image = np.arange(6, dtype=np.uint8).reshape(2, 3)

    result = slm.WriteImageToSLM(image, channelIdx=2)

    assert result == 1
    np.testing.assert_array_equal(slm.DisplayBuffer_arr_shm, image)
    assert slm.channel.value == 2
    assert slm.UpdateDisplay.set_calls == 1
    assert slm.Doorbell.set_calls == 1


def test_hdmi_write_returns_zero_without_signalling_for_invalid_input(monkeypatch):
    slm = make_hdmi_slm(monkeypatch)

    assert slm.WriteImageToSLM(None, channelIdx=0) == 0
    assert slm.WriteImageToSLM(np.zeros((1, 3)), channelIdx=0) == 0
    assert slm.WriteImageToSLM(np.zeros((2, 3)), channelIdx=3) == 0
    assert slm.UpdateDisplay.set_calls == 0
    assert slm.Doorbell.set_calls == 0
