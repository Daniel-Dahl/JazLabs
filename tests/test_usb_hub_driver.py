import subprocess
import tempfile
from usb_hub_test_support import create_uhubctl_stub
import unittest
from unittest.mock import patch
from JazLabs.hardware.USBHub.USBHub_Driver import USBHubDriver as Controller, parse_status, discover_trees


class HubTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.controller = Controller(binary=create_uhubctl_stub(self.directory.name))
        self.output = self.controller._scan()

    def test_documented_topology_has_ten_leaf_endpoints(self):
        trees = discover_trees(parse_status(self.output))
        self.assertEqual(len(trees['20-1']), 10)
        self.assertNotIn(('20-1', 3), trees['20-1'])
        self.assertNotIn(('20-1', 4), trees['20-1'])

    def test_missing_chip_blocks_entire_tree(self):
        hubs = parse_status(self.output)
        del hubs['20-1.4']
        self.assertEqual(discover_trees(hubs), {})

    def test_ganged_or_unknown_hardware_is_blocked(self):
        self.assertEqual(discover_trees(parse_status(self.output.replace('ppps', 'ganged'))), {})
        self.assertEqual(discover_trees(parse_status(self.output.replace('0bda:0411', '1234:5678'))), {})

    def test_usb2_companion_can_be_discovered(self):
        self.assertIn('20-1', discover_trees(parse_status(self.output.replace('0bda:0411', '0bda:5411'))))

    def test_older_uhubctl_discovery_omits_capability_label(self):
        live = Controller('/trusted/uhubctl')
        with patch.object(live, '_run_uhubctl', return_value=self.output.replace(', ppps', '')) as run:
            self.assertEqual(len(discover_trees(parse_status(live._scan()))['20-1']), 10)
        run.assert_called_once_with([])

    def test_switch_and_readback(self):
        output = self.controller.SetPower(('20-1.3', 2), False, '0bda:0411')
        self.assertFalse(output['hubs']['20-1.3']['ports'][2]['on'])
        self.assertTrue(output['hubs']['20-1.3']['ports'][1]['on'])

    def test_internal_link_and_changed_identity_cannot_switch(self):
        with self.assertRaises(RuntimeError):
            self.controller.SetPower(('20-1', 3), False, '0bda:0411')
        with self.assertRaises(RuntimeError):
            self.controller.SetPower(('20-1', 1), False, '1234:5678')
        self.assertEqual(self.controller._scan(), self.output)

    def test_live_command_is_explicit_and_retains_companion_handling(self):
        live = Controller('/trusted/uhubctl')
        off = self.output.replace('0200 power connect [1234:5678 Test device]', '0000 off connect [1234:5678 Test device]', 1)
        with patch('JazLabs.hardware.USBHub.USBHub_Driver.platform.system', return_value='Darwin'), patch.object(live, '_run_uhubctl', side_effect=[self.output, '', off]) as run:
            live.SetPower(('20-1', 1), False, '0bda:0411')
        self.assertEqual(run.call_args_list[1].args[0], ['-l', '20-1', '-p', '1', '-a', 'off'])

    def test_linux5_repeats_off_but_not_on_or_linux6(self):
        for kernel, on, repeat in [('5.15.0-139-generic', False, True), ('5.15.0', True, False), ('6.8.0', False, False)]:
            with self.subTest(kernel=kernel, on=on):
                live = Controller('/trusted/uhubctl')
                readback = self.output if on else self.output.replace('power connect', 'off connect', 1)
                with patch('JazLabs.hardware.USBHub.USBHub_Driver.platform.system', return_value='Linux'), patch('JazLabs.hardware.USBHub.USBHub_Driver.platform.release', return_value=kernel), patch.object(live, '_run_uhubctl', side_effect=[self.output, '', readback]) as run:
                    live.SetPower(('20-1', 1), on, '0bda:0411')
                expected = ['-l', '20-1', '-p', '1', '-a', 'on' if on else 'off']
                if repeat:
                    expected += ['-r', '100']
                self.assertEqual(run.call_args_list[1].args[0], expected)

    def test_failed_readback_is_not_success(self):
        live = Controller('/trusted/uhubctl')
        with patch.object(live, '_run_uhubctl', side_effect=[self.output, '', self.output]):
            with self.assertRaisesRegex(RuntimeError, 'not confirmed'):
                live.SetPower(('20-1', 1), False, '0bda:0411')

    def test_timeout_and_permission_errors(self):
        live = Controller('/trusted/uhubctl')
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('uhubctl', 25)):
            with self.assertRaisesRegex(RuntimeError, 'timed out'):
                live._scan()
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'Access denied')):
            with self.assertRaisesRegex(RuntimeError, 'Access denied'):
                live._scan()

    def test_nested_external_hub_blocks_control(self):
        output = self.output.replace('power connect [1234:5678 Test device]', 'power connect [2222:3333 Other hub, ganged]', 1)
        self.assertEqual(discover_trees(parse_status(output)), {})


if __name__ == '__main__':
    unittest.main()
