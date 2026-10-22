"""Named motor presets resolve to serial driver settings without opening ports."""
from unittest.mock import patch

import pytest

from JazLabs.launchers.config import get_named_config, load_config
from JazLabs.launchers.launch_motorised_stage_widget import main


@pytest.mark.parametrize('name,stage,port,axis,units', [
    ('newport_tip_tilt', 'CONEXAGAPSerial', 50941, 'U', 'deg'),
    ('newport_translation', 'CONEXAGPSerial', 50942, 'X', 'mm'),
    ('thorlabs_umc2', 'UMC2Serial', 50943, 'X', 'counts'),
])
def test_named_motor_server_options(name, stage, port, axis, units):
    config = load_config('motorised_mounts')
    preset = get_named_config(config, 'MOTOR_SERVERS', name)
    assert preset['stage_kwargs']['port'] is None
    assert preset['default_axis'] == axis
    assert preset['expected_units'] == units
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        main(['--serve', '--config', 'motorised_mounts', '--name', name, '--port', 'TEST_PORT'])
        args = server.call_args.args
        assert args[:3] == ('127.0.0.1', port, stage)
        assert args[3]['port'] == 'TEST_PORT'
        server.return_value.run_forever.assert_called_once()
    assert preset['stage_kwargs']['port'] is None  # Overrides must not edit the module's config.


def test_missing_serial_port_fails_before_constructing_server():
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        with pytest.raises(SystemExit):
            main(['--serve', '--config', 'motorised_mounts', '--name', 'thorlabs_umc2'])
        server.assert_not_called()


def test_limits_command_port_and_driver_overrides_are_used():
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        main(['--serve', '--config', 'motorised_mounts', '--name', 'newport_translation',
              '--port', 'TEST_PORT', '--command-port', '51942', '--bind', '0.0.0.0',
              '--driver-options', '{"address": 2}', '--limits', '{"X": [0, 10]}'])
        host, port, stage, options, limits = server.call_args.args
        assert (host, port, stage) == ('0.0.0.0', 51942, 'CONEXAGPSerial')
        assert options['address'] == 2
        assert options['units'] == 'mm'
        assert limits == {'X': [0, 10]}


def test_default_simulation_still_starts_without_hardware():
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        main(['--serve', '--demo-axes', '3'])
        assert server.call_args.args[2:4] == ('simulation', {'axes': 3, 'absolute_sensor': False})
