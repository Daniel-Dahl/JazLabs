import socket
import threading
import time

import numpy as np

from JazLabs.hardware.TimeTagger.TimeTagger_BridgeServer import (
    TimeTaggerZMQBridgeServer,
)
from JazLabs.hardware.TimeTagger.TimeTagger_Client import TimeTaggerClient
from JazLabs.hardware.TimeTagger.TimeTagger_Server import TimeTaggerZMQServer
import JazLabs.hardware.TimeTagger.TimeTaggerFunction as time_tagger_functions


def _unused_tcp_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeTagger:
    def __init__(self):
        self.trigger_levels = {}
        self.input_delays = {}

    def getSerial(self):
        return "fake-serial"

    def getModel(self):
        return "fake-model"

    def setTriggerLevel(self, channel, voltage):
        self.trigger_levels[channel] = voltage

    def getTriggerLevel(self, channel):
        return self.trigger_levels.get(channel, 0.0)

    def setInputDelay(self, channel, delay):
        self.input_delays[channel] = delay

    def getInputDelay(self, channel):
        return self.input_delays.get(channel, 0)


class FakeCountrate:
    def __init__(self, tagger, channels):
        self.channels = channels

    def clear(self):
        pass

    def startFor(self, duration):
        self.duration = duration

    def waitUntilFinished(self):
        pass

    def getData(self):
        return np.asarray([10.0 * (index + 1) for index in range(len(self.channels))])

    def getCountsTotal(self):
        return 100, 200, 10


class FakeCounter(FakeCountrate):
    def __init__(self, tagger, channels, binwidth, n_values):
        super().__init__(tagger, channels)
        self.n_values = n_values

    def getIndex(self):
        return np.arange(self.n_values)

    def getData(self):
        return np.tile(np.arange(self.n_values), (len(self.channels), 1))


class FakeCorrelation:
    def __init__(self, tagger, channel_1, channel_2, binwidth, n_bins):
        self.n_bins = n_bins

    def startFor(self, duration):
        self.duration = duration

    def waitUntilFinished(self):
        pass

    def getIndex(self):
        return np.arange(self.n_bins)

    def getData(self):
        return np.arange(self.n_bins) + 1

    def getDataNormalized(self):
        return (np.arange(self.n_bins) + 1) / 10


class FakeCoincidence:
    def __init__(self, tagger, channels, coincidenceWindow, timestamp):
        pass

    def getChannel(self):
        return 99


class FakeCoincidenceTimestamp:
    Last = "last"


class FakeTimeTaggerModule:
    Countrate = FakeCountrate
    Counter = FakeCounter
    Correlation = FakeCorrelation
    Coincidence = FakeCoincidence
    CoincidenceTimestamp = FakeCoincidenceTimestamp

    @staticmethod
    def createTimeTagger(**kwargs):
        return FakeTagger()

    @staticmethod
    def freeTimeTagger(tagger):
        pass


def _start_server(command_port):
    server = TimeTaggerZMQServer(
        host="127.0.0.1",
        command_port=command_port,
        time_tagger_module=FakeTimeTaggerModule,
    )
    thread = threading.Thread(target=server.run_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    return thread


def test_client_can_configure_and_measure_through_server():
    command_port = _unused_tcp_port()
    server_thread = _start_server(command_port)
    client = TimeTaggerClient(
        host="127.0.0.1",
        command_port=command_port,
        timeout_ms=1000,
    )

    assert client.properties["role"] == "time_tagger_server"
    assert client.SetTriggerLevel(1, 0.25) == 0.25
    assert client.SetInputDelay(1, 125) == 125
    np.testing.assert_array_equal(client.MeasureCountrate([1, 2], 0.01), [10, 20])

    time_bins, counts = client.MeasureCounts([1, 2], 100, 4, 0.01)
    np.testing.assert_array_equal(time_bins, [0, 1, 2, 3])
    assert counts.shape == (2, 4)

    result = client.MeasureCoincidences([1, 2], 100, 0.01)
    assert result.coincidences == 10
    assert result.coincidence_rate == 1000
    np.testing.assert_array_equal(
        time_tagger_functions.getCountrate(client, 1, 0.01),
        [10],
    )
    helper_result = time_tagger_functions.getCoincidences(
        client,
        [1, 2],
        100,
        0.01,
    )
    assert helper_result.coincidences == 10

    client.ShutdownServer()
    client.close()
    server_thread.join(timeout=1)
    assert not server_thread.is_alive()


def test_bridge_exposes_the_same_client_api():
    remote_port = _unused_tcp_port()
    local_port = _unused_tcp_port()
    server_thread = _start_server(remote_port)
    bridge = TimeTaggerZMQBridgeServer(
        local_host="127.0.0.1",
        local_command_port=local_port,
        remote_host="127.0.0.1",
        remote_command_port=remote_port,
        timeout_ms=1000,
    )
    bridge_thread = threading.Thread(target=bridge.run_forever, daemon=True)
    bridge_thread.start()
    time.sleep(0.05)

    bridge_client = TimeTaggerClient(
        host="127.0.0.1",
        command_port=local_port,
        timeout_ms=1000,
    )
    assert bridge_client.properties["role"] == "time_tagger_bridge_server"
    assert bridge_client.properties["remote_command_port"] == remote_port
    np.testing.assert_array_equal(
        bridge_client.MeasureCountrate([1, 2], 0.01),
        [10, 20],
    )
    bridge_client.SendCommand({"cmd": "shutdown_bridge"})
    bridge_client.close()
    bridge_thread.join(timeout=1)
    assert not bridge_thread.is_alive()

    server_client = TimeTaggerClient(
        host="127.0.0.1",
        command_port=remote_port,
        timeout_ms=1000,
    )
    server_client.ShutdownServer()
    server_client.close()
    server_thread.join(timeout=1)
    assert not server_thread.is_alive()
