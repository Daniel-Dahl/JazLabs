import sys
import Lab_Equipment.Config.config as config
import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import time

class PowerMeterObj:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, PWRMeterID=None):
        super().__init__()
        rm = pyvisa.ResourceManager()
        
        if PWRMeterID is None:
            # List of all the resources
            print(rm.list_resources())
            print("Need to work out from this list which resource is the OSA and then re-run initalise the object")
            return

        self.PWRMeterID = PWRMeterID
        self.PWRMeter = rm.open_resource(self.PWRMeterID,data_bits = 8, timeout=5000,baud_rate=115200)  # Open connection to the oscilloscope
        
        # Identify the connected oscilloscope
        self.idn = self.PWRMeter.query("*IDN?")  # Send IDN query to retrieve device information
        print("Connection successful. Device ID:", self.idn)
        
        
    def __del__(self):
        """Destructor to disconnect the oscilloscope."""
        print("Scope has been disconnected")
        self.PWRMeter.close()  # Close the VISA connection
    
    def GetAverageMeasure(self):
        avgCountTime_ms=float(self.PWRMeter.query("AVG?").strip())
        print("Current Average Count(ms): ", avgCountTime_ms)
        return avgCountTime_ms
    
    def SetAverageMeasure(self,avgCountTime_ms):
        self.PWRMeter.write("AVG {}".format(avgCountTime_ms))
        self.GetAverageMeasure()
        # print("Current Average Count(ms): ", avgCountTime_ms)
        
    def SetAutoOrManualRange(self,AutoRange=True):
        """
        Set the power meter to auto-range mode.
        """
        if AutoRange:
            self.PWRMeter.write("AUTO 1")
            print("Auto-range set to ON.")
        else:
            self.PWRMeter.write("AUTO 0")
            print("Manual-range set to ON.")     
    
    # There is a single wavelength setting but I dont have that module so 
    # I havve not implemented it yet.
    def SetWavelength(self,wavelength_nm,Module=0,Channel=1):
        """
        Set the wavelength for the power meter.
        """
        if wavelength_nm < 1250 or wavelength_nm > 1630:
            print("Wavelength out of range. Please provide a value between 1250 and 1630 nm.")
            return
        
        self.PWRMeter.write("DWAV "+ str(int(Module))+","+ str(int(Channel))+","+str(float(wavelength_nm)))
        wavelength_nm_new=self.GetWavelength(Module,Channel)
        Count=0
        while round(wavelength_nm_new,3)!=wavelength_nm:
            time.sleep(1e-3)
            wavelength_nm_new=self.GetWavelength(Module,Channel)
            Count=Count+1
            if Count > 3000:
                print("Wavelength not set in time")
                break
        

        # print("Wavelength set to {} nm.".format(wavelength_nm))

    def GetWavelength(self,Module=0,Channel=1):
        """
        Set the wavelength for the power meter.
        """
        
        wavelength_nm=float(self.PWRMeter.query("DWAV? "+ str(int(Module))+" "+ str(int(Channel))).strip())
        # print("Wavelength set to {} nm.".format(wavelength_nm))
        return wavelength_nm

    def GetUnits(self):
        units_int=(self.PWRMeter.query("UNIT?").strip())
        if units_int == '0':
            self.Units='dBm'
        elif units_int == '1':
            self.Units='mW'
        else:
            self.Units='Unknown'
        print("Current Units: ", self.Units)
        return self.Units
    
    def SetUnits( self,Units):
        if Units == 'dBm':
            self.PWRMeter.write("UNIT 0")
        elif Units == 'mW':
            self.PWRMeter.write("UNIT 1")
        else:
            print("Unknown units, please use 'dBm' or 'mW'")
            return
        self.GetUnits()
        print("Units set to "+str(self.Units))
        
        
        
        
    def GetPower(self,Module=0):# this will get the currently configured measure value.
        response=self.PWRMeter.query("READ? "+str(Module))
        # Strip \r\n and split by comma
        values = response.strip().split(',')
        # Convert to NumPy array of floats
        self.pwr = np.array(values, dtype=float)
        return self.pwr
    
   