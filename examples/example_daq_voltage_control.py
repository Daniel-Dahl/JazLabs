import numpy as np
from datetime import datetime
import time

from pwi_inst.hardware.DAQ_Controller.mcc_daq import DAQObject

# Select DAQ model to use
daq_model = 'mcc_daq' # 'ni_daq' or 'mcc_daq'

# Set DAQ parameters
n_channels = 3 # number of DAQ channels
refresh_rate = 0.05
device_number = 0 # board number for MCC DAQ or device number for NI DAQ (e.g. 0="Dev1")

## Set initial voltages for each channel (V) [tip, tilt, attn]
init_volts = [-0.5, 6, 0]

## If True, voltages will return to zero when DAQ is shut down at end of script
zero_daq = False


if __name__ == '__main__':
    # Import camera library based on model
    if daq_model == 'mcc_daq':
        import pwi_inst.hardware.DAQ_Controller.mcc_daq as DAQLib
    elif daq_model == 'ni_daq':
        import pwi_inst.hardware.DAQ_Controller.ni_daq as DAQLib
    else:
        raise ValueError('Unknown DAQ model specified')

    # Initialize DAC controller
    DAC_Controller = DAQLib.DAQObject(RefreshTime=refresh_rate,
                                       deviceNum=device_number,
                                       ChannelCount=n_channels)

    # Set channel voltages to initial values
    for ch in range(n_channels):
        DAC_Controller.SetVoltage(channel=ch, voltage=init_volts[ch])

    time.sleep(1) # hold voltages for 1 second before shutting down

    # Release the board and zero channels if required
    DAC_Controller.shutdown(zero=zero_daq)



