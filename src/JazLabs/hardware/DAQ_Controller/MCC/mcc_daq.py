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

        self.RefreshTime = RefreshTime
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

        if self.RefreshTime > 0:
            time.sleep(self.RefreshTime)


    def SetRefreshTime(self, NewRefreshTime):
        # Update the refresh time.
        if NewRefreshTime > 0:
            self.RefreshTime = NewRefreshTime
        else:
            print("Refresh time must be positive.")