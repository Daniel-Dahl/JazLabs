import sys
from types import SimpleNamespace

import numpy as np

try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules["cv2"] = SimpleNamespace()

from JazLabs.hardware.SLM.SLMStack.SLM_Viewer import SLMOutputViewer


def test_viewer_accumulates_confirmed_blue_green_and_red_masks():
    accumulated_rgb = np.zeros((2, 3, 3), dtype=np.uint8)
    blue_mask = np.full((2, 3), 10, dtype=np.uint8)
    green_mask = np.full((2, 3), 20, dtype=np.uint8)
    red_mask = np.full((2, 3), 30, dtype=np.uint8)

    SLMOutputViewer.apply_confirmed_channel_image(accumulated_rgb, blue_mask, 0)
    SLMOutputViewer.apply_confirmed_channel_image(accumulated_rgb, green_mask, 1)
    displayed = SLMOutputViewer.apply_confirmed_channel_image(
        accumulated_rgb,
        red_mask,
        2,
    )

    np.testing.assert_array_equal(displayed[:, :, 0], red_mask)
    np.testing.assert_array_equal(displayed[:, :, 1], green_mask)
    np.testing.assert_array_equal(displayed[:, :, 2], blue_mask)


def test_single_channel_viewer_keeps_grayscale_image():
    mask = np.arange(6, dtype=np.uint8).reshape(2, 3)

    displayed = SLMOutputViewer.apply_confirmed_channel_image(None, mask, 0)

    np.testing.assert_array_equal(displayed, mask)
    assert displayed.ndim == 2
