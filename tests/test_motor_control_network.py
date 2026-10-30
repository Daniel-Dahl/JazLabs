"""Exercise the new snapshot/intent protocol using a loopback simulator."""
import socket
import threading
import time
import types
import unittest
from unittest.mock import patch

from JazLabs.hardware.MotorisedStages.SimulatedStage import SimulatedStage
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient, MotorCommandRejected
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
            self.client.CloseStage()
            self.thread.join(3)
        self.assertFalse(self.thread.is_alive())

    def wait(self, predicate, timeout=3):
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline:
            try:
                if predicate():
                    return
            except TimeoutError:
                pass
            time.sleep(.02)
        self.fail('Network motion state did not arrive')

    def test_intuitive_position_readers(self):
        self.assertEqual(self.client.GetStatus('X')['axes']['X']['position'], 5)
        self.assertEqual({axis: feedback['position'] for axis, feedback in self.client.GetStatus()['axes'].items()}, {'X': 5})
        self.assertIn('homed', self.client.GetStatus('X')['axes']['X'])

    def test_newport_server_and_clients_use_the_single_status_dictionary(self):
        self.check_serial_status_driver('CONEXAGPSerial')

    def test_thorlabs_server_and_clients_use_the_single_status_dictionary(self):
        self.check_serial_status_driver('UMC2Serial')

    def check_serial_status_driver(self, stage_type):
        self.client.request('shutdown')
        self.thread.join(3)
        mount = SimulatedStage(axes=1)

        def get_status(axis=None):
            feedback = mount.GetStatus('X')['axes']['X']
            feedback.update(label='Translation', units='mm', limits=[0, 25],
                            resolution=.001, tolerance=.002, step=.01,
                            supports={'home': True, 'home_when_referenced': False, 'stop': True, 'speed': False})
            feedback.update(unit_scales={'counts': 1, 'mm': 1000},
                            limits_by_unit={'counts': [0, 25000], 'mm': [0, 25]},
                            step_by_unit={'counts': 10, 'mm': .01},
                            resolution_by_unit={'counts': 1, 'mm': .001},
                            independent_mount=True, stage={'part_number': 'Test stage'})
            return {'controller': stage_type, 'port': 'fake', 'move_timeout': 60,
                    'controller_state': 0x28 if feedback['moving'] else 0x32,
                    'controller_error': 0, 'axes': {'X': feedback}}

        # No old getters exist: the server must use GetStatus for configuration
        # and polling, and must explicitly request nonblocking homing.
        homes = []
        def home_axis(axis, wait):
            homes.append(wait)
            mount.HomeAxis(axis, wait=False)

        driver = types.SimpleNamespace(GetStatus=get_status, MoveAbs=mount.MoveAbs, MoveRel=mount.MoveRel,
                    HomeAxis=home_axis, EnableAxis=mount.EnableAxis,
                    StopAll=mount.StopAll, CloseStage=mount.CloseStage)
        with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.create_motorised_stage', return_value=driver):
            self.server = MotorisedStageZMQServer(command_port=self.port, stage_type=stage_type)
            self.thread = threading.Thread(target=self.server.run_forever)
            self.thread.start()
            self.wait(lambda: self.client.request('state')['connected'])
            status = self.client.GetStatus()
            self.assertEqual(status['port'], 'fake')
            self.assertEqual(status['axes']['X']['limits'], [0, 25])
            self.assertEqual(status['axes']['X']['position'], 5)
            self.assertTrue(status['axes']['X']['supports']['home'])
            capabilities = self.client.GetStatus('X')['axes']['X']
            self.assertEqual(capabilities['unit_scales'], {'counts': 1, 'mm': 1000})
            self.assertEqual(capabilities['stage']['part_number'], 'Test stage')
            self.assertTrue(capabilities['independent_mount'])
            self.client.MoveAbs('X', 5020, units='counts')
            observer = MotorisedStageClient(command_port=self.port)
            try:
                self.assertAlmostEqual(observer.GetStatus('X')['axes']['X']['position'], 5.02)
                self.client.HomeAxis('X', wait=False)
                self.wait(lambda: homes == [False])
                observer.StopAll()
                self.wait(lambda: self.client.GetStatus()['stopped'])
            finally:
                observer.CloseStage()

    def test_move_waits_for_its_own_stopped_completion_by_default(self):
        began = time.perf_counter()
        result = self.client.MoveAbs('X', 5.2)
        self.assertGreaterEqual(time.perf_counter() - began, .15)
        self.assertAlmostEqual(result['position'], 5.2, places=3)
        self.assertFalse(result['moving'])
        self.assertFalse(result['commanded'])

    def test_wait_false_returns_an_operation_before_motion_finishes(self):
        result = self.client.MoveAbs('X', 6, wait=False)
        operation_id = result['operation_id']
        self.assertIn(self.client.request('state')['operations'][operation_id]['status'], ('queued', 'running'))
        self.client.StopAll()

    def test_rejected_move_raises_without_claiming_completion(self):
        with self.assertRaisesRegex(RuntimeError, 'travel limit'):
            self.client.MoveAbs('X', 26)
        self.assertEqual(self.client.GetStatus('X')['axes']['X']['position'], 5)
        self.assertFalse(self.client.request('state')['stopped'])

    def test_same_position_is_a_successful_no_op(self):
        result = self.client.MoveAbs('X', 5)
        self.assertFalse(result['moving'])
        self.assertEqual(result['position'], 5)

    def test_client_timeout_requests_stop_and_raises(self):
        with self.assertRaises(TimeoutError):
            self.client.MoveAbs('X', 7, timeout=.1)
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_stop_from_another_client_interrupts_a_blocking_move(self):
        def stop_from_gui():
            stopper = MotorisedStageClient(command_port=self.port)
            try:
                stopper.StopAll()
            finally:
                stopper.CloseStage()
        stop_timer = threading.Timer(.2, stop_from_gui)
        stop_timer.start()
        try:
            with self.assertRaisesRegex(RuntimeError, 'stop'):
                self.client.MoveAbs('X', 7)
        finally:
            stop_timer.join(1)

    def test_user_client_exposes_the_driver_facing_api(self):
        self.assertEqual(next(iter(self.client.GetStatus()['axes'])), 'X')
        self.assertEqual(self.client.GetStatus()['controller'], 'simulation')
        self.assertEqual(self.client.GetStatus('X')['axes']['X']['position'], 5)
        self.client.MoveAbs('X', 5.02)
        self.wait(lambda: self.client.GetStatus('X')['axes']['X']['position'] >= 5.019)
        self.client.StopAll()
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_relative_move_waits_and_rejects_an_out_of_range_destination(self):
        result = self.client.MoveRel('X', .02)
        self.assertAlmostEqual(result['position'], 5.02)
        self.assertFalse(result['moving'])
        with self.assertRaisesRegex(RuntimeError, 'travel limit'):
            self.client.MoveRel('X', 25)
        self.assertFalse(self.client.GetStatus()['stopped'])

    def test_home_waits_by_default_and_enable_supports_both_states(self):
        self.client.EnableAxis('X', enabled=False)
        self.wait(lambda: not self.client.GetStatus()['axes']['X']['enabled'])
        self.client.EnableAxis('X')
        self.wait(lambda: self.client.GetStatus()['axes']['X']['enabled'])
        self.client.request('speed', 'X', 2)
        self.wait(lambda: self.client.GetStatus()['axes']['X']['speed'] == 2)
        self.client.MoveAbs('X', 0)
        result = self.client.HomeAxis('X')
        self.assertTrue(result['homed'])
        self.assertFalse(result['moving'])
        self.assertFalse(result['homing'])

    def test_client_and_simulator_expose_one_status_getter_without_legacy_aliases(self):
        for target in (self.client, SimulatedStage(axes=1)):
            for name in ('MoveAbs', 'MoveRel', 'HomeAxis', 'SetNominal', 'EnableAxis', 'StopAll', 'GetStatus'):
                self.assertTrue(callable(getattr(target, name)))
            for name in ('MoveTo', 'GetPosition', 'GetPositions', 'GetAxisStatus', 'GetProperties', 'GetMotionCapabilities', 'get_state'):
                self.assertFalse(hasattr(target, name))
        status = self.client.GetStatus()
        for name in ('properties', 'capabilities', 'device_status'):
            self.assertNotIn(name, status)

    def test_moves_and_stop_latch(self):
        self.client.request('relative', 'X', .02)
        self.wait(lambda: self.client.request('state')['axes']['X']['position'] >= 5.019)
        self.client.request('stop')
        self.wait(lambda: self.client.request('state')['stopped'])
        with self.assertRaises(RuntimeError):
            self.client.request('absolute', 'X', 5.1)
        self.client.request('resume')
        self.wait(lambda: not self.client.request('state')['stopped'])

    def test_stop_is_processed_after_the_current_serial_read_returns(self):
        entered = threading.Event()
        original = SimulatedStage.GetStatus
        def slow_read(mount, axis):
            entered.set()
            time.sleep(.4)
            return original(mount, axis)
        with patch.object(SimulatedStage, 'GetStatus', slow_read):
            self.assertTrue(entered.wait(1))
            began = time.perf_counter()
            self.client.timeout_ms = 1500
            result = self.client.request('stop')
            self.assertGreaterEqual(time.perf_counter() - began, .3)
            self.assertLess(time.perf_counter() - began, 1.0)
            self.assertTrue(result['stop_pending'] or result['stopped'])
        self.wait(lambda: self.client.request('state')['stopped'])

    def test_feedback_failure_reports_reason_and_resume_clears_it(self):
        original = SimulatedStage.GetStatus
        failed = False

        def fail_after_first_movement(mount, axis):
            nonlocal failed
            status = original(mount, axis)
            if not failed and status['axes']['X']['position'] > 5:
                failed = True
                raise OSError('simulated first-move serial read failure')
            return status

        with patch.object(SimulatedStage, 'GetStatus', fail_after_first_movement):
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
            self.client.MoveAbs('X', 5.1)

    def test_synchronous_rejected_move_does_not_send_stop(self):
        status = self.client.GetStatus()
        with patch.object(self.client, 'GetStatus', return_value=status), \
             patch.object(self.client, 'request', side_effect=MotorCommandRejected('command queue full')) as request:
            with self.assertRaises(MotorCommandRejected):
                self.client.MoveAbs('X', 5.1, timeout=1)
            self.assertEqual(request.call_count, 1)
            self.assertEqual(request.call_args.args[0], 'absolute')

    def test_client_calls_are_synchronous_and_get_status_always_requests_feedback(self):
        with patch.object(self.client, 'request', wraps=self.client.request) as request:
            self.client.GetStatus()
            self.client.GetStatus('X')
            self.assertEqual([call.args[0] for call in request.call_args_list], ['state', 'state'])
        for name in ('start', 'run', 'submit', 'thread', 'lock', 'commands', 'snapshot',
                     'stop_requested', 'release_requested', 'closing', 'wake'):
            self.assertFalse(hasattr(self.client, name))

    def test_disconnecting_one_client_does_not_stop_another_clients_move(self):
        self.client.MoveAbs('X', 6, wait=False)
        self.wait(lambda: self.client.GetStatus()['axes']['X']['commanded'])
        observer = MotorisedStageClient(command_port=self.port)
        observer.CloseStage()
        observer.CloseStage()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            observer.GetStatus()
        self.assertFalse(self.client.GetStatus()['stopped'])
        self.assertTrue(self.client.GetStatus()['axes']['X']['commanded'])

    def test_direct_short_tap_survives_immediate_jog_release(self):
        self.client.MoveRel('X', .01, wait=False)
        self.client.request('release_jog')
        self.wait(lambda: self.client.GetStatus()['axes']['X']['position'] >= 5.009)
        time.sleep(.3)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], 5.01)

    def test_rejected_request_does_not_poison_req_socket(self):
        with self.assertRaises(RuntimeError):
            self.client.request('bogus')
        self.assertTrue(self.client.request('state')['connected'])


if __name__ == '__main__':
    unittest.main()
