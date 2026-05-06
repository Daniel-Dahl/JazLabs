import pyvisa
import numpy as np
import matplotlib.pyplot as plt

class OscScope:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, ScopeID='USB0::1689::931::C016906::0::INSTR'):
        """
        Initializes the oscilloscope connection and retrieves basic configuration.

        Args:
            ScopeID (str): The VISA identifier for the oscilloscope device.
        """
        rm = pyvisa.ResourceManager()  # Initialize the VISA resource manager
        self.ScopeID = ScopeID
        self.scope = rm.open_resource(self.ScopeID, timeout=50000)  # Open connection to the oscilloscope
        
        # Identify the connected oscilloscope
        idn = self.scope.query("*IDN?")  # Send IDN query to retrieve device information
        print("Connection successful. Device ID:", idn)
        
        # Retrieve the number of data points (record length)
        self.Ndata = int(self.scope.query('HORizontal:RECOrdlength?'))

    def __del__(self):
        """Destructor to disconnect the oscilloscope."""
        print("Scope has been disconnected")
        self.scope.close()  # Close the VISA connection

    def Getdata(self, Plotdata=False, Channel='1'):
        """
        Retrieves waveform data from the oscilloscope and optionally plots it.

        Args:
            Plotdata (bool): Whether to plot the retrieved data.
            Channel (str): Oscilloscope channel to retrieve data from.

        Returns:
            tuple: (time_axis, voltages) where time_axis is the time points and voltages are the corresponding signal values.
        """
        # Set the data source and format
        self.scope.write(f"DATA:SOU CH{Channel}")
        self.scope.write('DATA:WIDTH 1')  # Set data width to 1 byte
        self.scope.write(":WAV:FORM BYTE")  # Set waveform format to 8-bit binary
        
        # Retrieve raw waveform data
        waveform = self.scope.query_binary_values("CURVE?", datatype='b', container=np.array)
        
        # Retrieve scaling factors for proper unit conversion
        yscale = self.GetYScale()
        yoffset = self.GetYOffset()
        x_increment = self.GetXIncrement()
        x_zero = self.GetXZero()
        
        # Convert raw data to proper voltage values and time axis
        self.voltages = (waveform - yoffset) * yscale
        self.time_axis = np.arange(0, self.Ndata) * x_increment + x_zero
        
        # Optionally plot the data
        if Plotdata:
            plt.figure(1)
            plt.plot(self.time_axis, self.voltages)
            plt.xlabel('Time (s)')
            plt.ylabel('Voltage (V)')
            plt.show()
        
        return self.time_axis, self.voltages

    # Trigger level manipulation
    def SetTriggerLevel(self, triggerlevel):
        """
        Sets the trigger level on the oscilloscope.

        Args:
            triggerlevel (float): The desired trigger level.

        Returns:
            float: The set trigger level.
        """
        self.scope.write(f"HORizontal:POSition {triggerlevel}")
        self.triggervalue = float(self.scope.query('HORizontal:POSition?'))
        return self.triggervalue

    def GetTriggerLevel(self):
        """
        Retrieves the current trigger level from the oscilloscope.

        Returns:
            float: The current trigger level.
        """
        self.triggervalue = float(self.scope.query('HORizontal:POSition?'))
        return self.triggervalue

    # Time scale manipulation
    def SetTimeScale(self, TimeScale):
        """
        Sets the time scale on the oscilloscope.

        Args:
            TimeScale (float): The desired time scale.

        Returns:
            float: The set time scale.
        """
        self.scope.write(f"HORizontal:SCAle {TimeScale}")
        self.TimeScale = float(self.scope.query('HORizontal:SCAle?'))
        return self.TimeScale

    def GetTimeScale(self):
        """
        Retrieves the current time scale from the oscilloscope.

        Returns:
            float: The current time scale.
        """
        self.TimeScale = float(self.scope.query('HORizontal:SCAle?'))
        return self.TimeScale

    # Voltage scale manipulation
    def GetVoltageScale(self, Channel='1'):
        """
        Retrieves the voltage scale for a specific channel.

        Args:
            Channel (str): The oscilloscope channel.

        Returns:
            float: The voltage scale for the specified channel.
        """
        self.VoltageScale = float(self.scope.query(f"CH{Channel}:SCAle?"))
        return self.VoltageScale

    def SetVoltageScale(self, VoltageScale, Channel='1'):
        """
        Sets the voltage scale for a specific channel.

        Args:
            VoltageScale (float): The desired voltage scale.
            Channel (str): The oscilloscope channel.

        Returns:
            float: The set voltage scale.
        """
        self.scope.write(f"CH{Channel}:SCAle {VoltageScale}")
        self.VoltageScale = float(self.scope.query(f"CH{Channel}:SCAle?"))
        return self.VoltageScale

    # Offset manipulation
    def GetVoltageOffset(self, Channel='1'):
        """
        Retrieves the voltage offset for a specific channel.

        Args:
            Channel (str): The oscilloscope channel.

        Returns:
            float: The voltage offset for the specified channel.
        """
        self.VoltageOffset = float(self.scope.query(f"CH{Channel}:POSition?"))
        return self.VoltageOffset

    def SetVoltageOffset(self, VoltageOffset, Channel='1'):
        """
        Sets the voltage offset for a specific channel.

        Args:
            VoltageOffset (float): The desired voltage offset.
            Channel (str): The oscilloscope channel.

        Returns:
            float: The set voltage offset.
        """
        self.scope.write(f"CH{Channel}:POSition {VoltageOffset}")
        self.VoltageOffset = float(self.scope.query(f"CH{Channel}:POSition?"))
        return self.VoltageOffset

    # Utility functions
    def GetAllProperties(self, Channel=1):
        """
        Prints all oscilloscope properties for debugging purposes.
        """
        self.GetTriggerLevel()
        print("Trigger Level:", self.triggervalue)
        self.GetTimeDelay()
        print("Time Delay:", self.TimeDelay)
        self.GetTimeScale()
        print("Time Scale:", self.TimeScale)
        self.GetVoltageOffset(Channel)
        print("Voltage Offset:", self.VoltageOffset)
        self.GetVoltageScale(Channel)
        print("Voltage Scale:", self.VoltageScale)

    def SetAutoSet(self, Channel=1):
        """
        Executes the Auto Set feature on the oscilloscope and retrieves updated properties.
        """
        self.scope.write("AUTOSet EXECute")
        self.GetAllProperties(Channel)
        return

    # Waveform preamble property accessors
    def GetXIncrement(self):
        """Retrieves the X-axis increment value from the waveform preamble."""
        self.x_increment = float(self.scope.query('WFMPRE:XINCR?'))
        return self.x_increment

    def GetXZero(self):
        """Retrieves the X-axis zero value from the waveform preamble."""
        self.x_zero = float(self.scope.query('WFMPRE:XZERo?'))
        return self.x_zero

    def GetYScale(self):
        """Retrieves the Y-axis scale factor from the waveform preamble."""
        self.yscale = float(self.scope.query('WFMPRE:YMUlt?'))
        return self.yscale

    def GetYOffset(self):
        """Retrieves the Y-axis offset value from the waveform preamble."""
        self.yoffset = float(self.scope.query('WFMPRE:YOFF?'))
        return self.yoffset