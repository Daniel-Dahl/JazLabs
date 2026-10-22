"""Behavioral tests for motion scheduling, leased jogs and serial adaptation."""
import importlib.util
from pathlib import Path
import struct
import threading
import time
import types
import unittest

from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import StageServerWorker
from JazLabs.hardware.MotorisedStages.SimulatedStage import SimulatedStage
from JazLabs.hardware.MotorisedStages.Thorlabs.apt_serial_motion import APTSerialMotion


def wait_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
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

    def MoveTo(self, axis, target, wait=True, timeout=None):
        self.moves.append((axis, target))
        return super().MoveTo(axis, target, wait=wait, timeout=timeout)

    def StopAll(self):
        self.stops += 1
        super().StopAll()

    def CloseStage(self):
        self.closed = True


class MotionTests(unittest.TestCase):
    def setUp(self):
        self.backend = RecordingMount()
        self.worker = StageServerWorker(lambda: self.backend, poll_interval=0.01)
        self.worker.start()
        wait_until(lambda: self.worker.get_state()['connected'])

    def tearDown(self):
        if self.worker.thread.is_alive():
            self.worker.close()
            self.worker.thread.join(2)
        self.assertFalse(self.worker.thread.is_alive())
        self.assertTrue(self.backend.closed)

    def test_tap_sends_one_move_and_waits_for_feedback(self):
        self.worker.submit('relative', 'X', 0.02)
        wait_until(lambda: len(self.backend.moves) == 1)
        wait_until(lambda: not self.worker.get_state()['axes']['X']['commanded'])
        time.sleep(.2)
        self.assertEqual(len(self.backend.moves), 1)
        self.assertAlmostEqual(self.worker.get_state()['axes']['X']['position'], 5.02)

    def test_rapid_taps_keep_one_pending_step_and_do_not_interrupt_active_move(self):
        self.worker.submit('relative', 'X', .2)
        wait_until(lambda: len(self.backend.moves) == 1)
        for _ in range(100):
            self.worker.submit('relative', 'X', .01)
        self.assertLessEqual(self.worker.commands.qsize(), 1)
        wait_until(lambda: len(self.backend.moves) == 2)
        wait_until(lambda: not self.worker.get_state()['axes']['X']['commanded'])
        self.assertFalse(self.worker.get_state()['stopped'])
        self.assertIsNone(self.worker.get_state()['error'])
        self.assertAlmostEqual(self.backend.GetPosition('X'), 5.21)
        time.sleep(.2)
        self.assertEqual(len(self.backend.moves), 2)

    def test_held_jog_waits_for_controller_to_finish_active_command(self):
        original = self.backend.GetAxisStatus
        controller_finished = threading.Event()

        def busy_until_controller_finishes(axis):
            status = original(axis)
            if axis == 'X' and self.backend.moves and not controller_finished.is_set():
                status['moving'] = True
            return status

        self.backend.GetAxisStatus = busy_until_controller_finishes
        for _ in range(10):
            self.worker.submit('jog', 'X', .01)
            time.sleep(.04)
        self.assertEqual(len(self.backend.moves), 1)
        controller_finished.set()
        self.worker.submit('jog', 'X', .01)
        wait_until(lambda: len(self.backend.moves) >= 2)
        self.worker.submit('release_jog')
        wait_until(lambda: not self.worker.get_state()['axes']['X']['commanded'])
        self.assertFalse(self.worker.get_state()['stopped'])
        self.assertIsNone(self.worker.get_state()['error'])

    def test_held_jog_repeats_without_queue_and_release_finishes_step(self):
        for _ in range(12):
            self.worker.submit('jog', 'X', .01)
            time.sleep(.05)
        self.worker.submit('release_jog')
        self.assertGreaterEqual(len(self.backend.moves), 2)
        wait_until(lambda: not self.worker.get_state()['axes']['X']['commanded'])
        number = len(self.backend.moves)
        time.sleep(.4)
        self.assertEqual(len(self.backend.moves), number)
        self.assertEqual(self.worker.commands.qsize(), 0)

    def test_jog_lease_expires_if_gui_stops_renewing(self):
        self.worker.submit('jog', 'X', .01)
        time.sleep(.7)
        count = len(self.backend.moves)
        time.sleep(.4)
        self.assertEqual(len(self.backend.moves), count)
        self.assertIsNone(self.worker.held_jog)

    def test_stop_drops_pending_move_and_requires_explicit_resume(self):
        self.worker.submit('relative', 'X', 1)
        wait_until(lambda: len(self.backend.moves) == 1)
        self.worker.submit('relative', 'X', 2)
        self.worker.submit('stop')
        wait_until(lambda: self.worker.get_state()['stopped'] and not self.worker.get_state()['stop_pending'])
        self.assertEqual(len(self.backend.moves), 1)
        with self.assertRaises(RuntimeError):
            self.worker.submit('relative', 'X', 1)
        self.worker.submit('resume')
        wait_until(lambda: not self.worker.get_state()['stopped'])
        self.worker.submit('relative', 'X', .01)
        wait_until(lambda: len(self.backend.moves) == 2)

    def test_unknown_axis_limits_homing_and_nan_are_rejected(self):
        for command, axis, value in [('relative', 'Z', 1), ('absolute', 'X', 26),
                                     ('relative', 'Y', .01), ('absolute', 'X', float('nan'))]:
            previous = self.worker.get_state()['sequence']
            self.worker.submit(command, axis, value)
            wait_until(lambda: self.worker.get_state()['sequence'] > previous and self.worker.commands.empty())
            self.assertFalse(self.backend.moves)
        self.worker.submit('home', 'Y')
        wait_until(lambda: self.worker.get_state()['axes']['Y']['homed'], timeout=8)
        self.worker.submit('relative', 'Y', .01)
        wait_until(lambda: len(self.backend.moves) == 1)

    def test_speed_is_validated_and_applied(self):
        self.worker.submit('speed', 'X', 1.5)
        wait_until(lambda: self.backend.velocity['X'] == 1.5)
        self.worker.submit('speed', 'X', -1)
        wait_until(lambda: self.worker.get_state()['error'] is not None)
        self.assertEqual(self.backend.velocity['X'], 1.5)

    def test_feedback_failure_latches_stop_instead_of_repeating(self):
        original = self.backend.GetAxisStatus
        fail = threading.Event()
        def poll(axis):
            if fail.is_set():
                raise TimeoutError('unplugged')
            return original(axis)
        self.backend.GetAxisStatus = poll
        self.worker.submit('jog', 'X', .01)
        wait_until(lambda: len(self.backend.moves) > 0)
        fail.set()
        wait_until(lambda: self.worker.get_state()['stopped'])
        count = len(self.backend.moves)
        time.sleep(.2)
        self.assertEqual(len(self.backend.moves), count)
        self.assertFalse(self.worker.get_state()['connected'])

    def test_stop_submit_does_not_wait_for_hardware_read_lock(self):
        original = self.backend.GetAxisStatus
        reading = threading.Event()
        release = threading.Event()
        def poll(axis):
            reading.set()
            release.wait(1)
            return original(axis)
        self.backend.GetAxisStatus = poll
        self.assertTrue(reading.wait(1))
        began = time.monotonic()
        self.worker.submit('stop')
        elapsed = time.monotonic() - began
        release.set()
        self.assertLess(elapsed, .05)
        wait_until(lambda: self.worker.get_state()['stopped'])


