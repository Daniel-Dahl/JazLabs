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

    def test_intuitive_position_readers(self):
        self.assertEqual(self.client.GetPosition('X'), 5)
        self.assertEqual(self.client.GetPositions(), {'X': 5})
        self.assertIn('homed', self.client.GetAxisStatus('X'))

    def test_move_waits_for_its_own_stopped_completion_by_default(self):
        began = time.monotonic()
        result = self.client.MoveTo('X', 5.2)
        self.assertGreaterEqual(time.monotonic() - began, .15)
        self.assertAlmostEqual(result['position'], 5.2, places=3)
        self.assertFalse(result['moving'])
        self.assertFalse(result['commanded'])

    def test_wait_false_returns_an_operation_before_motion_finishes(self):
        result = self.client.MoveTo('X', 6, wait=False)
        operation_id = result['operation_id']
        self.assertIn(self.client.request('state')['operations'][operation_id]['status'], ('queued', 'running'))
        self.client.StopAll()

    def test_rejected_move_raises_without_claiming_completion(self):
        with self.assertRaisesRegex(RuntimeError, 'travel limit'):
            self.client.MoveTo('X', 26)
        self.assertEqual(self.client.GetPosition('X'), 5)
        self.assertFalse(self.client.request('state')['stopped'])

    def test_same_position_is_a_successful_no_op(self):
        result = self.client.MoveTo('X', 5)
        self.assertFalse(result['moving'])
        self.assertEqual(result['position'], 5)

    def test_client_timeout_requests_stop_and_raises(self):
        with self.assertRaises(TimeoutError):
            self.client.MoveTo('X', 7, timeout=.1)
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_stop_from_another_client_interrupts_a_blocking_move(self):
        def stop_from_gui():
            stopper = MotorisedStageClient(command_port=self.port)
            try:
                stopper.StopAll()
            finally:
                stopper.close()
        stop_timer = threading.Timer(.2, stop_from_gui)
        stop_timer.start()
        try:
            with self.assertRaisesRegex(RuntimeError, 'stop'):
                self.client.MoveTo('X', 7)
        finally:
            stop_timer.join(1)

    def test_user_client_exposes_the_driver_facing_api(self):
        self.assertEqual(self.client.GetMotionCapabilities()[0]['id'], 'X')
        self.assertEqual(self.client.GetProperties()['stage_type'], 'simulation')
        self.assertEqual(self.client.GetAxisStatus('X')['position'], 5)
        self.client.MoveTo('X', 5.02)
        self.wait(lambda: self.client.GetAxisStatus('X')['position'] >= 5.019)
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
        original = SimulatedStage.GetAxisStatus
        def slow_read(mount, axis):
            entered.set()
            time.sleep(.4)
            return original(mount, axis)
        with patch.object(SimulatedStage, 'GetAxisStatus', slow_read):
            self.assertTrue(entered.wait(1))
            began = time.monotonic()
            result = self.client.request('stop')
            self.assertLess(time.monotonic() - began, .2)
            self.assertTrue(result['stop_pending'] or result['stopped'])
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_first_move_feedback_failure_preserves_stop_reason_after_resume(self):
        original = SimulatedStage.GetAxisStatus
        failed = False

        def fail_after_first_movement(mount, axis):
            nonlocal failed
            status = original(mount, axis)
            if not failed and status['position'] > 5:
                failed = True
                raise OSError('simulated first-move serial read failure')
            return status

        with patch.object(SimulatedStage, 'GetAxisStatus', fail_after_first_movement):
            self.client.request('relative', 'X', .02)
            self.wait(lambda: self.client.request('state')['stopped'])
            state = self.client.request('state')
            reason = state['stop_reason']
            self.assertIn('simulated first-move serial read failure', reason)
            self.assertIn(reason, state['message'])
            self.client.request('resume')
            self.wait(lambda: not self.client.request('state')['stopped'])
            state = self.client.request('state')
            self.assertIsNone(state['stop_reason'])
            self.assertEqual(state['last_stop_reason'], reason)
            self.client.MoveTo('X', 5.1)

    def test_gui_connection_failure_reports_why_it_requested_stop(self):
        endpoint = MotorisedStageClient(command_port=self.port)
        original_request = endpoint.request

        def lose_first_move_reply(command, *args, **kwargs):
            state = original_request(command, *args, **kwargs)
            if command == 'relative':
                raise TimeoutError('simulated lost first-move reply')
            return state

        with patch.object(endpoint, 'request', side_effect=lose_first_move_reply):
            endpoint.submit('relative', 'X', .02)
            endpoint.start()
            try:
                self.wait(lambda: endpoint.get_state()['stopped'])
                self.assertEqual(endpoint.get_state()['stop_reason'],
                                 'Client relative request failed: simulated lost first-move reply')
            finally:
                endpoint.close()
                endpoint.thread.join(2)

    def test_gui_initial_connection_timeout_does_not_latch_stop(self):
        endpoint = MotorisedStageClient(command_port=self.port)
        original_request = endpoint.request
        commands = []

        def timeout_first_state_poll(command, *args, **kwargs):
            commands.append(command)
            if len(commands) == 1:
                self.assertEqual(command, 'state')
                raise TimeoutError('server is still starting')
            return original_request(command, *args, **kwargs)

        with patch.object(endpoint, 'request', side_effect=timeout_first_state_poll):
            endpoint.start()
            try:
                self.wait(lambda: endpoint.get_state()['connected'])
                self.assertNotIn('stop', commands)
                self.assertFalse(endpoint.get_state()['stopped'])
                endpoint.submit('relative', 'X', .02)
                self.wait(lambda: endpoint.get_state()['axes']['X']['position'] >= 5.019)
                self.assertFalse(endpoint.get_state()['stopped'])
            finally:
                endpoint.close()
                endpoint.thread.join(2)

    def test_gui_state_timeout_after_connecting_still_latches_stop(self):
        endpoint = MotorisedStageClient(command_port=self.port)
        original_request = endpoint.request
        state_polls = 0

        def lose_second_state_reply(command, *args, **kwargs):
            nonlocal state_polls
            if command == 'state':
                state_polls += 1
                if state_polls == 2:
                    raise TimeoutError('lost feedback after connecting')
            return original_request(command, *args, **kwargs)

        with patch.object(endpoint, 'request', side_effect=lose_second_state_reply):
            endpoint.start()
            try:
                self.wait(lambda: endpoint.get_state()['stopped'])
                self.assertIn('lost feedback after connecting', endpoint.get_state()['stop_reason'])
            finally:
                endpoint.close()
                endpoint.thread.join(2)

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
