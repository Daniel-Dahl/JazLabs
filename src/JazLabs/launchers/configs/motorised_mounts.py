"""Serial-only motor setups for the motor notebook and jazlabs-motors launcher.

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
        "stage_type": "CONEXAGAPSerial",
        "stage_kwargs": {"port": None, "address": 1, "timeout": 0.5, "move_timeout": 30.0},
        "limits": {},  # Add calibrated U/V limits in degrees to enable sliders.
        "default_axis": "U",  # U = yaw, V = pitch.
        "relative_step": 0.005,
        "expected_units": "deg",
    },
    {
        "name": "newport_translation",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50942,
        "stage_type": "CONEXAGPSerial",
        "stage_kwargs": {
            "port": None, "address": 1, "timeout": 0.5, "move_timeout": 30.0,
            "units": "mm",  # Label only: verify that this matches the fitted AGP stage.
        },
        "limits": {},  # Add calibrated X endpoints in the stage's configured units.
        "default_axis": "X",
        "relative_step": 0.01,
        "expected_units": "mm",
    },
    {
        "name": "thorlabs_umc2",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50943,
        "stage_type": "UMC2Serial",
        "stage_kwargs": {
            "port": None, "baudrate": 115200, "timeout": 0.25,
            "move_timeout": 60.0, "destinations": (0x21, 0x22),
        },
        "limits": {},  # Native counts; set endpoints for the fitted stages.
        "default_axis": "X",  # X/Y map to the first/second controller bays.
        "relative_step": 100,
        "expected_units": "counts",
    },
    {
        "name": "simulation",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50944,
        "stage_type": "simulation",
        "stage_kwargs": {"axes": 2, "absolute_sensor": False},
        "limits": {},
        "default_axis": "X",
        "relative_step": 0.01,
        "expected_units": "mm",
    },
]
