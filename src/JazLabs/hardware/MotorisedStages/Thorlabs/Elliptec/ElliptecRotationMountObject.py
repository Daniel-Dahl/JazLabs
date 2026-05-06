# So the Elliptic library that the community has made is already wrapped up pretty well
# so I am NOT going to put it in another object but I will make some function that will 
# help to quickly load them in.
# 
# Changed my mind I think because I am going to use them in pair I want to have a single object
# that holds all of the mounts. 
# 
# NOTE the documentation of the thorlabs_elliptec is very good go and have a look at it to
# see how to control mounts

# So some time the board will need to be reset using thorlabs software as that software only 
# allows one COM port communication and it does so funny thing with alisis the other mount. 
# You just factor reset to fix.

# NOTE some times the mounts get stuck a little, if this happens you should just physically rotate them and that will make them unstuck


import numpy as np
import matplotlib.pyplot as plt
import time
from thorlabs_elliptec import ELLx, ELLError, ELLStatus, list_devices,find_device

# device=/dev/cu.usbserial-DT04N7X4, manufacturer=FTDI, product=FT230X Basic UART, vid=0x0403, pid=0x6015, serial_number=DT04N7X4, location=1-1.2.1
# device=/dev/cu.usbserial-DT04N7PW, manufacturer=FTDI, product=FT230X Basic UART, vid=0x0403, pid=0x6015, serial_number=DT04N7PW, location=0-1.3.3
#Angle offset for DT04N7X4 is: 5.5
#Angle offset for DT04N7PW is: 21.872
class ELL_RotationMountObj:
    def __init__(self, Serial_ports=[],AngleOffset=[]):
        self.Serial_ports = Serial_ports
        self.stageCount = len(self.Serial_ports)
        self.stages = np.empty(self.stageCount,dtype=object)
        self.AngleResolution = 0.002 # this is Obtained from thorlabs specsheet for the mount
        self.CurrentMountAngle = -10000 # If this is still a negative number after initilising the object there is a major problem i.e. the mount never connected
        self.CurrentOpticsAngle = -10000 # If this is still a negative number after initilising the object there is a major problem i.e. the mount never connected
       
        #if no serial port is given just list all serial port to help use workout which one is a rotation mount
        if(self.stageCount==0):
            print("No Serial ports were given. Have a look at the list below and work out what are the rotation mounts and use the device variable as the string for the serial port")
            print(list_devices())
            return 
        # if no angle offsets are give make them all be zero
        if(len(AngleOffset) == 0):
            self.AngleOffset = np.zeros((self.stageCount),dtype=float) # this is for the waveplate
        else:
            self.AngleOffset = np.asarray(AngleOffset)
        
        # Connect to the Mounts
        for istage in range(self.stageCount):
            print(Serial_ports[istage])
            self.stages[istage]=ELLx(serial_port=str(Serial_ports[istage]))
            print(f"{self.stages[istage].model_number}\n #{self.stages[istage].device_id} on {self.stages[istage].port_name},\n serial number {self.stages[istage].serial_number},\n status {self.stages[istage].status.description}")
        
        # self.HomeStages()
        
        
    def __del__(self):
        # Close the connection to the mounts
        print('Closing stage connections')
        for istage in range(self.stageCount):
            self.stages[istage].close()

    def SetAngle(self,angle,istage=0):
        # Apply the angle offset
        AngleOffsetAdjustment = (angle+self.AngleOffset[istage])%360
        # The mount has angle resolution so when the user puts in a value I want it to be 
        # within that resolution
        AngleOffsetAdjustment=round(AngleOffsetAdjustment / self.AngleResolution) * self.AngleResolution
        self.stages[istage].move_absolute(AngleOffsetAdjustment,blocking=True)
        self.GetAngle(istage)# CurrentMountAngle and CurrentOpticsAngle is filled in through GetAngle
        return self.CurrentMountAngle,self.CurrentOpticsAngle
        
    def GetAngle(self,istage):
        self.CurrentMountAngle = self.stages[istage].get_position()
        self.CurrentOpticsAngle = (self.CurrentMountAngle - self.AngleOffset[istage])%360
        return self.CurrentMountAngle,self.CurrentOpticsAngle
        
    def HomeStages(self):
        # Move device to the home position
        for istage in range(self.stageCount):
            print(self.GetAngle(istage))
            self.stages[istage].home(blocking=True)
            print(self.GetAngle(istage))
             
    # These functions do a angle adjustment that is a required for waveplates that are in pairs and angles of the waveplates are related to one another
    def AnglepairFunction(self,thetain):
        thetaOut = np.degrees(0.5*np.arccos(np.sqrt(0.5 * (1 - np.sqrt(np.sin(2 * np.radians(thetain)))))))
        return thetaOut
    
    def SetAnglePair(self,istage1,istage2,AngleSet):
        self.SetAngle(AngleSet,istage1)
        print(AngleSet,self.CurrentOpticsAngle,self.CurrentMountAngle)
        Mount1Angle=self.CurrentOpticsAngle
        AnglePair=self.AnglepairFunction(AngleSet)
        self.SetAngle(AnglePair,istage2)
        Mount2Angle=self.CurrentOpticsAngle
        print(AnglePair,self.CurrentOpticsAngle,self.CurrentMountAngle)
        return Mount1Angle,Mount2Angle




#####################
# These were the function way of setting up the mounts. I went with class way as I think it makes it easier when there are multiple mounts
####################
# def ConnectToMounts(Serial_ports=[]):
#     stageCount=len(Serial_ports)
#     stages=np.empty(stageCount)
#     if(stageCount==0):
#         print("No Serial ports were given. Have a look at the list below and work out what are the rotation mounts and use the device variable as the string for the serial port")
#         print(list_devices())
#         return stages

#     for istage in range(stageCount):
#         stages[istage]=ELLx(serial_port=Serial_ports[istage])
#         # stages.append( ELLx(serial_port='/dev/cu.usbserial-DT04N7X4'))
#         print(f"{stages[istage].model_number} #{stages[istage].device_id} on {stages[istage].port_name}, serial number {stages[istage].serial_number}, status {stages[istage].status.description}")
#     return stages

# def HomeStages(stages):
#     # Move device to the home position
#     stageCount=len(stages)
#     for istage in range(stageCount):
#         print(istage,stages[istage].get_position())
#         stages[istage].home(blocking=True)
#         print(istage,stages[istage].get_position())
    
# def SetAnglePair(stage1,stage2,AngleSet):
#     stage1.move_absolute(AngleSet,blocking=True)
#     AnglePair=AnglepairFunction(AngleSet)
#     stage2.move_absolute(AnglePair,blocking=True)
#     print(AngleSet,stage1.get_position())
#     print(AnglePair,stage2.get_position())
    
    