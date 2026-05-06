import time
import numpy as np
import nidaqmx
from nidaqmx.constants import AcquisitionType, TerminalConfiguration

class DAQObject():

    def __init__(self,
                RefreshRate=0.0,
                deviceNum=0,
                ChannelCount=2,
                min_val=-10.0,
                max_val=10.0):
        
        self.RefreshRate = RefreshRate
        self.deviceNum = deviceNum
        self.ChannelCount = ChannelCount
        self.min_val = min_val
        self.max_val = max_val

        if deviceNum == 0:
            device_name = "Dev1"
        else:
            raise ValueError(f"Device {deviceNum} does not exist.")

        self.tasks = []
        for ch in range(ChannelCount):
            task = nidaqmx.Task()
            task.ao_channels.add_ao_voltage_chan(
                f"{device_name}/ao{ch}",
                min_val=min_val,
                max_val=max_val,
            )
            self.tasks.append(task)

    def shutdown(self, zero=False):
        if zero:
            # Zero all channel voltages
            for task in self.tasks:
                task.write(0.0, auto_start=True)

        # Stop and close all tasks
        for task in self.tasks:
            task.stop()
            task.close()

    def SetVoltage(self, channel, voltage):
        if not 0 <= channel < self.ChannelCount:
            raise ValueError(f"Channel {channel} does not exist (max {self.ChannelCount - 1}).")
            # print(f"Channel {channel} does not exist (max {self.ChannelCount - 1}).") # change to raise an exception??
            # return

        self.tasks[channel].write(float(voltage), auto_start=True)

        if self.RefreshRate > 0:
            time.sleep(self.RefreshRate)

    def SetRefreshRate(self, NewRefreshRate):
        # Update the refresh rate
        if NewRefreshRate >= 0:
            self.RefreshRate = NewRefreshRate
        else:
            print("Refresh time must be non-negative.")