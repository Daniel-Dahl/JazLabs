"""Named motor presets resolve to serial driver settings without opening ports."""
from unittest.mock import patch

import pytest

from JazLabs.launchers.config import get_named_config, load_config
from JazLabs.launchers.launch_motorised_stage_server import main


@pytest.mark.parametrize('name,stage,port,axis,units', [
    ('newport_tip_tilt', 'CONEXAGAPSerial', 50941, 'U', 'deg'),
    ('newport_translation', 'CONEXAGPSerial', 50942, 'X', 'mm'),
    ('thorlabs_umc2', 'UMC2Serial', 50943, 'X', 'auto'),
])
def test_named_motor_server_options(name, stage, port, axis, units):
    config = load_config('motorised_mounts')
    preset = get_named_config(config, 'MOTOR_SERVERS', name)
    assert preset['stage_kwargs']['port'] is None
    assert preset['default_axis'] == axis
    assert preset['expected_units'] == units
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        main(['--config', 'motorised_mounts', '--name', name, '--serial-port', 'TEST_PORT'])
        args = server.call_args.kwargs
        assert (args['host'], args['command_port'], args['stage_type']) == ('127.0.0.1', port, stage)
        assert args['stage_kwargs']['port'] == 'TEST_PORT'
        server.return_value.run_forever.assert_called_once()
    assert preset['stage_kwargs']['port'] is None  # Overrides must not edit the module's config.


def test_missing_serial_port_fails_before_constructing_server():
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        with pytest.raises(SystemExit):
            main(['--config', 'motorised_mounts', '--name', 'thorlabs_umc2'])
        server.assert_not_called()


def test_newport_presets_put_limits_in_the_driver_options():
    config = load_config('motorised_mounts')
    for name, limits in (('newport_translation', {'X': [0, 27]}),
                         ('newport_tip_tilt', {'U': [-.76, .76], 'V': [-.76, .76]})):
        preset = get_named_config(config, 'MOTOR_SERVERS', name)
        assert preset['stage_kwargs']['limits'] == limits
        assert preset['limits'] == {}


def test_limits_command_port_and_driver_overrides_are_used():
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        main(['--config', 'motorised_mounts', '--name', 'newport_translation',
              '--serial-port', 'TEST_PORT', '--command-port', '51942', '--host', '0.0.0.0',
              '--driver-options', '{"address": 2}', '--limits', '{"X": [0, 10]}'])
        kwargs = server.call_args.kwargs
        assert (kwargs['host'], kwargs['command_port'], kwargs['stage_type']) == ('0.0.0.0', 51942, 'CONEXAGPSerial')
        assert kwargs['stage_kwargs']['address'] == 2
        assert kwargs['stage_kwargs']['units'] == 'mm'
        assert kwargs['limits'] == {'X': [0, 10]}


def test_simulation_is_launched_as_its_own_named_server():
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        main(['--config', 'motorised_mounts', '--name', 'simulation'])
        assert server.call_args.kwargs['stage_type'] == 'simulation'
        assert server.call_args.kwargs['stage_kwargs'] == {'axes': 2, 'absolute_sensor': False}


def test_widget_connects_only_to_client_and_does_not_start_hardware():
    from JazLabs.launchers.launch_motorised_stage_widget import main as widget_main
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Client.MotorisedStageClient') as client, \
         patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Widget.MotorisedStageControlWindow') as window, \
         patch('JazLabs.hardware.MotorisedStages.MotorisedStage_Server.MotorisedStageZMQServer') as server:
        client.return_value.thread.is_alive.return_value = False
        widget_main(['--config', 'motorised_mounts', '--name', 'newport_tip_tilt', '--bridge'])
        client.assert_called_once_with(host='127.0.0.1', command_port=51941, timeout_ms=500)
        window.assert_called_once_with(client.return_value, 'alignment')
        window.return_value.run.assert_called_once()
        client.return_value.close.assert_called_once()
        server.assert_not_called()


def test_bridge_uses_separate_local_and_remote_ports():
    from JazLabs.launchers.launch_motorised_stage_bridge import main as bridge_main
    with patch('JazLabs.hardware.MotorisedStages.MotorisedStage_BridgeServer.MotorisedStageZMQBridgeServer') as bridge:
        bridge_main(['--config', 'motorised_mounts', '--name', 'thorlabs_umc2',
                     '--remote-host', '192.168.1.25'])
        bridge.assert_called_once_with(remote_host='192.168.1.25', remote_command_port=50943,
            local_host='127.0.0.1', local_command_port=51943, timeout_ms=500, poll_timeout_ms=50)
        bridge.return_value.run_forever.assert_called_once()
