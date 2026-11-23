import unittest
import tempfile
from usb_hub_test_support import create_uhubctl_stub

import zmq

from JazLabs.hardware.USBHub.USBHub_Client import USBHubClient
from JazLabs.hardware.USBHub.USBHub_Server import USBHubZMQServer


class NetworkTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.binary = create_uhubctl_stub(self.directory.name)
        self.server = USBHubZMQServer(command_port=0, binary=self.binary)
        self.server.start()
        self.port = self.server.command_port
        self.client = USBHubClient(command_port=self.port, timeout_ms=1000)

    def tearDown(self):
        self.client.close()
        self.server.stop()

    def test_two_clients_share_one_driver_state(self):
        first = self.client.GetStatus()
        self.assertNotIn('demo', first)
        self.assertEqual(len(first['trees']['20-1']), 10)
        self.client.SetPower(('20-1.3', 2), False, '0bda:0411', first['session_id'])
        second = USBHubClient(command_port=self.port, timeout_ms=1000).GetStatus()
        self.assertFalse(second['hubs']['20-1.3']['ports'][2]['on'])
        self.assertTrue(second['hubs']['20-1.3']['ports'][1]['on'])

    def test_invalid_requests_do_not_break_server_or_change_state(self):
        snapshot = self.client.GetStatus()
        valid = {'cmd': 'set_power', 'location': '20-1', 'port': 1, 'on': False,
                 'expected_identity': '0bda:0411', 'session_id': snapshot['session_id']}
        bad_requests = [[], {'cmd': 'run_shell'}, {**valid, 'on': 'false'},
                        {**valid, 'port': True}, {**valid, 'port': 3},
                        {**valid, 'session_id': 'old-server'},
                        {**valid, 'expected_identity': '1234:5678'},
                        {**valid, 'location': '20-1; echo nope'}]
        context = zmq.Context()
        try:
            for request in bad_requests:
                with self.subTest(request=request):
                    socket = context.socket(zmq.REQ)
                    socket.setsockopt(zmq.RCVTIMEO, 1000)
                    socket.setsockopt(zmq.LINGER, 0)
                    socket.connect(f'tcp://127.0.0.1:{self.port}')
                    socket.send_json(request)
                    self.assertFalse(socket.recv_json()['ok'])
                    socket.close(0)
            socket = context.socket(zmq.REQ)
            socket.setsockopt(zmq.RCVTIMEO, 1000)
            socket.setsockopt(zmq.LINGER, 0)
            socket.connect(f'tcp://127.0.0.1:{self.port}')
            socket.send(b'not JSON')
            self.assertFalse(socket.recv_json()['ok'])
            socket.close(0)
        finally:
            context.term()
        after = self.client.GetStatus()
        self.assertTrue(after['hubs']['20-1']['ports'][1]['on'])

    def test_server_errors_surface_in_client(self):
        with self.assertRaisesRegex(RuntimeError, 'Unknown USB hub command'):
            self.client.request('surprise')
        self.assertIn('20-1', self.client.GetStatus()['trees'])

    def test_timeout_then_recovery_without_replaying_command(self):
        # Stop the server; restart on the same port after observing a timeout.
        self.client.ShutdownServer()
        self.server.process.join(3)
        with self.assertRaises(TimeoutError):
            self.client.GetStatus()
        self.server = USBHubZMQServer(command_port=self.port, binary=self.binary)
        self.server.start()
        self.assertIn('20-1', self.client.GetStatus()['trees'])

    def test_shutdown_is_explicit_and_clean(self):
        self.client.ShutdownServer()
        self.server.process.join(3)
        self.assertEqual(self.server.process.exitcode, 0)


if __name__ == '__main__':
    unittest.main()
