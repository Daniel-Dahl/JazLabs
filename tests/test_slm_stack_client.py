import sys
from types import SimpleNamespace

import numpy as np
import pytest

try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules["cv2"] = SimpleNamespace()

from JazLabs.hardware.SLM.SLMStack.SLM_Client import SLMClient


def make_client(image_shape=(4, 6), number_of_channels=1):
    client = object.__new__(SLMClient)
    client.image_shape = image_shape
    client.single_channel_shape = image_shape
    client.NumberOfChannels = number_of_channels
    return client


def test_prepare_image_keeps_two_dimensional_layout_for_hdmi_channel():
    client = make_client(number_of_channels=3)
    source = np.arange(24, dtype=np.uint8).reshape(4, 6)

    image, channel_index = client._prepare_image_for_display(source, channelIdx=2)

    assert image.shape == (4, 6)
    assert image.flags.c_contiguous
    np.testing.assert_array_equal(image, source)
    assert channel_index == 2


def test_prepare_image_for_single_channel_slm_uses_channel_zero():
    client = make_client(number_of_channels=1)

    image, channel_index = client._prepare_image_for_display(
        np.zeros((4, 6)),
        channelIdx=None,
    )

    assert image.dtype == np.uint8
    assert channel_index == 0


def test_prepare_image_requires_channel_for_multi_channel_slm():
    client = make_client(number_of_channels=3)

    with pytest.raises(ValueError, match="channelIdx must be specified"):
        client._prepare_image_for_display(np.zeros((4, 6)), channelIdx=None)


def test_prepare_image_rejects_channel_outside_slm_range():
    client = make_client(number_of_channels=3)

    with pytest.raises(ValueError, match="channelIdx 3 out of range"):
        client._prepare_image_for_display(np.zeros((4, 6)), channelIdx=3)


@pytest.mark.parametrize("shape", [(4, 6, 3), (3, 4, 6), (4, 5)])
def test_prepare_image_rejects_obsolete_or_incorrect_layouts(shape):
    client = make_client(number_of_channels=3)

    with pytest.raises(ValueError, match="Expected 2D image shape"):
        client._prepare_image_for_display(np.zeros(shape), channelIdx=0)
