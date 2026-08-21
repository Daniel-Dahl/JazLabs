"""Connect to a DAC, set one channel voltage, and read it back."""

from JazLabs.hardware.DAQ_Controller.DAQ_stack.DAQ_Client import DAQClient


HOST = "127.0.0.1"
COMMAND_PORT = 50831
VOLTAGE_PORT = 50832
CHANNEL = 0
VOLTAGE = 0.5


dac = DAQClient(
    host=HOST,
    command_port=COMMAND_PORT,
    voltage_pub_port=VOLTAGE_PORT,
)

try:
    dac.SetVoltage(CHANNEL, VOLTAGE)
    print("Voltage:", dac.GetVoltage(CHANNEL))
finally:
    dac.close()
