import json
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


def test_wait_for_display_notification_accepts_metadata_only_server_ack():
    class MetadataSubscriber:
        def recv_multipart(self):
            return [
                b"slm.display",
                json.dumps(
                    {
                        "type": "slm_display_ack",
                        "write_id": 4,
                        "frame_id": 9,
                        "ok": True,
                    }
                ).encode("utf-8"),
            ]

    client = make_client()
    client.display_sub_socket = MetadataSubscriber()

    notification = client.WaitForDisplayNotification()

    assert notification["write_id"] == 4
    assert notification["frame_id"] == 9


def test_get_confirmed_display_state_decodes_channel_images():
    class SnapshotSocket:
        def __init__(self):
            self.request = None

        def send_json(self, request):
            self.request = request

        def recv_multipart(self):
            header = {
                "ok": True,
                "client_id": "test-client",
                "result": {
                    "channels": [
                        {
                            "confirmed": True,
                            "channelIdx": 2,
                            "frame_id": 5,
                            "shape": [2, 3],
                            "dtype": "uint8",
                            "part_index": 1,
                        }
                    ]
                },
            }
            image = np.arange(6, dtype=np.uint8).reshape(2, 3)
            return [json.dumps(header).encode("utf-8"), image.tobytes()]

    client = make_client(image_shape=(2, 3), number_of_channels=3)
    client.client_id = "test-client"
    client.command_socket = SnapshotSocket()

    channel_states = client.GetConfirmedDisplayState()

    assert client.command_socket.request["cmd"] == "get_confirmed_display_state"
    assert channel_states[0]["channelIdx"] == 2
    assert channel_states[0]["frame_id"] == 5
    np.testing.assert_array_equal(
        channel_states[0]["image"],
        np.arange(6, dtype=np.uint8).reshape(2, 3),
    )
