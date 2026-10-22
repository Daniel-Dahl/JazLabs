"""Serial-only motor setups for the motor server, bridge, widget and notebook.

Replace each hardware port with its OS serial port. Limits are deliberately
unset until calibrated for the installed mechanism. The simulation needs no
serial hardware and can be used to exercise the same client/server path.
"""

MOTOR_SERVERS = [
    {
        "name": "newport_tip_tilt",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50941,
        "local_host": "127.0.0.1",
        "local_command_port": 51941,
        "remote_host": None,  # Hardware computer address for bridge use.
        "stage_type": "CONEXAGAPSerial",
        "stage_kwargs": {"port": None, "address": 1, "timeout": 0.5, "move_timeout": 30.0},
        "limits": {"U": [-0.7600, 0.7600], "V": [-0.7600, 0.7600]},  # Add calibrated U/V limits in degrees to enable sliders.
        "default_axis": "U",  # U = yaw, V = pitch.
        "relative_step": 0.005,
        "expected_units": "deg",
    },
    {
        "name": "newport_translation",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50942,
        "local_host": "127.0.0.1",
        "local_command_port": 51942,
        "remote_host": None,  # Hardware computer address for bridge use.
        "stage_type": "CONEXAGPSerial",
        "stage_kwargs": {
            "port": None, "address": 1, "timeout": 0.5, "move_timeout": 30.0,
            "units": "mm",  # Label only: verify that this matches the fitted AGP stage.
        },
        "limits": {"X": [0, 27]},  # Add calibrated X endpoints in the stage's configured units.
        "default_axis": "X",
        "relative_step": 0.1,
        "expected_units": "mm",
    },
    {
        "name": "thorlabs_umc2",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50943,
        "local_host": "127.0.0.1",
        "local_command_port": 51943,
        "remote_host": None,  # Hardware computer address for bridge use.
        "stage_type": "UMC2Serial",
        "stage_kwargs": {
            "port": None, "baudrate": 115200, "timeout": 0.25,
            "move_timeout": 60.0, "destinations": (0x21, 0x22),
            "detect_stages": True,
            "mounts": {
                # Declare mm only for linear stages/actuators. Stage replies
                # supply counts-per-unit but do not distinguish mm/degrees.
                "X": {"label": "Mount 1", "physical_units": "mm", "units": "auto"},
                "Y": {"label": "Mount 2", "physical_units": "mm", "units": "auto"},
                # If detection is unavailable, add counts_per_mm and limits_mm
                # to each mount using that actuator's verified calibration.
            },
        },
        "limits": {},  # Optional narrower limits, in each mount's advertised units.
        "default_axis": "X",  # X/Y map to the first/second controller bays.
        "relative_step": 100,
        "expected_units": "auto",
    },
    {
        "name": "simulation",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50944,
        "local_host": "127.0.0.1",
        "local_command_port": 51944,
        "remote_host": None,  # Hardware computer address for bridge use.
        "stage_type": "simulation",
        "stage_kwargs": {"axes": 2, "absolute_sensor": False},
        "limits": {},
        "default_axis": "X",
        "relative_step": 0.01,
        "expected_units": "mm",
    },
]
