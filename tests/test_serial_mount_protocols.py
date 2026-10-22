"""Protocol tests without attached hardware or optional pyserial installation."""
import builtins
import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'src/JazLabs/hardware/MotorisedStages'


class SerialPort:
    def __init__(self, **kwargs):
        self.settings = kwargs
        self.timeout = kwargs.get("timeout", .5)
        self.writes = []
        self.chunks = []
        self.is_open = True

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def write(self, data):
        self.writes.append(data)

    def read(self, size):
        return self.chunks.pop(0) if self.chunks else b''

    def read_until(self, terminator):
        return self.read(100)

    def reset_input_buffer(self):
        self.chunks.clear()

    def reset_output_buffer(self):
        pass

    def close(self):
        self.is_open = False


def load_driver(name, path):
    fake_serial = types.SimpleNamespace(Serial=SerialPort, EIGHTBITS=8,
                                        PARITY_NONE='N', STOPBITS_ONE=1)
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, serial=fake_serial):
        spec.loader.exec_module(module)
    return module


umc = load_driver('umc', 'Thorlabs/UMC2SerialStage.py')
agp = load_driver('agp', 'Newport/newport_agp_serial_stage.py')
agap = load_driver('agap', 'Newport/newport_agap_serial_stage.py')


def packet(message, source, payload):
    return struct.pack('<HHBB', message, len(payload), 0x81, source) + payload


