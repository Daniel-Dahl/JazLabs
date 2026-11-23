"""Tk widget. Knows the client API; never invokes uhubctl or imports the driver."""
import time
import tkinter as tk
from tkinter import ttk, messagebox



class USBHubWidget:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller
        self.busy = False
        self.hubs = {}
        self.trees = {}
        self.mapping = [None] * 10
        self.last_scan = 0
        self.session_id = None
        root.title('JazLabs USB Hub · USB power')
        root.geometry('930x790')
        root.minsize(760, 650)
        root.configure(bg='#101923')
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', background='#101923', foreground='#e6edf3', font=('Helvetica Neue', 12))
        style.configure('TButton', background='#243548', padding=9)
        style.map('TButton', background=[('active', '#36526c')])
        style.configure('TCombobox', fieldbackground='#243548', foreground='#e6edf3')
        style.configure('TCheckbutton', background='#101923')
        main = ttk.Frame(root, padding=24)
        main.pack(fill='both', expand=True)
        top = ttk.Frame(main)
        top.pack(fill='x')
        ttk.Label(top, text='JazLabs USB Hub', font=('Helvetica Neue', 28, 'bold')).pack(side='left')
        ttk.Label(top, text='  /  RSH-A10', foreground='#8aa1b7').pack(side='left', pady=10)
        self.refresh = ttk.Button(top, text='↻  Refresh', command=self.scan)
        self.refresh.pack(side='right')
        self.status = tk.StringVar(value='Discovering supported hubs…')
        ttk.Label(main, textvariable=self.status, wraplength=820, foreground='#71d9bd').pack(anchor='w', pady=(12, 10))
        self.selection = tk.StringVar()
        self.hub_choice = ttk.Combobox(main, textvariable=self.selection, state='readonly')
        self.hub_choice.pack(fill='x')
        self.hub_choice.bind('<<ComboboxSelected>>', self.choose_tree)
        ttk.Label(main, text='Map each physical socket to a detected endpoint. Number sockets from the cable end.\nUse a spare USB light to identify sockets; keep physical buttons pressed. Never map an internal hub link.', foreground='#aab9c8', wraplength=820).pack(anchor='w', pady=12)
        grid = ttk.Frame(main)
        grid.pack(fill='both', expand=True)
        self.rows = []
        for index in range(10):
            row = ttk.Frame(grid, padding=(8, 5))
            row.pack(fill='x', pady=2)
            ttk.Label(row, text=f'{index + 1:02}', width=4, font=('Helvetica Neue', 15, 'bold')).pack(side='left')
            endpoint = tk.StringVar(value='Unmapped')
            choice = ttk.Combobox(row, textvariable=endpoint, state='readonly', width=19)
            choice.pack(side='left', padx=(0, 12))
            choice.bind('<<ComboboxSelected>>', lambda event, i=index: self.map_port(i))
            state = tk.StringVar(value='Unknown')
            ttk.Label(row, textvariable=state, width=9).pack(side='left')
            device = tk.StringVar(value='Map a socket to begin')
            ttk.Label(row, textvariable=device, width=35).pack(side='left', fill='x', expand=True)
            button = ttk.Button(row, text='—', width=9, command=lambda i=index: self.toggle(i), state='disabled')
            button.pack(side='right')
            self.rows.append((endpoint, choice, state, device, button))
        self.armed = tk.BooleanVar(value=False)
        ttk.Checkbutton(main, text='I verified the socket mappings and removed/ejected storage before switching.', variable=self.armed, command=self.render).pack(anchor='w', pady=(12, 4))
        ttk.Label(main, text='Reported power ≠ measured voltage. USB2/USB3 companions are handled by uhubctl.', foreground='#8aa1b7').pack(anchor='w')
        ttk.Button(main, text='Discovery & error details', command=self.diagnostics).pack(anchor='w', pady=(8, 0))
        self.raw = ''
        self.root.after(1000, self.check_age)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after_idle(self.scan)

    def scan(self):
        if self.busy:
            return
        self.status.set('Reading USB topology…')
        self.busy = True
        self.render()
        # Schedule after repaint; networking runs in the Tk callback, with no
        # worker thread or result queue. A slow server can hold this callback
        # until the configured client timeout.
        self.root.after_idle(self.read_status)

    def read_status(self):
        try:
            result = self.controller.GetStatus()
            self.apply_status(result)
        except Exception as error:
            self.show_connection_error(error)
        finally:
            self.busy = False
            self.render()

    def apply_status(self, result):
        self.raw = result['raw']
        # A new hardware owner invalidates every physical socket mapping.
        if self.session_id != result['session_id']:
            self.mapping = [None] * 10
            self.armed.set(False)
        self.session_id = result['session_id']
        self.hubs = result['hubs']
        self.trees = {location: [tuple(endpoint) for endpoint in endpoints]
                      for location, endpoints in result['trees'].items()}
        self.last_scan = time.perf_counter()
        self.hub_choice['values'] = list(self.trees)
        if self.selection.get() not in self.trees:
            self.selection.set(next(iter(self.trees), ''))
            self.mapping = [None] * 10
            self.armed.set(False)
        if self.trees:
            self.status.set('Compatible topology detected · map sockets before control · refreshed ' + time.strftime('%H:%M:%S'))
        else:
            self.status.set('No verified RSH-A10 topology found. Controls locked. See the USB hub guide.')
        self.update_choices()

    def show_connection_error(self, error):
        self.raw = str(error)
        self.hubs = {}
        self.last_scan = 0
        self.armed.set(False)
        self.status.set('Discovery/control failed · states unknown · controls locked')
        messagebox.showerror('USB Hub', str(error) + '\n\nSee docs/guides/usb-hub.md for setup and troubleshooting.')

    def choose_tree(self, event=None):
        self.mapping = [None] * 10
        self.armed.set(False)
        self.update_choices()
        self.render()

    def update_choices(self):
        values = ['Unmapped'] + [f'{loc} / {port}' for loc, port in self.trees.get(self.selection.get(), [])]
        for index, (endpoint, choice, *_rest) in enumerate(self.rows):
            choice['values'] = values
            mapped = self.mapping[index]
            label = f'{mapped[0]} / {mapped[1]}' if mapped else 'Unmapped'
            if label not in values:
                self.mapping[index] = None
                label = 'Unmapped'
                self.armed.set(False)
            endpoint.set(label)

    def map_port(self, index):
        value = self.rows[index][0].get()
        endpoint = None
        if value != 'Unmapped':
            location, port = value.split(' / ')
            endpoint = (location, int(port))
        if endpoint and endpoint in self.mapping[:index] + self.mapping[index + 1:]:
            messagebox.showwarning('Already mapped', 'Each endpoint can map to only one physical socket.')
            self.update_choices()
            return
        self.mapping[index] = endpoint
        self.armed.set(False)
        self.render()

    def check_age(self):
        self.render()
        self.root.after(1000, self.check_age)

    def render(self):
        fresh = time.perf_counter() - self.last_scan < 30
        self.refresh['state'] = 'disabled' if self.busy else 'normal'
        self.hub_choice['state'] = 'disabled' if self.busy else 'readonly'
        for index, (_endpoint, choice, state, device, button) in enumerate(self.rows):
            choice['state'] = 'disabled' if self.busy else 'readonly'
            mapped = self.mapping[index]
            observed = self.hubs[mapped[0]]['ports'].get(mapped[1]) if mapped and mapped[0] in self.hubs else None
            if observed and fresh:
                state.set('● On' if observed['on'] else '○ Off')
                details = observed['details']
                device.set(details[details.find('['):] if '[' in details else ('Device connected' if 'connect' in details else 'No device reported'))
                button['text'] = 'Turn off' if observed['on'] else 'Turn on'
            else:
                state.set('Unknown')
                device.set('Refresh required' if mapped else 'Map a socket to begin')
                button['text'] = '—'
            button['state'] = 'normal' if observed and fresh and self.armed.get() and not self.busy else 'disabled'

    def toggle(self, index):
        endpoint = self.mapping[index]
        if self.busy or not endpoint or not self.armed.get() or time.perf_counter() - self.last_scan >= 30:
            return
        observed = self.hubs[endpoint[0]]['ports'][endpoint[1]]
        on = not observed['on']
        if not on and not messagebox.askokcancel('Turn off port?', f'Turn off socket {index + 1} ({endpoint[0]} / {endpoint[1]})?\nEject storage first. Connected devices will disconnect.'):
            return
        identity = self.hubs[endpoint[0]]['identity']
        self.status.set(f'Applying power {"on" if on else "off"} to socket {index + 1}…')
        self.busy = True
        self.render()
        # Capture the mapping/session before returning to Tk's event loop.
        self.root.after_idle(self.set_power, endpoint, on, identity, self.session_id)

    def set_power(self, endpoint, on, identity, session_id):
        try:
            result = self.controller.SetPower(endpoint, on, identity, session_id)
            self.apply_status(result)
        except Exception as error:
            self.show_connection_error(error)
        finally:
            self.busy = False
            self.render()

    def close(self):
        # Closing the GUI disconnects only; it never changes port power.
        self.controller.close()
        self.root.destroy()

    def diagnostics(self):
        window = tk.Toplevel(self.root)
        window.title('JazLabs USB Hub diagnostics')
        text = tk.Text(window, width=100, height=28, wrap='word', bg='#101923', fg='#e6edf3')
        text.pack(fill='both', expand=True)
        text.insert('1.0', self.raw or 'No discovery output yet.')
        text.configure(state='disabled')


if __name__ == '__main__':
    from JazLabs.launchers.launch_usb_hub_widget import main
    main()
