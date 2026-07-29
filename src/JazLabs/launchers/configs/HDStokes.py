from pathlib import Path


TMUX_SESSION = "jazlabs_servers"

CAMERA_HOST = "127.0.0.1"

HDSTOKES_WORKSPACE = Path(__file__).resolve().parents[5]

CAMERA_SERVERS = [
    {
        "name": "cam_pl",
        "camera_type": "First Light C-Red3_2Lite",
        "camera_serial_number": '01-00000c86ca65',
        "command_port": 50731,
        "frame_pub_port": 50732,
        "frame_topic": "camera.frame",
        "poll_sleep": 0.0000,
        "verbose": False,
    },
    {
        "name": "cam_slm",
        "camera_type": "First Light C-Red3_2Lite",
        "camera_serial_number": '01-00001de3043d',
        "command_port": 50733,
        "frame_pub_port": 50734,
        "frame_topic": "camera.frame",
        "poll_sleep": 0.0000,
        "verbose": False,
    },
    {
        "name": "cam_backref",
        "camera_type": "First Light C-Red3_2Lite",
        "camera_serial_number": '01-00001b284082 ',
        "command_port": 50735,
        "frame_pub_port": 50736,
        "frame_topic": "camera.frame",
        "poll_sleep": 0.0000,
        "verbose": False,
        "enabled": False,
    },
]

SPOT_POWER_VIEWERS = [
    {
        "name": "cam_backref_spots",
        "camera_name": "cam_backref",
        "centres": (
            HDSTOKES_WORKSPACE
            / "Data"
            / "HDStokes"
            / "OrderedSpotCenters__Vgroove_HandAdjustment.npy"
        ),
        "radius_y": 3,
        "radius_x": 3,
        "dark_frame": (
            HDSTOKES_WORKSPACE
            / "Data"
            / "darkframe_1000frames_vgroovecam_exp20ms_64x256.npy"
        ),
        "refresh_ms": 100,
    },
]

# Set host to "0.0.0.0" on the laser computer to accept remote clients.
# Change laser_type/laser_kwargs here if the connected laser is not the
# Anritsu MG963x on COM3. Kept disabled so `jazlabs-tmux all` is unchanged.
LASER_HOST = "127.0.0.1"

LASER_SERVERS = [
    {
        "name": "tunable_laser",
        "laser_type": "Anritsu MG963x",
        "laser_kwargs": {"port": "COM3"},
        "command_port": 50931,
        "poll_timeout_ms": 100,
        "enabled": False,
    },
]

SLM_STACK_SERVER = {
    "name": "slm_stack",
    "host": "0.0.0.0",
    "viewer_host": "127.0.0.1",
    "command_port": 5555,
    "display_pub_port": 5556,
    "display_topic": "slm.display",
    "slm_type": "Blink OverDrive Plus",
    "refresh_rate": 0,
    "lut_file": None,
    "timeout_ms": 5000,
    "enabled": True,
}

SLM_STACK_VIEWER = {
    "host": "127.0.0.1",
    "command_port": SLM_STACK_SERVER["command_port"],
    "display_pub_port": SLM_STACK_SERVER["display_pub_port"],
    "window_name": "HDStokes SLM viewer",
    "zoom": 0.2,
    "fps": 30,
    "timeout_ms": SLM_STACK_SERVER["timeout_ms"],
}

DAQ_SERVERS = [
    {
        "name": "daq",
        "host": "10.196.0.67",
        "command_port": 50831,
        "voltage_pub_port": 50832,
        "voltage_topic": "daq.voltages",
        "daq_type": "ni_daq",
        "device_num": 0,
        "channel_count": 2,
        "voltage_min": -10.0,
        "voltage_max": 10.0,
        "refresh_time": 0.0,
        "serial_port": None,
        "publish_voltages_over_zmq": True,
        "enabled": False,
    },
    {
        "name": "coremorrow_mount",
        "host": "127.0.0.1",
        "command_port": 50833,
        "voltage_pub_port": 50834,
        "voltage_topic": "coremorrow_mount.voltages",
        "daq_type": "coremorrow_daq",
        "device_num": 0,
        "channel_count": 3,
        "voltage_min": 0.0,
        "voltage_max": 120.0,
        "refresh_time": 0.0,
        "serial_port": "/dev/ttyACM0",
        "publish_voltages_over_zmq": True,
        "enabled": True,
    },
]