class ProtocolTests(unittest.TestCase):
    def test_newport_package_has_only_serial_drivers_and_never_imports_visa(self):
        package_name = 'newport_serial_only_test'
        folder = ROOT / 'Newport'
        spec = importlib.util.spec_from_file_location(package_name, folder / '__init__.py',
                                                     submodule_search_locations=[str(folder)])
        package = importlib.util.module_from_spec(spec)
        fake_serial = types.SimpleNamespace(Serial=SerialPort, EIGHTBITS=8,
                                            PARITY_NONE='N', STOPBITS_ONE=1)
        original_import = builtins.__import__
        def reject_visa(name, *args, **kwargs):
            if name.startswith(('pyvisa', 'visa')):
                raise AssertionError('Newport must not import a VISA backend')
            return original_import(name, *args, **kwargs)
        with patch.dict(sys.modules, {package_name: package, 'serial': fake_serial}):
            with patch('builtins.__import__', side_effect=reject_visa):
                spec.loader.exec_module(package)
                self.assertEqual(set(package.__all__), {'Axes', 'NewportAGPSerialStage',
                                                       'NewportM100DSerialStage', 'NewportESP300'})
                stage = package.NewportESP300('COM5', axes=(1, 2))
                stage.MoveRel('2', -1.5, wait=False)
                self.assertEqual(stage.ser.writes[-1], b'2PR-1.5\r')
                self.assertEqual(stage.ser.settings['port'], 'COM5')
                self.assertTrue(stage.ser.settings['rtscts'])
                stage.CloseStage()
                self.assertFalse(stage.ser.is_open)
        self.assertEqual({path.name for path in folder.glob('*.py')},
                         {'__init__.py', 'newport_agp_serial_stage.py',
                          'newport_agap_serial_stage.py', 'newport_esp300.py'})

    def test_umc_bay_routing_and_signed_move(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        stage.serial.chunks = [packet(0x0494, 0x22, struct.pack('<HiiHhI', 1, 0, 0, 0, 0, 0))]
        stage.MoveRel('Y', -42)
        self.assertEqual(stage.serial.writes[-1], bytes.fromhex('48040600a2010100d6ffffff'))
        self.assertTrue(stage.serial.settings['rtscts'])

    def test_umc_fragmented_position_packets(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        first = packet(0x0412, 0x21, struct.pack('<Hi', 1, -123))
        second = packet(0x0412, 0x22, struct.pack('<Hi', 1, 456))
        stage.serial.chunks = [first[:3], b'', first[3:8], first[8:], second]
        self.assertEqual(stage.GetPositions(), [-123.0, 456.0])

    def test_umc_completion_matches_bay(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        stage.serial.chunks = [packet(0x0494, 0x21, struct.pack('<HiiHhI', 1, 0, 0, 0, 0, 0)),
                               packet(0x0464, 0x22, struct.pack('<H', 1)),
                               packet(0x0464, 0x21, struct.pack('<H', 1))]
        stage.MoveAbs('X', 123, wait=True)
        self.assertEqual(stage.serial.chunks, [])

    def test_umc_status_format(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        stage.serial.chunks = [packet(0x0494, 0x22, struct.pack('<HiiHhI', 1, 12, 10, 3, -5, 0x80000400))]
        status = stage.GetStatusBits('Y')
        self.assertEqual(status['encoder_position'], 10)
        self.assertEqual(status['motor_current_ma'], -5)
        self.assertTrue(status['homed'])

    def test_umc_timeout_and_invalid_count(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        with self.assertRaises(TimeoutError):
            stage._wait_response(0x0412, 0x21, 0.001)
        for value in (0.5, 2**31, float('nan')):
            with self.assertRaises(ValueError):
                stage.MoveAbs(0, value)

    def test_umc_detects_separate_mount_calibrations_and_converts_units(self):
        port = SerialPort(timeout=.01)
        first = struct.pack('<HHH16sIIiiiii4H4I', 1, 0x1000, 0,
                            b'MLS203-X', 12345, 1000, -1000, 25000, 10, 10, 20,
                            *([0] * 8))
        second = struct.pack('<HHH16sIIiiiii4H4I', 1, 0x1100, 1,
                             b'MLS203-Y', 12345, 2000, 0, 50000, 15, 15, 30,
                             *([0] * 8))
        port.chunks = [packet(0x04F2, 0x21, first), packet(0x04F2, 0x22, second)]
        with patch.object(umc.serial, 'Serial', return_value=port):
            stage = umc.UMC2SerialStage('fake', mounts={
                'X': {'physical_units': 'mm', 'label': 'Focus'},
                'Y': {'physical_units': 'mm', 'label': 'Translation'}})
        x, y = stage.GetMotionCapabilities()
        self.assertEqual((x['label'], y['label']), ('Focus', 'Translation'))
        self.assertTrue(x['independent_mount'])
        self.assertEqual(x['stage']['part_number'], 'MLS203-X')
        self.assertEqual(x['limits_by_unit'], {'counts': [-1000, 25000], 'mm': [-1, 25]})
        self.assertEqual(y['unit_scales']['mm'], 2000)
        self.assertEqual(y['maximum'], 25)
        self.assertEqual(stage.ConvertPosition('X', 1000, 'counts', 'mm'), 1)
        self.assertEqual(stage.ConvertPosition('Y', 1000, 'counts', 'mm'), .5)
        # Detection must only read stage parameters, not change settings or move.
        self.assertEqual([struct.unpack_from('<H', data)[0] for data in port.writes],
                         [0x0012, 0x046C, 0x0012, 0x046C, 0x04F1, 0x04F1])
        stage.MoveTo('Y', 1, units='mm', wait=False)
        self.assertEqual(struct.unpack_from('<i', port.writes[-1], 8)[0], 2000)
        stage.MoveTo('X', 123, units='counts', wait=False)
        self.assertEqual(struct.unpack_from('<i', port.writes[-1], 8)[0], 123)
        with self.assertRaises(ValueError):
            stage.MoveTo('X', 26000, units='counts', wait=False)
        port.chunks = [packet(0x0494, 0x22, struct.pack('<HiiHhI', 1, 1000, 1000, 0, 0, 0x80000400))]
        status = stage.GetAxisStatus('Y')
        self.assertEqual(status['positions'], {'counts': 1000, 'mm': .5})

    def test_umc_missing_detection_keeps_counts_and_rejects_unavailable_mm(self):
        stage = umc.UMC2SerialStage('fake', timeout=.001,
                                  mounts={'X': {'physical_units': 'mm'}})
        spec = stage.GetMotionCapabilities()[0]
        self.assertEqual(spec['unit_scales'], {'counts': 1})
        self.assertIn('Stage detection unavailable', spec['calibration_note'])
        self.assertIsNone(spec['minimum'])
        with self.assertRaises(ValueError):
            stage.MoveTo('X', 1, units='mm', wait=False)

    def test_umc_explicit_calibration_and_narrowed_limits_work_without_detection(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, mounts={
            'X': {'counts_per_mm': 1000, 'limits_mm': [0, 13], 'step': .1}})
        spec = stage.GetMotionCapabilities()[0]
        self.assertEqual((spec['units'], spec['maximum'], spec['step']), ('mm', 13, .1))
        self.assertEqual(spec['limits_by_unit']['counts'], [0, 13000])
        self.assertEqual(stage.GetMotionCapabilities()[1]['units'], 'counts')
        for scale in (0, -1, float('nan')):
            with self.assertRaises(ValueError):
                umc.UMC2SerialStage('fake', detect_stages=False, mounts={'X': {'counts_per_mm': scale}})

    def test_umc_does_not_infer_mm_from_counts_per_unit_alone(self):
        port = SerialPort(timeout=.001)
        data = struct.pack('<HHH16sIIiiiii4H4I', 1, 1, 0, b'UNKNOWN', 1, 1000,
                           0, 10000, 1, 1, 1, *([0] * 8))
        port.chunks = [packet(0x04F2, 0x21, data), packet(0x04F2, 0x22, data)]
        with patch.object(umc.serial, 'Serial', return_value=port):
            stage = umc.UMC2SerialStage('fake')
        spec = stage.GetMotionCapabilities()[0]
        self.assertEqual(spec['units'], 'counts')
        self.assertNotIn('mm', spec['unit_scales'])
        self.assertEqual(spec['maximum'], 10000)

    def test_agap_wire_commands_and_enum(self):
        stage = agap.NewportM100DSerialStage('fake')
        stage.serial.chunks = [b'1TE@\r\n']
        stage.MoveAbs(agap.Axes.YAW, -0.25, wait=False)
        self.assertEqual(stage.serial.writes, [b'1PAU-0.25\r\n', b'1TE\r\n'])
        self.assertTrue(stage.serial.settings['xonxoff'])
        self.assertEqual(stage.serial.settings['baudrate'], 921600)

    def test_agp_position_and_homing(self):
        stage = agp.NewportAGPSerialStage('fake')
        stage.serial.chunks = [b'1TP1.25\r\n']
        self.assertEqual(stage.GetPositions(), [1.25])
        stage.serial.chunks = [b'1TS00000A\r\n', b'1TE@\r\n', b'1TS00001E\r\n', b'1TS000032\r\n']
        stage.HomeAll()
        self.assertIn(b'1OR\r\n', stage.serial.writes)

    def test_agp_home_already_referenced_sends_no_home_command(self):
        stage = agp.NewportAGPSerialStage('fake')
        stage.serial.chunks = [b'1TS000032\r\n']
        stage.HomeAxis('X')
        self.assertEqual(stage.serial.writes, [b'1TS\r\n'])
        self.assertFalse(stage.GetMotionCapabilities()[0]['home_when_referenced'])

    def test_agp_idle_stop_consumes_rejection_before_next_move(self):
        stage = agp.NewportAGPSerialStage('fake')
        stage.serial.chunks = [b'1TEK\r\n', b'1TS000032\r\n', b'1TE@\r\n']
        stage.StopAll()
        stage.MoveAbs('X', 1.25, wait=False)
        self.assertEqual(stage.serial.writes,
                         [b'1ST\r\n', b'1TE\r\n', b'1TS\r\n', b'1PA1.25\r\n', b'1TE\r\n'])

    def test_agp_stop_sends_immediately_and_checks_acceptance(self):
        stage = agp.NewportAGPSerialStage('fake')
        stage.serial.chunks = [b'1TE@\r\n']
        stage.StopAll()
        self.assertEqual(stage.serial.writes, [b'1ST\r\n', b'1TE\r\n'])

    def test_agp_rejected_stop_does_not_hide_motion_or_hardware_fault(self):
        for response in (b'1TS000028\r\n', b'1TS002032\r\n'):
            with self.subTest(response=response):
                stage = agp.NewportAGPSerialStage('fake')
                stage.serial.chunks = [b'1TEK\r\n', response]
                with self.assertRaises(RuntimeError):
                    stage.StopAll()

    def test_agap_positions(self):
        stage = agap.NewportM100DSerialStage('fake')
        stage.serial.chunks = [b'1TPU0.2\r\n', b'1TPV-0.3\r\n']
        self.assertEqual(stage.GetPositions(), {'U': 0.2, 'V': -0.3})
        with self.assertRaises(NotImplementedError):
            stage.HomeAll()

    def test_newport_disabled_and_fault_are_not_ready(self):
        stage = agap.NewportM100DSerialStage('fake')
        for response in (b'1TS00003C\r\n', b'1TS002032\r\n'):
            stage.serial.chunks = [response]
            with self.assertRaises(RuntimeError):
                stage.is_ready()

    def test_newport_rejected_command_and_bad_reply(self):
        stage = agp.NewportAGPSerialStage('fake')
        stage.serial.chunks = [b'1TEH\r\n']
        with self.assertRaises(RuntimeError):
            stage.MoveRel(0, 1)
        stage.serial.chunks = [b'2TP0\r\n']
        with self.assertRaises(RuntimeError):
            stage.GetPositions()
        stage.serial.chunks = [b'1TP0']
        with self.assertRaises(TimeoutError):
            stage.GetPositions()
        stage.CloseStage()
        self.assertFalse(stage.serial.is_open)


if __name__ == '__main__':
    unittest.main()
