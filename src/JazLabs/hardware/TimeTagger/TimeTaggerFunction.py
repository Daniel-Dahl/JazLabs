import numpy as np
import time
# import multiprocessing
# from multiprocessing import shared_memory
import TimeTagger
import cv2
import copy
import numba
import matplotlib.pyplot as plt
import shutil
from scipy.signal import find_peaks

import os
import psutil

import TimeTagger

def CheckFileCanBeLoaded(files_path):
    
    # Get available RAM in bytes
    available_ram = psutil.virtual_memory().available

    # Convert available RAM to a readable format (e.g., MB)
    available_ram_mb = available_ram / (1024 * 1024* 1024)

    print(f"Available RAM: {available_ram_mb:.2f} GB")

    # Get the size of the file in bytes
    file_size=0
    for ifile in files_path:
        file_size = file_size + os.path.getsize(ifile)

    # Estimate the size of the array in memory (add a safety margin)
    file_size_with_margin = file_size * 1.2  # Add a 20% safety margin

    # Check if the file size is smaller than the available RAM
    if file_size_with_margin < available_ram:
        print("File can be loaded. File size is "+ str(file_size_with_margin / (1024 * 1024* 1024)) + " GB")
        
        Readfiles=True
    else:
        print(f"Not enough RAM to load the file. File size (with margin): {file_size_with_margin / (1024 * 1024* 1024):.2f} GB")
        Readfiles=False
    return Readfiles
        
def ReadRawTagFiles(FolderName):
    # could use this to read in postion of the file
    # array = np.fromfile(file_path, dtype=dtype, count=num_elements, offset=offset)
    Files=["_type.bin","_missed_events.bin","_channel.bin","_time.bin"]

    Filepaths = [FolderName + filepath for filepath in Files]
    Readfiles = CheckFileCanBeLoaded(Filepaths)
    if(Readfiles):
        dtype_for_tags = np.dtype([('type', np.uint8), ('missed_event', np.uint16), ('channel', np.int32), ('time', np.int64)])
        
        
        # Create an empty tags array with the same length as the individual arrays read in the the type array as that will be the smallest and 
        # fastest to read in. get the size and then del to save memory space
        tempArr= np.fromfile(Filepaths[0], dtype=np.uint8)
        tags = np.zeros(tempArr.size, dtype=dtype_for_tags)
        del tempArr

        # Fill the structured array with the individual arrays
        tags['type'] = np.fromfile(Filepaths[0], dtype=np.uint8)
        tags['missed_event'] = np.fromfile(Filepaths[1], dtype=np.uint16)
        tags['channel'] = np.fromfile(Filepaths[2], dtype=np.int32)
        tags['time'] = np.fromfile(Filepaths[3], dtype=np.int64)
    return tags

def MoveRawTags(SourceFolder,DestinationFolder):
    
    Files=["_type.bin","_missed_events.bin","_channel.bin","_time.bin"]
    
    Filepaths = [SourceFolder + filepath for filepath in Files]
    
    os.makedirs(DestinationFolder, exist_ok=True)

    for ifile in Filepaths:
        shutil.copy2(ifile, DestinationFolder)


################################################
# Function to help determine best settings for the time tagger
################################################
    

# this is a nice way of working out the delay that need to be applied to the single to set them to be zero.
def CalculateTimeDelay(timeData,CorrData):
    #Average way of calculating delay
    timeDelay_avg = np.sum(timeData * CorrData) / np.sum(CorrData)
    # print(timeDelay_avg)
    
    # Max value in correlation way of calculating delay
    maxIdax=np.argmax(CorrData)
    timeDelay_max=timeData[maxIdax]
    # print(timeData[maxIdax])
    
    return timeDelay_avg,timeDelay_max

