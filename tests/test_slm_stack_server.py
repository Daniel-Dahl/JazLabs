import sys
from types import SimpleNamespace

try:
    import cv2  # noqa: F401
except ImportError:
    sys.modules["cv2"] = SimpleNamespace()

from JazLabs.hardware.SLM.SLMStack.SLM_Server import SLMZMQServer
from JazLabs.launchers.launch_slm_stack_server import build_parser


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
