import sys
import Lab_Equipment.Config.config as config
import pyvisa
import numpy as np
import time 
import matplotlib.pyplot as plt

class LaserObject_SantecSweept:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, LaserID=None):
        super().__init__()
        rm = pyvisa.ResourceManager()
        
        if LaserID is None:
            # List of all the resources
            print(rm.list_resources())
            print("Need to work out from this list which resource is the OSA and then re-run initalise the object")
            return

        self.LaserID = LaserID
        self.Laser = rm.open_resource(self.LaserID, timeout=2000)
        self.channel=0
        self.Source=0
        
        # Identify the connected oscilloscope
        self.idn = self.Laser.query("*IDN?")  # Send IDN query to retrieve device information
        print("Connection successful. Device ID:", self.idn)
        
        self.Get_wavelengthUnits()     
        self.Get_wavelength()
        self.Get_PowerState()
        self.Set_PowerUnits(1)   
        self.Get_PowerUnits()   
        self.Get_PowerLevel()     
        self.Get_PowerAttenuation()
        
            # :SOURCE["+str(self.Source)+"]:CHANNEL["+str(self.channel)+"]
    def __del__(self):
        """Destructor to disconnect the oscilloscope."""
        print("Scope has been disconnected")
        self.Laser.close()  # Close the VISA connection
    def Get_wavelengthUnits(self):
        wavelengthUnits_int =int(self.Laser.query(":WAVelength:UNIT?"))
        if wavelengthUnits_int==0:
            self.wavelengthUnits="nm" 
        else:
            self.wavelengthUnits="THz" 
            
        return self.wavelengthUnits    
    def Set_wavelengthUnits(self, wavelengthUnits="nm"):
        if wavelengthUnits not in ("nm","THz"):
            print("Invalid wavelength units can only be nm or THz")
            return
        self.Laser.write(":WAVelength:UNIT "+wavelengthUnits)
        self.Get_wavelengthUnits()
        return self.wavelengthUnits
    
    def Get_wavelength(self):
        self.wavelength =float(self.Laser.query(":WAVELENGTH?"))
        print("Wavelength is", str(self.wavelength) + " " + (self.wavelengthUnits))
        return self.wavelength   
    
    def Set_wavelength(self,wavelength=1550):
        wavelength=wavelength*1e-9
        command=":WAVELENGTH " + str(wavelength)
        self.Laser.write(command)
        time.sleep(5)
        self.Get_wavelength()
        return self.wavelength  
    
    def Get_PowerState(self):
        self.PowerState =int(self.Laser.query(":POWer:STATe?"))
        if self.PowerState==0:
            self.PowerState="OFF"
            print("Laser is OFF")
        else:
            self.PowerState="ON"
            print("Laser is ON")
        return self.PowerState
    
    def Set_PowerState(self,PowerState=0):
        if PowerState not in (0,1):
            print("Invalid Power state value can only be 0=OFF or 1=ON")
            return
        self.Laser.write(":POWer:STATe "+str(PowerState))
        self.Get_PowerState()
        return self.PowerState
    
    def Get_PowerUnits(self):
        self.PowerUnits =int(self.Laser.query(":POWer:UNIT?"))
        if self.PowerUnits==0:
            self.PowerUnits="dBm"
            print("Power units are in dBm")
        else:
            self.PowerUnits="mW"
            print("Power units are in mW")
        return self.PowerUnits
    
    def Set_PowerUnits(self,PowerUnits=0):
        if PowerUnits not in (0,1):
            print("Invalid Power units value can only be 0=dBm or 1=mW")
            return
        self.Laser.write(":POWer:UNIT "+str(PowerUnits))
        self.Get_PowerUnits()
        return self.PowerUnits
    
    def Get_PowerAttenuation(self):
        self.PowerAttenuation = float(self.Laser.query(":POWer:ATTenuation?"))
        print("Power attenuation is", str(self.PowerAttenuation)+ "dbm")
        return self.PowerAttenuation
    
    def Set_PowerAttenuation(self, PowerAttenuation=0.0):
        if PowerAttenuation < 0:
            print("Invalid Power attenuation value. It must be non-negative.")
            return
        self.Laser.write(":POWer:ATTenuation "+str(PowerAttenuation))
        self.Get_PowerAttenuation()
        return self.PowerAttenuation
    
    def Get_PowerLevel(self):
        self.PowerLevelset = float(self.Laser.query(":POWer?"))
        print("Power level is set to ", str(self.PowerLevelset) + " " + self.PowerUnits)
        self.PowerLevel = float(self.Laser.query(":POWer:ACTual?"))
        print("Actual power level is set to ", str(self.PowerLevel) + " " + self.PowerUnits)
        
        
        return self.PowerLevel
    
    def Set_PowerLevel(self, PowerLevel=0.0):
        if PowerLevel < 0:
            print("Invalid Power level value. It must be non-negative.")
            return
        self.Laser.write(":POWer "+str(PowerLevel))
        self.Get_PowerLevel()
        return self.PowerLevel
        
    def Get_CoherenceControl(self):
        self.CoherenceControl =int(self.Laser.query(":COHCtrl?"))
        return self.CoherenceControl
    
    def Set_CoherenceControl(self,CoherenceControl=0):
        if CoherenceControl not in (0,1):
            print("Invalid CoherenceControl value can only be 0=OFF or 1=ON")
            return
        self.Laser.write(":COHCtrl "+str(CoherenceControl))
        self.Get_CoherenceControl()
        return self.CoherenceControl
       
    