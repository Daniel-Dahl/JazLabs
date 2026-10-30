"""Direct simulator behaviour must match the hardware-facing motor API."""
import types
import unittest
from unittest.mock import patch

import JazLabs.hardware.MotorisedStages.SimulatedStage as simulator


class SimulatedStageTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        clock = types.SimpleNamespace(perf_counter=lambda: self.now, sleep=self.advance)
        self.clock_patch = patch.object(simulator, 'time', clock)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def advance(self, seconds):
        self.now += seconds

    def test_status_exposes_per_axis_calibration_and_copies_configuration(self):
        stage = simulator.SimulatedStage(counts_per_unit={'X': 1000, 'Y': 2000})
        status = stage.GetStatus()
        x, y = status['axes']['X'], status['axes']['Y']
        self.assertEqual(x['positions'], {'counts': 5000, 'mm': 5})
        self.assertEqual(y['positions'], {'counts': 12000, 'mm': 6})
        self.assertEqual(y['limits_by_unit']['counts'], [0, 50000])
        self.assertEqual(y['step_by_unit']['counts'], 20)
        self.assertEqual(y['resolution_by_unit']['mm'], .0005)
        self.assertEqual(stage.ConvertPosition('Y', 1000, 'counts', 'mm'), .5)
        x['limits'][0] = 10
        self.assertEqual(stage.GetStatus('X')['axes']['X']['limits'], [0, 25])

    def test_count_moves_wait_by_default_and_relative_moves_share_limits(self):
        stage = simulator.SimulatedStage(axes=1, limits={'X': [0, 5.03]})
        result = stage.MoveAbs('X', 5010, units='counts')
        self.assertAlmostEqual(result['position'], 5.01)
        self.assertFalse(result['moving'])
        result = stage.MoveRel('X', 10, units='counts')
        self.assertAlmostEqual(result['position'], 5.02)
        with self.assertRaisesRegex(ValueError, 'travel limits'):
            stage.MoveRel('X', 20, units='counts', wait=False)
        self.assertAlmostEqual(stage.targets['X'], 5.02)
        for move in (stage.MoveAbs, stage.MoveRel):
            with self.assertRaises(ValueError):
                move('X', .5, units='counts', wait=False)
            with self.assertRaises(ValueError):
                move('X', 1, units='deg', wait=False)

    def test_rounded_target_is_checked_against_travel_limits(self):
        stage = simulator.SimulatedStage(axes=1, limits={'X': [5.0004, 5.01]})
        with self.assertRaisesRegex(ValueError, 'Rounded target'):
            stage.MoveAbs('X', 5.0004, wait=False)

    def test_active_motion_cannot_be_replaced(self):
        stage = simulator.SimulatedStage(axes=1)
        self.assertIsNone(stage.MoveAbs('X', 5.5, wait=False))
        for move in (lambda: stage.MoveAbs('X', 6, wait=False),
                     lambda: stage.MoveRel('X', .1, wait=False),
                     lambda: stage.HomeAxis('X', wait=False)):
            with self.assertRaises(RuntimeError):
                move()
            self.assertEqual(stage.targets['X'], 5.5)

    def test_stop_and_disable_advance_to_the_event_time_and_cancel_motion(self):
        stage = simulator.SimulatedStage(axes=1)
        stage.MoveAbs('X', 5.5, wait=False)
        self.advance(.1)
        stage.StopAll()
        self.assertAlmostEqual(stage.positions['X'], 5.1)
        self.advance(1)
        self.assertFalse(stage.GetStatus('X')['axes']['X']['moving'])
        stage.MoveAbs('X', 5.5, wait=False)
        self.advance(.1)
        stage.EnableAxis('X', False)
        stopped = stage.positions['X']
        self.advance(1)
        self.assertFalse(stage.GetStatus('X')['axes']['X']['enabled'])
        stage.EnableAxis('X')
        self.advance(1)
        self.assertAlmostEqual(stage.GetStatus('X')['axes']['X']['position'], stopped)
        self.assertFalse(stage.GetStatus('X')['axes']['X']['moving'])

    def test_speed_changes_apply_only_after_the_change_and_reject_invalid_values(self):
        stage = simulator.SimulatedStage(axes=1)
        stage.MoveAbs('X', 6, wait=False)
        self.advance(.1)
        stage.SetSpeed('X', 2)
        self.assertAlmostEqual(stage.positions['X'], 5.1)
        self.advance(.1)
        self.assertAlmostEqual(stage.GetStatus('X')['axes']['X']['position'], 5.3)
        for value in (0, -1, .001, 3, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                stage.SetSpeed('X', value)
        self.assertEqual(stage.velocity['X'], 2)

    def test_homing_can_reach_zero_outside_ordinary_limits_and_mirrors_reject_homing(self):
        stage = simulator.SimulatedStage(axes=1, limits={'X': [1, 10]})
        result = stage.HomeAxis('X')
        self.assertTrue(result['homed'])
        self.assertFalse(result['homing'])
        self.assertFalse(result['moving'])
        self.assertEqual(result['position'], 0)
        with self.assertRaises(ValueError):
            stage.MoveAbs('X', .5)
        mirror = simulator.SimulatedStage(absolute_sensor=True)
        self.assertEqual(mirror.GetStatus()['axes']['U']['units'], 'deg')
        self.assertEqual(mirror.ConvertPosition('U', 100, 'counts', 'deg'), .1)
        with self.assertRaisesRegex(ValueError, 'absolute sensor'):
            mirror.HomeAxis('U')

    def test_timeouts_stop_motion_and_interrupted_homing_keeps_reference_unset(self):
        stage = simulator.SimulatedStage(axes=1)
        with self.assertRaises(TimeoutError):
            stage.MoveAbs('X', 6, timeout=.005)
        self.assertFalse(stage.GetStatus('X')['axes']['X']['moving'])
        with self.assertRaises(TimeoutError):
            stage.HomeAxis('X', timeout=.005)
        status = stage.GetStatus('X')['axes']['X']
        self.assertFalse(status['moving'])
        self.assertFalse(status['homing'])
        self.assertFalse(status['homed'])

    def test_nominal_checks_all_limits_and_uses_midpoints_for_every_axis(self):
        stage = simulator.SimulatedStage(limits={'Y': [None, None]})
        targets = dict(stage.targets)
        with self.assertRaisesRegex(ValueError, 'configure travel limits'):
            stage.SetNominal(wait=False)
        self.assertEqual(stage.targets, targets)
        with self.assertRaisesRegex(ValueError, 'configure travel limits'):
            stage.MoveAbs('Y', 1, wait=False)
        mirror = simulator.SimulatedStage(absolute_sensor=True,
                                         limits={'U': [-.1, .3], 'V': [-.2, .2]})
        mirror.SetNominal(wait=False)
        self.advance(1)
        status = mirror.GetStatus()
        self.assertEqual(status['axes']['U']['position'], .1)
        self.assertEqual(status['axes']['V']['position'], 0)
        self.assertFalse(any(axis['moving'] for axis in status['axes'].values()))

    def test_unknown_axes_invalid_configuration_and_closed_connections_are_rejected(self):
        stage = simulator.SimulatedStage(axes=1)
        for call in (lambda: stage.GetStatus('Y'), lambda: stage.MoveAbs('Y', 1),
                     lambda: stage.MoveRel('Y', 1), lambda: stage.HomeAxis('Y'),
                     lambda: stage.EnableAxis('Y'), lambda: stage.SetSpeed('Y', 1)):
            with self.assertRaises(ValueError):
                call()
        for options in ({'move_timeout': 0}, {'move_timeout': float('nan')},
                        {'counts_per_unit': -1}, {'counts_per_unit': {'X': 1000}},
                        {'limits': {'X': [0, 26]}}, {'limits': {'X': [None, -1]}},
                        {'limits': {'X': [26, None]}}):
            with self.assertRaises(ValueError):
                simulator.SimulatedStage(**options)
        with simulator.SimulatedStage(axes=1) as opened:
            opened.MoveAbs('X', 6, wait=False)
            self.advance(.1)
        self.assertFalse(opened.is_open)
        self.assertAlmostEqual(opened.positions['X'], opened.targets['X'])
        opened.CloseStage()
        with self.assertRaisesRegex(RuntimeError, 'closed'):
            opened.GetStatus()
