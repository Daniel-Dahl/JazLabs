from pathlib import Path


TMUX_SESSION = "jazlabs_servers"

CAMERA_HOST = "127.0.0.1"

HDSTOKES_WORKSPACE = Path(__file__).resolve().parents[5]

CAMERA_SERVERS = [
    {
        "name": "cam_mplc_1",
        "camera_type": "Xeva",
        "camera_serial_number": '5920',
        "command_port": 50731,
        "frame_pub_port": 50732,
        "frame_topic": "camera.frame",
        "poll_sleep": 0.0000,
        "verbose": False,
    },
    {
            "name": "cam_mplc_2",
            "camera_type": "Xeva",
            "camera_serial_number": '8755',
            "command_port": 50733,
            "frame_pub_port": 50734,
            "frame_topic": "camera.frame",
            "poll_sleep": 0.0000,
            "verbose": False,
        },
    {
                "name": "cam_mplc_3",
                "camera_type": "Allied Vision",
                "camera_serial_number": '8755',
                "command_port": 50735,
                "frame_pub_port": 50736,
                "frame_topic": "camera.frame",
                "poll_sleep": 0.0000,
                "verbose": False,
            },
]



# Set host to "0.0.0.0" on the laser computer to accept remote clients.
# Change laser_type/laser_kwargs here if the connected laser is not the
# Anritsu MG963x on COM3. Kept disabled so `jazlabs-tmux all` is unchanged.
LASER_HOST = "127.0.0.1"

LASER_SERVERS = [
    {
        "name": "tunable_laser",
        "laser_type": "NKT BasiK",
        "laser_kwargs": {"port": "COM3"},
        "command_port": 50931,
        "poll_timeout_ms": 100,
        "enabled": False,
    },
]
SLM_BRIDGE = {
    "name": "slm_bridge",
    "local_host": "127.0.0.1",
    "local_command_port": 5565,
    "local_display_pub_port": 5566,
    # "remote_host": "10.161.4.65",
    "remote_host": "127.0.0.1",

    "remote_command_port": 15555,
    "remote_display_pub_port": 15556,
    "display_topic": "slm.display",
    "timeout_ms": 30000,
    "poll_sleep": 0.0,
    "enabled": True,
}

SLM_SERVER = {
    "name": "slm_server",
    "host": "0.0.0.0",
    "command_port": 5555,
    "display_pub_port": 5556,
    "display_topic": "slm.display",
    "slm_type": "HDMI SLM",
    "board_number": 1,
    "monitor_index": 2,
    "refresh_rate": 0.5,
    "lut_file": None,
    "timeout_ms": 5000,
    "enabled": False,
}

SLM_VIEWER = {
    "host": SLM_BRIDGE["local_host"],
    "command_port": SLM_BRIDGE["local_command_port"],
    "display_pub_port": SLM_BRIDGE["local_display_pub_port"],
    "window_name": "SLM viewer",
    "zoom": 0.2,
    "fps": 30,
    "timeout_ms": SLM_BRIDGE["timeout_ms"],
}
