TMUX_SESSION = "jazlabs_servers"

CAMERA_HOST = "127.0.0.1"

CAMERA_SERVERS = [
    {
        "name": "cam_oah",
        "camera_type": "Lucid Vision",
        "camera_idx": 0,
        "command_port": 50733,
        "frame_pub_port": 50734,
        "frame_topic": "camera.frame",
        "poll_sleep": 1e-12,
        "verbose": False,
    },
    
]

SLM_SHM_NAME = "slm_shared"

SLM_BRIDGE = {
    "name": "slm_bridge",
    "client_id": "slm_bridge",
    "shm_name": SLM_SHM_NAME,
    "bind_host": "127.0.0.1",
    "local_command_port": 5565,
    "server_host": "10.196.0.67",
    "server_command_port": 5555,
    "server_image_port": 5556,
    "server_ack_port": 5557,
    "image_topic": "slm.image",
    "ack_topic": "slm.ack",
    "timeout_ms": 5000,
    "create_shm": True,
    "acquire_control": False,
    "poll_timeout_s": 1e-3,
}

SLM_SERVER = {
    "name": "slm_server",
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
