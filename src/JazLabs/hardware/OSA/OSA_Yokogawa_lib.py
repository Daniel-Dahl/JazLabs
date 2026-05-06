import sys
from dataclasses import dataclass
import Lab_Equipment.Config.config as config
import pyvisa
import numpy as np
import matplotlib.pyplot as plt



class OSA_Yoko:
    """
    Class to interact with an oscilloscope via VISA commands, providing methods to retrieve and manipulate 
    oscilloscope settings, data, and waveform properties.
    """
    def __init__(self, OSAID=None,output_dtype=np.float32, baud_rate=115200):
        super().__init__()
        rm = pyvisa.ResourceManager()
        
        if OSAID is None:
            # List of all the resources
            print(rm.list_resources())
            print("Need to work out from this list which resource is the OSA and then re-run initalise the object")
            return

        self.OSAID = OSAID
        self.OSA = rm.open_resource(self.OSAID, timeout=5000)  # Open connection to the oscilloscope

        # self.OSA.read_termination = '\r'
        self.OSA.baud_rate = baud_rate

        # Identify the connected oscilloscope
        self.idn = self.OSA.query("*IDN?")  # Send IDN query to retrieve device information
        print("Connection successful. Device ID:", self.idn)

        ######### NOTE ###############
        # Not really sure if this is needed I dont really know what it is doing but during testing it might be needed
        # maybe the idn has a squence that is similar to the two possible values below
        # Set command mode = AQ637X/AQ638X mode
        # self.OSA.write(":SYSTem:COMMunicate:CFORmat AQ6317")
        # self.OSA.write(":SYSTem:COMMunicate:CFORmat AQ6374")
        
        # going to set the sweep mode to Auto when initally connecting so you dont really have to worry about setting all the wavelenght bonds
        # self.Set_SweepMode("AUTO")
        # self.Initiate_Sweep("AUTO")
        
        self.Output_type="ASCII"
        #self.Output_type="Binary"
        
        # A sweep hasn't been conducted yet so the number of data points is undetermined
        self.Ns=0

        self.output_dtype = output_dtype 
        if  self.Output_type=="ASCII":
            self.OSA.write("FORMAT:DATA ASCii")
        elif(self.Output_type=="Binary"):
            if self.output_dtype == np.float32:
                self.OSA.write("FORMAT:DATA REAL,32")

            elif self.output_dtype == np.float64:
                self.OSA.write("FORMAT:DATA REAL,64")
            else:
                print("data output type invalid. Needs to be float32 or float64.")
                print("data output type set to float32.")
                self.OSA.write("FORMAT:DATA REAL,32")
        else:
            print("Invalid Data output type. Output type has been set to ASCII")
            self.OSA.write("FORMAT:DATA ASCii")
    def __del__(self):
        """Destructor to disconnect the oscilloscope."""
        print("Scope has been disconnected")
        self.OSA.close()  # Close the VISA connection
        
    def Get_SensorBandWidthResolution(self):
        bandWidth_res=float(self.OSA.query(":SENSE:BANDWIDTH?"))
        return bandWidth_res
        
    def Set_SensorBandWidthResolution(self, bandWidth):
        self.OSA.write(":SENSE:BANDWIDTH " + str(bandWidth))
        new_bandwidth = self.Get_SensorBandWidthResolution()
        return new_bandwidth

    def Set_Span(self, startWavelength, stopWavelength, resolution, resolution_correction):
        """ Start and stop wavelegnth in nm. Returns set wavelengths"""

        self.OSA.write(f":SENS:BAND:RES {resolution:.4f}NM")
        self.OSA.write(":SENS:SETT:CORR "+str(int(resolution_correction)))

        self.OSA.write(f":SENSE:WAVELENGTH:START {startWavelength:.3f}NM")
        self.OSA.write(f":SENSE:WAVELENGTH:STOP {stopWavelength:.3f}NM")

        # Start and stop wavelengths will be rounded to nearest value depending on set resolution
        # Read back the start and stop wavelengths actually set
        set_startWavelength = round(float(self.OSA.query(":SENSE:WAVELENGTH:START?").strip())*1e9,9)
        set_stopWavelength = round(float(self.OSA.query(":SENSE:WAVELENGTH:STOP?").strip())*1e9,9)

        return set_startWavelength, set_stopWavelength
    
    def Set_SweepMode(self, SweepMode):
        if SweepMode not in ("SINGle","REPeat", "AUTO", "SEGMent"):
            print("Invalid Sweep mode can only be SINGle, REPeat, AUTO or SEGMent")
            return
        
        self.OSA.write(":INITIATE:SMODE " + SweepMode)
                
        mode=int(self.OSA.query(":INITIATE:SMODE?"))
        if mode == 1:
            SweepMode_str="SINGle"
        elif mode == 2:
            SweepMode_str="REPeat"
        elif mode ==3:
            SweepMode_str="AUTO"
        elif mode ==4:
            SweepMode_str="SEGMent"
        else:
            SweepMode_str="ERROR"
        print("Sweep mode was set to " + SweepMode_str)
        return SweepMode_str

    def Initiate_Sweep(self,SweepMode=None):
        if SweepMode is not None:
             self.Set_SweepMode( SweepMode)
             
        self.OSA.write("*CLS")
        
        self.OSA.write(":INITIATE")
        #wait until sweep complete
        while True:
            a = self.OSA.query(":STATUS:OPERATION:EVENT?")
            if a[:1] == "1":
                break
        print("sweep complete")
        
    def Get_NumberOfDataPoints(self,TraceChannel="TRA"):
        Ns=int(self.OSA.query(":TRACE:DATA:SNUMBER? "+TraceChannel))

        return Ns
    
    def Get_Sampling(self):
        if bool(self.OSA.query(":SENSE:SWEEP:POINTS:AUTO?")):
            auto_sampling = str("AUTO ON")
        else:
            auto_sampling = str("AUTO OFF")
        sampling_points = int(self.OSA.query(":SENSE:SWEEP:POINTS?"))

        return auto_sampling, sampling_points

    
    def ConvertRawBinaryData(self,data_raw,dataType):
         # Check for the header (first byte should be "#")
        if data_raw[0:1] != b'#':
            raise ValueError("Unexpected binary format")

        # The next byte tells you how many digits make up the length
        num_digits = int(data_raw[1:2].decode())

        # Get the length of the binary data as an integer
        data_length = int(data_raw[2:2+num_digits].decode())

        # Now extract the binary data block
        binary_data = data_raw[2+num_digits:2+num_digits+data_length]

        # Convert the binary data to a NumPy array:
        data = np.frombuffer(binary_data, dtype=dataType)
        return data
    
    def ConvertRawASCIIData(self,data_raw):
        # Split the string by commas and convert each element to float
        string_list = data_raw.split(',')  # Split by commas

        # Convert the list of strings to floats and then create a numpy array
        data = np.array([float(x) for x in string_list])
        
        return data
    
    
    def Get_Xdata(self,TraceChannel="TRA"):
        data_raw=(self.OSA.query(":TRACE:X? "+TraceChannel))
        
        if(self.Output_type=="ASCII"):
            xdata = self.ConvertRawASCIIData(data_raw)
        elif(self.Output_type=="Binary"):
            xdata = self.ConvertRawBinaryData(data_raw,self.output_dtype)
        else:
            print("Invalid Data output type. Output type has been set to ASCII")
            self.OSA.write("FORMAT:DATA ASCii")
            xdata = self.ConvertRawASCIIData(data_raw)
    
        return xdata
    
    def Get_Ydata(self,TraceChannel="TRA",PowerDensityOutput=False,NRF=0.1e-9):
        if PowerDensityOutput:
            data_raw=(self.OSA.query(":TRACE:Y:PDENSITY? "+TraceChannel+","+str(NRF)))
        else:
            data_raw=(self.OSA.query(":TRACE:Y? "+TraceChannel))
            
        if(self.Output_type=="ASCII"):
            ydata = self.ConvertRawASCIIData(data_raw)
        elif(self.Output_type=="Binary"):
            ydata = self.ConvertRawBinaryData(data_raw,self.output_dtype)
        else:
            print("Invalid Data output type. Output type has been set to ASCII")
            self.OSA.write("FORMAT:DATA ASCii")
            ydata = self.ConvertRawASCIIData(data_raw)               
        return ydata
        
    def Get_data(self,TraceChannel="TRA",PowerDensityOutput=0,SweepMode="SINGle",Plotdata=False,):
        
        self.Initiate_Sweep(SweepMode=SweepMode)
        self.Ns=self.Get_NumberOfDataPoints(TraceChannel)
        self.wavelength=self.Get_Xdata(TraceChannel)
        self.PowerSpectrum=self.Get_Ydata(TraceChannel,PowerDensityOutput)

               
        # Optionally plot the data
        if Plotdata:
            plt.figure(1)
            plt.plot(self.wavelength, self.PowerSpectrum)
            plt.xlabel('wavelength (m)')
            plt.ylabel('PowerSpectrum (W)')
            plt.show()
        
        return self.wavelength, self.PowerSpectrum
    def _Get_AnalysisData(self, category):
        """
        Helper method to perform an analysis for a given category.
        It sends the SCPI commands to set the analysis category, triggers an
        immediate calculation, and then queries the result.
        
        Parameters:
          category (str): The analysis category command string, e.g., "SWTHresh", "POWer", etc.
          
        Returns:
          float: The first numeric value from the analysis result, or None if parsing fails.
        """
        # Set the analysis category.
        self.OSA.write(":CALCulate:CATegory " + category)
        # Trigger immediate analysis.
        self.OSA.write(":CALCulate:IMMediate")
        # Query the analysis data.
        data_str = self.OSA.query(":CALCulate:DATA?")
        try:
            # Parse the first comma-separated value.
            result = float(data_str.strip().split(",")[0])
        except Exception as e:
            print(f"Error parsing analysis data for category {category}: {data_str}")
            result = None
        return result

    def Get_SWTHresh(self):
        """Spectrum width analysis (Threshold)"""
        return self._Get_AnalysisData("SWTHresh")

    def Get_SWENvelope(self):
        """Spectrum width analysis (Envelope)"""
        return self._Get_AnalysisData("SWENvelope")

    def Get_SWRMs(self):
        """Spectrum width analysis (RMS)"""
        return self._Get_AnalysisData("SWRMs")

    def Get_SWPKrms(self):
        """Spectrum width analysis (Peak-RMS)"""
        return self._Get_AnalysisData("SWPKrms")

    def Get_NOTCh(self):
        """Notch width analysis"""
        return self._Get_AnalysisData("NOTCh")

    def Get_DFBLd(self):
        """DFB-LD parameter analysis"""
        return self._Get_AnalysisData("DFBLd")

    def Get_FPLD(self):
        """FP-LD parameter analysis"""
        return self._Get_AnalysisData("FPLD")

    def Get_LED(self):
        """LED parameter analysis"""
        return self._Get_AnalysisData("LED")

    def Get_SMSR(self):
        """SMSR analysis"""
        return self._Get_AnalysisData("SMSR")

    def Get_POWer(self):
        """Power analysis"""
        return self._Get_AnalysisData("POWer")

    def Get_PMD(self):
        """PMD analysis"""
        return self._Get_AnalysisData("PMD")

    def Get_WDM(self):
        """WDM analysis"""
        return self._Get_AnalysisData("WDM")

    def Get_NF(self):
        """NF analysis"""
        return self._Get_AnalysisData("NF")

    def Get_FILPk(self):
        """Filter peak analysis"""
        return self._Get_AnalysisData("FILPk")

    def Get_FILBtm(self):
        """Filter bottom analysis"""
        return self._Get_AnalysisData("FILBtm")

    def Get_WFPeak(self):
        """WDM FIL-PK analysis"""
        return self._Get_AnalysisData("WFPeak")

    def Get_WFBtm(self):
        """WDM FIL-BTM analysis"""
        return self._Get_AnalysisData("WFBtm")

    def Get_COLor(self):
        """COLOR analysis"""
        return self._Get_AnalysisData("COLor")
    
    def Get_Sensitivity(self):
        """Returns sensitivity setting"""

        sens_dict = {
            "NORM/HOLD" : 0,
            "NORM/AUTO" : 1,
            "NORM" : 6,
            "MID" : 2,
            "HIGH1" : 3,
            "HIGH2" : 4,
            "HIGH3" : 5
        }

        sens = int(self.OSA.query(":SENSE:SENSE?").strip())

        for label, value in sens_dict.items():
            if value == sens:
                return label

        return None
    
    def Set_Sensitivity(self, sens):
        sens_dict = {
            "NORM/HOLD" : 0,
            "NORM/AUTO" : 1,
            "NORM" : 6,
            "MID" : 2,
            "HIGH1" : 3,
            "HIGH2" : 4,
            "HIGH3" : 5
        }

        if sens in sens_dict:
            self.OSA.write(":SENSE:SENSE "+sens)
        else:
            print('Invalid sensitivity. Must use: "NORM", "MID", "HIGH1", "HIGH2", "HIGH3"')
    
        return

    
    def Get_yAxisUnits(self):

        units_dict = {
            "dBm" : 0,
            "W" : 1,
            "dBm/nm" : 2,
            "W/nm" : 3
        }

        units = int(self.OSA.query(":DISPLAY:TRACE:Y1:SCALE:UNIT?").strip())

        for label, value in units_dict.items():
            if value == units:
                return label

        return None

    def test_function(self):
        #return round(float(self.OSA.query(":SENSE:BANDWIDTH?").strip())*1e9,9)
        self.OSA.write(":SENSE:SENSE NORM")
        
        return
        #return round(float(self.OSA.query(":DISPLAY:TRACE:Y1:PDIV?")))

    

    def Get_SweepConfig(self):

        startWavelength = round(float(self.OSA.query(":SENSE:WAVELENGTH:START?").strip())*1e9,9)
        stopWavelength = round(float(self.OSA.query(":SENSE:WAVELENGTH:STOP?").strip())*1e9,9)

        sweepResolution = round(float(self.OSA.query(":SENSE:BANDWIDTH?").strip())*1e9,9) # returns resolution in nm
        sweepSensitivity = self.Get_Sensitivity()
        resolutionCorrection = bool(self.OSA.query(":SENS:SETT:CORR?").strip())
        sweepAveraging = int(self.OSA.query(":SENSE:AVERAGE:COUNT?").strip())

        yAxisUnits = self.Get_yAxisUnits()
        yAxisScale = round(float(self.OSA.query(":DISPLAY:TRACE:Y1:PDIV?")))
        yAxisRef = round(float(self.OSA.query(":DISPLAY:TRACE:Y1:RLEVEL?").strip()),9) # returns reference level in dBm

        current_SweepConfig = SweepConfig(
            startWavelength = startWavelength,
            stopWavelength = stopWavelength,
            sweepResolution = sweepResolution,
            sweepSensitivity = sweepSensitivity,
            sweepAveraging = sweepAveraging,
            resolutionCorrection = resolutionCorrection,
            yAxisUnits = yAxisUnits,
            yAxisScale = yAxisScale,
            yAxisRef = yAxisRef,

        )

        return current_SweepConfig
    
    def Set_SweepConfig(self, SweepConfig):

        self.Set_Span(SweepConfig.startWavelength, SweepConfig.stopWavelength, SweepConfig.sweepResolution, SweepConfig.resolutionCorrection)
        self.Set_Sensitivity(SweepConfig.sweepSensitivity)
        self.OSA.write(":SENSE:AVERAGE:COUNT "+str(SweepConfig.sweepAveraging))
        if SweepConfig.yAxisUnits == "LOG":
            self.OSA.write(f":DISPLAY:TRACE:Y1:SPACING "+str(SweepConfig.yAxisUnits))
            self.OSA.write(f":DISPLAY:TRACE:Y1:PDIV {SweepConfig.yAxisScale:.1f}")
            self.OSA.write(f":DISPLAY:TRACE:Y1:RLEVEL {SweepConfig.yAxisRef:.3f}")
        elif SweepConfig.yAxisUnits == "LINEAR":
            self.OSA.write(f":DISPLAY:TRACE:Y1:SPACING "+str(SweepConfig.yAxisUnits))
            self.OSA.write(f":DISPLAY:TRACE:Y1:RLEVEL {SweepConfig.yAxisRef:.3f}")

        return 

@dataclass
class SweepConfig:
    startWavelength: float
    stopWavelength: float
    sweepResolution: float
    sweepSensitivity: str
    sweepAveraging: int
    resolutionCorrection: bool
    yAxisUnits: str
    yAxisScale: float
    yAxisRef: float


