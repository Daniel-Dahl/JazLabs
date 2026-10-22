"""Exercise the new snapshot/intent protocol using a loopback simulator."""
import socket
import threading
import time
import unittest
from unittest.mock import patch

from JazLabs.hardware.MotorisedStages.SimulatedStage import SimulatedStage
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer


class NetworkTests(unittest.TestCase):
    def setUp(self):
        with socket.socket() as reservation:
            try:
                reservation.bind(('127.0.0.1', 0))
            except PermissionError:
                self.skipTest('Localhost sockets are unavailable in this sandbox')
            self.port = reservation.getsockname()[1]
        self.server = MotorisedStageZMQServer(command_port=self.port, stage_kwargs={'axes': 1})
        self.thread = threading.Thread(target=self.server.run_forever)
        self.thread.start()
        self.client = MotorisedStageClient(command_port=self.port, timeout_ms=300)
        self.wait(lambda: self.client.request('state')['connected'])

    def tearDown(self):
        try:
            self.client.request('shutdown')
        finally:
            self.client.close()
            self.thread.join(3)
        self.assertFalse(self.thread.is_alive())

    def wait(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except TimeoutError:
                pass
            time.sleep(.02)
        self.fail('Network motion state did not arrive')

    def test_user_client_exposes_the_driver_facing_api(self):
        self.assertEqual(self.client.GetMotionCapabilities()[0]['id'], 'X')
        self.assertEqual(self.client.GetProperties()['stage_type'], 'simulation')
        self.assertEqual(self.client.GetAxisState('X')['position'], 5)
        self.client.MoveTo('X', 5.02)
        self.wait(lambda: self.client.GetAxisState('X')['position'] >= 5.019)
        self.client.StopAll()
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_moves_and_stop_latch(self):
        self.client.request('relative', 'X', .02)
        self.wait(lambda: self.client.request('state')['axes']['X']['position'] >= 5.019)
        self.client.request('stop')
        self.wait(lambda: self.client.request('state')['stopped'])
        with self.assertRaises(RuntimeError):
            self.client.request('absolute', 'X', 5.1)
        self.client.request('resume')
        self.wait(lambda: not self.client.request('state')['stopped'])

    def test_server_acknowledges_stop_while_hardware_poll_is_slow(self):
        entered = threading.Event()
        original = SimulatedStage.GetAxisState
        def slow_read(mount, axis):
            entered.set()
            time.sleep(.4)
            return original(mount, axis)
        with patch.object(SimulatedStage, 'GetAxisState', slow_read):
            self.assertTrue(entered.wait(1))
            began = time.monotonic()
            result = self.client.request('stop')
            self.assertLess(time.monotonic() - began, .2)
            self.assertTrue(result['stop_pending'] or result['stopped'])
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_remote_short_tap_survives_release_before_network_send(self):
        endpoint = MotorisedStageClient(command_port=self.port)
        # Both events happen before the network loop gets a turn.
        endpoint.submit('relative', 'X', .01)
        endpoint.submit('release_jog')
        endpoint.start()
        try:
            self.wait(lambda: endpoint.get_state()['axes'].get('X', {}).get('position', 0) >= 5.009)
            time.sleep(.3)
            self.assertAlmostEqual(endpoint.get_state()['axes']['X']['position'], 5.01)
        finally:
            endpoint.close()
            endpoint.thread.join(2)
        self.assertFalse(endpoint.thread.is_alive())

    def test_rejected_request_does_not_poison_req_socket(self):
        with self.assertRaises(RuntimeError):
            self.client.request('bogus')
        self.assertTrue(self.client.request('state')['connected'])


if __name__ == '__main__':
    unittest.main()
