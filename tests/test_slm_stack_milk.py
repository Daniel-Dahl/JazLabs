import json
import sys
from types import ModuleType, SimpleNamespace

import numpy as np


class FakeSHM:
    def __init__(self, name="test", data=None, **kwargs):
        self.name = name
        self.data = (
            np.zeros((2, 3), dtype=np.uint8)
            if data is None
            else np.asarray(data).copy()
        )
        self.counter = 0
        self.keywords = {}
        self.operations = []

    def get_data(self, copy=True):
        return self.data.copy() if copy else self.data

    def set_data(self, data):
        self.operations.append(("set_data", np.asarray(data).copy()))
        self.data = np.asarray(data).copy()
        self.counter += 1

    def get_counter(self):
        return self.counter

    def get_keywords(self):
        return dict(self.keywords)

    def set_keywords(self, keywords):
        self.operations.append(("set_keywords", dict(keywords)))
        self.keywords.update(keywords)

    def close(self):
        pass


py_milk_module = ModuleType("pyMilk")
py_milk_interfacing_module = ModuleType("pyMilk.interfacing")
py_milk_shm_module = ModuleType("pyMilk.interfacing.isio_shmlib")
py_milk_shm_module.SHM = FakeSHM
sys.modules.setdefault("pyMilk", py_milk_module)
sys.modules.setdefault("pyMilk.interfacing", py_milk_interfacing_module)
sys.modules.setdefault("pyMilk.interfacing.isio_shmlib", py_milk_shm_module)

try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules["cv2"] = SimpleNamespace()

from JazLabs.hardware.SLM.SLMStackMilk.SLM_BridgeServer import SLMZMQBridgeServer
from JazLabs.hardware.SLM.SLMStackMilk.SLM_Client import SLMClient
from JazLabs.hardware.SLM.SLMStackMilk.SLM_Server import SLMZMQServer
from JazLabs.hardware.SLM.SLMStackMilk.SLM_Viewer import SLMViewer


def test_milk_client_writes_two_dimensional_image_with_channel_keywords():
    client = object.__new__(SLMClient)
    client.single_channel_shape = (2, 3)
    client.image_shape = (2, 3)
    client.NumberOfChannels = 3
    client.shm = FakeSHM(data=np.zeros((2, 3), dtype=np.uint8))

    image = np.arange(6, dtype=np.uint8).reshape(2, 3)
    result = client.WriteImageToSLM(image, channelIdx=2, wait=False)

    assert result == 1
    np.testing.assert_array_equal(client.shm.data, image)
    assert client.shm.keywords == {"WRITING": 0, "CHANIDX": 2, "SHMCNT": 1}
    assert client.shm.operations[0] == (
        "set_keywords",
        {"WRITING": 1, "CHANIDX": 2},
    )
    assert client.shm.operations[1][0] == "set_data"


def test_milk_bridge_commits_only_matching_successful_ack_to_confirmed_stream():
    bridge = object.__new__(SLMZMQBridgeServer)
    bridge.confirmed_shm = FakeSHM(data=np.zeros((2, 3), dtype=np.uint8))
    image = np.full((2, 3), 17, dtype=np.uint8)
    bridge.pending_writes = {
        4: {"image": image, "channelIdx": 1, "shm_counter": 9}
    }

    bridge._commit_acknowledged_image({"frame_id": 4, "ok": True})

    np.testing.assert_array_equal(bridge.confirmed_shm.data, image)
    assert bridge.confirmed_shm.keywords == {
        "WRITING": 0,
        "CHANIDX": 1,
        "FRAMEID": 4,
        "SHMCNT": 1,
    }
    assert bridge.pending_writes == {}


def test_milk_bridge_does_not_commit_failed_ack():
    bridge = object.__new__(SLMZMQBridgeServer)
    bridge.confirmed_shm = FakeSHM(data=np.full((2, 3), 3, dtype=np.uint8))
    bridge.pending_writes = {
        5: {
            "image": np.full((2, 3), 21, dtype=np.uint8),
            "channelIdx": 2,
            "shm_counter": 10,
        }
    }

    bridge._commit_acknowledged_image({"frame_id": 5, "ok": False})

    np.testing.assert_array_equal(
        bridge.confirmed_shm.data,
        np.full((2, 3), 3, dtype=np.uint8),
    )
    assert bridge.confirmed_shm.operations == []
    assert bridge.pending_writes == {}


def test_milk_server_snapshot_returns_each_confirmed_channel():
    server = object.__new__(SLMZMQServer)
    server.number_of_channels = 3
    server.expected_shape = (2, 3)
    server.confirmed_channel_images = [
        np.full((2, 3), channel_index, dtype=np.uint8)
        for channel_index in range(3)
    ]
    server.confirmed_channel_metadata = [
        {
            "confirmed": True,
            "frame_id": channel_index + 1,
            "write_id": channel_index + 10,
            "last_write_time_ns": 100 + channel_index,
        }
        for channel_index in range(3)
    ]

    reply_parts = server._build_confirmed_display_state_reply("viewer")
    header = json.loads(reply_parts[0].decode("utf-8"))

    assert header["client_id"] == "viewer"
    assert len(header["result"]["channels"]) == 3
    assert len(reply_parts) == 4


def test_milk_viewer_retains_previous_confirmed_colour_channels():
    accumulated_rgb = np.zeros((2, 3, 3), dtype=np.uint8)

    SLMViewer.apply_confirmed_channel_image(
        accumulated_rgb,
        np.full((2, 3), 11, dtype=np.uint8),
        0,
    )
    SLMViewer.apply_confirmed_channel_image(
        accumulated_rgb,
        np.full((2, 3), 22, dtype=np.uint8),
        1,
    )
    displayed = SLMViewer.apply_confirmed_channel_image(
        accumulated_rgb,
        np.full((2, 3), 33, dtype=np.uint8),
        2,
    )

    assert np.all(displayed[:, :, 0] == 33)
    assert np.all(displayed[:, :, 1] == 22)
    assert np.all(displayed[:, :, 2] == 11)
