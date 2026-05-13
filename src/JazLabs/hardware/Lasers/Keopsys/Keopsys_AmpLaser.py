import sys
import time
import Lab_Equipment.Config.config as config
import pyvisa
import numpy as np
import matplotlib.pyplot as plt

class LaserObject:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, LaserAmpID=None):
        super().__init__()
        rm = pyvisa.ResourceManager()
        
        if LaserAmpID is None:
            # List of all the resources
            print(rm.list_resources())
            print("Need to work out from this list which resource is the OSA and then re-run initalise the object")
            return

        self.LaserAmpID = LaserAmpID
        # NOTE many of these values are specified in the Manual under the RS232 communication section 
        self.LaserAmp = rm.open_resource(LaserAmpID,
                                         baud_rate = 19200,
                                         data_bits = 8,
                                         parity = pyvisa.constants.Parity.none,
                                         stop_bits = pyvisa.constants.StopBits.one,
                                         read_termination = '\r',
                                         write_termination = '\r')
        
        
        # Identify the connected oscilloscope
        self.idn = self.LaserAmp.query("DES?")  # Send IDN query to retrieve device information
        self.snu = self.LaserAmp.query("SNU?")
        print("Connection successful.\n", self.idn, "\n", self.snu)

        
      
        
    def __del__(self):
        """Destructor to disconnect the oscilloscope."""
        print("Amplifier has been disconnected")
        self.LaserAmp.close()  # Close the VISA connection
    def Get_stateOfPump(self):
        state = int(self.LaserAmp.query("STS?").replace("STS=", ""))
        if state:
            print("Amplifier is ON")
        else:
            print("Amplifier is OFF")
        return state
    
    def Get_ControlMode(self):
        controlmode = self.LaserAmp.query("ASS?")
        return controlmode   
    
    def Set_ControlMode(self,controlmode=1):
        if controlmode== 0:
            print("Pump diode is off. Note laser could still be emitting")
        elif controlmode == 1:
             print("Laser is in Automatic Current Control. i.e pump current is stable")
        elif controlmode== 2:
            print("Laser is in Automatic Power Control. i.e pump power is stable")
        else:
            print("Invalid contorl mode set setting to power mode controlmode=2")
            controlmode=2
            
        self.LaserAmp.write("ASS="+str(controlmode))
        controlmode=self.Get_ControlMode()

        self.Get_stateOfPump()

        return controlmode  
    
    # Most values are returned in 1/10dBm or 1/100dBm
    # Conversion is generally done within each function already
    
    def Get_MaxOutputPower(self):
        """Reads the maximum (nominal) output power in dBm"""
        max_power = float(self.LaserAmp.query("PON?").replace("PON=", ""))/10
        print("Maximum Output Power = "+str(max_power)+ " dBm")
        return max_power

    def Get_OutputPowerSetPoint(self):
        """Reads the output power set point in APC mode in dBm."""

        if self.LaserAmp.query("SOP?") == "SOP!":
            return -1
        else:
            set_point = float(self.LaserAmp.query("SOP?").replace("SOP=", ""))/10
            print("Output Power Set Point = " + str(set_point) + " dBm")
            return set_point

    def Set_OutputPowerSetPoint(self, set_point):
        """Writes the output power set point in APC mode.
        
        Args:
            set_point (float): Desired power set point in dBm (Min 20, Max: 30).
        """
        if set_point >= 20 and set_point <= 30:
            self.LaserAmp.write(f"SOP={int(set_point*10)}")
        else:
            print("Invalid set power. Min 20 dBm, Max: 30 dBm")

        confirmed_set_point=-1
        while confirmed_set_point == -1:
            confirmed_set_point = self.Get_OutputPowerSetPoint()
        return confirmed_set_point

    def Get_ActualInputPower(self):
        """Reads the actual input power in dBm."""
        input_power = self.LaserAmp.query("IPW?")

        # add execption for high input power

        return float(input_power.replace("IPW=", ""))/10

    def Get_ActualOutputPower(self):
        """Reads the actual output power in dBm."""
        output_power = self.LaserAmp.query("OPW?")
        return float(output_power.replace("OPW=", ""))/10
    
    def Get_PreamplifierDiodeCurrentSetPoint(self):
        """Reads the preamplifier diode current set point in mA."""
        current_set_point = self.LaserAmp.query("IC1?")
        return float(current_set_point)
    

    def Set_PreamplifierDiodeCurrentSetPoint(self, set_point):
        """Writes the preamplifier diode current set point in mA.
        
        Args:
            set_point (float): Desired current set point in mA.
        """
        self.LaserAmp.write(f"IC1={int(set_point)}")
        confirmed_set_point = self.Get_PreamplifierDiodeCurrentSetPoint()
        return confirmed_set_point

    def Get_ActualPreamplifierDiodeCurrent(self):
        """Reads the actual preamplifier diode current in mA."""
        actual_current = self.LaserAmp.query("ID1?")
        return float(actual_current)

    def Get_ActualPreamplifierDiodeTemperature(self):
        """Reads the actual preamplifier diode temperature in 1/100°C."""
        actual_temperature = self.LaserAmp.query("TD1?")
        return float(actual_temperature) / 100.0  # Convert to °C
    
    def Get_BoosterDiodeCurrentSetPoint(self):
        """Reads the booster diode current set point in mA."""
        current_set_point = self.LaserAmp.query("IC2?")
        return float(current_set_point)

    def Set_BoosterDiodeCurrentSetPoint(self, set_point):
        """Writes the booster diode current set point in mA.
        
        Args:
            set_point (float): Desired current set point in mA.
        """
        self.LaserAmp.write(f"IC2={int(set_point)}")
        confirmed_set_point = self.Get_BoosterDiodeCurrentSetPoint()
        return confirmed_set_point

    def Get_ActualBoosterDiodeCurrent(self):
        """Reads the actual booster diode current in mA."""
        actual_current = self.LaserAmp.query("ID2?")
        return float(actual_current)