# fix me please i needed to be fixed!!!!!!!!!!!!!!!!!!!!!!!!!!
# You have been fixed. go into the world and become something great
def ScanVoltageTriggerLevels(tagger:TimeTagger.TimeTagger,voltmin=0.1,voltmax=0.6,VoltCount=2,ChannelToSweep=1,Channels=[1,2],binWidth=100,CountTime=10):

    VoltCount=int(voltmax-voltmin/0.001)# the 0.001 is the lowest precision the voltage trigger level can be
    voltageVal=np.linspace(voltmin,voltmax,VoltCount)
    countdata_arr=np.zeros(VoltCount)
    for ivolt in range(VoltCount):
        voltval=voltageVal[ivolt]
        tagger.setTriggerLevel(channel=ChannelToSweep, voltage=voltval)
        data=getCoincidences(tagger,measurementChannels=Channels,binWidth=binWidth,countingTime=CountTime)
        countdata_arr[ivolt]=data.channel1_counts
        print(data.channel1_counts ,ivolt,voltval)

    plt.plot(voltageVal,countdata_arr)

################################################
# Function to perform measurements 
################################################

def GetCorrelationAndCountsdata_SynMulti(sm:TimeTagger.SynchronizedMeasurements,MeasurementList,channelList,CountTime,binCount,PlotResutls=False):
    MeasurementCount=len(MeasurementList)
    print(MeasurementCount)
    # Start measurements and accumulate data for Counting time
    sm.startFor(int(CountTime*1e12), clear=True)
    sm.waitUntilFinished()
    timeData=np.zeros((MeasurementCount,binCount))
    MeasurementData=np.zeros((MeasurementCount,binCount))
    MeasurementDataNorm=np.zeros((MeasurementCount,binCount))
   
    if (PlotResutls): # Lets plot the data
        plt.figure()
        fig, axs = plt.subplots(MeasurementCount, 1)  # 2 rows, 1 column of subplots

    for measurements,imeasure in zip(MeasurementList,range(MeasurementCount)):
        # timeData[imeasure,:] = measurements.getIndex()
        if (len(measurements.getData())!=binCount):
            # I am going to assume the size is one i just want it to work. 
            data=measurements.getData()
            if (len(data)>1):
                print("The measurement object for countrate needs to just be one channel. If you want multiple channels add mor measurement objects to the list")
                return
            MeasurementData[imeasure,:]=np.ones(binCount)*data[0]
            timeData[imeasure,:] =np.zeros(binCount)
        else:
            MeasurementData[imeasure,:]= measurements.getData()
            timeData[imeasure,:] = measurements.getIndex()
        try:
            # Code that might raise an error
            MeasurementDataNorm[imeasure,:] = measurements.getDataNormalized()
            if (PlotResutls):
                # axs[iplot].plot(time,CorrData)
                # axs[ichannel].plot(timeData[ichannel,:],CorrDataNorm[ichannel,:])
                axs[imeasure].plot(timeData[imeasure,:],MeasurementData[imeasure,:])
            
            timedelay_avg,timedelay_max=CalculateTimeDelay(timeData[imeasure,:],MeasurementData[imeasure,:])
        except Exception as e:
            continue  # optional — loop continues anyway
    return timeData,MeasurementData, MeasurementDataNorm
        
