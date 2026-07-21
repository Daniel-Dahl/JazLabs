TMUX_SESSION = "jazlabs_servers"

CAMERA_HOST = "127.0.0.1"

CAMERA_SERVERS = [
    {
        "name": "cam_oah",
        "camera_type": "First Light C-Red3_2Lite",
        "camera_idx": 0,
        "command_port": 50731,
        "frame_pub_port": 50732,
        "frame_topic": "camera.frame",
        "poll_sleep": 1e-12,
        "verbose": False,
    },
    {
        "name": "cam_PL",
        "camera_type": "First Light C-Blue",
        "camera_idx": 0,
        "command_port": 50733,
        "frame_pub_port": 50734,
        "frame_topic": "camera.frame",
        "poll_sleep": 1e-12,
        "verbose": False,
    },
    {
        "name": "cam_backref",
        "camera_type": "FLIR",
        "camera_idx": 1,
        "command_port": 50735,
        "frame_pub_port": 50736,
        "frame_topic": "camera.frame",
        "poll_sleep": 1e-12,
        "verbose": False,
        "enabled": False,
    },
]

OPTICAL_SWITCH_HOST = "127.0.0.1"

OPTICAL_SWITCH_SERVERS = [
    {
        "name": "pol_switch",
        "switch_type": "JDS_Pol",
        "host": OPTICAL_SWITCH_HOST,
        "command_port": 50835,
        "serial_port": "/dev/ttyUSB0",
        "serial_timeout": 2.0,
        "rtscts": True,
        "dsrdtr": True,
        "enabled": True,
    },
    {
        "name": "optical_switch",
        "switch_type": "JDS_SC",
        "host": OPTICAL_SWITCH_HOST,
        "command_port": 50836,
        "serial_port": "/dev/ttyUSB1",
        "serial_timeout": 2.0,
        "rtscts": True,
        "dsrdtr": True,
        "enabled": True,
    },
]

SLM_SHM_NAME = "slm_linux_shared"

SLM_LINUX_SERVER = {
    "name": "slm",
    "client_id": "linux_shm_server",
    "shm_name": SLM_SHM_NAME,
    "bind_host": "127.0.0.1",
    "local_command_port": 5565,
    "windows_host": "10.196.0.67",
    "windows_command_port": 5555,
    "windows_image_port": 5556,
    "windows_ack_port": 5557,
    "image_topic": "slm.image",
    "ack_topic": "slm.ack",
    "timeout_ms": 5000,
    "create_shm": True,
    "acquire_control": False,
    "poll_timeout_s": 1e-3,
}

SLM_WINDOWS_SERVER = {
    "name": "slm_windows",
    "host": "0.0.0.0",
    "command_port": 5555,
    "image_sub_port": 5556,
    "ack_pub_port": 5557,
    "image_topic": "slm.image",
    "ack_topic": "slm.ack",
    "slm_type": "Blink Plus",
    "refresh_rate": 0.5,
    "lut_file": None,
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
