"""Explicit graphical test with a separate server and test executable. Never accesses USB."""
import time
from usb_hub_test_support import create_uhubctl_stub
import tkinter as tk
from unittest.mock import patch

from JazLabs.hardware.USBHub.USBHub_Client import USBHubClient
from JazLabs.hardware.USBHub.USBHub_Server import USBHubZMQServer
from JazLabs.hardware.USBHub.USBHub_Widget import USBHubWidget


def test_widget_mapping_and_switching(tmp_path):
    import pytest
    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display unavailable: {error}")
    server = USBHubZMQServer(command_port=0, binary=create_uhubctl_stub(tmp_path))
    client = None
    try:
        server.start()
        client = USBHubClient(command_port=server.command_port, timeout_ms=2000)
        app = USBHubWidget(root, client)
        root.update()
        deadline = time.perf_counter() + 5
        while app.busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert not app.busy and app.trees
        assert len(app.rows) == 10
        assert all(str(row[4]['state']) == 'disabled' for row in app.rows)
        for index, endpoint in enumerate(app.trees[app.selection.get()]):
            app.rows[index][0].set(f'{endpoint[0]} / {endpoint[1]}')
            app.map_port(index)
        app.armed.set(True)
        app.render()
        with patch('JazLabs.hardware.USBHub.USBHub_Widget.messagebox.askokcancel', return_value=True):
            app.toggle(0)
        deadline = time.perf_counter() + 5
        while app.busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert app.rows[0][2].get() == '○ Off'
        assert app.rows[1][2].get() == '● On'
        app.last_scan = time.perf_counter() - 31
        app.render()
        assert all(str(row[4]['state']) == 'disabled' for row in app.rows)
        # A changed server session must invalidate mapping even at the same address.
        app.session_id = 'previous-session'
        app.scan()
        deadline = time.perf_counter() + 5
        while app.busy and time.perf_counter() < deadline:
            root.update()
            time.sleep(0.02)
        assert app.mapping == [None] * 10 and not app.armed.get()
        print('PASS: widget -> client -> server -> stub executable, mapping, readback, stale lock, session reset')
    finally:
        if root is not None:
            root.destroy()
        if client is not None:
            client.close()
        server.stop()
