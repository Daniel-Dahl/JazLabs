"""Opt-in native Tk smoke tests: JAZLABS_TEST_MOTOR_GUI=1 pytest ..."""
import os
from copy import deepcopy
import time
import types
import unittest
from unittest.mock import Mock, patch

from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer
from JazLabs.hardware.MotorisedStages.MotorisedStage_Widget import MotorisedStageControlWindow


class FocusCheckTests(unittest.TestCase):
    def test_tcl_only_combobox_popdown_does_not_require_python_widget(self):
        window = types.SimpleNamespace(root=Mock(), focus_after_id='pending', release_jog=Mock())
        window.root._w = '.'
        window.root.tk.call.return_value = '.layout.popdown.f.l'
        MotorisedStageControlWindow.check_application_focus(window)
        window.root.tk.call.assert_called_once_with('focus', '-displayof', '.')
        window.root.focus_displayof.assert_not_called()
        window.release_jog.assert_not_called()
        self.assertIsNone(window.focus_after_id)

    def test_focus_outside_application_releases_and_disarms_jog(self):
        window = types.SimpleNamespace(root=Mock(), focus_after_id='pending', release_jog=Mock())
        window.root.tk.call.return_value = ''
        MotorisedStageControlWindow.check_application_focus(window)
        window.release_jog.assert_called_once_with(disarm=True)


class KeyboardModifierTests(unittest.TestCase):
    def test_lock_keys_allow_jog_and_shortcut_modifiers_block_it(self):
        cases = [
            ('win32', 0x8, True),  # Windows Num Lock must not block movement.
            ('win32', 0x2 | 0x8 | 0x20, True),  # Caps/Num/Scroll Lock.
            ('win32', 0x4 | 0x8, False),
            ('win32', 0x20000 | 0x8, False),
            ('aqua', 0x2, True),
            ('aqua', 0x4, False),
            ('aqua', 0x8, False),
            ('aqua', 0x10, False),
            ('x11', 0x10, True),  # Typical X11 Num Lock mapping.
            ('x11', 0x4, False),
            ('x11', 0x8, False),
            ('x11', 0x40, False),
        ]
        for window_system, state, should_move in cases:
            with self.subTest(window_system=window_system, state=state):
                window = types.SimpleNamespace(
                    root=Mock(), keyboard=Mock(), held_key=None,
                    capabilities={'X': {}}, can_move=Mock(return_value=True),
                    jog_once=Mock(return_value=True), step=Mock(), axis_steps={},
                    controller_value=lambda axis, value: value)
                window.keyboard.get.return_value = True
                window.step.get.return_value = '0.1'
                window.root.tk.call.return_value = window_system
                widget = Mock()
                widget.winfo_class.return_value = 'Tk'
                event = types.SimpleNamespace(keysym='d', widget=widget, state=state)
                MotorisedStageControlWindow.key_pressed(window, event)
                if should_move:
                    window.jog_once.assert_called_once_with('X', 1)
                    self.assertEqual(window.held_key, 'd')
                else:
                    window.jog_once.assert_not_called()


