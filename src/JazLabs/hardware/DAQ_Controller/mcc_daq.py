from mcculw import ul
from mcculw.enums import ULRange
import numpy as np
import time


class DAQObject():
    def __init__(self, 
                 RefreshTime=0.0, 
                 deviceNum=0,
                 ChannelCount=4, 
                 voltage_range=ULRange.BIP10VOLTS):

        self.RefreshRate = RefreshTime
        self.boardNumber = deviceNum
        self.ChannelCount = ChannelCount
        self.voltage_range = voltage_range


    def shutdown(self, zero=False):
        if zero:
            # Zero all channel voltages
            for ichan in range(self.ChannelCount):
                ul.v_out(self.boardNumber, ichan, self.voltage_range, 0)

        # Release the board
        ul.release_daq_device(self.boardNumber)


    def SetVoltage(self, channel, voltage):
        # Set voltage on a single DAC channel, then throttle."""
        if channel < self.ChannelCount:
            ul.v_out(self.boardNumber, channel, self.voltage_range, float(voltage))
        else:
            print(f"Channel {channel} does not exist (max {self.ChannelCount - 1}).")

        if self.RefreshRate > 0:
            time.sleep(self.RefreshRate)


    def SetRefreshRate(self, NewRefreshRate):
        # Update the refresh rate.
        if NewRefreshRate > 0:
            self.RefreshRate = NewRefreshRate
        else:
            print("Refresh rate must be positive.")