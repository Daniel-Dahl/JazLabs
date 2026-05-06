import os
import time
import sys
import clr
import ctypes
import numpy as np
import matplotlib.pyplot as plt
import multiprocessing
from multiprocessing import shared_memory
import copy
import cv2

from Lab_Equipment.Config import config # This is were the path to the dll are setup

ftd2xxdll= ctypes.cdll.LoadLibrary("C:\\Program Files\\Thorlabs\\Kinesis\\ftd2xx.dll")# You need this so the other dll can work correctly Thorlabs docs dont have this
PiezoStrainGaugedll= ctypes.cdll.LoadLibrary("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.PiezoStrainGauge.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.FTD2xx_Net.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericPiezoCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.PiezoStrainGaugeCLI.dll")
from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.GenericPiezoCLI import *
from Thorlabs.MotionControl.KCube.PiezoStrainGaugeCLI import *
from System import Decimal  # necessary for real world units


class PiezoStrainGaugeObj():
    def __init__(self,serial_no= "113250191",loopMode=0,polligTime_ms=250):
        super().__init__() # inherit from parent class
        self.mountTol = 8e-9# this is from the thorlab page for the mount it is actually 6nm but I went a little bigger https://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=720
        self.serial_no = serial_no  
        self.polligTime_ms=polligTime_ms
        self.loopMode=loopMode
       
        # Connect, begin polling, and enable
        self.device = KCubePiezoStrainGauge.CreateKCubePiezoStrainGauge(self.serial_no)
        
        check1=PiezoStrainGaugedll.TLI_BuildDeviceList()
        print(check1)
        check2 = PiezoStrainGaugedll.TLI_GetDeviceListSize();
        print(check2)
      
        try:
            self.device.Connect(serial_no)
            # Get Device Information and display description
            self.device_info = self.device.GetDeviceInfo()
            print("A conection has been made to ",self.device_info.Description)
        except Exception as e:
            # This block will run for any other exceptions that are not explicitly caught above
            print("Could not connect to the device " + serial_no)
            
        # Start polling and enable
        
        self.device.StartPolling(self.polligTime_ms)  #250ms polling rate
        time.sleep(polligTime_ms*1e-3)
        self.device.EnableDevice()
        time.sleep(polligTime_ms*1e-3)  # Wait for device to enable

        if not self.device.IsSettingsInitialized():
            self.device.WaitForSettingsInitialized(10000)  # 10 second timeout
            assert self.device.IsSettingsInitialized() is True

        # Load the device configuration
        self.device_config = self.device.GetPiezoConfiguration(serial_no)

        # This shows how to obtain the device settings
        self.device_settings = self.device.PiezoDeviceSettings

        # Set the Zero point of the device
        self.SetZeroPoint()
        self.deviceMode = self.device.GetPositionControlMode()# initalise the device mode 
        #Set to openloop to get the position control mode
        # self.device.SetPositionControlMode(self.deviceMode.OpenLoop)
        # Get the maximum voltage output of the KPZ
       
        self.device.SetPositionControlMode(self.deviceMode.CloseLoop)
        self.CurrentPostion = self.device.GetPosition()
        self.CurrentVoltage=self.device.GetOutputVoltage()    
        # Get the maximum travel distance output of the KPZ
        self.max_voltage = self.device.GetMaxOutputVoltage()  # This is stored as a .NET decimal
        self.max_travel = self.device.GetMaxTravel()  # This is stored as a .NET decimal
        self.SetLoopMode(self.loopMode)
        
    def __del__(self):
        """Destructor to disconnect from camera."""
        self.device.StopPolling()  #Stop the polling
        self.device.Disconnect()
        print("device "+ self.serial_no+ " object is has been destroied ")       
         
    def SetZeroPoint(self):
        # Set the Zero point of the device
            print("Setting Zero Point")
            self.device.SetZero()
            time.sleep(5)# really should have a while loop that breaks once the SetZero is done. need to go look at documentation to work out how to do this
            
    def SetVoltage(self,voltage):
        if(self.loopMode==1):
            # Go to a voltage
            dev_voltage = Decimal(voltage)# the Decimal is taking the voltage value that will actually be in binary format for computer
            if dev_voltage != Decimal(0) and dev_voltage <= self.max_voltage:
                self.device.SetOutputVoltage(dev_voltage)
                time.sleep(self.polligTime_ms)
            else:
                print(f'Voltage must be between 0 and {self.max_voltage}')
        else:
            print("you need to change to open loop mode for this function to work use SetLoopMode()")
    
    def GetVoltage(self):
            self.CurrentVoltage=self.device.GetOutputVoltage()    
            

    def SetPosition(self,traveldist_um):
        if(self.loopMode==0):
            dev_travel = Decimal(traveldist_um)
            if dev_travel > Decimal(0) and dev_travel <= self.max_travel:
                self.device.SetPosition(dev_travel)
                time.sleep(self.polligTime_ms*4*1e-3) # this is determined by move the mount from min to max value and seeing how long it takes
                PostionVal=self.GetPosition()
                return PostionVal
            else:
                print(f'Position must be between 0 and {self.max_travel}')
        else:
            print("you need to change to closed loop mode for this function to work use SetLoopMode()")
    def GetPosition(self):
        if(self.loopMode==0):
            self.CurrentPostion=self.device.GetPosition()
            
        else:
            print("you need to change to closed loop mode for this function to work use SetLoopMode()")
        return self.CurrentPostion
            
            
    def SetLoopMode(self,loopmode):
        self.loopMode=loopmode
        if(self.loopMode==0):# Closed loop control
            self.device.SetPositionControlMode(self.deviceMode.CloseLoop)

        elif(self.loopMode==1):# Open loop control
            self.device.SetPositionControlMode(self.deviceMode.OpenLoop)
        else:
            print("invalid loop mode")