
import JazLabs.hardware.PowerMeters.Thorlabs.TLPMX as TLPMX
from TLPMX import TLPM_DEFAULT_CHANNEL
import pyvisa
# from ThorlabsPM100 import ThorlabsPM100 # go and look at documentation to see the other functions that can be used to change things on the power meter. You need to pip install this
import ThorlabsPM100
import numpy as np
import ctypes
from enum import IntEnum

class DriverSelector(IntEnum):
    NIVISA = 0
    TLPM = 1
    
# OK... so... there is some crazy bull shit with the drivers with the PM100D, 
#if you install the thorlabs software the drivers are set to TLM drivers (these are the new drivers) the drivers need to be NI-VISA driver.
#To switch the drivers there is a some software located in C:\Program Files (x86)\Thorlabs\OPM\Tools\DriverSwitcher called Thorlabs.PMDriverSwitcher.exe. You can switch the drivers there.
#NOTE the USB codes are USB[board]::vendorID::productID::serialNumber::INSTR example 'USB::0x1313::0x8078::P0024994::INSTR'
class PowerMeterObject:
    def __init__(self, deviceName='',wavelength=925,AvgCount=1,Units="W",driver=DriverSelector.NIVISA):
        # super().__init__()  # Initialize the base class
        self.deviceName=deviceName
        self.wavelength=wavelength # this is in nm 
        self.AvgCount=AvgCount
        self.Units=Units
        self.driver=driver
        if driver == DriverSelector.NIVISA:
            # open a Resource Manger to look for the power meter
            rm = pyvisa.ResourceManager()# This just looks at all the USB stuff that is on the computer
            # If the user has no idea the ID of the power meter the class will give a list of the connected device so the user can re-initialise with to correct ID 
            if (deviceName==''):
                print("No devices given the list below shows connected device please work out which one is the power meter and re-initialise the class with the string")
                print("USB codes are USB[board]::vendorID::productID::serialNumber::INSTR example 'USB::0x1313::0x8078::P0024994::INSTR' \n")
                # rm.list_resources()# this will print out all the USB connected device you need to manually work out what is what. Unplug and re-run to see what is on the list and what isn't
                print(rm.list_resources())
                return

            # connect to the device
            self.inst1 = rm.open_resource(str(self.deviceName),timeout=100000000)# this gets the specific USB deivce that you want to access

            self.power_meter = ThorlabsPM100.ThorlabsPM100(inst=self.inst1)# this invokes the Thorlabs python lib that hides the tedious serial writes to the powermeter
        elif driver == DriverSelector.TLPM:
            if (deviceName==''):
                print("No devices given the list below shows connected device please work out which one is the power meter and re-initialise the class with the string")
                print("USB codes are USB[board]::vendorID::productID::serialNumber::INSTR example 'USB::0x1313::0x8078::P0024994::INSTR' \n")
                 
                tlPM = TLPMX.TLPMX()
                deviceCount = ctypes.c_uint32()
                tlPM.findRsrc(ctypes.byref(deviceCount))

                print("devices found: " + str(deviceCount.value))

                resourceName = ctypes.create_string_buffer(1024)

                for i in range(0, deviceCount.value):
                    tlPM.getRsrcName(ctypes.c_int(i), resourceName)
                    print(ctypes.c_char_p(resourceName.raw).value)
                    break
                tlPM.close()
                return
            
            self.power_meter = TLPMX.TLPMX()
            resourceName = ctypes.c_char_p(deviceName.encode('utf-8'))
            #resourceName = create_string_buffer(b"COM1::115200")
            # print(ctypes.c_char_p(resourceName.raw).value)
            self.power_meter.open(resourceName, ctypes.c_bool(True), ctypes.c_bool(True))

            
        #set the average counts for the device 
        self.SetAverageMeasure(self.AvgCount)
        
        #set the wavelength for the device 
        self.SetWaveLength(self.wavelength)
        
        #set the units for the device 
        self.SetUnits(self.Units)
        
        # Get a power Measruement
        self.pwr=self.GetPower()
        
        
    def __del__(self):
        # stop the connection to the power meter
        if self.driver == DriverSelector.TLPM:
            self.power_meter.close()
        elif self.driver == DriverSelector.NIVISA: 
        
            self.inst1.close()
        
    def SetAverageMeasure(self,AvgCount):
        self.AvgCount=AvgCount
        if self.driver == DriverSelector.TLPM:
            AvgCount_c =  ctypes.c_int16(AvgCount)
            self.power_meter.setAvgCnt(AvgCount_c, TLPM_DEFAULT_CHANNEL)
            
        elif self.driver == DriverSelector.NIVISA: 
            self.power_meter.sense.average.count=self.AvgCount
        
    def SetWaveLength(self,Wavelength):
        self.wavelength=Wavelength
        if self.driver == DriverSelector.TLPM:
            wavelength_c =  ctypes.c_double(Wavelength)
            self.power_meter.setWavelength(wavelength_c, TLPM_DEFAULT_CHANNEL)
            # self.power_meter.getWavelength(wavelength_c, TLPM_DEFAULT_CHANNEL)
        elif self.driver == DriverSelector.NIVISA:   
            self.power_meter.sense.correction.wavelength=self.wavelength
        
        print("Wavelength set to "+str(self.wavelength)+' nm')
        # The two lines below do the same thing as the one line above it is just that the lines below do a specific serial write to the power meter
        # the specific codes like SENS:CORR:WAV are specified in the ThorlabsPM100 library
        # wavelength=1565
        # power_meter.inst.write('SENS:CORR:WAV %f' %wavelength)  
    
    def SetUnits(self,Units):
        self.Units=Units
        if self.driver == DriverSelector.TLPM:
            if Units=="W":
                Unit=0
            elif Units=="dBm":
                Unit=1
            
            Units_c =  ctypes.c_int16(Unit)
            self.power_meter.setPowerUnit( Units_c, TLPM_DEFAULT_CHANNEL)
        elif self.driver == DriverSelector.NIVISA:   
            self.power_meter.sense.power.dc.unit=self.Units
            #NOTE when ever you change the units you need to call configure.X.X(). This is the same with if you wanted to measure a different value like voltage or current.
            self.power_meter.configure.scalar.power()
        print("Units set to "+str(self.Units))
        
        
    def GetPower(self):# this will get the currently configured measure value.
        if self.driver == DriverSelector.TLPM:
            power =  ctypes.c_double()
            self.power_meter.measPower(ctypes.byref(power), TLPM_DEFAULT_CHANNEL)
            self.pwr =power.value
        elif self.driver == DriverSelector.NIVISA:
            self.pwr=self.power_meter.read
        return self.pwr
    def StartDarkMeasurement(self,channel=1):
        if self.driver == DriverSelector.TLPM:
            chan =  ctypes.c_uint16(channel)
            self.power_meter.startDarkAdjust(TLPM_DEFAULT_CHANNEL)
            darkOffset=  ctypes.c_double()
            DarkPowerOffset=self.power_meter.getDarkOffset(ctypes.byref(darkOffset),TLPM_DEFAULT_CHANNEL)
            print(darkOffset.value)
        elif self.driver == DriverSelector.NIVISA:
            print("Not implemented")
        return DarkPowerOffset
    def GetDeviceCount(self):
        device_count = ctypes.c_int()
        self.power_meter.findRsrc(ctypes.byref(device_count))
        print("Found devices:", device_count.value)
        
