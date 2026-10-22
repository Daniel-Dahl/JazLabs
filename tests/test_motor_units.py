"""Unit selection uses driver calibration, including different mount scales."""
import unittest
from unittest.mock import patch

from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient


class ClientUnitsTests(unittest.TestCase):
    def setUp(self):
        self.client = MotorisedStageClient()
        self.snapshot = {
            'connected': True,
            'capabilities': [
                {'id': 'X', 'units': 'mm', 'unit_scales': {'counts': 1, 'mm': 1000}},
                {'id': 'Y', 'units': 'counts', 'unit_scales': {'counts': 1, 'mm': 2000}}],
            'axes': {
                'X': {'position': 1, 'positions': {'counts': 1000, 'mm': 1}, 'age': 0},
                'Y': {'position': 1000, 'positions': {'counts': 1000, 'mm': .5}, 'age': 0}}}

    def tearDown(self):
        self.client.close()

    def test_reads_both_units_without_confusing_different_mount_calibrations(self):
        with patch.object(self.client, 'request', return_value=self.snapshot):
            self.assertEqual(self.client.GetPosition('X', units='counts'), 1000)
            self.assertEqual(self.client.GetPosition('Y', units='mm'), .5)
            self.assertEqual(self.client.GetPositions(units='mm'), {'X': 1, 'Y': .5})
            self.assertEqual(self.client.GetPositions(), {'X': 1, 'Y': 1000})
            with self.assertRaises(ValueError):
                self.client.GetPosition('X', units='deg')

    def test_move_converts_requested_units_to_each_mounts_server_units(self):
        with patch.object(self.client, 'GetMotionCapabilities', return_value=self.snapshot['capabilities']), \
             patch.object(self.client, 'request', return_value=self.snapshot) as request:
            self.client.MoveTo('X', 2500, units='counts', wait=False, timeout=1)
            self.assertEqual(request.call_args.args, ('absolute', 'X', 2.5))
            self.client.MoveTo('Y', 2.5, units='mm', wait=False, timeout=1)
            self.assertEqual(request.call_args.args, ('absolute', 'Y', 5000))
            count = request.call_count
            for target, unit in ((.5, 'counts'), (1, 'deg')):
                with self.assertRaises(ValueError):
                    self.client.MoveTo('X', target, units=unit, wait=False, timeout=1)
            self.assertEqual(request.call_count, count)
