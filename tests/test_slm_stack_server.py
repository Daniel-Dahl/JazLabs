import sys
from types import SimpleNamespace

import pytest

try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules["cv2"] = SimpleNamespace()

from JazLabs.hardware.SLM.SLMStack.SLM_Server import SLMZMQServer
from JazLabs.launchers.launch_slm_server import build_parser


class RecordingSLMObject:
    def __init__(self, calls, **kwargs):
        calls.append(kwargs)


def fake_slm_module(calls):
    return SimpleNamespace(
        SLMObject=lambda **kwargs: RecordingSLMObject(calls, **kwargs)
    )


def test_hdmi_slm_uses_monitor_index(monkeypatch):
    calls = []
    server = SLMZMQServer(
        SLMType="HDMI SLM",
        BoardNumber=7,
        MonitorIndex=2,
        RefreshRate=0.25,
        LutFile="unused.lut",
    )
    monkeypatch.setattr(server, "_load_slm_module", lambda: fake_slm_module(calls))

    server._open_slm()

    assert calls == [{"monitor_index": 2, "RefreshRate": 0.25}]


def test_blink_slm_uses_board_number(monkeypatch):
    calls = []
    server = SLMZMQServer(
        SLMType="Blink Plus",
        BoardNumber=3,
        MonitorIndex=8,
        RefreshRate=0.5,
        LutFile="slm.lut",
    )
    monkeypatch.setattr(server, "_load_slm_module", lambda: fake_slm_module(calls))

    server._open_slm()

    assert calls == [
        {
            "board_number_in": 3,
            "RefreshRate": 0.5,
            "LutFile": "slm.lut",
        }
    ]


def test_launcher_accepts_device_selectors():
    args = build_parser().parse_args(
        ["--board-number", "4", "--monitor-index", "2"]
    )

    assert args.board_number == 4
    assert args.monitor_index == 2


def test_slm_launcher_uses_normal_default_config():
    args = build_parser().parse_args([])

    assert args.config == "default_lab"


def test_server_shuts_down_slm_when_server_loop_is_interrupted(monkeypatch):
    class FakeSLM:
        monitor_height = 2
        monitor_width = 3
        NumberOfChannels = 3

        def __init__(self):
            self.shutdown_calls = 0

        def shutdown(self):
            self.shutdown_calls += 1

    class InterruptingSocket:
        def bind(self, endpoint):
            raise KeyboardInterrupt

        def close(self, linger):
            pass

    class FakeContext:
        def socket(self, socket_type):
            return InterruptingSocket()

        def term(self):
            pass

    class FakeViewerSharedMemory:
        name = "test_slm_viewer"

        def __init__(self, create, size):
            self.buf = bytearray(size)

        def close(self):
            pass

        def unlink(self):
            pass

    slm = FakeSLM()
    server = SLMZMQServer(SLMType="HDMI SLM")
    monkeypatch.setattr(server, "_open_slm", lambda: slm)
    monkeypatch.setattr(
        "JazLabs.hardware.SLM.SLMStack.SLM_Server.zmq.Context",
        FakeContext,
    )
    monkeypatch.setattr(
        "JazLabs.hardware.SLM.SLMStack.SLM_Server.shared_memory.SharedMemory",
        FakeViewerSharedMemory,
    )

    with pytest.raises(KeyboardInterrupt):
        server.run_forever()

    assert slm.shutdown_calls == 1
