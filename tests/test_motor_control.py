"""Behavioral tests for motion scheduling, leased jogs and serial adaptation."""
import threading
import time
import unittest

from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer
from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
from unittest.mock import patch
import socket
from JazLabs.hardware.MotorisedStages.SimulatedStage import SimulatedStage


def wait_until(predicate, timeout=2):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        if predicate():
            return
        time.sleep(0.005)
    raise AssertionError('Timed out waiting for motion state')


class RecordingMount(SimulatedStage):
    def __init__(self):
        super().__init__(axes=2)
        self.moves = []
        self.stops = 0
        self.closed = False

    def MoveAbs(self, axis, target, wait=True, timeout=None, units=None):
        result = super().MoveAbs(axis, target, wait=wait, timeout=timeout, units=units)
        self.moves.append((axis, target))
        return result

    def StopAll(self):
        self.stops += 1
        super().StopAll()

    def CloseStage(self):
        self.closed = True


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.backend = RecordingMount()
        self.factory_patch = patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.create_motorised_stage',
                                   return_value=self.backend)
        self.factory_patch.start()
        with socket.socket() as reservation:
            try:
                reservation.bind(('127.0.0.1', 0))
            except PermissionError:
                self.factory_patch.stop()
                self.skipTest('Localhost sockets are unavailable in this sandbox')
            port = reservation.getsockname()[1]
        self.server = MotorisedStageZMQServer(command_port=port)
        self.server_thread = threading.Thread(target=self.server.run_forever)
        self.server_thread.start()
        self.client = MotorisedStageClient(command_port=port, timeout_ms=1500)
        wait_until(lambda: self.client.request('state')['connected'])

    def tearDown(self):
        try:
            self.client.request('shutdown')
            self.server_thread.join(3)
            self.assertFalse(self.server_thread.is_alive())
            self.assertTrue(self.backend.closed)
        finally:
            self.client.CloseStage()
            self.factory_patch.stop()

    def test_tap_sends_one_move_and_waits_for_feedback(self):
        self.client.request('relative', 'X', 0.02)
        wait_until(lambda: len(self.backend.moves) == 1)
        wait_until(lambda: not self.client.request('state')['axes']['X']['commanded'])
        time.sleep(.2)
        self.assertEqual(len(self.backend.moves), 1)
        self.assertAlmostEqual(self.client.request('state')['axes']['X']['position'], 5.02)

    def test_rapid_taps_keep_one_pending_step_and_do_not_interrupt_active_move(self):
        self.client.request('relative', 'X', .2)
        wait_until(lambda: len(self.backend.moves) == 1)
        for _ in range(100):
            self.client.request('relative', 'X', .01)
        wait_until(lambda: len(self.backend.moves) == 2)
        wait_until(lambda: not self.client.request('state')['axes']['X']['commanded'])
        self.assertFalse(self.client.request('state')['stopped'])
        self.assertIsNone(self.client.request('state')['error'])
        self.assertAlmostEqual(self.backend.GetStatus('X')['axes']['X']['position'], 5.21)
        time.sleep(.2)
        self.assertEqual(len(self.backend.moves), 2)

    def test_held_jog_waits_for_controller_to_finish_active_command(self):
        original = self.backend.GetStatus
        controller_finished = threading.Event()

        def busy_until_controller_finishes(axis):
            status = original(axis)
            if axis == 'X' and self.backend.moves and not controller_finished.is_set():
                status['axes']['X']['moving'] = True
            return status

        self.backend.GetStatus = busy_until_controller_finishes
        for _ in range(10):
            self.client.request('jog', 'X', .01)
            time.sleep(.04)
        self.assertEqual(len(self.backend.moves), 1)
        controller_finished.set()
        self.client.request('jog', 'X', .01)
        wait_until(lambda: len(self.backend.moves) >= 2)
        self.client.request('release_jog')
        wait_until(lambda: not self.client.request('state')['axes']['X']['commanded'])
        self.assertFalse(self.client.request('state')['stopped'])
        self.assertIsNone(self.client.request('state')['error'])

    def test_held_jog_repeats_without_queue_and_release_finishes_step(self):
        for _ in range(12):
            self.client.request('jog', 'X', .01)
            time.sleep(.05)
        self.client.request('release_jog')
        self.assertGreaterEqual(len(self.backend.moves), 2)
        wait_until(lambda: not self.client.request('state')['axes']['X']['commanded'])
        number = len(self.backend.moves)
        time.sleep(.4)
        self.assertEqual(len(self.backend.moves), number)

    def test_jog_lease_expires_if_gui_stops_renewing(self):
        self.client.request('jog', 'X', .01)
        time.sleep(.7)
        count = len(self.backend.moves)
        time.sleep(.4)
        self.assertEqual(len(self.backend.moves), count)

    def test_stop_drops_pending_move_and_requires_explicit_resume(self):
        self.client.request('relative', 'X', 1)
        wait_until(lambda: len(self.backend.moves) == 1)
        self.client.request('relative', 'X', 2)
        self.client.request('stop')
        wait_until(lambda: self.client.request('state')['stopped'] and not self.client.request('state')['stop_pending'])
        self.assertEqual(len(self.backend.moves), 1)
        with self.assertRaises(RuntimeError):
            self.client.request('relative', 'X', 1)
        self.client.request('resume')
        wait_until(lambda: not self.client.request('state')['stopped'])
        self.client.request('relative', 'X', .01)
        wait_until(lambda: len(self.backend.moves) == 2)

    def test_unknown_axis_limits_homing_and_nan_are_rejected(self):
        for command, axis, value in [('relative', 'Z', 1), ('absolute', 'X', 26),
                                     ('relative', 'Y', .01), ('absolute', 'X', float('nan'))]:
            previous = self.client.request('state')['sequence']
            self.client.request(command, axis, value)
            wait_until(lambda: self.client.request('state')['sequence'] > previous and self.client.request('state')['error'] is not None)
            self.assertFalse(self.backend.moves)
        self.client.request('home', 'Y')
        wait_until(lambda: self.client.request('state')['axes']['Y']['homed'], timeout=8)
        self.client.request('relative', 'Y', .01)
        wait_until(lambda: len(self.backend.moves) == 1)

    def test_speed_is_validated_and_applied(self):
        self.client.request('speed', 'X', 1.5)
        wait_until(lambda: self.backend.velocity['X'] == 1.5)
        self.client.request('speed', 'X', -1)
        wait_until(lambda: self.client.request('state')['error'] is not None)
        self.assertEqual(self.backend.velocity['X'], 1.5)

    def test_feedback_failure_latches_stop_instead_of_repeating(self):
        original = self.backend.GetStatus
        fail = threading.Event()
        def poll(axis):
            if fail.is_set():
                raise TimeoutError('unplugged')
            return original(axis)
        self.backend.GetStatus = poll
        self.client.request('jog', 'X', .01)
        wait_until(lambda: len(self.backend.moves) > 0)
        fail.set()
        wait_until(lambda: self.client.request('state')['stopped'])
        count = len(self.backend.moves)
        time.sleep(.2)
        self.assertEqual(len(self.backend.moves), count)
        self.assertFalse(self.client.request('state')['connected'])

    def test_nominal_waits_for_every_axis_and_uses_each_limits_midpoint(self):
        for axis, spec in self.backend.axes.items():
            self.backend.homed[axis] = True
            spec['limits'] = [self.backend.positions[axis], self.backend.positions[axis] + .1]
        wait_until(lambda: self.client.GetStatus()['axes']['Y']['limits'] == [6, 6.1])
        self.client.SetNominal()
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], 5.05)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['Y']['position'], 6.05)
        self.assertEqual(len(self.backend.moves), 2)

    def test_nominal_rejects_missing_limits_before_any_axis_moves(self):
        original = self.backend.GetStatus
        def missing_limits(axis=None):
            status = original(axis)
            if 'Y' in status['axes']:
                status['axes']['Y']['limits'] = [None, None]
            return status
        self.backend.GetStatus = missing_limits
        wait_until(lambda: self.client.GetStatus()['axes']['Y']['limits'] == [None, None])
        with self.assertRaisesRegex(RuntimeError, 'configure travel limits'):
            self.client.SetNominal()
        self.assertFalse(self.backend.moves)
        self.assertFalse(self.client.GetStatus()['stopped'])

    def test_hardware_calls_run_on_the_server_loop_thread(self):
        called_from = []
        original = self.backend.GetStatus

        def record_thread(axis):
            called_from.append(threading.get_ident())
            return original(axis)

        self.backend.GetStatus = record_thread
        self.client.MoveAbs('X', 5.02)
        self.assertTrue(called_from)
        self.assertEqual(set(called_from), {self.server_thread.ident})



class BlockingDriverTests(unittest.TestCase):
    def test_direct_driver_move_waits_by_default(self):
        stage = SimulatedStage(axes=1)
        began = time.perf_counter()
        status = stage.MoveAbs('X', 5.2)
        self.assertGreaterEqual(time.perf_counter() - began, .15)
        self.assertFalse(status['moving'])
        self.assertAlmostEqual(stage.GetStatus('X')['axes']['X']['position'], 5.2)

    def test_direct_driver_timeout_raises_and_stops(self):
        stage = SimulatedStage(axes=1)
        with self.assertRaises(TimeoutError):
            stage.MoveAbs('X', 7, timeout=.05)
        self.assertFalse(stage.GetStatus('X')['axes']['X']['moving'])


if __name__ == '__main__':
    unittest.main()
