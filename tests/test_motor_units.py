"""Unit selection uses driver calibration, including different mount scales."""
import unittest
from unittest.mock import patch

from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient


class ClientUnitsTests(unittest.TestCase):
    def setUp(self):
        self.client = MotorisedStageClient()
        self.snapshot = {
            'connected': True, 'move_timeout': 60, 'axes': {
                'X': {'units': 'mm', 'unit_scales': {'counts': 1, 'mm': 1000},
                      'position': 1, 'positions': {'counts': 1000, 'mm': 1}, 'age': 0},
                'Y': {'units': 'counts', 'unit_scales': {'counts': 1, 'mm': 2000},
                      'position': 1000, 'positions': {'counts': 1000, 'mm': .5}, 'age': 0}}}

    def tearDown(self):
        self.client.CloseStage()

    def test_reads_both_units_from_the_single_status_dictionary(self):
        with patch.object(self.client, 'request', return_value=self.snapshot):
            self.assertEqual(self.client.GetStatus('X')['axes']['X']['positions']['counts'], 1000)
            self.assertEqual(self.client.GetStatus('Y')['axes']['Y']['positions']['mm'], .5)
            self.assertEqual(self.client.ConvertPosition('X', 1000, 'counts', 'mm'), 1)
            self.assertEqual(self.client.ConvertPosition('Y', 1000, 'counts', 'mm'), .5)
            with self.assertRaises(ValueError):
                self.client.ConvertPosition('X', 1, 'mm', 'deg')

    def test_absolute_and_relative_moves_use_each_mounts_calibration(self):
        with patch.object(self.client, 'GetStatus', return_value=self.snapshot), \
             patch.object(self.client, 'request', return_value=self.snapshot) as request:
            self.client.MoveAbs('X', 2500, units='counts', wait=False, timeout=1)
            self.assertEqual(request.call_args.args, ('absolute', 'X', 2.5))
            self.client.MoveRel('Y', 2.5, units='mm', wait=False, timeout=1)
            self.assertEqual(request.call_args.args, ('relative', 'Y', 5000))
            count = request.call_count
            for move in (self.client.MoveAbs, self.client.MoveRel):
                for target, unit in ((.5, 'counts'), (1, 'deg')):
                    with self.assertRaises(ValueError):
                        move('X', target, units=unit, wait=False, timeout=1)
            self.assertEqual(request.call_count, count)
