"""Config selection and launcher wiring without accessing live USB devices."""
from unittest.mock import patch

from JazLabs.launchers.config import load_config
from JazLabs.launchers.launch_usb_hub_bridge import main as bridge_main
from JazLabs.launchers.launch_usb_hub_server import main as server_main
from JazLabs.launchers.launch_usb_hub_widget import main as widget_main
from JazLabs.launchers.tmux import usb_hub_tasks


def test_default_hub_is_disabled_and_uses_distinct_endpoints():
    config = load_config("default_lab")
    hub = config["USB_HUB_SERVERS"][0]
    assert hub["name"] == "usb_hub"
    assert not hub["enabled"]
    motor_ports = {motor["command_port"] for motor in config["MOTOR_SERVERS"]}
    assert hub["command_port"] not in motor_ports
    assert hub["local_command_port"] != hub["command_port"]
    assert hub["timeout_ms"] > hub["bridge_timeout_ms"] > 3 * hub["command_timeout"] * 1000
    assert list(usb_hub_tasks("default_lab", config)) == []
    tasks = list(usb_hub_tasks("test_lab", {"USB_HUB_SERVERS": [{**hub, "enabled": True}]}))
    assert "launch_usb_hub_server" in tasks[0][1]


def test_server_selects_explicit_executable():
    with patch("JazLabs.hardware.USBHub.USBHub_Server.USBHubZMQServer") as server:
        server_main(["--name", "usb_hub", "--uhubctl", "/trusted/uhubctl"])
        server.assert_called_once_with(host="127.0.0.1", command_port=50951,
                                       binary="/trusted/uhubctl", command_timeout=25.0)
        server.return_value.run_forever.assert_called_once()
    assert "demo" not in load_config("default_lab")["USB_HUB_SERVERS"][0]


def test_bridge_uses_separate_local_port():
    with patch("JazLabs.hardware.USBHub.USBHub_BridgeServer.USBHubZMQBridgeServer") as bridge:
        bridge_main(["--name", "usb_hub", "--remote-host", "192.168.1.25"])
        bridge.assert_called_once_with(remote_host="192.168.1.25", remote_command_port=50951,
            local_host="127.0.0.1", local_command_port=51951, timeout_ms=90000)
        bridge.return_value.run_forever.assert_called_once()


def test_widget_only_constructs_client_and_window():
    with patch("JazLabs.hardware.USBHub.USBHub_Client.USBHubClient") as client, \
         patch("JazLabs.hardware.USBHub.USBHub_Widget.USBHubWidget") as widget, \
         patch("tkinter.Tk") as root, \
         patch("JazLabs.hardware.USBHub.USBHub_Server.USBHubZMQServer") as server:
        widget_main(["--name", "usb_hub", "--bridge"])
        client.assert_called_once_with("127.0.0.1", 51951, timeout_ms=100000)
        widget.assert_called_once_with(root.return_value, client.return_value)
        root.return_value.mainloop.assert_called_once()
        client.return_value.close.assert_called_once()
        server.assert_not_called()
