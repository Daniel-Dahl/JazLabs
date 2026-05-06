import sys
import numpy as np
import matplotlib.pyplot as plt
import serial.tools.list_ports
import time

from JazLabs.hardware.Lasers.NKTPhotonics.NKTP_DLL import *
# This function will help determine what he mdoule(laser module) is. the value that is output in results should be converted to hex format
# for example the output of BasiK_K1x2 is ((0,51), 0) converting 51 into hex is 33h. you can then find which laser in the SDK has that as its 
# module hex value which is the BasiK_K1x2
def deviceGetType(portname, devId):
    """Returns the module type for a given device ID."""
    _readValue = c_ubyte(0)
    result = deviceGetType(portname, devId, _readValue)
    return result, _readValue.value

class Laser_NKT_BasiK_K1x2:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, LaserComport=None):
        super().__init__()
        if LaserComport is None:
            # Get a list of available COM ports
            ports = serial.tools.list_ports.comports()

            # Print available ports with details
            for port in ports:
                print(f"Port: {port.device} - {port.description} - {port.hwid}")

            # Alternative: Get just the port names as a list
            available_ports = [port.device for port in ports]
            print("Available COM ports:", available_ports)
            return
    
        self.LaserComport = LaserComport
        self.device_id=1
        self.BaseWavelength=self.Get_wavelength_standard() 
        
        # Open the COM port
        # Not nessesary, but would speed up the communication, since the functions does
        # not have to open and close the port on each call
        openResult = openPorts(self.LaserComport, 0, 0)
        print('Opening the comport:', PortResultTypes(openResult))

        self.Set_emission(True)
        self.Set_PowerUnits(0)

        self.Wavelength=self.Get_Wavelength()
        print("Input/output units for Set_Wavelengh()/Get_Wavelength() are nm ")

        self.Power=self.Get_Power()
        print("Input/output units for Set_Power()/Get_Power() are mW ")

        # display some properties
        setup = self.get_setup_bits()
        if setup:
            print("Module Setup Bits:")
            for feature, enabled in setup.items():
                print(f"- {feature}: {'Enabled' if enabled else 'Disabled'}")
        print("My creator got annoyed at NKT and has not immplemented enabling or disabling these features yet")
                
    def __del__(self):
        """Destructor to disconnect the laser."""
        self.Set_emission(False)
        closeResult = closePorts(self.LaserComport)
        print('Close the comport:', PortResultTypes(closeResult))
        
    def Set_emission(self, state):
        """Set the emission state of the laser.
        Args:
            state (bool): True to turn on emission, False to turn off.
        """
        EMISSION_REGISTER = 0x30  # 30h in hexadecimal
        value = 1 if state else 0
        result = registerWriteU8(self.LaserComport, self.device_id, EMISSION_REGISTER, value, -1)
        print(f"Emission {'ON' if state else 'OFF'} - Result: {result}")
        return result
    ############################################
    # Power/Current 
    ############################################
    def Set_PowerUnits(self, units=0):
        if units not in [0, 1]:
            print("Invalid units. Defaulting to mW. Input needs to be 0=mW and1=dBm")
            units = 0
        if units == 0:
            print("Units set to mW")
            self.PowerUnits=0
        else:
            print("Units set to dBm")
            self.PowerUnits=1
        
    def Get_output_power(self):
        """Read the output power in 1/100 mW or 1/100 dBm."""
        OUTPUT_POWER_REGISTER_MW = 0x17
        OUTPUT_POWER_REGISTER_DBM = 0x90
        if (self.PowerUnits==0):
           error, power = registerReadU16(self.LaserComport, self.device_id, OUTPUT_POWER_REGISTER_MW, -1)
        else:
            error,power = registerReadS16(self.LaserComport, self.device_id, OUTPUT_POWER_REGISTER_DBM, -1)
        return power
    
    def Set_Output_power(self, value):
        """Read the output power in 1/100 mW or 1/100 dBm."""
        OUTPUT_POWER_REGISTER_MW =  0x22
        OUTPUT_POWER_REGISTER_DBM =  0xA0
        if (self.PowerUnits==0):
            registerWriteU16(self.LaserComport, self.device_id, OUTPUT_POWER_REGISTER_MW, value, -1)

        else:
            registerWriteS16(self.LaserComport, self.device_id, OUTPUT_POWER_REGISTER_DBM, value, -1)
        # time.sleep(0.2)
    
    def Set_Power(self, value):
        value_int = int(value*1e2)
        self.Set_Output_power(value_int)
        while np.abs(self.Get_output_power()-value_int)>10:
            time.sleep(3) # 1e-6
        power=self.Get_Power()
        return power
                  
    def Get_Power(self):
        power=self.Get_output_power()
        return power*1e-2
    
    
    ############################################
    # wavelength
    ############################################
    
    def Set_Wavelength_offset_setpoint(self, value):
        """Set the wavelenght by adjusting its off set Resolution is in 1/10 pm."""
        FIBER_LASER_SETPOINT_REGISTER = 0x2A
        return registerWriteS16(self.LaserComport, self.device_id, FIBER_LASER_SETPOINT_REGISTER, value, -1)
    
    def Set_Wavelength_Offset(self, value):
        value_int=int(value)
        self.Set_Wavelength_offset_setpoint(value_int)
        while np.abs(self.Get_wavelength_offset()-int(value_int))>40:
            # print(np.abs(self.Get_wavelength_offset()-int(value_int)))
            time.sleep(1e-3)

        self.Wavelength=self.Get_Wavelength()
        return self.Wavelength

    def Set_Wavelength(self, value):
        value_int=int(value*1e4)

        Wavelength_offset=int((value_int-(self.BaseWavelength)))
        self.Set_Wavelength_offset_setpoint(int(Wavelength_offset))

        while np.abs(self.Get_wavelength_offset()-int(Wavelength_offset))>40:
            # print(np.abs(self.Get_wavelength_offset()-int(Wavelength_offset)))
            time.sleep(1e-3)

        self.Wavelength=self.Get_Wavelength()
        return self.Wavelength
        

    def Get_Wavelength(self):
        # """Total wavelength [nm] = Wavelength offset [nm] + Wavelength readout [pm] / 1000."""
        """Total wavelength [nm] = Wavelength standard [nm] + Wavelength offset [nm]."""
        wavelen_standard = self.Get_wavelength_standard()
        wavelen_offset = self.Get_wavelength_offset()
        wavelength = wavelen_standard + wavelen_offset
        return wavelength*1e-4
    
    def Get_wavelength_standard(self):
        """Read the present wavelength in nanometers (nm)."""
        WAVELENGTH_STANDARD_REGISTER = 0x32
        error,wavelength_standard=registerReadU32(self.LaserComport, self.device_id, WAVELENGTH_STANDARD_REGISTER, -1)
        return wavelength_standard

    def Get_wavelength_offset(self):
        """Read the wavelength offset in nanometers (nm)."""
        WAVELENGTH_OFFSET_REGISTER = 0x72
        error,wavelength_offset=registerReadS32(self.LaserComport, self.device_id, WAVELENGTH_OFFSET_REGISTER, -1)
        # print(error)
        return wavelength_offset
    
    ############################################
    # setting features
    ############################################
    def get_setup_bits(self,):
        """Reads the 16-bit setup bits register (31h) and parses its meaning."""
    
        # Read the 16-bit register (setup bits)
        result, setup_bits = registerReadU16(self.LaserComport, self.device_id, 0x31, -1)
        
        if result != 0:
            print(f"Error reading setup bits: {RegisterResultTypes(result)}")
            return None

        # Parse the bits into a dictionary
        setup_flags = {
            "Narrow wavelength modulation range": bool(setup_bits & (1 << 1)),
            "Enable external wavelength modulation": bool(setup_bits & (1 << 2)),
            "Wavelength modulation DC coupled": bool(setup_bits & (1 << 3)),
            "Enable internal wavelength modulation": bool(setup_bits & (1 << 4)),
            "Enable modulation output": bool(setup_bits & (1 << 5)),
            "Pump operation constant current": bool(setup_bits & (1 << 8)),
            "External amplitude modulation source": bool(setup_bits & (1 << 9)),
        }

        return setup_flags

    ############################################
    # Module features
    ############################################
    
    def Get_module_temperature(self):
        """Read the module temperature in 1/10 °C."""
        MODULE_TEMPERATURE_REGISTER = 0x1C
        return registerReadU16(self.LaserComport, self.device_id, MODULE_TEMPERATURE_REGISTER, -1)

    def Get_module_input_voltage(self):
        """Read the module supply voltage in millivolts (mV)."""
        MODULE_INPUT_VOLTAGE_REGISTER = 0x1E
        return registerReadU16(self.LaserComport, self.device_id, MODULE_INPUT_VOLTAGE_REGISTER, -1)
    
    ############################################
    # Modulation settings
    ############################################
    
    def Set_modulation_setup(self, value):
        """Set modulation setup bits."""
        MODULATION_SETUP_REGISTER = 0xB7
        return registerWriteU8(self.LaserComport, self.device_id, MODULATION_SETUP_REGISTER, value, -1)

    def Set_wavelength_modulation_frequency(self, frequency):
        """Set wavelength modulation frequency."""
        MODULATION_FREQUENCY_REGISTER = 0xB8
        return registerWriteF32(self.LaserComport, self.device_id, MODULATION_FREQUENCY_REGISTER, frequency, -1)

    def Set_wavelength_modulation_level(self, level):
        """Set wavelength modulation level."""
        MODULATION_LEVEL_REGISTER = 0x2B
        return registerWriteU16(self.LaserComport, self.device_id, MODULATION_LEVEL_REGISTER, level, -1)

    def Set_wavelength_modulation_offset(self, offset):
        """Set wavelength modulation offset."""
        MODULATION_OFFSET_REGISTER = 0x2F
        return registerWriteU16(self.LaserComport, self.device_id, MODULATION_OFFSET_REGISTER, offset, -1)

    def Set_amplitude_modulation_frequency(self, frequency):
        """Set amplitude modulation frequency."""
        AMPLITUDE_FREQUENCY_REGISTER = 0xBA
        return registerWriteF32(self.LaserComport, self.device_id, AMPLITUDE_FREQUENCY_REGISTER, frequency, -1)

    def Set_amplitude_modulation_depth(self, depth):
        """Set amplitude modulation depth."""
        AMPLITUDE_DEPTH_REGISTER = 0x2C
        return registerWriteU16(self.LaserComport, self.device_id, AMPLITUDE_DEPTH_REGISTER, depth, -1)
    
    def Configure_modulation_setup(self, amp_freq_select=0, amp_waveform=0, wav_freq_select=0, wav_waveform=0):
        """Set modulation setup bits for amplitude and wavelength modulation.
 
        Args:
            amp_freq_select (int): Amplitude modulation frequency selector (Bit 0).
            amp_waveform (int): Amplitude modulation waveform (Bit 2). 0 = Sine, 1 = Triangle.
            wav_freq_select (int): Wavelength modulation frequency selector (Bit 4).
            wav_waveform (int): Wavelength modulation waveform (Bits 6-7).
                                0 = Sine, 1 = Triangle, 2 = Sawtooth, 3 = Inverse Sawtooth.
 
        Returns:
            int: Result of the register write operation.
        """
        if amp_freq_select not in [0, 1]:
            print("Invalid amplitude modulation frequency selector. Must be 0 or 1.")
            return
        if amp_waveform not in [0, 1]:
            print("Invalid amplitude modulation waveform. Must be 0 (Sine) or 1 (Triangle).")
            return
        if wav_freq_select not in [0, 1]:
            print("Invalid wavelength modulation frequency selector. Must be 0 or 1.")
            return
        if wav_waveform not in [0, 1, 2, 3]:
            print("Invalid wavelength modulation waveform. Must be 0 (Sine), 1 (Triangle), 2 (Sawtooth), or 3 (Inverse Sawtooth).")
            return
 
        modulation_value = (amp_freq_select << 0) | (amp_waveform << 2) | (wav_freq_select << 4) | (wav_waveform << 6)
        MODULATION_SETUP_REGISTER = 0xB7
        result = registerWriteU16(self.LaserComport, self.device_id, MODULATION_SETUP_REGISTER, modulation_value, -1)
        print(f"Set modulation setup: {bin(modulation_value)} (Result: {result})")
        return result
    




