import time
import nidaqmx
from nidaqmx.system import System

class DAQObject():

    def __init__(self,
                 RefreshTime=0.0,
                 deviceNum=0,
                 ChannelCount=2):

        self.RefreshTime = RefreshTime
        self.deviceNum = deviceNum
        self.ChannelCount = ChannelCount

        # ----------------------------
        # Select device
        # ----------------------------
        if deviceNum == 0:
            self.device_name = "Dev1"
        else:
            raise ValueError(f"Device {deviceNum} does not exist.")

        # ----------------------------
        # Query hardware voltage limits
        # ----------------------------
        self.hardware_min, self.hardware_max = self.GetHardwareVoltageLimits()

        print(
            f"{self.device_name} analogue output range: "
            f"{self.hardware_min} V to {self.hardware_max} V"
        )

        # ----------------------------
        # Create output tasks
        # ----------------------------
        self.tasks = []

        for ch in range(ChannelCount):

            task = nidaqmx.Task()

            task.ao_channels.add_ao_voltage_chan(
                f"{self.device_name}/ao{ch}",
                min_val=self.hardware_min,
                max_val=self.hardware_max,
            )

            self.tasks.append(task)

    # ==========================================================
    # Hardware Information
    # ==========================================================

    def GetHardwareVoltageLimits(self):

        system = System.local()
        device = system.devices[self.device_name]

        ao_voltage_rngs = device.ao_voltage_rngs

        # Example:
        # [-10.0, 10.0]
        # or
        # [-1.0, 1.0, -5.0, 5.0, -10.0, 10.0]

        min_voltage = min(ao_voltage_rngs)
        max_voltage = max(ao_voltage_rngs)

        return min_voltage, max_voltage

    def GetSupportedVoltageRanges(self):

        system = System.local()
        device = system.devices[self.device_name]

        return device.ao_voltage_rngs

    # ==========================================================
    # Output Control
    # ==========================================================

    def SetVoltage(self, channel, voltage):

        if not 0 <= channel < self.ChannelCount:
            raise ValueError(
                f"Channel {channel} does not exist "
                f"(max {self.ChannelCount - 1})."
            )

        # Prevent invalid voltages
        if voltage < self.hardware_min or voltage > self.hardware_max:
            raise ValueError(
                f"Voltage {voltage} V is outside hardware limits "
                f"({self.hardware_min} V to {self.hardware_max} V)."
            )

        self.tasks[channel].write(float(voltage), auto_start=True)

        if self.RefreshTime > 0:
            time.sleep(self.RefreshTime)

    def SetRefreshTime(self, NewRefreshTime):

        if NewRefreshTime >= 0:
            self.RefreshTime = NewRefreshTime
        else:
            raise ValueError("Refresh time must be non-negative.")

    # ==========================================================
    # Shutdown
    # ==========================================================

    def shutdown(self, zero=False):

        if zero:
            for task in self.tasks:
                task.write(0.0, auto_start=True)

        for task in self.tasks:
            task.stop()
            task.close()
            
            
  