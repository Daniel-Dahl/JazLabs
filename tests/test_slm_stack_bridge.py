import json
import sys
from types import SimpleNamespace

import numpy as np
import pytest

try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules["cv2"] = SimpleNamespace()

from JazLabs.hardware.SLM.SLMStack.SLM_BridgeServer import SLMZMQBridgeServer


class FakeRemoteCommandSocket:
    def __init__(self, reply):
        self.reply = reply
        self.sent_parts = None

    def send_multipart(self, parts):
        self.sent_parts = parts

    def recv_json(self):
        return self.reply


class FakeLocalDisplaySocket:
    def __init__(self):
        self.messages = []

    def send_multipart(self, parts):
        self.messages.append(parts)


def make_bridge():
    bridge = SLMZMQBridgeServer()
    bridge.viewer_shape = (2, 3)
    bridge.viewer_dtype = np.dtype(np.uint8)
    bridge.viewer_arr = np.zeros(bridge.viewer_shape, dtype=bridge.viewer_dtype)
    bridge.viewer_metadata = np.zeros(4, dtype=np.int64)
    bridge.viewer_metadata[3] = 3
    return bridge


def write_header(write_id=7):
    return {
        "cmd": "write_to_display",
        "client_id": "test-client",
        "write_id": write_id,
        "shape": [2, 3],
        "dtype": "uint8",
        "channelIdx": 0,
    }


def remote_reply(display_ok=True, write_id=7, frame_id=12):
    return {
        "ok": True,
        "client_id": "test-client",
        "result": {
            "display_ok": display_ok,
            "write_id": write_id,
            "frame_id": frame_id,
            "last_write_time_ns": 1234,
            "timing": {"sdk_write_ms": 0.25},
        },
    }


def test_bridge_commits_retained_image_after_matching_success_acknowledgement():
    bridge = make_bridge()
    image = np.arange(6, dtype=np.uint8).reshape(2, 3)
    remote_socket = FakeRemoteCommandSocket(remote_reply())
    local_display_socket = FakeLocalDisplaySocket()

    bridge._submit_display_write(
        remote_socket,
        local_display_socket,
        write_header(),
        image.tobytes(),
    )

    np.testing.assert_array_equal(bridge.viewer_arr, image)
    assert bridge.last_frame_id == 12
    assert bridge.last_display_success is True
    assert bridge.viewer_metadata.tolist() == [2, 12, 0, 3]
    assert len(local_display_socket.messages) == 1
    topic, header_bytes, published_image = local_display_socket.messages[0]
    assert topic == b"slm.display"
    assert json.loads(header_bytes)["write_id"] == 7
    np.testing.assert_array_equal(
        np.frombuffer(published_image, dtype=np.uint8).reshape(2, 3),
        image,
    )


def test_bridge_keeps_confirmed_image_when_physical_write_fails():
    bridge = make_bridge()
    bridge.viewer_arr.fill(3)
    bridge.last_frame_id = 11
    remote_socket = FakeRemoteCommandSocket(remote_reply(display_ok=False))
    local_display_socket = FakeLocalDisplaySocket()

    bridge._submit_display_write(
        remote_socket,
        local_display_socket,
        write_header(),
        np.full((2, 3), 9, dtype=np.uint8).tobytes(),
    )

    np.testing.assert_array_equal(bridge.viewer_arr, np.full((2, 3), 3))
    assert bridge.last_frame_id == 11
    assert bridge.last_display_success is False
    assert local_display_socket.messages == []


def test_bridge_rejects_mismatched_write_acknowledgement_without_committing():
    bridge = make_bridge()
    bridge.viewer_arr.fill(4)
    remote_socket = FakeRemoteCommandSocket(remote_reply(write_id=8))
    local_display_socket = FakeLocalDisplaySocket()

    with pytest.raises(RuntimeError, match="does not match"):
        bridge._submit_display_write(
            remote_socket,
            local_display_socket,
            write_header(write_id=7),
            np.full((2, 3), 9, dtype=np.uint8).tobytes(),
        )

    np.testing.assert_array_equal(bridge.viewer_arr, np.full((2, 3), 4))
    assert local_display_socket.messages == []


def test_bridge_keeps_viewer_image_two_dimensional_with_aligned_metadata(monkeypatch):
    class FakeViewerSharedMemory:
        name = "test_bridge_viewer"

        def __init__(self, create, size):
            self.buf = bytearray(size)

        def close(self):
            pass

        def unlink(self):
            pass

    monkeypatch.setattr(
        "JazLabs.hardware.SLM.SLMStack.SLM_BridgeServer.shared_memory.SharedMemory",
        FakeViewerSharedMemory,
    )
    bridge = SLMZMQBridgeServer()
    try:
        bridge._create_local_viewer_shared_memory(
            {
                "input_expected_shape": [2, 3],
                "number_of_channels": 3,
            }
        )
        properties = bridge._get_local_properties()

        assert bridge.viewer_arr.shape == (2, 3)
        assert properties["viewer_shape"] == [2, 3]
        assert properties["viewer_metadata_offset"] % 8 == 0
        assert bridge.viewer_metadata.tolist() == [0, 0, 0, 3]
    finally:
        if bridge.viewer_shm is not None:
            bridge.viewer_shm.close()
            bridge.viewer_shm.unlink()
