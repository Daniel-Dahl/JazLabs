


import time
import numpy as np
from pathlib import Path



class VOAObject():
    def __init__(self,DAType=None,CalibrationFileName='VoltagePowerCal',RefreshTime=0.05,boardNumber=0,Channel=1,voltStepCount=256,voltMinLim=0,voltMaxLim=5):
            super().__init__()
            # InstaCal board number
            self.boardNumber=boardNumber
            self.channel = Channel
            # NOTE this is based on the DAQ NOT the device that is being manipulated
            #self.voltage_range = ULRange.UNI5VOLTS
            if DAType == 'mcc_daq':
                import pwi_inst.hardware.DAQ_Controller.MCC.mcc_daq as DAQLib
            elif DAType == 'ni_daq':
                import pwi_inst.hardware.DAQ_Controller.NI.NI_DAQ as DAQLib
            else:
                raise ValueError('Unknown DAQ model specified')
            
            self.VoltageController=DAQLib.DAQObject(RefreshTime=RefreshTime,deviceNum=boardNumber,ChannelCount=Channel)
            
            
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
        self.SetVoltage(voltage)
        
        
    def SetVoltage(self,voltage):

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
        else:
            voltageCalArrToSave=voltageCalArr
        if powerCalArr is None: 
            powerCalArrToSave=self.powersCals_arr
        else:
            powerCalArrToSave=powerCalArr

        calibration_dir = Path(__file__).resolve().parents[5] / "calibrations" / "VOA"
        calibration_dir.mkdir(parents=True, exist_ok=True)
        calibration_file_path = calibration_dir / f"{filename}.npz"
        np.savez(calibration_file_path, voltageCalArr=voltageCalArrToSave, powerCalArr=powerCalArrToSave)

       
    def LoadVoltagePowerCal(self,filename="VoltagePowerCal"):
        calibration_file_path = Path(__file__).resolve().parents[5] / "calibrations" / "VOA" / f"{filename}.npz"
        data = np.load(calibration_file_path)
        self.voltagesCals_arr = data['voltageCalArr']
        self.powersCals_arr = data['powerCalArr']
        self.SetVoltPwrCal(self.voltagesCals_arr,self.powersCals_arr)
        
        
        
