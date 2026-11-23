"""Real child-process bridge tests; uhubctl is replaced by a test executable."""
import multiprocessing as mp

import pytest
from usb_hub_test_support import create_uhubctl_stub

from JazLabs.hardware.USBHub.USBHub_BridgeServer import USBHubZMQBridgeServer
from JazLabs.hardware.USBHub.USBHub_Client import USBHubClient
from JazLabs.hardware.USBHub.USBHub_Server import USBHubZMQServer


@pytest.fixture
def bridged_hub(tmp_path):
    server = USBHubZMQServer(command_port=0, binary=create_uhubctl_stub(tmp_path))
    server.start()
    parent_ready, child_ready = mp.Pipe(duplex=False)
    bridge = USBHubZMQBridgeServer("127.0.0.1", server.command_port,
                                  local_command_port=0, timeout_ms=500)
    process = mp.Process(target=bridge.run_forever, args=(child_ready,))
    process.start()
    child_ready.close()
    client = None
    try:
        assert parent_ready.poll(5), "Bridge did not start"
        reply = parent_ready.recv()
        assert "error" not in reply, reply
        client = USBHubClient(command_port=reply["command_port"], timeout_ms=1500)
        yield server, process, client
    finally:
        if client is not None:
            try:
                if process.is_alive():
                    client.request("shutdown_bridge")
            finally:
                client.close()
        process.join(3)
        if process.is_alive():
            process.terminate()
            process.join(3)
        parent_ready.close()
        server.stop()


def test_bridge_shares_state_and_shuts_down_without_stopping_owner(bridged_hub):
    server, process, client = bridged_hub
    direct = USBHubClient(command_port=server.command_port, timeout_ms=1500)
    try:
        status = client.GetStatus()
        assert isinstance(status["trees"]["20-1"][0], tuple)
        client.SetPower(("20-1.3", 2), False, "0bda:0411", status["session_id"])
        assert not direct.GetStatus()["hubs"]["20-1.3"]["ports"][2]["on"]
        client.request("shutdown_bridge")
        process.join(3)
        assert process.exitcode == 0
        assert "20-1" in direct.GetStatus()["trees"]
    finally:
        direct.close()


def test_bridge_recovers_after_timeout_and_preserves_restart_guard(bridged_hub):
    server, process, client = bridged_hub
    old = client.GetStatus()
    port = server.command_port
    server.stop()
    with pytest.raises(RuntimeError, match="outcome unknown"):
        client.GetStatus()
    server.command_port = port
    server.start()
    assert client.GetStatus()["session_id"] != old["session_id"]
    with pytest.raises(RuntimeError, match="restarted"):
        client.SetPower(("20-1", 1), False, "0bda:0411", old["session_id"])
    assert client.GetStatus()["hubs"]["20-1"]["ports"][1]["on"]


def test_bridge_rejects_looping_endpoint():
    with pytest.raises(ValueError, match="endpoints must differ"):
        USBHubZMQBridgeServer("127.0.0.1", 50951, local_command_port=50951)
