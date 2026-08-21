"""Connect to an optical switch, read its port, and select another port."""

from JazLabs.hardware.OpticalSwitch.OpticalSwitch_Client import OpticalSwitchClient


HOST = "127.0.0.1"
COMMAND_PORT = 50831
NEW_PORT = 2


optical_switch = OpticalSwitchClient(host=HOST, command_port=COMMAND_PORT)

try:
    print("Current port:", optical_switch.GetChannel())
    optical_switch.SetChannel(NEW_PORT)
    print("New port:", optical_switch.GetChannel())
finally:
    optical_switch.close()
