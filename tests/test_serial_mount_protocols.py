"""Protocol tests without attached hardware or optional pyserial installation."""
import builtins
import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / 'src/JazLabs/hardware/MotorisedStages'


class SerialPort:
    def __init__(self, **kwargs):
        self.settings = kwargs
        self.timeout = kwargs.get("timeout", .5)
        self.writes = []
        self.chunks = []
        self.is_open = True
        self.auto_apt = False
        self.apt_positions = {}

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks else 0

    def write(self, data):
        self.writes.append(data)
        if self.auto_apt:
            message = struct.unpack_from('<H', data)[0]
            destination = data[4] & 0x7f
            position = self.apt_positions.get(destination, 0)
            if message == 0x0493:
                self.chunks.append(packet(0x0494, destination,
                    struct.pack('<HiiHhI', 1, position, position, 0, 0, 0x80000400)))
            elif message == 0x0411:
                self.chunks.append(packet(0x0412, destination, struct.pack('<Hi', 1, position)))
            elif message == 0x0429:
                self.chunks.append(packet(0x042A, destination, struct.pack('<HI', 1, 0x80000400)))
            elif message == 0x0453:
                self.apt_positions[destination] = struct.unpack_from('<i', data, 8)[0]

    def read(self, size):
        return self.chunks.pop(0) if self.chunks else b''

    def read_until(self, terminator):
        return self.read(100)

    def readline(self):
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
    with patch.dict(sys.modules, {'serial': fake_serial, name: module}):
        spec.loader.exec_module(module)
    return module


umc = load_driver('umc', 'Thorlabs/UMC2SerialStage.py')
kst = load_driver('kst', 'Thorlabs/KST201SerialStage.py')
bsc = load_driver('bsc', 'Thorlabs/BSC203SerialStage.py')
kdc = load_driver('kdc', 'Thorlabs/KDC101SerialStage.py')
agp = load_driver('agp', 'Newport/newport_agp_serial_stage.py')
agap = load_driver('agap', 'Newport/newport_agap_serial_stage.py')
esp300 = load_driver('esp300', 'Newport/newport_esp300.py')


def packet(message, source, payload):
    return struct.pack('<HHBB', message, len(payload), 0x81, source) + payload


def read_all_thorlabs_status(stage):
    stage.serial.auto_apt = True
    return list(stage.GetStatus()["axes"].values())


