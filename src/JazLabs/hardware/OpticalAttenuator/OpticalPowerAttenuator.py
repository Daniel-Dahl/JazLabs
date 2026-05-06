from Lab_Equipment.Config import config
import Lab_Equipment.DAC.DAC_controllerThread as VoltageControllerThread
import time
import numpy as np



class Thorlabs_VOA():
    def __init__(self,VoltageController:VoltageControllerThread.Voltage_Controller,CalibrationFileName='VoltagePowerCal',RefreshTime=0.05,boardNumber=0,Channel=1,voltStepCount=256,voltMinLim=0,voltMaxLim=5):
            super().__init__()
            # InstaCal board number
            self.boardNumber=boardNumber
            self.channel = Channel
            # NOTE this is based on the DAQ NOT the device that is being manipulated
            #self.voltage_range = ULRange.UNI5VOLTS
            self.VoltageController=VoltageController
            
            
            self.voltStepCount=voltStepCount
            self.voltagesCals_arr=np.zeros(voltStepCount)
            self.powersCals_arr=np.zeros(voltStepCount)
            self.voltMinLim=voltMinLim
            self.voltMaxLim=voltMaxLim
            
    def __del__(self):
        pass
        
            
            
    def PowerToVolts(self,
                      input_power: float,
                      method: str = 'nearest') -> float:
        """
        Given arrays of voltages and their corresponding power readings,
        return the voltage corresponding to a desired input_power.

        Parameters
        ----------
        voltages : np.ndarray
            1D array of voltage values.
        powers : np.ndarray
            1D array of power readings, same shape as `voltages`.
        input_power : float
            The target power for which to find the voltage.
        method : {'linear', 'nearest'}, optional
            Interpolation method. 
            'linear' (default) does linear interpolation,
            'nearest' picks the voltage at the closest power reading.

        Returns
        -------
        float
            Interpolated (or nearest) voltage corresponding to input_power.
        """
        
        # Ensure arrays are 1D and same shape
        voltages = np.ravel(self.voltagesCals_arr)
        powers = np.ravel(self.powersCals_arr)
        if voltages.shape != powers.shape:
            raise ValueError("`voltages` and `powers` must have the same shape.")
        
        # Optionally sort by power if not already monotonic
        sort_idx = np.argsort(powers)
        powers_sorted = powers[sort_idx]
        volts_sorted  = voltages[sort_idx]
        
        if method == 'nearest':
            # find index of closest power
            idx = np.abs(powers_sorted - input_power).argmin()
            return float(volts_sorted[idx])
        elif method == 'linear':
            # np.interp returns float
            return float(np.interp(input_power, powers_sorted, volts_sorted))
        else:
            raise ValueError("`method` must be 'linear' or 'nearest'.")
        
    
    def SetPowerValue(self,power,printVoltage=False):
        voltage=self.PowerToVolts(power)
        if printVoltage==True:
            print(voltage)
        self.SetVoltValue(voltage)
        
        
    def SetVoltValue(self,voltage):

        if voltage>=self.voltMinLim and voltage<=self.voltMaxLim:
            self.VoltageController.SetVoltage(self.channel,voltage)
        else:
            print("Voltage " + str(voltage) +"value is not valid.")
        
        
    def SetVoltPwrCal(self,voltageCalArr,powerCalArr):
        self.SetPowerCal(powerCalArr)
        self.SetVoltCal(voltageCalArr)
        
        self.pwrLimMin=np.min(powerCalArr)
        self.pwrLimMax=np.max(powerCalArr)  
        self.voltMinLim=np.min(voltageCalArr)
        self.voltMaxLim=np.max(voltageCalArr)
        
                
        
    def SetPowerCal(self,powerCalArr):
        self.powersCals_arr=np.copy(powerCalArr)
    
    def SetVoltCal(self,voltageCalArr):
        self.voltagesCals_arr=np.copy(voltageCalArr)
        
    def SaveVoltagePowerCal(self,voltageCalArr=None,powerCalArr=None,filename="VoltagePowerCal"):
        # Save to compressed file
        if voltageCalArr is None: 
            voltageCalArrToSave=self.voltagesCals_arr
        if powerCalArr is None: 
            powerCalArrToSave=self.powersCals_arr
        CalibrationFilePath=config.PATH_OPTICAL_PWR_ATTENUATION +"CalibrationFiles\\"+filename
        np.savez(CalibrationFilePath+'.npz', voltageCalArr=voltageCalArrToSave, powerCalArr=powerCalArrToSave)

       
    def LoadVoltagePowerCal(self,filename="VoltagePowerCal"):
        
        CalibrationFilePath=config.PATH_OPTICAL_PWR_ATTENUATION +"CalibrationFiles\\"+filename+".npz"
        
        data = np.load(CalibrationFilePath)
        self.voltagesCals_arr = data['voltageCalArr']
        self.powersCals_arr = data['powerCalArr']
        self.SetVoltPwrCal(self.voltagesCals_arr,self.powersCals_arr)
        
        
        