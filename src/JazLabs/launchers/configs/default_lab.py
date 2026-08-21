"""Default camera and SLM setup used by the calibration commands.

Copy this file or pass another JazLabs launcher config with ``--config`` when
the host names, ports, camera, wavelength, or measurement window differ.
"""

from pathlib import Path


TMUX_SESSION = "jazlabs_servers"
CAMERA_HOST = "127.0.0.1"
JAZLABS_ROOT = Path(__file__).resolve().parents[4]

CAMERA_SERVERS = [
    {
        "name": "cam_slm",
        "camera_type": "FLIR",
        # Required: replace with the serial number printed on the camera.
        "camera_serial_number": None,
        "command_port": 50731,
        "frame_pub_port": 50732,
        "frame_topic": "camera.frame",
        "poll_sleep": 1e-12,
        "verbose": False,
    },
]

TIME_TAGGER_SERVERS = [
    {
        "name": "time_tagger",
        "host": "0.0.0.0",
        "command_port": 50931,
        "serial": None,
        "create_kwargs": {},
        "poll_timeout_ms": 100,
        # Enable after this config is copied to the Time Tagger host.
        "enabled": False,
    },
]

DARK_FRAME_CONFIG = {
    "camera_name": "cam_slm",
    "num_frames": 100,
    "description": "",
    "output_directory": JAZLABS_ROOT / "data" / "Camera" / "DarkFrames",
    "save_preview": True,
    "camera_timeout_ms": 60000,
    "camera_client_id": "camera_dark_frame",
}

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
    "monitor_index": 1,
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

# Optional pyMilk SLM transport. Uncomment these settings only when using the
# explicit jazlabs-*-slm-milk commands.
#
# SLM_MILK_SHM_NAME = "slm_shared"
#
# SLM_MILK_BRIDGE = {
#     "name": "slm_milk_bridge",
#     "client_id": "slm_milk_bridge",
#     "shm_name": SLM_MILK_SHM_NAME,
#     "confirmed_shm_name": f"{SLM_MILK_SHM_NAME}_confirmed",
#     "bind_host": "127.0.0.1",
#     "local_command_port": 5565,
#     "server_host": "10.161.4.65",
#     "server_command_port": 5555,
#     "server_image_port": 5556,
#     "server_ack_port": 5557,
#     "image_topic": "slm.image",
#     "ack_topic": "slm.ack",
#     "timeout_ms": 5000,
#     "create_shm": True,
#     "acquire_control": False,
#     "poll_timeout_s": 1e-3,
#     "enabled": True,
# }
#
# SLM_MILK_SERVER = {
#     "name": "slm_milk_server",
#     "host": "0.0.0.0",
#     "command_port": 5555,
#     "image_sub_port": 5556,
#     "ack_pub_port": 5557,
#     "image_topic": "slm.image",
#     "ack_topic": "slm.ack",
#     "slm_type": "Blink Plus",
#     "board_number": 1,
#     "monitor_index": 1,
#     "refresh_rate": 0.5,
#     "lut_file": None,
#     "enabled": False,
# }

SLM_CENTER_ALIGNMENT_CONFIG = {
    # Camera measurement window, determined with the camera viewer.
    "x_beam_center_on_camera": 48,
    "y_beam_center_on_camera": 48,
    "x_beam_window_width": 30,
    "y_beam_window_width": 30,

    # Alignment settings.
    "slm_channel": "Red",
    "polarisation": "H",
    "stripe_width": 15,
    "mask_size": [600, 600],
    "coarse_step_count": 100,
    "coarse_starting_sweep_point": 0,
    "beam_radius_scan_initial_radius": 1,
    "beam_radius_scan_final_radius": 150,
    "beam_radius_scan_step": 1,
    "average_frame_count": 1,
    "coarse_metric_type": "POWERMinusHalfRef",
    "fine_metric_type": "POWERMinusHalfRef",
    "beam_radius_metric_type": "POWER",

    # Camera and SLM bridge connections.
    "camera_host": CAMERA_HOST,
    "camera_command_port": CAMERA_SERVERS[0]["command_port"],
    "camera_frame_port": CAMERA_SERVERS[0]["frame_pub_port"],
    "camera_timeout_ms": 60000,
    "camera_client_id": "slm_center_alignment",
    "slm_host": SLM_BRIDGE["local_host"],
    "slm_command_port": SLM_BRIDGE["local_command_port"],
    "slm_display_port": SLM_BRIDGE["local_display_pub_port"],
    "slm_timeout_ms": SLM_BRIDGE["timeout_ms"],

    # SLM properties.
    "slm_pixel_size": 17e-6,
    "slm_wavelength": 600e-9,
    "slm_refresh_time": 40e-3,
    "load_lut_from_file": False,
    "slm_lut_file": (
        JAZLABS_ROOT
        / "calibrations"
        / "SLM"
        / "CustomLutFiles"
        / "SLM_PhaseCalibration_New_2.lut"
    ),

    # Saved mask properties, plots, and optional radius estimate.
    "mask_properties_filename": "SLM_CenterAlignment",
    "save_mask_properties": True,
    "load_saved_properties_after_alignment": False,
    "run_beam_radius_scan": True,
    "save_plots": True,
    "show_plots": True,
    "plot_file_format": "png",
    "output_directory": JAZLABS_ROOT / "data" / "SLM" / "CenterAlignment",
}
