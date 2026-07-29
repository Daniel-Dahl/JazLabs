TMUX_SESSION = "jazlabs_servers"

CAMERA_HOST = "127.0.0.1"

CAMERA_SERVERS = [
    {
        "name": "cam_oah",
        "camera_type": "First Light C-Red3_2Lite",
        "camera_serial_number": '01-00001de3be41',
        "command_port": 50731,
        "frame_pub_port": 50732,
        "frame_topic": "camera.frame",
        "poll_sleep": 1e-6,
        "verbose": False,
    },
    
]
# Laser server configuration.  Set the host to "0.0.0.0" on the machine
# connected to the laser when clients will connect from another computer.
# Change laser_type and laser_kwargs to match the instrument and connection.
LASER_HOST = "127.0.0.1"
# LASER_HOST = "10.196.64.172"
LASER_SERVERS = [
    {
        "name": "Anritsu",
        "laser_type": "Anritsu MG963x",
        "laser_kwargs": {"port": "COM3"},
        "command_port": 50631,
        "poll_timeout_ms": 100,
        # Keep disabled until the correct laser connection details are set.
        "enabled": False,
    },
    {
            "name": "JDS",
            "laser_type": "JDS Tunable",
            "laser_kwargs": {"port": "GPIB0::1::INSTR"},
            "command_port": 50632,
            "poll_timeout_ms": 100,
            # Keep disabled until the correct laser connection details are set.
            "enabled": False,
        },
]
OPTICAL_SWITCH_HOST = "127.0.0.1"

OPTICAL_SWITCH_SERVERS = [
    {
        "name": "pol_switch",
        "switch_type": "JDS_Pol",
        "host": OPTICAL_SWITCH_HOST,
        "command_port": 50832,
        "serial_port": "COM4",
        "serial_timeout": 2.0,
        "rtscts": True,
        "dsrdtr": True,
        "enabled": True,
    },
    {
        "name": "optical_switch",
        "switch_type": "JDS_SC",
        "host": OPTICAL_SWITCH_HOST,
        "command_port": 50831,
        "serial_port": "COM12",
        "serial_timeout": 2.0,
        "rtscts": True,
        "dsrdtr": True,
        "enabled": True,
    },
]



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
    
]