def getCorrelations(tagger:TimeTagger.TimeTagger, measurementChannels, binWidth, binNum,countingTime,PlotResutls=False):
        
        correlation = TimeTagger.Correlation(tagger=tagger,
                                     channel_1=measurementChannels[0],
                                     channel_2=measurementChannels[1],
                                     binwidth=binWidth,
                                     n_bins=binNum)
        correlation.startFor(capture_duration=int(countingTime*1e12))
        correlation.waitUntilFinished()

        correlationTimebins_data=np.asarray(correlation.getIndex())
        correlation_data = np.asarray(correlation.getData())
        correlationNorm_data=np.asarray(correlation.getDataNormalized())

        if (PlotResutls):
            # Create figure and first axis
            # fig, ax1 = plt.subplots()

            # # Plot first data set on ax1
            # color = 'tab:blue'
            # ax1.set_xlabel('Time(ps)')
            # ax1.set_ylabel('Correlations (Counts/bin)', color=color)
            # ax1.plot(correlationTimebins_data, correlation_data, color=color)
            # ax1.tick_params(axis='y', labelcolor=color)

            # # Create second y-axis sharing the same x-axis
            # ax2 = ax1.twinx()  

            # # Plot second data set on ax2
            # color = 'tab:red'
            # ax2.set_ylabel('Norm Correlations (Counts/Sec)', color=color)
            # ax2.plot(correlationTimebins_data, correlationNorm_data, color=color)
            # ax2.tick_params(axis='y', labelcolor=color)

            # Improve layout
            #fig.tight_layout()

            fig, ax = plt.subplots(1,2)

            # Plot first data set on ax1
            color = 'tab:blue'
            ax[0].set_xlabel('Time(ps)')
            ax[0].set_ylabel('Correlations (Counts/bin)', color=color)
            ax[0].plot(correlationTimebins_data, correlation_data, color=color, marker='o')

            #ax[0].tick_params(axis='y', labelcolor=color)

            # Plot second data set on ax2
            #color = 'tab:red'
            ax[1].set_ylabel('Norm Correlations (Counts/Sec)', color=color)
            ax[1].plot(correlationTimebins_data, correlationNorm_data, color=color, marker='o')
            #ax[1].tick_params(axis='Time(ps)', labelcolor=color)

            # Improve layout
            fig.tight_layout()


        return correlationTimebins_data,correlation_data,correlationNorm_data
    
def getCounts(tagger:TimeTagger.TimeTagger,clearbuffer, measurementChannel, binWidth, binNum,countingTime):
    if not isinstance(measurementChannel, list):
        measurementChannel = [measurementChannel]
    counter = TimeTagger.Counter(tagger=tagger,
                                    channels=measurementChannel,
                                    binwidth=binWidth,
                                    n_values=binNum)
    if (clearbuffer==True):
        counter.clear()
    counter.startFor(capture_duration=int(countingTime*1e12))

    counter.waitUntilFinished()
    Couter_data = np.asarray(counter.getData())
    CounterTimebins_data=np.asarray(counter.getIndex())
    return CounterTimebins_data,Couter_data

def getCountrate(tagger:TimeTagger.TimeTagger, measurementChannel,countingTime,clearbuffer=True):
    
    countRate = TimeTagger.Countrate(tagger=tagger,channels=[measurementChannel])
    if (clearbuffer==True):
        countRate.clear()
    countRate.startFor(capture_duration=int(countingTime*1e12))
    countRate.waitUntilFinished()
    Couter_data =np.asarray(countRate.getData())
    # Couter_data =(countRate.getData())
    
    # CounterTimebins_data=np.asarray(countRate.getIndex())
    # return CounterTimebins_data,Couter_data[0,:]
    return Couter_data



from dataclasses import dataclass
@dataclass
class CoincidenceResults:
    channel1_counts: int
    channel2_counts: int
    coincidences: int
    channel1_rate: float
    channel2_rate: float
    coincidence_rate: float
    accidental_rate: float
    contrast_CAR: float


def getCoincidences(tagger:TimeTagger.TimeTagger, measurementChannels, binWidth, countingTime) -> CoincidenceResults:
    coincidenceMeasurement = TimeTagger.Coincidence(
        tagger=tagger,
        channels=measurementChannels,
        coincidenceWindow=binWidth,
        timestamp=TimeTagger.CoincidenceTimestamp.Last
    )
    coincidenceChannel = coincidenceMeasurement.getChannel()

    coincidenceRate = TimeTagger.Countrate(
        tagger=tagger,
        channels=[*measurementChannels, coincidenceChannel]
    )
    coincidenceRate.startFor(int(countingTime* 1e12))
    coincidenceRate.waitUntilFinished()

    channel1Counts, channel2Counts, coincidences = coincidenceRate.getCountsTotal()
    countingTimeInSec = countingTime
    
    channel1_rate = channel1Counts / countingTimeInSec
    channel2_rate = channel2Counts / countingTimeInSec
    coincidence_rate = coincidences / countingTimeInSec

    contrast_CAR = -1
    accidental_rate=-1
    if channel1Counts != 0 and channel2Counts != 0:
        #accidentals = channel1Counts * channel2Counts * 2 * (binWidth * 1e-12)  #conver bin_width in ps to sec
        accidental_rate = channel1_rate * channel2_rate *2 * (binWidth * 1e-12) 
        
        # CAR calculation following Bristol thesis 
        # Where CAR = Rcc / Racc
        # Rcc = Coincidence Rate (including accidentals)
        # Racc = Accidental rate
   
        contrast_CAR = coincidence_rate / accidental_rate
    CoincidenceData=CoincidenceResults(
        channel1_counts=channel1Counts,
        channel2_counts=channel2Counts,
        coincidences=coincidences,
        channel1_rate=channel1_rate,
        channel2_rate=channel2_rate,
        coincidence_rate=coincidence_rate,
        accidental_rate=accidental_rate,
        contrast_CAR=contrast_CAR
    )
    return CoincidenceData


