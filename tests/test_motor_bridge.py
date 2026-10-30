"""Motor bridge forwards the existing protocol without owning stage hardware."""
import queue
import socket
import threading
import time
import unittest

import zmq

from JazLabs.hardware.MotorisedStages.MotorisedStage_BridgeServer import MotorisedStageZMQBridgeServer
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer


class Ready:
    def __init__(self):
        self.messages = queue.Queue()
    def send(self, message):
        self.messages.put(message)
    def close(self):
        pass


class BridgeTests(unittest.TestCase):
    def setUp(self):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', 0))
            except PermissionError:
                self.skipTest('Localhost sockets are unavailable in this sandbox')
        self.server = MotorisedStageZMQServer(command_port=0, stage_kwargs={'axes': 1})
        ready = Ready()
        self.server_thread = threading.Thread(target=self.server.run_forever, kwargs={'ready_connection': ready})
        self.server_thread.start()
        port = ready.messages.get(timeout=2)['command_port']
        self.hardware = MotorisedStageClient(command_port=port)
        self.wait(lambda: self.hardware.request('state')['connected'])
        self.bridge = MotorisedStageZMQBridgeServer('127.0.0.1', port, local_command_port=0)
        ready = Ready()
        self.bridge_thread = threading.Thread(target=self.bridge.run_forever, kwargs={'ready_connection': ready})
        self.bridge_thread.start()
        port = ready.messages.get(timeout=2)['command_port']
        self.client = MotorisedStageClient(command_port=port, timeout_ms=1000)

    def tearDown(self):
        try:
            if self.bridge_thread.is_alive():
                self.client.request('shutdown_bridge')
            self.bridge_thread.join(2)
            self.hardware.request('shutdown')
            self.server_thread.join(3)
        finally:
            self.client.close()
            self.hardware.close()
        self.assertFalse(self.bridge_thread.is_alive())
        self.assertFalse(self.server_thread.is_alive())

    def wait(self, predicate, timeout=2):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return
            time.sleep(.02)
        self.fail('Expected bridged motor state did not arrive')

    def test_feedback_and_absolute_move(self):
        state = self.client.request('state')
        self.assertEqual(state['bridge']['remote_command_port'], self.server.command_port)
        self.assertEqual(self.client.GetMotionCapabilities()[0]['id'], 'X')
        self.assertGreaterEqual(state['axes']['X']['age'], 0)
        self.client.MoveAbs('X', 5.02)
        self.wait(lambda: self.client.GetAxisStatus('X')['position'] >= 5.019)

    def test_hold_release_stop_and_resume_through_bridge(self):
        for _ in range(8):
            self.client.request('jog', 'X', .01)
            time.sleep(.06)
        self.client.request('release_jog')
        time.sleep(.4)
        position = self.client.GetAxisStatus('X')['position']
        self.assertGreaterEqual(position, 5.02)
        time.sleep(.4)
        self.assertEqual(self.client.GetAxisStatus('X')['position'], position)
        self.client.StopAll()
        self.wait(lambda: self.client.request('state')['stopped'])
        with self.assertRaises(RuntimeError):
            self.client.MoveAbs('X', 5.1)
        self.client.request('resume')
        self.wait(lambda: not self.client.request('state')['stopped'])

    def test_shutdown_bridge_does_not_stop_hardware_server(self):
        self.client.request('shutdown_bridge')
        self.bridge_thread.join(2)
        self.assertFalse(self.bridge_thread.is_alive())
        self.assertTrue(self.hardware.request('state')['connected'])

    def test_remote_errors_do_not_break_the_next_request(self):
        with self.assertRaises(RuntimeError):
            self.client.request('not_a_motor_command')
        self.assertTrue(self.client.request('state')['connected'])


class BridgeTimeoutTests(unittest.TestCase):
    def test_same_computer_bridge_cannot_forward_to_itself(self):
        with self.assertRaises(ValueError):
            MotorisedStageZMQBridgeServer('localhost', 50941, local_command_port=50941)

    def test_timeout_does_not_replay_move_and_next_socket_recovers(self):
        with socket.socket() as probe:
            try:
                probe.bind(('127.0.0.1', 0))
            except PermissionError:
                self.skipTest('Localhost sockets are unavailable in this sandbox')
        remote_ready = Ready()
        requests = []
        def remote_server():
            context = zmq.Context()
            remote = context.socket(zmq.REP)
            remote.setsockopt(zmq.LINGER, 0)
            remote.setsockopt(zmq.RCVTIMEO, 2000)
            port = remote.bind_to_random_port('tcp://127.0.0.1')
            remote_ready.send({'command_port': port})
            try:
                for index in range(2):
                    requests.append(remote.recv_json())
                    if index == 0:
                        time.sleep(.15)
                    remote.send_json({'ok': True, 'state': {'connected': True, 'axes': {}}})
            finally:
                remote.close()
                context.term()
        remote_thread = threading.Thread(target=remote_server)
        remote_thread.start()
        remote_port = remote_ready.messages.get(timeout=2)['command_port']
        bridge = MotorisedStageZMQBridgeServer('127.0.0.1', remote_port, local_command_port=0, timeout_ms=50)
        bridge_ready = Ready()
        bridge_thread = threading.Thread(target=bridge.run_forever, kwargs={'ready_connection': bridge_ready})
        bridge_thread.start()
        bridge_port = bridge_ready.messages.get(timeout=2)['command_port']
        client = MotorisedStageClient(command_port=bridge_port, timeout_ms=1000)
        try:
            with self.assertRaisesRegex(RuntimeError, 'not retried'):
                client.request('relative', 'X', .01)
            time.sleep(.2)
            self.assertTrue(client.request('state')['connected'])
            self.assertEqual([item['command'] for item in requests], ['relative', 'state'])
        finally:
            client.request('shutdown_bridge')
            client.close()
            bridge_thread.join(2)
            remote_thread.join(2)
        self.assertFalse(bridge_thread.is_alive())
        self.assertFalse(remote_thread.is_alive())
