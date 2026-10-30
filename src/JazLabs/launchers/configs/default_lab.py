"""Example connections for JazLabs launchers and calibration commands.

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

SPOT_POWER_VIEWERS = [
    {
        "name": "cam_slm_spots",
        "camera_name": "cam_slm",
        "centres": None,  # Optional file of (y, x) centres; otherwise edit in the GUI.
        "radius_y": 3,
        "radius_x": 3,
        "dark_frame": None,
        "refresh_ms": 100,
    },
]

# Hardware examples are disabled for bulk launch until their connection details
# have been checked. Explicit --name launches still select disabled entries.
LASER_HOST = "127.0.0.1"
LASER_SERVERS = [
    {
        "name": "tunable_laser",
        "laser_type": "Anritsu MG963x",
        "laser_kwargs": {"port": "COM3"},  # Replace with the instrument's port.
        "command_port": 50921,
        "poll_timeout_ms": 100,
        "enabled": False,
    },
]

DAQ_SERVERS = [
    {
        "name": "daq",
        "host": "127.0.0.1",
        "command_port": 50831,
        "voltage_pub_port": 50832,
        "voltage_topic": "daq.voltages",
        "daq_type": "ni_daq",  # Also supports mcc_daq and coremorrow_daq.
        "device_num": 0,
        "channel_count": 2,
        "voltage_min": -10.0,  # Match the hardware and connected load.
        "voltage_max": 10.0,
        "refresh_time": 0.0,
        "serial_port": None,  # Set for a serial CoreMorrow controller.
        "publish_voltages_over_zmq": True,
        "enabled": False,
    },
]

OPTICAL_SWITCH_HOST = "127.0.0.1"
OPTICAL_SWITCH_SERVERS = [
    {
        "name": "optical_switch",
        "switch_type": "JDS_SC",
        "host": OPTICAL_SWITCH_HOST,
        "command_port": 50841,
        "serial_port": "COM4",  # Replace with the instrument's port.
        "serial_timeout": 2.0,
        "rtscts": True,
        "dsrdtr": True,
        "enabled": False,
    },
    {
        "name": "pol_switch",
        "switch_type": "JDS_Pol",
        "host": OPTICAL_SWITCH_HOST,
        "command_port": 50842,
        "serial_port": "COM5",
        "serial_timeout": 2.0,
        "rtscts": True,
        "dsrdtr": True,
        "enabled": False,
    },
]

MOTOR_SERVERS = [
    {
        "enabled": False,
        "name": "newport_tip_tilt",
        "host": "127.0.0.1",
        "client_host": "127.0.0.1",
        "command_port": 50941,
        "local_host": "127.0.0.1",
        "local_command_port": 51941,
        "remote_host": None,  # Hardware computer address for bridge use.
        "stage_type": "CONEXAGAPSerial",
        "stage_kwargs": {
            "port": None, "address": 1, "timeout": 0.5, "move_timeout": 30.0,
            "limits": {"U": [-0.7600, 0.7600], "V": [-0.7600, 0.7600]},
        },  # Calibrate U/V limits in degrees for the installed mount.
        "limits": {},  # Optional narrower server limits.
        "default_axis": "U",  # U = yaw, V = pitch.
        "relative_step": 0.005,
        "expected_units": "deg",
    },
    {
        "enabled": False,
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
            "limits": {"X": [0, 27]},  # Calibrate endpoints in the fitted stage's units.
        },
        "limits": {},  # Optional narrower server limits.
        "default_axis": "X",
        "relative_step": 0.1,
        "expected_units": "mm",
    },
    {
        "enabled": False,
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
        "enabled": False,
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
    "remote_host": "127.0.0.1",

    "remote_command_port": 5555,
    "remote_display_pub_port": 5556,
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

# Digital holography is a viewer of the camera above, not a separate server.
DIGITAL_HOLOGRAPHY_CONFIG = {
    "camera_name": "cam_slm",
    "pixel_size_m": 6.9e-6,
    "wavelength_m": 1550e-9,
    "fft_radius": 0.4,
    "max_mode_group": 3,
}

# Power meters currently use direct driver objects, without a server launcher.
# Example for the Santec driver; replace the VISA resource with your device.
POWER_METER_CONFIG = {
    "resource": "GPIB0::1::INSTR",
    "units": "mW",
}