class Laser_NKT_BasiK_K80_1:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, LaserComport=None):
        super().__init__()
        if LaserComport is None:
            # Get a list of available COM ports
            ports = serial.tools.list_ports.comports()

            # Print available ports with details
            for port in ports:
                print(f"Port: {port.device} - {port.description} - {port.hwid}")

            # Alternative: Get just the port names as a list
            available_ports = [port.device for port in ports]
            print("Available COM ports:", available_ports)
            return
       

        
        self.LaserComport = LaserComport
        self.device_id=10
        
        # Open the COM port
        # Not nessesary, but would speed up the communication, since the functions does
        # not have to open and close the port on each call
        openResult = openPorts(self.LaserComport, 0, 0)
        print('Opening the comport:', PortResultTypes(openResult))
        self.Set_emission(True)
        self.Set_temperature_compensation_mode(True)
        self.Set_current_power_mode(1)  
        self.Set_temperature_wavelength_mode(1)
        self.Wavelength=self.Get_Wavelength()
        self.Power=self.Get_Power()
        
    def __del__(self):
        """Destructor to disconnect the laser."""
        closeResult = closePorts(self.LaserComport)
        print('Close the comport:', PortResultTypes(closeResult))
        
    def Set_emission(self, state):
        """Set the emission state of the laser.
        Args:
            state (bool): True to turn on emission, False to turn off.
        """
        EMISSION_REGISTER = 0x30  # 30h in hexadecimal
        value = 1 if state else 0
        result = registerWriteU8(self.LaserComport, self.device_id, EMISSION_REGISTER, value, -1)
        print(f"Emission {'ON' if state else 'OFF'} - Result: {result}")
        return result
    ############################################
    # Power/Current 
    ############################################
    def Set_current_power_mode(self, mode=1):
        """Set the laser to current mode (0) or power mode (1)."""
        if mode not in [0, 1]:
            print("Invalid mode. Defaulting to Power mode.")
            mode = 1
        if mode == 1:
            print("Power mode selected.")
            print("Set_Power takes mW values to 1e-2mW precision ")
        else:
            print("Current mode selected (default).")
            print("Set_Current takes Amp values to mAmp precision ")
            
        CURRENT_POWER_MODE_REGISTER = 0x31
        self.CurrentPowerMode = registerWriteU8(self.LaserComport, self.device_id, CURRENT_POWER_MODE_REGISTER, mode, -1)
        return self.CurrentPowerMode
    
    
    def Get_pump_current(self):
        """Read the pump current in milliamps (mA)."""
        PUMP_CURRENT_REGISTER = 0x15
        return registerReadU16(self.LaserComport, self.device_id, PUMP_CURRENT_REGISTER, -1)
    
    def Get_output_power(self):
        """Read the output power in 1/100 mW."""
        OUTPUT_POWER_REGISTER = 0x18
        return registerReadU16(self.LaserComport, self.device_id, OUTPUT_POWER_REGISTER, -1)
    
    def Set_setpoint(self, value):
        """Set the pump current (mA) or output power (0.01mW)."""
        SETPOINT_REGISTER = 0x23
        return registerWriteU16(self.LaserComport, self.device_id, SETPOINT_REGISTER, value, -1)
    
    def Set_Power(self, value):
        value = int(value*1e2)
        if self.CurrentPowerMode==1:
            self.Set_setpoint(value)
            self.Power=self.Get_Power()
        else:
            print("Laser is in Current mode. Need to switch to Power mode using Set_current_power_mode(1)")
            
    def Set_Current(self, value):
        value = int(value*1e3)
        if self.CurrentPowerMode==0:
            self.Set_setpoint(value)
            self.Power=self.Get_Current()
        else:
            print("Laser is in Power mode. Need to switch to Current mode using Set_current_power_mode(0)")
            
    def Get_Power(self):
        power=self.Get_output_power()
        return power*100
    def Get_Current(self):
        current=self.Get_pump_current()
        return current*1e-3
    
    ############################################
    # wavelength/Temperature 
    ############################################
    def Set_temperature_wavelength_mode(self, mode=1):
        """Set temperature mode (0) or wavelength mode (1)."""
        if mode not in [0, 1]:
            print("Invalid mode. Defaulting to wavelength mode.")
            mode = 1
        if mode == 0:
            print("Temperature mode selected.")
            print("Set_Temperature takes C values to mC precision ")
        else:
            print("Wavelength mode selected (default).")
            print("Set_wavelength takes nm values pm precision  ")
        TEMP_WAVELENGTH_MODE_REGISTER = 0x34
        self.WavelenTempMode = registerWriteU8(self.LaserComport, self.device_id, TEMP_WAVELENGTH_MODE_REGISTER, mode, -1)
        return self.WavelenTempMode
    
    def Set_fiber_laser_setpoint(self, value):
        """Set fiber laser temperature (m°C) or wavelength (pm)."""
        FIBER_LASER_SETPOINT_REGISTER = 0x25
        return registerWriteU16(self.LaserComport, self.device_id, FIBER_LASER_SETPOINT_REGISTER, value, -1)
    
    def Set_Wavelength(self, value):
        value=int(value*1e3)
        if self.WavelenTempMode==1:
            self.Set_fiber_laser_setpoint(value)
            self.Wavelength=self.Get_Wavelength()
        else:
            print("Laser is in Temperature mode. Need to switch to Wavelength mode using Set_temperature_wavelength_mode(1)")
            
    def Set_Temperature(self, value):
        value=int(value*1e3)
        if self.WavelenTempMode==0:
            self.Set_fiber_laser_setpoint(value)
            self.Temperature=self.Get_temperature()
        else:
            print("Laser is in Wavelength mode. Need to switch to Temperature mode using Set_temperature_wavelength_mode(0)")
            
    def Get_Wavelength(self):
        """Total wavelength [nm] = Wavelength offset [nm] + Wavelength readout [pm] / 1000."""
        wavelen_readout=self.Get_wavelength_readout()
        wavelen_offset=self.Get_wavelength_offset()
        wavelength=wavelen_offset+wavelen_readout/1000
        return wavelength
    def Get_temperature(self):
        """Temperature in Celsius (m°C). """
        Temperature=self.Get_fiber_laser_temperature()
        return Temperature*1e-3
    
    def Get_wavelength_readout(self):
        """Read the present wavelength in picometers (pm)."""
        WAVELENGTH_READOUT_REGISTER = 0x10
        return registerReadU16(self.LaserComport, self.device_id, WAVELENGTH_READOUT_REGISTER, 12)

    def Get_wavelength_offset(self):
        """Read the wavelength offset in nanometers (nm)."""
        WAVELENGTH_OFFSET_REGISTER = 0x10
        return registerReadU16(self.LaserComport, self.device_id, WAVELENGTH_OFFSET_REGISTER, 13)
    
    def Get_fiber_laser_temperature(self):
        """Read the fiber laser temperature in milli-degrees Celsius (m°C)."""
        FIBER_LASER_TEMPERATURE_REGISTER = 0x11
        return registerReadU16(self.LaserComport, self.device_id, FIBER_LASER_TEMPERATURE_REGISTER, -1)

    ############################################
    # Additional properties 
    ############################################
    def Set_piezo_modulation(self, state):
        """Enable (1) or disable (0) piezo modulation."""
        PIEZO_MODULATION_REGISTER = 0x32
        return registerWriteU8(self.LaserComport, self.device_id, PIEZO_MODULATION_REGISTER, state, -1)

    def Set_RIN_suppression(self, state):
        """Enable (1) or disable (0) RIN suppression."""
        RIN_SUPPRESSION_REGISTER = 0x33
        return registerWriteU8(self.LaserComport, self.device_id, RIN_SUPPRESSION_REGISTER, state, -1)

    def Set_temperature_compensation_mode(self, state=True):
        if state not in [True, False]:
            print("Invalid mode. Defaulting to temperature compensation mode.")
            state = True
        if state:
            print("Temperature compensation enabled")
        else:
            print("Temperature compensation disabled")
        """Enable (1) or disable (0) temperature compensation."""
        value = 1 if state else 0
        TEMP_COMPENSATION_MODE_REGISTER = 0x35
        return registerWriteU8(self.LaserComport, self.device_id, TEMP_COMPENSATION_MODE_REGISTER, value, -1)
    
    def Set_acknowledge_mode(self, state):
        """Enable (1) or disable (0) acknowledge mode."""
        ACKNOWLEDGE_MODE_REGISTER = 0x36
        return registerWriteU8(self.LaserComport, self.device_id, ACKNOWLEDGE_MODE_REGISTER, state, -1)
    
    def Get_module_temperature(self):
        """Read the module temperature in 1/10 °C."""
        MODULE_TEMPERATURE_REGISTER = 0x19
        return registerReadU16(self.LaserComport, self.device_id, MODULE_TEMPERATURE_REGISTER, -1)

    def Get_module_input_voltage(self):
        """Read the module supply voltage in millivolts (mV)."""
        MODULE_INPUT_VOLTAGE_REGISTER = 0x1B
        return registerReadU16(self.LaserComport, self.device_id, MODULE_INPUT_VOLTAGE_REGISTER, -1)
    