class AptPort:
    timeout = .25
    def __init__(self):
        self.writes = []
        self.reply = bytearray()
    @property
    def in_waiting(self):
        return len(self.reply)
    def write(self, value):
        self.writes.append(value)
        message, = struct.unpack_from('<H', value)
        destination = value[4] & 0x7F
        if message == 0x0411:
            payload = struct.pack('<Hi', 1, 123)
            self.reply.extend(struct.pack('<HHBB', 0x0412, 6, 0x81, destination) + payload)
        elif message == 0x0429:
            payload = struct.pack('<HI', 1, 0x80000400)
            self.reply.extend(struct.pack('<HHBB', 0x042A, 6, 0x81, destination) + payload)
    def read(self, size):
        # Deliberately fragmented serial reads.
        part = bytes(self.reply[:min(size, 3)])
        del self.reply[:len(part)]
        return part


class FakeAPTDriver(APTSerialMotion):
    def __init__(self, routes=None, units="counts", scale=1.0, limits=None):
        self.serial = AptPort()
        self._configure_motion(routes or {"X": 0x50}, units, scale, limits)

    def GetProperties(self):
        return {"stage_type": "test"}

    def CloseStage(self):
        pass


class BlockingDriverTests(unittest.TestCase):
    def test_direct_driver_move_waits_by_default(self):
        stage = SimulatedStage(axes=1)
        began = time.monotonic()
        status = stage.MoveTo('X', 5.2)
        self.assertGreaterEqual(time.monotonic() - began, .15)
        self.assertFalse(status['moving'])
        self.assertAlmostEqual(stage.GetPosition('X'), 5.2)

    def test_direct_driver_timeout_raises_and_stops(self):
        stage = SimulatedStage(axes=1)
        with self.assertRaises(TimeoutError):
            stage.MoveTo('X', 7, timeout=.05)
        self.assertFalse(stage.GetAxisStatus('X')['moving'])


class DriverTests(unittest.TestCase):
    def test_apt_fragmented_poll_home_stop_and_custom_slot_routing(self):
        driver = FakeAPTDriver(routes={"Z": 0x23, "X": 0x21}, limits={"Z": [0, 1000]})
        state = driver.GetAxisStatus('Z')
        self.assertEqual(state['position'], 123)
        self.assertTrue(state['homed'])
        self.assertTrue(state['enabled'])
        driver.MoveTo('Z', 321, wait=False)
        self.assertEqual(driver.serial.writes[-1], struct.pack('<HHBBHi', 0x0453, 6, 0xA3, 1, 1, 321))
        driver.HomeAxis('X')
        self.assertEqual(driver.serial.writes[-1], struct.pack('<HBBBB', 0x0443, 1, 0, 0x21, 1))
        driver.StopAll()
        self.assertEqual([packet[4] for packet in driver.serial.writes[-2:]], [0x23, 0x21])

    def test_driver_unit_conversion_and_travel_limits(self):
        driver = FakeAPTDriver(units='mm', scale=1000, limits={'X': [.1, 12.9]})
        self.assertAlmostEqual(driver.GetAxisStatus('X')['position'], .123)
        driver.MoveTo('X', 2.5, wait=False)
        self.assertEqual(struct.unpack_from('<i', driver.serial.writes[-1], 8)[0], 2500)
        with self.assertRaises(ValueError):
            driver.MoveTo('X', 13)

    def test_server_limits_cannot_widen_the_driver_travel(self):
        driver = FakeAPTDriver(units='mm', scale=1000, limits={'X': [.1, 12.9]})
        worker = StageServerWorker(lambda: driver, limits={'X': [0, 13]})
        worker.start()
        worker.thread.join(1)
        self.assertFalse(worker.thread.is_alive())
        self.assertIn("cannot widen", worker.get_state()['error'])

    def test_stop_event_interrupts_slow_apt_read(self):
        driver = FakeAPTDriver()
        driver.SetStopRequested(lambda: True)
        with self.assertRaises(InterruptedError):
            driver.GetAxisStatus('X')


if __name__ == '__main__':
    unittest.main()