def getCoincidencesAndCorrelations(tagger:TimeTagger.TimeTagger, measurementChannels, binWidth,binNum, countingTime,PlotResutls=True) -> CoincidenceResults:
    coincidenceMeasurement = TimeTagger.Coincidence(
        tagger=tagger,
        channels=measurementChannels,
        coincidenceWindow=binWidth,
        timestamp=TimeTagger.CoincidenceTimestamp.Last
    )
    coincidenceChannel = coincidenceMeasurement.getChannel()

    coincidenceRate = TimeTagger.Countrate(
        tagger=tagger,
        channels=[*measurementChannels, coincidenceChannel]
    )
    correlation = TimeTagger.Correlation(tagger=tagger,
                                     channel_1=measurementChannels[0],
                                     channel_2=measurementChannels[1],
                                     binwidth=binWidth,
                                     n_bins=binNum)
    
    # Run the measurement and wait for the results 
    coincidenceRate.startFor(int(countingTime* 1e12)) 
    coincidenceRate.waitUntilFinished()

    # Process the Coincidence results
    channel1Counts, channel2Counts, coincidences = coincidenceRate.getCountsTotal()
    countingTimeInSec = countingTime

    channel1_rate = channel1Counts / countingTimeInSec
    channel2_rate = channel2Counts / countingTimeInSec
    coincidence_rate = coincidences / countingTimeInSec

    contrast_CAR = 0
    if channel1Counts != 0 and channel2Counts != 0:
        #accidentals = channel1Counts * channel2Counts * 2 * (binWidth * 1e-12)  #conver bin_width in ps to sec
        accidental_rate = channel1_rate * channel2_rate * (binWidth * 1e-12) 
        
        # CAR calculation following Bristol thesis 
        # Where CAR = Rcc / Racc
        # Rcc = Coincidence Rate (including accidentals)
        # Racc = Accidental rate
        contrast_CAR = coincidence_rate / accidental_rate
    CoincidenceData=CoincidenceResults(
        channel1_counts=channel1Counts,
        channel2_counts=channel2Counts,
        coincidences=coincidences,
        channel1_rate=channel1_rate,
        channel2_rate=channel2_rate,
        coincidence_rate=coincidence_rate,
        accidental_rate=accidental_rate,
        contrast_CAR=contrast_CAR
    )
    # Process the Correlation results
    correlationTimebins_data=np.asarray(correlation.getIndex())
    correlation_data = np.asarray(correlation.getData())
    correlationNorm_data=np.asarray(correlation.getDataNormalized())

    if (PlotResutls):
        # Create figure and first axis
        # fig, ax1 = plt.subplots()

        # # Plot first data set on ax1
        # color = 'tab:blue'
        # ax1.set_xlabel('Time(ps)')
        # ax1.set_ylabel('Correlations (Counts/bin)', color=color)
        # ax1.plot(correlationTimebins_data, correlation_data, color=color)
        # ax1.tick_params(axis='y', labelcolor=color)

        # # Create second y-axis sharing the same x-axis
        # ax2 = ax1.twinx()  

        # # Plot second data set on ax2
        # color = 'tab:red'
        # ax2.set_ylabel('Norm Correlations (Counts/Sec)', color=color)
        # ax2.plot(correlationTimebins_data, correlationNorm_data, color=color)
        # ax2.tick_params(axis='Time(ps)', labelcolor=color)

        # # Improve layout
        # fig.tight_layout()

        fig, ax = plt.subplots(1,2, figsize=(8,3))

        # Plot first data set on ax1
        color = 'tab:blue'
        ax[0].set_xlabel('Time(ps)')
        ax[0].set_ylabel('Correlations (Counts/bin)', color=color)
        ax[0].plot(correlationTimebins_data, correlation_data, color=color, marker='o')

        #ax[0].tick_params(axis='y', labelcolor=color)

        # Plot second data set on ax2
        #color = 'tab:red'
        ax[1].set_ylabel('Norm Correlations (Counts/Sec)', color=color)
        ax[1].plot(correlationTimebins_data, correlationNorm_data, color=color, marker='o')
        #ax[1].tick_params(axis='Time(ps)', labelcolor=color)

        # Improve layout
        fig.tight_layout()


    return CoincidenceData,correlationTimebins_data,correlation_data,correlationNorm_data
    
