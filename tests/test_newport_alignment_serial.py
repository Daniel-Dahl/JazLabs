"""Serial alignment API and physical-unit focus regression tests."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np


class NewportAlignmentTests(unittest.TestCase):
    def setUp(self):
        helper = types.ModuleType('JazLabs.utils.AlignmentFunctions')
        helper.MakeBoundsFromCentre = lambda centre, steps: (centre - steps, centre + steps)
        helper.physical_to_normalised = lambda value, lower, upper: 2 * (value - lower) / (upper - lower) - 1
        helper.normalised_to_physical = lambda value, lower, upper: lower + (value + 1) * (upper - lower) / 2
        helper.CheckFileForStopAliginment = lambda: False
        helper.ChangeFileForStopAliginment = lambda value: None
        camera_helper = types.ModuleType('JazLabs.utils.camera_utils')
        camera_helper.get_relative_power = lambda **kwargs: 1
        fake_serial = types.SimpleNamespace(Serial=None)
        path = Path(__file__).resolve().parents[1] / 'src/JazLabs/procedures/MotorisedStages/NewportTipTiltStage_AlignmentRoutines.py'
        spec = importlib.util.spec_from_file_location('serial_alignment_test', path)
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'serial': fake_serial, 'cma': types.ModuleType('cma'),
                                     helper.__name__: helper, camera_helper.__name__: camera_helper}):
            spec.loader.exec_module(self.module)
        self.mirror_moves = []
        self.focus_moves = []
        mirror = types.SimpleNamespace(GetPositions=lambda: {'U': .1, 'V': -.2},
                         MoveAbs=lambda axis, value, wait: self.mirror_moves.append((axis, value, wait)))
        focus = types.SimpleNamespace(GetPositions=lambda: [1.2345],
                         MoveAbs=lambda axis, value, wait: self.focus_moves.append((axis, value, wait)))
        self.alignment = self.module.AlignmentObj([mirror], pwr_objs=[types.SimpleNamespace(GetPower=lambda: 1)],
                                                  stage_obj_trans=[focus])

    def test_alignment_uses_waited_absolute_serial_moves_and_keeps_focus_precision(self):
        def optimise(objective, initial, **kwargs):
            objective(np.array([0., 0., 0.]))
            objective(np.array([.5, .5, .5]))
            return types.SimpleNamespace(success=True)
        with patch.object(self.module, 'minimize', side_effect=optimise):
            result = self.alignment.multi_dim_alignment_of_stage(
                [0], [{'AlignYAW': True, 'AlignPITCH': True, 'AlignFOCUS': True}],
                initial_step_sizes=[{'d_YAW': .02, 'd_PITCH': .02, 'd_FOCUS': .01}],
                optimiser='Powell', pwr_meter_obj_idx=0)
        self.assertEqual(result['eval_count'], 2)
        self.assertTrue(all(move[2] for move in self.mirror_moves + self.focus_moves))
        self.assertEqual([move[0] for move in self.mirror_moves], ['U', 'V'] * 3)
        self.assertAlmostEqual(self.focus_moves[0][1], 1.2345)
        self.assertAlmostEqual(self.focus_moves[1][1], 1.2395)
        self.assertEqual(self.focus_moves[0][0], 'X')
        self.assertAlmostEqual(self.focus_moves[-1][1], 1.2345)

    def test_focus_requires_explicit_step_in_configured_units(self):
        with self.assertRaisesRegex(ValueError, 'explicit d_FOCUS'):
            self.alignment.multi_dim_alignment_of_stage([0], [{'AlignFOCUS': True}],
                                                       pwr_meter_obj_idx=0)


if __name__ == '__main__':
    unittest.main()
