from pathlib import Path


TMUX_SESSION = "jazlabs_servers"

CAMERA_HOST = "127.0.0.1"
JAZLABS_ROOT = Path(__file__).resolve().parents[4]
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

SLM_SERVER = {
    "name": "slm_server",
    "host": "0.0.0.0",
    "viewer_host": "127.0.0.1",
    "command_port": 5555,
    "display_pub_port": 5556,
    "display_topic": "slm.display",
    "slm_type": "Blink OverDrive Plus",
    # Blink SLMs use board_number; HDMI SLMs use monitor_index.
    "board_number": 1,
    "monitor_index": 1,
    "refresh_rate": 0,
    "lut_file": None,
    "timeout_ms": 5000,
    "enabled": True,
}

SLM_VIEWER = {
    "host": "127.0.0.1",
    "command_port": SLM_SERVER["command_port"],
    "display_pub_port": SLM_SERVER["display_pub_port"],
    "window_name": "HDStokes SLM viewer",
    "zoom": 0.2,
    "fps": 30,
    "timeout_ms": SLM_SERVER["timeout_ms"],
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
JAZLABS_ROOT = Path(__file__).resolve().parents[4]

SLM_CENTER_ALIGNMENT_CONFIG = {
    # Camera measurement window, determined with the camera viewer.
    "x_beam_center_on_camera": 64,
    "y_beam_center_on_camera": 64,
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
    "camera_command_port": CAMERA_SERVERS[1]["command_port"],
    "camera_frame_port": CAMERA_SERVERS[1]["frame_pub_port"],
    "camera_timeout_ms": 60000,
    "camera_client_id": "slm_center_alignment",
    "slm_host": SLM_SERVER["viewer_host"],
    "slm_command_port": SLM_SERVER["command_port"],
    "slm_display_port": SLM_SERVER["display_pub_port"],
    "slm_timeout_ms": SLM_SERVER["timeout_ms"],

    # SLM properties.
    "slm_pixel_size": 17e-6,
    "slm_wavelength": 1550e-9,
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
    "load_saved_properties_after_alignment": True,
    "run_beam_radius_scan": False,
    "save_plots": True,
    "show_plots": True,
    "plot_file_format": "png",
    "output_directory": JAZLABS_ROOT / "data" / "SLM" / "CenterAlignment",
}