def VisibiliityCal(time_arr, Coincidence_arr, epsilon=520, threshold=1000, search_window=2000):
    """
    Compute g²(0) from a histogram of time differences using only NumPy arrays.

    Parameters:
        time_ps (np.ndarray): Array of time differences (in ps).
        counts (np.ndarray): Array of counts corresponding to time_ps bins.
        epsilon (float): Half-width (in ps) around each peak to include for area.
        threshold (float): Minimum height to identify side peaks.
        search_window (float): Range (in ps) around 0 to search for the central peak.

    Returns:
        dict: {
            'central_peak_time': float,
            'central_area': float,
            'average_side_area': float,
            'g2': float,
            'side_regions': list of (start_ps, end_ps)
        }
    """

    # Identify side peaks above the threshold
    peaks, _ = find_peaks(Coincidence_arr, height=threshold)
    peak_times = time_arr[peaks]

    # Find the central peak within a search window around zero
    central_mask = np.abs(time_arr) <= search_window
    central_window_counts = Coincidence_arr[central_mask]
    central_window_times = time_arr[central_mask]
    central_idx = np.argmax(central_window_counts)
    central_peak_time = central_window_times[central_idx]

    # Define central integration region and compute area
    central_start = central_peak_time - epsilon
    central_end = central_peak_time + epsilon
    central_region_mask = (time_arr >= central_start) & (time_arr <= central_end)
    central_area = np.sum(Coincidence_arr[central_region_mask])

    # Compute side peak areas (excluding overlap with central region)
    side_areas = []
    side_regions = []

    for t in peak_times:
        if (t + epsilon < central_start) or (t - epsilon > central_end):
            region_mask = (time_arr >= t - epsilon) & (time_arr <= t + epsilon)
            side_area = np.sum(Coincidence_arr[region_mask])
            side_areas.append(side_area)
            side_regions.append((t - epsilon, t + epsilon))

    average_side_area = np.mean(side_areas)
    Visibiliity = central_area / average_side_area if average_side_area > 0 else np.nan

    # Plot the histogram and marked regions
    plt.figure(figsize=(12, 6))
    plt.plot(time_arr, Coincidence_arr, linewidth=0.8, label="Histogram")

    for start, end in side_regions:
        plt.axvline(start, color='purple', linestyle='dashed', linewidth=1)
        plt.axvline(end, color='purple', linestyle='dashed', linewidth=1)

    plt.axvline(central_start, color='red', linestyle='dashed', linewidth=1, label='Central Region')
    plt.axvline(central_end, color='red', linestyle='dashed', linewidth=1)

    plt.xlabel("Time differences (ps)")
    plt.ylabel("Counts per bin")
    plt.title("g²(0) with ε = {} ps around the peak \n$g^{{(2)}}(0)$ = {:.3f}".format(epsilon, Visibiliity))
    plt.grid(True)
    plt.tight_layout()
    plt.legend()
    plt.show()

    return Visibiliity 