class ProtocolTests(unittest.TestCase):
    def test_all_thorlabs_reply_timeouts_use_performance_counter(self):
        for driver in (umc.UMC2SerialStage, kst.KST201SerialStage,
                       bsc.BSC203SerialStage, kdc.KDC101SerialStage):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake', **({'detect_stages': False} if driver is umc.UMC2SerialStage else {}))
                clock = types.SimpleNamespace(perf_counter=Mock(side_effect=[10, 10, 11]))
                with patch.object({'umc': umc, 'kst': kst, 'bsc': bsc, 'kdc': kdc}[driver.__module__], 'time', clock):
                    with self.assertRaises(TimeoutError):
                        stage.query(0x0411, 0x0412, 0x21, timeout=.5)
                stage.CloseStage()

    def test_each_thorlabs_driver_is_self_contained(self):
        for driver in (umc.UMC2SerialStage, kst.KST201SerialStage,
                       bsc.BSC203SerialStage, kdc.KDC101SerialStage):
            with self.subTest(driver=driver.__name__):
                self.assertEqual(driver.__bases__, (object,))
                for name in ('write', 'query', 'GetStatus', 'MoveAbs', 'MoveRel', 'HomeAxis', 'StopAll'):
                    self.assertIn(name, driver.__dict__)
        self.assertFalse((ROOT / 'Thorlabs' / 'apt_serial_motion.py').exists())

    def test_each_thorlabs_driver_preserves_fragmented_feedback(self):
        for driver, axis, destination in ((umc.UMC2SerialStage, 'X', 0x21),
                (kst.KST201SerialStage, 'X', 0x50), (bsc.BSC203SerialStage, 'Z', 0x21),
                (kdc.KDC101SerialStage, 'X', 0x50)):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake', **({'detect_stages': False} if driver is umc.UMC2SerialStage else {}))
                if driver is umc.UMC2SerialStage:
                    reply = packet(0x0494, destination, struct.pack('<HiiHhI', 1, 123, 123, 0, 0, 0x80000400))
                else:
                    reply = packet(0x0412, destination, struct.pack('<Hi', 1, 123))
                    reply += packet(0x042A, destination, struct.pack('<HI', 1, 0x80000400))
                stage.serial.chunks = [reply[:2], b'', reply[2:7], reply[7:]]
                status = stage.GetStatus(axis)['axes'][axis]
                self.assertEqual(status['positions']['counts'], 123)
                self.assertTrue(status['enabled'])
                self.assertTrue(status['homed'])
                stage.CloseStage()

    def test_each_thorlabs_move_and_home_timeout_stops_using_performance_counter(self):
        for driver, module, axis in ((umc.UMC2SerialStage, umc, 'X'),
                (kst.KST201SerialStage, kst, 'X'), (bsc.BSC203SerialStage, bsc, 'Z'),
                (kdc.KDC101SerialStage, kdc, 'X')):
            for operation in ('move', 'home'):
                with self.subTest(driver=driver.__name__, operation=operation):
                    stage = driver('fake', limits={axis: [1, 10]},
                        **({'detect_stages': False} if driver is umc.UMC2SerialStage else {}))
                    status = {'fault': None, 'enabled': True, 'homed': operation == 'move',
                              'moving': False, 'homing': False, 'position': 1}
                    clock = types.SimpleNamespace(perf_counter=Mock(side_effect=[10, 10, 11]))
                    with patch.object(module, 'time', clock), patch.object(stage, 'GetStatus', return_value={'axes': {axis: status}}):
                        with self.assertRaisesRegex(TimeoutError, 'did not finish'):
                            if operation == 'move':
                                stage.MoveAbs(axis, 5, timeout=.5)
                            else:
                                stage.HomeAxis(axis, timeout=.5)
                    stops = [data for data in stage.serial.writes if struct.unpack_from('<H', data)[0] == 0x0465]
                    self.assertEqual([data[4] for data in stops], list(stage._axis_destinations.values()))
                    stage.CloseStage()

    def test_thorlabs_query_matches_reply_id_and_bay_and_reports_controller_errors(self):
        for driver in (umc.UMC2SerialStage, kst.KST201SerialStage,
                       bsc.BSC203SerialStage, kdc.KDC101SerialStage):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake', **({'detect_stages': False} if driver is umc.UMC2SerialStage else {}))
                destination = next(iter(stage._axis_destinations.values()))
                expected = struct.pack('<Hi', 1, 123)
                stage.serial.chunks = [packet(0x0464, destination, struct.pack('<H', 1)),
                    packet(0x0412, destination + 1, struct.pack('<Hi', 1, 999)),
                    packet(0x0412, destination, expected)]
                self.assertEqual(stage.query(0x0411, 0x0412, destination), expected)
                self.assertEqual(stage.serial.writes[-1], struct.pack('<HBBBB', 0x0411, 1, 0, destination, 1))
                stage.serial.chunks = [packet(0x0081, destination, b'error')]
                with self.assertRaisesRegex(RuntimeError, 'APT controller error'):
                    stage.query(0x0411, 0x0412, destination)
                self.assertFalse(hasattr(stage, '_read_response'))
                stage.CloseStage()

    def test_kst_identifies_supplied_profiles_and_applies_mount_limits_before_connecting(self):
        actuator = kst.ActuatorProfile('Custom actuator', 0x41, 8, 1000)
        mount = kst.MountProfile('Custom mount', ('Custom actuator',), (('PITCH', -1, 1),))
        stage = kst.KST201SerialStage('fake', actuator=actuator, mount=mount, mount_axis='pitch',
            minimum_mm=1, maximum_mm=7, safety_margin_mm=.2, limits={'PITCH': [2, 6]})
        stage.serial.auto_apt = True
        status = stage.GetStatus()
        self.assertEqual(status['actuator'], 'Custom actuator')
        self.assertEqual(status['mount_axis'], 'PITCH')
        self.assertEqual(status['axes']['PITCH']['limits'], [2, 6])
        self.assertEqual(status['axes']['PITCH']['unit_scales']['mm'], 1000)
        self.assertEqual((stage.minimum_mm, stage.maximum_mm), (1.2, 6.8))
        self.assertIn(struct.pack('<HBBBB', 0x04FE, 0x41, 0, 0x50, 1), stage.serial.writes)
        stage.MoveAbs('PITCH', 3000, units='counts', wait=False)
        self.assertEqual(struct.unpack_from('<i', stage.serial.writes[-1], 8)[0], 3000)
        stage.CloseStage()
        for options in ({'actuator': 'unknown'}, {'mount': 'unknown'}, {'mount_axis': 'PITCH'},
                {'mount': 'PY004/M'}, {'mount': 'PY004/M', 'mount_axis': 'invalid'},
                {'mount': mount}, {'minimum_mm': -1}, {'maximum_mm': 14},
                {'safety_margin_mm': float('nan')}, {'safety_margin_mm': 7},
                {'limits': {'X': [0, 13]}}, {'limits': {'Y': [1, 10]}}):
            with self.subTest(options=options), patch.object(kst.serial, 'Serial') as connect:
                with self.assertRaises(ValueError):
                    kst.KST201SerialStage('fake', **options)
                connect.assert_not_called()

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
                stage = package.NewportESP300('COM5', axes=(1, 2), limits={2: [0, 10]})
                stage.ser.chunks = [b'1\r\n', b'2\r\n', b'0\r\n', b'0\r\n']
                stage.MoveRel('2', -1.5, wait=False)
                self.assertIn(b'2PA0.5\r', stage.ser.writes)
                self.assertEqual(stage.ser.writes[-1], b'TE?\r')
                self.assertEqual(stage.ser.settings['port'], 'COM5')
                self.assertTrue(stage.ser.settings['rtscts'])
                stage.CloseStage()
                self.assertFalse(stage.ser.is_open)
        self.assertEqual({path.name for path in folder.glob('*.py')},
                         {'__init__.py', 'newport_agp_serial_stage.py',
                          'newport_agap_serial_stage.py', 'newport_esp300.py'})

    def test_umc_bay_routing_and_signed_move(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'Y': [-100, 100]})
        stage.serial.auto_apt = True
        stage.MoveRel('Y', -42, wait=False)
        self.assertEqual(stage.serial.writes[-1], bytes.fromhex('53040600a2010100d6ffffff'))
        self.assertTrue(stage.serial.settings['rtscts'])

    def test_umc_fragmented_status_packets(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        first = packet(0x0494, 0x21, struct.pack('<HiiHhI', 1, -123, -123, 0, 0, 0x80000400))
        second = packet(0x0494, 0x22, struct.pack('<HiiHhI', 1, 456, 456, 0, 0, 0x80000400))
        stage.serial.chunks = [first[:3], b'', first[3:8], first[8:], second]
        status = stage.GetStatus()
        self.assertEqual([info['position'] for info in status['axes'].values()], [-123, 456])

    def test_umc_move_waits_for_correct_bay_position_not_completion_alone(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'X': [0, 1000]})
        def feedback(source, position, flags=0x80000400):
            return packet(0x0494, source, struct.pack('<HiiHhI', 1, position, position, 0, 0, flags))
        stage.serial.chunks = [feedback(0x21, 0),
                               packet(0x0464, 0x22, struct.pack('<H', 1)),
                               feedback(0x22, 123), feedback(0x21, 100, 0xA0000400),
                               feedback(0x21, 123)]
        result = stage.MoveAbs('X', 123)
        self.assertEqual(result['position'], 123)
        self.assertFalse(result['moving'])
        self.assertEqual(stage.serial.chunks, [])

    def test_umc_status_format(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        stage.serial.chunks = [packet(0x0494, 0x22, struct.pack('<HiiHhI', 1, 12, 10, 3, -5, 0x80000400))]
        status = stage.GetStatus('Y')['axes']['Y']
        self.assertEqual(status['encoder_position'], 10)
        self.assertEqual(status['motor_current_ma'], -5)
        self.assertEqual(status['velocity_counts_per_cycle'], 3)
        self.assertTrue(status['homed'])

    def test_umc_active_command_is_busy_even_after_direction_bits_clear(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'X': [0, 1000]})
        for flags in (0xA0000400, 0x80000C00):
            with self.subTest(flags=flags):
                stage.serial.chunks = [packet(0x0494, 0x21, struct.pack('<HiiHhI', 1, 100, 100, 0, 0, flags))]
                with self.assertRaisesRegex(RuntimeError, 'Wait for this axis'):
                    stage.MoveAbs('X', 200, wait=False)
                self.assertNotIn(0x0453, [struct.unpack_from('<H', data)[0] for data in stage.serial.writes])

    def test_umc_timeout_and_invalid_count(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'X': [-2**31, 2**31-1]})
        with self.assertRaises(TimeoutError):
            stage.query(0x0411, 0x0412, 0x21, timeout=.001)
        for value in (0.5, 2**31, float('nan')):
            with self.assertRaises(ValueError):
                stage.MoveAbs('X', value)

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
        # Detection must only read stage parameters, not change settings or move.
        self.assertEqual([struct.unpack_from('<H', data)[0] for data in port.writes],
                         [0x0012, 0x046C, 0x0012, 0x046C, 0x04F1, 0x04F1])
        x, y = read_all_thorlabs_status(stage)
        self.assertEqual((x['label'], y['label']), ('Focus', 'Translation'))
        self.assertTrue(x['independent_mount'])
        self.assertEqual(x['stage']['part_number'], 'MLS203-X')
        self.assertEqual(x['limits_by_unit'], {'counts': [-1000, 25000], 'mm': [-1, 25]})
        self.assertEqual(y['unit_scales']['mm'], 2000)
        self.assertEqual(y['limits'][1], 25)
        self.assertEqual(stage.ConvertPosition('X', 1000, 'counts', 'mm'), 1)
        self.assertEqual(stage.ConvertPosition('Y', 1000, 'counts', 'mm'), .5)
        stage.MoveAbs('Y', 1, units='mm', wait=False)
        self.assertEqual(struct.unpack_from('<i', port.writes[-1], 8)[0], 2000)
        stage.MoveAbs('X', 123, units='counts', wait=False)
        self.assertEqual(struct.unpack_from('<i', port.writes[-1], 8)[0], 123)
        with self.assertRaises(ValueError):
            stage.MoveAbs('X', 26000, units='counts', wait=False)
        port.auto_apt = False
        port.chunks = [packet(0x0494, 0x22, struct.pack('<HiiHhI', 1, 1000, 1000, 0, 0, 0x80000400))]
        status = stage.GetStatus('Y')['axes']['Y']
        self.assertEqual(status['positions'], {'counts': 1000, 'mm': .5})

    def test_umc_stepper_position_scale_enables_mm_without_encoder_calibration(self):
        port = SerialPort(timeout=.01)
        # XA's current 72-byte StageAxisParams follows the channel word.
        # Deliberately use distinct scales to catch reading countsPerUnit,
        # velocityScale, or a hard-coded scale for every mount.
        first = struct.pack('<HHH16sIIiiIIIHHfff8s', 1, 1, 1, b'DRV250',
                            12345, 0, 0, 50000, 10, 10, 20,
                            1, 2048, 1000, 2000, 3000, b'')
        second = struct.pack('<HHH16sIIiiIIIHHfff8s', 1, 2, 1, b'NRT100/M',
                             67890, 0, 0, 200000, 10, 10, 20,
                             1, 2048, 2000, 4000, 6000, b'')
        port.chunks = [packet(0x04F2, 0x21, first), packet(0x04F2, 0x22, second)]
        with patch.object(umc.serial, 'Serial', return_value=port):
            stage = umc.UMC2SerialStage('fake')
        x, y = read_all_thorlabs_status(stage)
        self.assertEqual((x['units'], y['units']), ('mm', 'mm'))
        self.assertEqual((x['limits'][1], y['limits'][1]), (50, 100))
        self.assertEqual((x['unit_scales']['mm'], y['unit_scales']['mm']), (1000, 2000))
        self.assertEqual(x['stage']['counts_per_unit'], 0)
        self.assertEqual(x['stage']['microsteps'], 2048)
        self.assertIn('positionScale', x['calibration_note'])
        stage.MoveAbs('X', .01, units='mm', wait=False)
        self.assertEqual(struct.unpack_from('<i', port.writes[-1], 8)[0], 10)
        stage.MoveAbs('Y', .01, units='mm', wait=False)
        self.assertEqual(struct.unpack_from('<i', port.writes[-1], 8)[0], 20)
        with self.assertRaises(ValueError):
            stage.MoveAbs('X', 50.01, units='mm', wait=False)

    def test_umc_position_scale_override_and_invalid_scale_fallback(self):
        for reported_scale in (0, -1, float('nan'), float('inf'), 2000):
            with self.subTest(position_scale=reported_scale):
                data = struct.pack('<HHH16sIIiiIIIHHfff8s', 1, 1, 1, b'DRV250',
                                   1, 0, 0, 50000, 1, 1, 1,
                                   1, 2048, reported_scale, 0, 0, b'')
                port = SerialPort(timeout=.01)
                port.chunks = [packet(0x04F2, 0x21, data), packet(0x04F2, 0x22, data)]
                with patch.object(umc.serial, 'Serial', return_value=port):
                    stage = umc.UMC2SerialStage('fake', mounts={
                        'X': {'counts_per_mm': 1000, 'limits_mm': [1, 40]}})
                x, y = read_all_thorlabs_status(stage)
                self.assertEqual((x['limits'][0], x['limits'][1]), (1, 40))
                self.assertEqual(x['unit_scales']['mm'], 1000)
                self.assertEqual(y['units'], 'mm' if reported_scale == 2000 else 'counts')
                if reported_scale == 2000:
                    self.assertEqual(y['limits'][1], 25)  # Never widen detected travel to 50 mm.

    def test_umc_missing_detection_keeps_counts_and_rejects_unavailable_mm(self):
        stage = umc.UMC2SerialStage('fake', timeout=.001,
                                  mounts={'X': {'physical_units': 'mm'}})
        spec = read_all_thorlabs_status(stage)[0]
        self.assertEqual(spec['unit_scales'], {'counts': 1})
        self.assertIn('Stage detection unavailable', spec['calibration_note'])
        self.assertIsNone(spec['limits'][0])
        with self.assertRaises(ValueError):
            stage.MoveAbs('X', 1, units='mm', wait=False)

    def test_umc_explicit_calibration_and_narrowed_limits_work_without_detection(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, mounts={
            'X': {'counts_per_mm': 1000, 'limits_mm': [0, 13], 'step': .1}})
        spec = read_all_thorlabs_status(stage)[0]
        self.assertEqual((spec['units'], spec['limits'][1], spec['step']), ('mm', 13, .1))
        self.assertEqual(spec['limits_by_unit']['counts'], [0, 13000])
        self.assertEqual(read_all_thorlabs_status(stage)[1]['units'], 'counts')
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
        spec = read_all_thorlabs_status(stage)[0]
        self.assertEqual(spec['units'], 'counts')
        self.assertNotIn('mm', spec['unit_scales'])
        self.assertEqual(spec['limits'][1], 10000)

    def test_thorlabs_direct_moves_require_limits_and_all_nominal_bounds_before_moving(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'X': [0, 100]})
        stage.serial.auto_apt = True
        stage.MoveAbs('X', 10)
        stage.serial.writes.clear()
        with self.assertRaisesRegex(ValueError, 'configure travel limits'):
            stage.MoveAbs('Y', 10, wait=False)
        with self.assertRaisesRegex(ValueError, 'configure travel limits'):
            stage.SetNominal()
        self.assertEqual(stage.serial.writes, [])

    def test_thorlabs_relative_moves_obey_limits_and_nominal_uses_midpoints(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False,
                                  limits={'X': [-50, 100], 'Y': [100, 201]})
        stage.serial.auto_apt = True
        stage.serial.apt_positions = {0x21: 90, 0x22: 150}
        with self.assertRaisesRegex(ValueError, 'outside'):
            stage.MoveRel('X', 20, wait=False)
        self.assertNotIn(0x0453, [struct.unpack_from('<H', data)[0] for data in stage.serial.writes])
        stage.SetNominal()
        self.assertEqual(stage.serial.apt_positions, {0x21: 25, 0x22: 150})

    def test_thorlabs_move_failure_stops_all_bays(self):
        for flags, message in ((0x400, 'disabled'), (0xC0000400, 'APT fault'), (0x80000000, 'home reference')):
            with self.subTest(flags=flags):
                stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'X': [0, 1000]})
                stage.serial.chunks = [packet(0x0494, 0x21, struct.pack('<HiiHhI', 1, 0, 0, 0, 0, 0x80000400)),
                                       packet(0x0494, 0x21, struct.pack('<HiiHhI', 1, 123, 123, 0, 0, flags))]
                with self.assertRaisesRegex(RuntimeError, message):
                    stage.MoveAbs('X', 123)
                self.assertEqual(stage.serial.writes[-2:], [struct.pack('<HBBBB', 0x0465, 1, 1, bay, 1)
                                                           for bay in (0x21, 0x22)])

    def test_thorlabs_home_waits_until_stopped_and_referenced(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False)
        stage.serial.chunks = [packet(0x0494, 0x21, struct.pack('<HiiHhI', 1, 20, 20, 0, 0, flags))
                               for flags in (0x80000000, 0x80000200, 0x80000400)]
        result = stage.HomeAxis('X')
        self.assertTrue(result['homed'])
        self.assertFalse(result['homing'])
        self.assertFalse(result['moving'])
        self.assertIn(struct.pack('<HBBBB', 0x0443, 1, 0, 0x21, 1), stage.serial.writes)

    def test_kst_uses_mm_and_keeps_profile_limits_and_metadata(self):
        stage = kst.KST201SerialStage('fake', mount='PY004/M', mount_axis='PITCH',
                                    minimum_mm=2, maximum_mm=10, limits={'PITCH': [3, 8]})
        stage.serial.auto_apt = True
        status = stage.GetStatus()
        self.assertEqual(status['actuator'], 'ZFS13B')
        self.assertEqual(status['mount_angle_range_deg'], (-2.5, 2.5))
        self.assertEqual(status['axes']['PITCH']['limits'], [3, 8])
        self.assertEqual(status['axes']['PITCH']['units'], 'mm')
        stage.MoveAbs('PITCH', 4, wait=False)
        self.assertEqual(struct.unpack_from('<i', stage.serial.writes[-1], 8)[0], stage.actuator.mm_to_counts(4))
        with self.assertRaisesRegex(ValueError, 'cannot widen'):
            kst.KST201SerialStage('fake', limits={'X': [0, 13]})

    def test_bsc_and_kdc_routes_calibrations_and_single_public_status_api(self):
        stages = [bsc.BSC203SerialStage('fake', slots=(2, 0), units='mm',
                    counts_per_mm={'Z': 1000, 'X': 2000}, limits={'Z': [0, 10], 'X': [0, 20]}),
                  kdc.KDC101SerialStage('fake', units='mm', counts_per_mm=1000, limits={'X': [0, 10]}),
                  umc.UMC2SerialStage('fake', detect_stages=False), kst.KST201SerialStage('fake')]
        for stage in stages:
            stage.serial.auto_apt = True
            status = stage.GetStatus()
            self.assertTrue(status['axes'])
            for removed in ('MoveTo', 'GetPositions', 'GetPositionsMM', 'GetAxisStatus', 'GetStatusBits',
                            'GetProperties', 'GetMotionCapabilities', 'MoveAbsMM', 'MoveRelMM', 'ReadStageParameters'):
                self.assertFalse(hasattr(stage, removed), f'{stage.controller}: {removed}')
        stages[0].MoveAbs('Z', 1, wait=False)
        self.assertEqual(stages[0].serial.writes[-1], struct.pack('<HHBBHi', 0x0453, 6, 0xA3, 1, 1, 1000))
        stages[0].MoveAbs('X', 1, wait=False)
        self.assertEqual(stages[0].serial.writes[-1], struct.pack('<HHBBHi', 0x0453, 6, 0xA1, 1, 1, 2000))
        stages[1].MoveAbs('X', 1000, units='counts', wait=False)
        self.assertEqual(stages[1].serial.writes[-1], struct.pack('<HHBBHi', 0x0453, 6, 0xD0, 1, 1, 1000))

    def test_server_passes_narrowed_limits_into_every_thorlabs_driver(self):
        from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import create_motorised_stage
        cases = [('UMC2Serial', umc, 'UMC2SerialStage', 'X', {'detect_stages': False}),
                 ('KDC101Serial', kdc, 'KDC101SerialStage', 'X', {}),
                 ('KST201Serial', kst, 'KST201SerialStage', 'X', {}),
                 ('BSC203Serial', bsc, 'BSC203SerialStage', 'Z', {})]
        for stage_type, module, module_name, axis, options in cases:
            with self.subTest(stage_type=stage_type):
                module_path = f'JazLabs.hardware.MotorisedStages.Thorlabs.{module_name}'
                with patch.dict(sys.modules, {module_path: module}):
                    stage = create_motorised_stage(stage_type,
                        {'port': 'fake', 'limits': {axis: [1, 10]}, **options}, {axis: [2, 5]})
                    with self.assertRaisesRegex(ValueError, 'outside'):
                        stage.MoveAbs(axis, 6, wait=False)
                    self.assertEqual(stage._limits[axis], (2, 5))
                    with self.assertRaisesRegex(ValueError, 'cannot widen'):
                        create_motorised_stage(stage_type,
                            {'port': 'fake', 'limits': {axis: [2, 5]}, **options}, {axis: [1, 10]})

    def test_thorlabs_partial_move_write_failure_requests_stop_even_without_wait(self):
        stage = umc.UMC2SerialStage('fake', detect_stages=False, limits={'X': [0, 100]})
        stage.serial.auto_apt = True
        original_write = stage.serial.write
        def fail_move_write(data):
            if struct.unpack_from('<H', data)[0] == 0x0453:
                raise OSError('Serial write timed out')
            original_write(data)
        stage.serial.write = fail_move_write
        with self.assertRaisesRegex(OSError, 'Serial write timed out'):
            stage.MoveAbs('X', 50, wait=False)
        self.assertEqual(stage.serial.writes[-2:], [struct.pack('<HBBBB', 0x0465, 1, 1, bay, 1)
                                                   for bay in (0x21, 0x22)])

    def test_agap_wire_commands_and_enum(self):
        stage = agap.NewportM100DSerialStage('fake', limits={'U': [-.76, .76], 'V': [-.76, .76]})
        stage.serial.chunks = [b'1TE@\r\n']
        stage.MoveAbs(agap.Axes.YAW, -0.25, wait=False)
        self.assertEqual(stage.serial.writes, [b'1PAU-0.25\r\n', b'1TE\r\n'])
        self.assertTrue(stage.serial.settings['xonxoff'])
        self.assertEqual(stage.serial.settings['baudrate'], 921600)

    def test_agp_position_and_homing(self):
        stage = agp.NewportAGPSerialStage('fake', limits={'X': [0, 27]})
        stage.serial.chunks = [b'1TP1.25\r\n', b'1TS000032\r\n']
        self.assertEqual(stage.GetStatus()['axes']['X']['position'], 1.25)
        stage.serial.chunks = [b'1TS00000A\r\n', b'1TE@\r\n', b'1TS00001E\r\n', b'1TS000032\r\n']
        stage.HomeAxis()
        self.assertIn(b'1OR\r\n', stage.serial.writes)

    def test_agp_home_already_referenced_sends_no_home_command(self):
        stage = agp.NewportAGPSerialStage('fake', limits={'X': [0, 27]})
        stage.serial.chunks = [b'1TS000032\r\n']
        stage.HomeAxis('X')
        self.assertEqual(stage.serial.writes, [b'1TS\r\n'])
        stage.serial.chunks = [b'1TP0\r\n', b'1TS000032\r\n']
        self.assertFalse(stage.GetStatus()['axes']['X']['supports']['home_when_referenced'])

    def test_agp_idle_stop_consumes_rejection_before_next_move(self):
        stage = agp.NewportAGPSerialStage('fake', limits={'X': [0, 27]})
        stage.serial.chunks = [b'1TEK\r\n', b'1TS000032\r\n', b'1TE@\r\n']
        stage.StopAll()
        stage.MoveAbs('X', 1.25, wait=False)
        self.assertEqual(stage.serial.writes,
                         [b'1ST\r\n', b'1TE\r\n', b'1TS\r\n', b'1PA1.25\r\n', b'1TE\r\n'])

    def test_agp_stop_sends_immediately_and_checks_acceptance(self):
        stage = agp.NewportAGPSerialStage('fake', limits={'X': [0, 27]})
        stage.serial.chunks = [b'1TE@\r\n']
        stage.StopAll()
        self.assertEqual(stage.serial.writes, [b'1ST\r\n', b'1TE\r\n'])

    def test_agp_rejected_stop_does_not_hide_motion_or_hardware_fault(self):
        for response in (b'1TS000028\r\n', b'1TS002032\r\n'):
            with self.subTest(response=response):
                stage = agp.NewportAGPSerialStage('fake', limits={'X': [0, 27]})
                stage.serial.chunks = [b'1TEK\r\n', response]
                with self.assertRaises(RuntimeError):
                    stage.StopAll()

    def test_agap_positions(self):
        stage = agap.NewportM100DSerialStage('fake', limits={'U': [-.76, .76], 'V': [-.76, .76]})
        stage.serial.chunks = [b'1TPU0.2\r\n', b'1TPV-0.3\r\n', b'1TS000032\r\n']
        status = stage.GetStatus()
        self.assertEqual({axis: info['position'] for axis, info in status['axes'].items()}, {'U': .2, 'V': -.3})
        self.assertFalse(status['axes']['U']['supports']['home'])
        self.assertFalse(hasattr(stage, 'HomeAxis'))

    def test_newport_status_contains_configuration_and_live_axes_once(self):
        stage = agap.NewportM100DSerialStage('fake', limits={'U': [-.5, .5], 'V': [-.4, .6]})
        stage.serial.chunks = [b'1TPU0.2\r\n', b'1TPV-0.3\r\n', b'1TS000032\r\n']
        status = stage.GetStatus()
        self.assertEqual(status['controller'], 'CONEXAGAPSerial')
        self.assertEqual(status['port'], 'fake')
        self.assertEqual(status['controller_state'], 0x32)
        self.assertEqual(status['axes']['V']['limits'], [-.4, .6])
        self.assertEqual(status['axes']['U']['units'], 'deg')
        self.assertTrue(status['axes']['U']['enabled'])
        self.assertEqual(stage.serial.writes, [b'1TPU\r\n', b'1TPV\r\n', b'1TS\r\n'])
        stage.serial.chunks = [b'1TPV0.1\r\n', b'1TS000028\r\n']
        self.assertEqual(set(stage.GetStatus('V')['axes']), {'V'})
        self.assertEqual(stage.serial.writes[-2:], [b'1TPV\r\n', b'1TS\r\n'])

    def test_newport_drivers_have_one_public_status_getter(self):
        for stage in (agp.NewportAGPSerialStage('fake'), agap.NewportM100DSerialStage('fake'),
                      esp300.NewportESP300('fake')):
            with self.subTest(driver=type(stage).__name__):
                for name in ('get_status_raw', 'GetProperties', 'GetMotionCapabilities',
                             'GetAxisStatus', 'GetPositions', 'GetPosition', 'is_ready', 'wait_until_ready'):
                    self.assertFalse(hasattr(stage, name), name)

    def test_newport_status_reports_disabled_and_fault_feedback(self):
        stage = agap.NewportM100DSerialStage('fake')
        stage.serial.chunks = [b'1TPU0\r\n', b'1TS00003C\r\n']
        self.assertFalse(stage.GetStatus('U')['axes']['U']['enabled'])
        stage.serial.chunks = [b'1TPU0\r\n', b'1TS002032\r\n']
        status = stage.GetStatus('U')
        self.assertEqual(status['controller_error'], 0x20)
        self.assertIn('0020', status['axes']['U']['fault'])

    def test_newport_rejected_command_and_bad_reply(self):
        stage = agp.NewportAGPSerialStage('fake', limits={'X': [0, 27]})
        stage.serial.chunks = [b'1TEH\r\n', b'1TE@\r\n']
        with self.assertRaises(RuntimeError):
            stage.MoveAbs(0, 1)
        stage.serial.chunks = [b'2TP0\r\n']
        with self.assertRaises(RuntimeError):
            stage.GetStatus()
        stage.serial.chunks = [b'1TP0']
        with self.assertRaises(TimeoutError):
            stage.GetStatus()
        stage.CloseStage()
        self.assertFalse(stage.serial.is_open)

    def test_conex_homing_timeout_uses_performance_counter_and_stops(self):
        stage = agp.NewportAGPSerialStage('fake')
        stage.serial.chunks = [b'1TS00001E\r\n', b'1TS00001E\r\n', b'1TE@\r\n']
        clock = types.SimpleNamespace(perf_counter=Mock(side_effect=[10, 10, 11]))
        with patch.object(agp, 'time', clock):
            with self.assertRaisesRegex(TimeoutError, 'did not become ready'):
                stage.HomeAxis(timeout=.5)
        self.assertEqual(stage.serial.writes, [b'1TS\r\n', b'1TS\r\n', b'1ST\r\n', b'1TE\r\n'])

    def test_conex_move_timeout_still_stops_with_performance_counter(self):
        for module, driver, axis, position_reply, move_command in (
                (agp, agp.NewportAGPSerialStage, 'X', b'1TP0\r\n', b'1PA1\r\n'),
                (agap, agap.NewportM100DSerialStage, 'U', b'1TPU0\r\n', b'1PAU1\r\n')):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake', limits={'X': [0, 27]} if module is agp else {'U': [-2, 2], 'V': [-2, 2]})
                stage.serial.chunks = [b'1TE@\r\n', position_reply, b'1TS000028\r\n', b'1TE@\r\n']
                clock = types.SimpleNamespace(perf_counter=Mock(side_effect=[10, 10, 11]),
                                              sleep=Mock())
                with patch.object(module, 'time', clock):
                    with self.assertRaisesRegex(TimeoutError, 'did not finish'):
                        stage.MoveAbs(axis, 1, timeout=.5)
                self.assertEqual(stage.serial.writes[0], move_command)
                self.assertIn(b'1ST\r\n', stage.serial.writes)

    def test_esp300_wait_timeout_uses_performance_counter(self):
        stage = esp300.NewportESP300('fake')
        clock = types.SimpleNamespace(perf_counter=Mock(side_effect=[10, 11]), sleep=Mock())
        with patch.object(esp300, 'time', clock):
            with self.assertRaisesRegex(TimeoutError, 'motion timeout'):
                stage._wait_until_done(1, timeout=.5)

    def test_conex_abs_waits_for_stopped_target_without_a_sleep(self):
        for module, driver, axis, limits in (
                (agp, agp.NewportAGPSerialStage, 'X', {'X': [0, 27]}),
                (agap, agap.NewportM100DSerialStage, 'U', {'U': [-.76, .76]})):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake', limits=limits)
                stage.serial.chunks = [b'1TE@\r\n']
                ready = {'fault': None, 'enabled': True, 'homing': False, 'homed': True,
                         'moving': False, 'position': .25}
                feedback = [{'axes': {axis: value}} for value in (dict(ready, position=0), dict(ready, moving=True), ready)]
                # No sleep attribute: the move loop must be paced by replies.
                clock = types.SimpleNamespace(perf_counter=Mock(side_effect=[10, 10, 10.01, 10.02]))
                with patch.object(module, 'time', clock), \
                        patch.object(stage, 'GetStatus', side_effect=feedback) as poll:
                    self.assertEqual(stage.MoveAbs(axis, .25), ready)
                self.assertEqual(poll.call_count, 3)
                self.assertFalse(hasattr(stage, 'MoveTo'))

    def test_conex_limits_protect_absolute_relative_and_nonblocking_moves(self):
        for driver, axis, limits in ((agp.NewportAGPSerialStage, 'X', {'X': [0, 1]}),
                                     (agap.NewportM100DSerialStage, 'U', {'U': [-1, 1]})):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake', limits=limits)
                reply = b'1TP0\r\n' if axis == 'X' else b'1TPU0\r\n'
                stage.serial.chunks = [reply, b'1TS000032\r\n']
                spec = stage.GetStatus(axis)['axes'][axis]
                self.assertEqual(spec['limits'], limits[axis])
                before = list(stage.serial.writes)
                for wait in (True, False):
                    with self.assertRaisesRegex(ValueError, 'travel limits'):
                        stage.MoveAbs(axis, 1.01, wait=wait)
                    current = {'position': .9, 'moving': False, 'homing': False,
                               'homed': True, 'enabled': True, 'fault': None}
                    with patch.object(stage, 'GetStatus', return_value={'axes': {axis: current}}):
                        with self.assertRaisesRegex(ValueError, 'travel limits'):
                            stage.MoveRel(axis, .2, wait=wait)
                self.assertEqual(stage.serial.writes, before)

    def test_conex_missing_limits_prevents_motion_but_allows_readout(self):
        for driver, axis, reply in ((agp.NewportAGPSerialStage, 'X', b'1TP0\r\n'),
                                    (agap.NewportM100DSerialStage, 'U', b'1TPU0\r\n')):
            with self.subTest(driver=driver.__name__):
                stage = driver('fake')
                stage.serial.chunks = [reply, b'1TS000032\r\n']
                self.assertEqual(stage.GetStatus(axis)["axes"][axis]["position"], 0)
                before = list(stage.serial.writes)
                with self.assertRaisesRegex(ValueError, 'Configure travel limits'):
                    stage.MoveAbs(axis, .1, wait=False)
                self.assertEqual(stage.serial.writes, before)

    def test_newport_server_overrides_are_applied_to_driver_limits(self):
        from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import create_motorised_stage
        fake_serial = types.SimpleNamespace(Serial=SerialPort, EIGHTBITS=8,
                                            PARITY_NONE='N', STOPBITS_ONE=1)
        with patch.dict(sys.modules, serial=fake_serial):
            with patch('JazLabs.hardware.MotorisedStages.Newport.newport_agp_serial_stage.NewportAGPSerialStage') as driver:
                create_motorised_stage('CONEXAGPSerial', {'port': 'fake', 'limits': {'X': [0, 1]}},
                                       limits={'X': [.1, .9]})
                self.assertEqual(driver.call_args.kwargs['limits'], {'X': (.1, .9)})
                driver.reset_mock()
                with self.assertRaisesRegex(ValueError, 'cannot widen'):
                    create_motorised_stage('CONEXAGPSerial', {'port': 'fake', 'limits': {'X': [0, 1]}},
                                           limits={'X': [0, 2]})
                driver.assert_not_called()

    def test_conex_fault_or_disabled_feedback_requests_stop(self):
        for driver, axis in ((agp.NewportAGPSerialStage, 'X'), (agap.NewportM100DSerialStage, 'U')):
            for changes in ({'fault': 'Encoder failure'}, {'enabled': False}):
                with self.subTest(driver=driver.__name__, changes=changes):
                    stage = driver('fake', limits={axis: [0, 1]})
                    stage.serial.chunks = [b'1TE@\r\n', b'1TE@\r\n']
                    current = {'position': 0, 'moving': True, 'homing': False,
                               'enabled': True, 'fault': None}
                    current.update(changes)
                    with patch.object(stage, 'GetStatus', return_value={'axes': {axis: current}}):
                        with self.assertRaises(RuntimeError):
                            stage.MoveAbs(axis, .5)
                    self.assertIn(b'1ST\r\n', stage.serial.writes)

    def test_esp300_absolute_move_checks_limits_target_and_error_feedback(self):
        stage = esp300.NewportESP300('fake', limits={1: [0, 1]})
        with self.assertRaisesRegex(ValueError, 'travel limits'):
            stage.MoveAbs(1, 2, wait=False)
        self.assertEqual(stage.ser.writes, [])
        stage.ser.chunks = [b'0\r\n', b'1\r\n', b'0.5\r\n', b'0\r\n']
        self.assertEqual(stage.MoveAbs(1, .5)['position'], .5)
        self.assertEqual(stage.ser.writes, [b'1PA0.5\r', b'TE?\r', b'1MD?\r', b'1TP?\r', b'TE?\r'])
        stage.ser.chunks = [b'101\r\n']
        with self.assertRaisesRegex(RuntimeError, 'controller error 101'):
            stage.MoveAbs(1, .25)
        self.assertEqual(stage.ser.writes[-1], b'1ST\r')

    def test_newport_nominal_moves_to_each_configured_midpoint(self):
        translation = agp.NewportAGPSerialStage('fake', limits={'X': [2, 8]})
        translation.serial.chunks = [b'1TE@\r\n']
        translation.SetNominal(wait=False)
        self.assertEqual(translation.serial.writes, [b'1PA5\r\n', b'1TE\r\n'])

        mirror = agap.NewportM100DSerialStage('fake', limits={'U': [.1, .5], 'V': [-.8, -.2]})
        mirror.serial.chunks = [b'1TE@\r\n', b'1TE@\r\n']
        mirror.SetNominal(wait=False)
        self.assertEqual(mirror.serial.writes,
                         [b'1PAU0.3\r\n', b'1TE\r\n', b'1PAV-0.5\r\n', b'1TE\r\n'])

        stage = esp300.NewportESP300('fake', axes=(1, 2), limits={1: [2, 8], 2: [-10, -4]})
        stage.ser.chunks = [b'0\r\n', b'0\r\n']
        stage.SetNominal(wait=False)
        self.assertEqual(stage.ser.writes, [b'1PA5.0\r', b'TE?\r', b'2PA-7.0\r', b'TE?\r'])

    def test_newport_nominal_requires_all_limits_before_moving_any_axis(self):
        stages = [agp.NewportAGPSerialStage('fake'),
                  agap.NewportM100DSerialStage('fake', limits={'U': [-1, 1]}),
                  esp300.NewportESP300('fake', axes=(1, 2), limits={1: [0, 10]})]
        for stage in stages:
            with self.subTest(driver=type(stage).__name__):
                with self.assertRaisesRegex(ValueError, 'Configure travel limits'):
                    stage.SetNominal()
                port = stage.ser if isinstance(stage, esp300.NewportESP300) else stage.serial
                self.assertEqual(port.writes, [])


if __name__ == '__main__':
    unittest.main()
