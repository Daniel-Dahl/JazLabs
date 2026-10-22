"""Opt-in native Tk smoke tests: JAZLABS_TEST_MOTOR_GUI=1 pytest ..."""
import os
import time
import types
import unittest

from JazLabs.hardware.MotorisedStages.MotorisedStage_Client import MotorisedStageClient
from JazLabs.hardware.MotorisedStages.MotorisedStage_Server import MotorisedStageZMQServer
from JazLabs.hardware.MotorisedStages.MotorisedStage_Widget import MotorisedStageControlWindow


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
        self.client.thread.join(2)
        self.assertFalse(self.client.thread.is_alive())
        self.server.stop()

    def pump(self, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.window.root.update()
            time.sleep(.01)

    def test_layouts_homing_state_and_hold_jog(self):
        gui = self.window
        self.assertEqual(len(gui.axis_widgets), 3)
        self.assertIn('Needs homing', gui.axis_widgets['Y']['status'].get())
        gui.keyboard.set(True)
        event = types.SimpleNamespace(keysym='d', widget=gui.root, state=0)
        gui.key_pressed(event)
        self.pump(.85)
        gui.key_released(event)
        self.pump(.5)
        position = self.client.get_state()['axes']['X']['position']
        self.assertGreaterEqual(position, 5.02)
        self.pump(.6)
        self.assertAlmostEqual(self.client.get_state()['axes']['X']['position'], position)
        gui.layout.set('console')
        gui.rebuild_layout()
        self.pump(.1)
        self.assertFalse(gui.keyboard.get())
        self.assertTrue(all('target' in row for row in gui.axis_widgets.values()))
        gui.stop()
        self.pump(.2)
        self.assertTrue(self.client.get_state()['stopped'])
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
        before = self.client.get_state()['axes']['X']['position']
        gui.root.event_generate('<KeyPress-d>')
        self.pump(.85)
        gui.root.event_generate('<KeyRelease-d>')
        self.pump(.5)
        after = self.client.get_state()['axes']['X']['position']
        self.assertGreater(after, before)
        self.pump(.5)
        self.assertAlmostEqual(self.client.get_state()['axes']['X']['position'], after)

    def test_absolute_move_slider_release_and_close(self):
        gui = self.window
        gui.axis_widgets['X']['target'].set('5.1')
        gui.absolute_move('X')
        self.pump(.6)
        self.assertAlmostEqual(self.client.get_state()['axes']['X']['position'], 5.1)
        gui.axis_widgets['X']['slider'].set(5.2)
        self.pump(.15)
        self.assertAlmostEqual(self.client.get_state()['axes']['X']['position'], 5.1)
        gui.slider_released('X')
        self.pump(.6)
        self.assertAlmostEqual(self.client.get_state()['axes']['X']['position'], 5.2)

    def test_typing_disarms_and_focus_loss_releases(self):
        gui = self.window
        gui.keyboard.set(True)
        gui.held_key = 'd'
        event = types.SimpleNamespace(widget=gui.axis_widgets['X']['entry'])
        gui.focus_entered(event)
        self.assertIsNone(gui.held_key)
        self.assertFalse(gui.keyboard.get())