@unittest.skipUnless(os.environ.get('JAZLABS_TEST_MOTOR_GUI') == '1', 'Requires a desktop display')
class NativeGuiTests(unittest.TestCase):
    def setUp(self):
        self.server = MotorisedStageZMQServer(command_port=0, stage_kwargs={"axes": 3})
        self.server.start()
        self.client = MotorisedStageClient(command_port=self.server.command_port)
        self.window = MotorisedStageControlWindow(self.client)
        self.pump(.5)

    def tearDown(self):
        self.window.close()
        self.server.stop()

    def pump(self, seconds):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            self.window.root.update()
            time.sleep(.01)

    def test_layouts_homing_state_and_hold_jog(self):
        gui = self.window
        self.assertEqual(len(gui.axis_widgets), 3)
        self.assertIn('Needs homing', gui.axis_widgets['Y']['status'].get())
        gui.root.focus_force()
        gui.keyboard.set(True)
        gui.keyboard_changed()
        self.pump(.1)
        event = types.SimpleNamespace(keysym='d', widget=gui.root, state=0)
        gui.key_pressed(event)
        self.pump(.85)
        gui.key_released(event)
        self.pump(.5)
        position = self.client.GetStatus()['axes']['X']['position']
        self.assertGreaterEqual(position, 5.02)
        self.pump(.6)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], position)
        gui.layout.set('console')
        gui.rebuild_layout()
        self.pump(.1)
        self.assertFalse(gui.keyboard.get())
        self.assertTrue(all('target' in row for row in gui.axis_widgets.values()))
        gui.stop()
        self.pump(.2)
        self.assertTrue(self.client.GetStatus()['stopped'])
        self.assertIn('disabled', gui.axis_widgets['X']['move_controls'][0].state())

    def test_checkbox_takes_focus_and_real_key_events_move(self):
        gui = self.window
        gui.root.focus_force()
        gui.axis_widgets['X']['entry'].focus_set()
        self.pump(.1)
        gui.keyboard_checkbox.invoke()
        self.pump(.1)
        self.assertTrue(gui.keyboard.get())
        self.assertEqual(gui.root.focus_get(), gui.root)
        before = self.client.GetStatus()['axes']['X']['position']
        gui.root.event_generate('<KeyPress-d>')
        self.pump(.85)
        gui.root.event_generate('<KeyRelease-d>')
        self.pump(.5)
        after = self.client.GetStatus()['axes']['X']['position']
        self.assertGreater(after, before)
        self.pump(.5)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], after)

    def test_absolute_move_slider_release_and_close(self):
        gui = self.window
        gui.axis_widgets['X']['target'].set('5.1')
        gui.absolute_move('X')
        self.pump(.6)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], 5.1)
        gui.axis_widgets['X']['slider'].set(5.2)
        self.pump(.15)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], 5.1)
        gui.slider_released('X')
        self.pump(.6)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], 5.2)

    def test_independent_mount_panels_have_separate_steps_and_unit_selection(self):
        gui = self.window
        original = self.client.GetStatus

        def calibrated_mount_state(axis=None):
            state = original(axis)
            for index, spec in enumerate(state['axes'].values(), start=1):
                spec.update(independent_mount=True, label=f'Mount {index}',
                            unit_scales={'counts': 1, 'mm': index * 1000})
            return state

        with patch.object(self.client, 'GetStatus', side_effect=calibrated_mount_state):
            self.pump(.2)
            self.assertEqual(set(gui.axis_steps), {'X', 'Y', 'Z'})
            gui.axis_units['X'].set('counts')
            gui.units_changed('X')
            self.assertEqual(gui.axis_units['Y'].get(), 'mm')
            self.assertEqual(float(gui.axis_steps['X'].get()), 10)
            self.assertEqual(float(gui.axis_steps['Y'].get()), .01)
            gui.axis_widgets['X']['target'].set('5100')
            gui.absolute_move('X')
            self.pump(.6)
            self.assertAlmostEqual(original()['axes']['X']['position'], 5.1)
            self.assertAlmostEqual(original()['axes']['Y']['position'], 6)
            gui.axis_steps['X'].set('20')
            gui.jog_once('X', 1)
            self.pump(.5)
            self.assertAlmostEqual(original()['axes']['X']['position'], 5.12)
            self.assertAlmostEqual(float(gui.axis_widgets['X']['slider'].get()), 5000)

    def test_units_are_visible_and_default_to_mm_with_counts_server_units(self):
        snapshot = self.client.GetStatus()
        for index, (axis, spec) in enumerate(snapshot['axes'].items(), start=1):
            scale = index * 1000
            spec.update(units='counts', unit_scales={'counts': 1, 'mm': scale},
                        independent_mount=True, step=100, resolution=1,
                        limits=[0, 25000])
            snapshot['axes'][axis]['position'] *= scale
        self.window.close()
        client = Mock()
        client.GetStatus.side_effect = lambda: deepcopy(snapshot)
        self.window = MotorisedStageControlWindow(client)
        gui = self.window
        self.pump(.1)
        self.assertEqual(gui.axis_units['X'].get(), 'mm')
        self.assertEqual(gui.axis_widgets['X']['unit_selector'].cget('values'), ('counts', 'mm'))
        self.assertNotIn('disabled', gui.axis_widgets['X']['unit_selector'].state())
        gui.axis_steps['X'].set('.25')
        gui.axis_units['X'].set('counts')
        gui.axis_widgets['X']['unit_selector'].event_generate('<<ComboboxSelected>>')
        self.pump(.1)
        self.assertEqual(float(gui.axis_steps['X'].get()), 250)
        self.assertEqual(gui.axis_units['Y'].get(), 'mm')
        gui.axis_units['X'].set('mm')
        gui.axis_widgets['X']['unit_selector'].event_generate('<<ComboboxSelected>>')
        self.pump(.1)
        self.assertEqual(float(gui.axis_steps['X'].get()), .25)
        snapshot['axes']['X']['unit_scales'] = {'counts': 1}
        self.pump(.2)
        self.assertEqual(gui.axis_units['X'].get(), 'counts')
        self.assertIn('disabled', gui.axis_widgets['X']['unit_selector'].state())
        self.assertIn('calibration', gui.axis_widgets['X']['unit_note'].get())
        self.assertEqual(float(gui.axis_steps['X'].get()), 100)

    def test_quick_key_tap_survives_immediate_release(self):
        gui = self.window
        gui.root.focus_force()
        gui.keyboard.set(True)
        gui.keyboard_changed()
        self.pump(.1)
        event = types.SimpleNamespace(keysym='d', widget=gui.root, state=0)
        gui.key_pressed(event)
        gui.key_released(event)
        self.pump(.5)
        self.assertAlmostEqual(self.client.GetStatus()['axes']['X']['position'], 5.01)
        self.assertIsNone(gui.held_key)

    def test_lost_move_reply_disarms_and_retries_stop_without_repeating_move(self):
        gui = self.window
        original = self.client.request
        commands = []
        def lose_first_move_reply(command, *args, **kwargs):
            commands.append(command)
            status = original(command, *args, **kwargs)
            if command == 'relative':
                raise TimeoutError('lost first-move reply')
            return status
        with patch.object(self.client, 'request', side_effect=lose_first_move_reply):
            self.assertFalse(gui.send('relative', 'X', .02))
            self.pump(.3)
            status = self.client.GetStatus()
            self.assertTrue(status['stopped'])
            self.assertIn('GUI relative request failed: lost first-move reply', status['stop_reason'])
            self.assertFalse(gui.keyboard.get())
            self.assertEqual(commands.count('relative'), 1)

    def test_initial_connection_timeout_retries_polling_without_requesting_stop(self):
        self.window.close()
        self.client = MotorisedStageClient(command_port=self.server.command_port)
        self.client.request('resume')
        original = self.client.request
        commands = []
        def timeout_first_poll(command, *args, **kwargs):
            commands.append(command)
            if len(commands) == 1:
                raise TimeoutError('server is still starting')
            return original(command, *args, **kwargs)
        with patch.object(self.client, 'request', side_effect=timeout_first_poll):
            self.window = MotorisedStageControlWindow(self.client)
            self.pump(.3)
            self.assertTrue(self.window.state['connected'])
            self.assertNotIn('stop', commands)
            self.assertFalse(self.client.GetStatus()['stopped'])

    def test_lost_status_reply_after_connecting_requests_stop_and_recovers_polling(self):
        original = self.client.GetStatus
        calls = 0
        def lose_one_poll(axis=None):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError('lost feedback after connecting')
            return original(axis)
        with patch.object(self.client, 'GetStatus', side_effect=lose_one_poll):
            self.pump(.4)
            status = original()
            self.assertTrue(status['stopped'])
            self.assertIn('lost feedback after connecting', status['stop_reason'])
            self.assertTrue(self.window.state['connected'])

    def test_rejected_gui_command_does_not_stop_another_clients_active_move(self):
        self.client.MoveAbs('X', 6, wait=False)
        self.pump(.1)
        self.assertTrue(self.client.GetStatus()['axes']['X']['commanded'])
        self.client.request('absolute', 'X', 5.5, operation_id='reserved-pending-move')
        self.assertFalse(self.window.send('absolute', 'X', 5.2))
        status = self.client.GetStatus()
        self.assertFalse(status['stopped'])
        self.assertIsNone(status['stop_reason'])

    def test_closing_gui_requests_stop_before_closing_client_connection(self):
        observer = MotorisedStageClient(command_port=self.server.command_port)
        try:
            self.client.MoveAbs('X', 6, wait=False)
            self.window.close()
            self.pump(.2)
            status = observer.GetStatus()
            self.assertTrue(status['stopped'])
            self.assertFalse(status['axes']['X']['moving'])
            self.assertTrue(self.client.closed)
        finally:
            observer.CloseStage()

    def test_typing_disarms_and_focus_loss_releases(self):
        gui = self.window
        gui.keyboard.set(True)
        gui.held_key = 'd'
        event = types.SimpleNamespace(widget=gui.axis_widgets['X']['entry'])
        gui.focus_entered(event)
        self.assertIsNone(gui.held_key)
        self.assertFalse(gui.keyboard.get())
