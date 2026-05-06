
import numpy as np
import time
import multiprocessing
from multiprocessing import shared_memory
import TimeTagger
import cv2
# Importing necessary libraries
import sys
import matplotlib.pyplot as plt
import numpy as np
import cv2
import multiprocessing
from multiprocessing import shared_memory
import time
import copy
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

import JazLabs.hardware.TimeTagger.TimeTaggerFunction as TimetaggerFunc
IMAGE_X = 1600
IMAGE_Y = 580
THREAD_SLEEP_TIME=1e-12
from queue import Empty  # Note: 'Empty' exception is imported from the queue module

def clear_queue(q):
    try:
        while True:
            q.get_nowait()
    except Empty:
        pass
# Function to convert a matplotlib plot to an OpenCV-compatible image
def plot_to_opencv_img(fig):
    """
    Converts a Matplotlib figure to an OpenCV image for display.

    Args:
        fig (matplotlib.figure.Figure): The Matplotlib figure to convert.

    Returns:
        numpy.ndarray: OpenCV-compatible image.
    """
    canvas = FigureCanvas(fig)
    canvas.draw()  # Render the figure onto the canvas
    buf = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)  # Get the RGB buffer
    buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))  # Reshape to image dimensions
    return cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)  # Convert RGB to BGR for OpenCV

def displayCounts(measurementChannels, channel1Counts, channel2Counts, coincidences, coincidencesAverage,
                  coincidencesDeviation, contrast, contrastAverage, contrastDeviation):

    font_scale = 2.5
    thickness = 3
    text_color = (255, 255, 255)
    margin = 10
    line_spacing = 30
    font = cv2.FONT_HERSHEY_DUPLEX
    image = np.zeros((IMAGE_Y, IMAGE_X, 3), np.uint8)

    # Prepare your text lines separately, clearly defining two columns
    lines = [
        f"Ch{measurementChannels[0]}: {channel1Counts}",
        f"Ch{measurementChannels[1]}: {channel2Counts}",
        "",
        f"{'Coincidence':<20}{'CAR':>20}",
        f"{'Current: ':<1}{coincidences:<10}{'Current: ':>15}{contrast:<10}",
        f"{'Avg: ':<1}{coincidencesAverage:<10.3f}{'Avg: ':>15}{contrastAverage:<10.3f}",
        f"{'Std: ':<1}{coincidencesDeviation:<10.3f}{'Std: ':>15}{contrastDeviation:<10.3f}",
    ]

    # Decide fixed horizontal positions (in pixels)
    left_col_x = margin
    right_col_x = IMAGE_X // 2  # midpoint, adjust as needed

    text_y_start = 60  # start drawing a bit lower to fit neatly
    for i, line in enumerate(lines):
        text_y = text_y_start + i * (50 + line_spacing)

        if i < 3:  # For the first 3 lines (channel counts and empty line)
            cv2.putText(image, line, (left_col_x, text_y), font, font_scale, text_color, thickness)
        else:
            # Split the line clearly into two columns (Coincidence | CAR)
            coincidence_part = line[:len(line)//2].rstrip()
            car_part = line[len(line)//2:].lstrip()

            cv2.putText(image, coincidence_part, (left_col_x, text_y), font, font_scale, text_color, thickness)
            cv2.putText(image, car_part, (right_col_x, text_y), font, font_scale, text_color, thickness)

    cv2.imshow('Counting Window', image)


def displayError(error, imageSize, windowName):
    image = np.zeros(imageSize, np.uint8)
    cv2.putText(image, str(error), (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imshow(windowName, image)



class TimeTaggerLiveDisplayThread:
    """
    Encapsulates a multiprocessing thread for real-time data processing and visualization.

    This class handles the creation of shared memory buffers, synchronization events,
    and the management of a background thread that performs operations such as 
    generating sine wave data and updating parameters dynamically.
    """

    def __init__(self):
        """
        Initializes the thread object, shared memory buffers, and synchronization events.
        """
        
        # Events for synchronizing actions between processes
        self.GetCountsDataEvent = multiprocessing.Event()  # Signal to retrieve data
        self.SetBinWidthEvent = multiprocessing.Event()  # Signal to set amplitude
        self.SetCountTimeEvent = multiprocessing.Event()  # Signal to set phase shift
        self.SetAvgNumOfCountMeasEvent = multiprocessing.Event()  # Signal to set phase shift
        self.PauseThreadEvent = multiprocessing.Event()  # Signal to set phase shift
        self.CreateReleaseTaggerEvent = multiprocessing.Event()  # Signal to set phase shift
        self.SetTriggerLevelEvent = multiprocessing.Event()  # Signal to set phase shift
        self.SetChannelEvent = multiprocessing.Event()  # Signal to set phase shift
        self.SetDisplayNormalisedValuesEvent= multiprocessing.Event()  # Signal to set phase shift

        self.terminateThreadEvent = multiprocessing.Event()  # Signal to terminate thread

        # Shared placeholder value for passing parameters between processes
        self.sharedFloat = multiprocessing.Value('f', 0.0)  # Float value
        self.sharedInt = multiprocessing.Value('i', 0)  # Float value

        # Queue for thread communication
        self.queue = multiprocessing.Queue()

        # Set the size of data arrays (e.g., based on device output, here set to 1024)
        self.Narr = 1024

        # Shared memory buffer for oscilloscope data
        self.sharedMemoryCounts = shared_memory.SharedMemory(create=True, size=int(4 * np.dtype(int).itemsize))
        self.sharedMemoryCountsName = self.sharedMemoryCounts.name
        self.countsarr_shm = np.ndarray((4), dtype=np.dtype(int), buffer=self.sharedMemoryCounts.buf)
        self.countsarr=np.zeros(4,dtype=int)
        # Start the thread process
        self.Process = self.start_Thread()


    def __del__(self):
        """
        Destructor to clean up resources when the object is deleted.

        This ensures that the background thread is terminated, shared memory buffers are closed,
        and all allocated resources are released.
        """
        print("Cleaning up resources...")
        self.terminateThreadEvent.set()  # Signal thread termination

        # Close shared memory buffers
        self.sharedMemoryCounts.close()

        # Terminate and join the thread process
        self.Process.terminate()
        self.Process.join()

        # Unlink shared memory buffers to release resources
        self.sharedMemoryCounts.unlink()

    def start_Thread(self):
        """
        Starts the background thread process.

        The thread runs the `HelloWorldThread` function with required parameters.
        """
        process = multiprocessing.Process(target=TaggerLiveThreadWindow, args=(
            self.queue, 
            self.terminateThreadEvent, 
            self.PauseThreadEvent,
            self.CreateReleaseTaggerEvent,
            self.SetTriggerLevelEvent,
            self.SetChannelEvent,
            self.SetDisplayNormalisedValuesEvent,
            self.GetCountsDataEvent,
            self.SetBinWidthEvent,
            self.SetCountTimeEvent,
            self.SetAvgNumOfCountMeasEvent,
            self.sharedMemoryCountsName, 
            self.sharedFloat,
            self.sharedInt
        ))
        process.start()  # Start the process
        return process



    def GetCountsData(self):
        self.GetCountsDataEvent.set()  # Signal to retrieve data

        # Wait until the thread updates the shared memory
        while self.GetCountsDataEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)
        np.copyto(self.countsarr,self.countsarr_shm)
        return self.countsarr
    
    def SetBinWidth(self,NewbinWidth):
        self.sharedInt.value=int(NewbinWidth)
        self.SetBinWidthEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memory
        while self.SetBinWidthEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)
            
    def SetCountTime(self,NewCountTime):
        self.sharedFloat.value=(NewCountTime)
        self.SetCountTimeEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memory
        while self.SetCountTimeEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)

    def SetAvgNumOfCountMeas(self,NewAvgNumOfCountMeas):
        self.sharedInt.value=int(NewAvgNumOfCountMeas)
        self.SetAvgNumOfCountMeasEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memory
        while self.SetAvgNumOfCountMeasEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)

    def SetTriggerLevel(self,channel=1,NewTriggerLevel=0.5):
        self.sharedInt.value=int(channel)
        self.sharedFloat.value=round(NewTriggerLevel, 3)
        self.SetTriggerLevelEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memory
        while self.SetTriggerLevelEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)
        print("Trigger Level was set to : " +str(self.sharedFloat.value))

    def SetSetChanneL(self,Channel_idx,NewChannel):


        if Channel_idx not in (0, 1):
            print("Channel_idx needs to be either 0 or 1")
            return
        self.sharedInt.value=int(NewChannel)
        self.sharedFloat.value=float(Channel_idx)
        self.SetChannelEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memsry
        while self.SetChannelEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)

    def CreateReleaseTagger(self):
        clear_queue(self.queue)     
        self.CreateReleaseTaggerEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memory
        while self.CreateReleaseTaggerEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)
        print(self.queue.get_nowait())
        # self.queue.clear()

    def SetPausePlayTimeTagger(self):
        if(self.PauseThreadEvent.is_set()):
            self.PauseThreadEvent.clear()
            self.CreateReleaseTagger()

        else:
            self.PauseThreadEvent.set()
            self.CreateReleaseTagger()

    def SetDisplayNormalisedValues(self,DisplayNormalisedValues=True):
        if DisplayNormalisedValues:
            self.sharedInt.value=1
        else:
            self.sharedInt.value=0

        self.SetDisplayNormalisedValuesEvent.set()  # Signal to retrieve data
        # Wait until the thread updates the shared memory
        while self.SetDisplayNormalisedValuesEvent.is_set():
            time.sleep(THREAD_SLEEP_TIME)




def TaggerLiveThreadWindow(queue, terminateThreadEvent, PauseThreadEvent,
                           CreateReleaseTaggerEvent,SetTriggerLevelEvent,SetChannelEvent,SetDisplayNormalisedValuesEvent,
                           GetCountsDataEvent,SetBinWidthEvent,SetCountTimeEvent,SetAvgNumOfCountMeasEvent,
                           sharedMemoryCountsName, 
                           sharedFloat,sharedInt):
    
    sharedMemoryCounts = shared_memory.SharedMemory(name=sharedMemoryCountsName)
    countsarr_shm = np.ndarray((4), dtype=np.dtype(int), buffer=sharedMemoryCounts.buf)
    

    coincidencesHistory = []
    contrastHistory = []
    coincidencesAverage = 0
    coincidencesDeviation = 0
    contrastAverage = 0
    contrastDeviation = 0

    image = np.zeros((IMAGE_Y, IMAGE_X, 3), np.uint8)
    binWidth=100
    measurementChannels=[1,2]
    countingTime=0.1
    numberSamples=1
    
    cv2.imshow('Counting Window', image)
    
    DisplayNormalisedValues=True

    DeviceIsCreated=False
    CreateReleaseTaggerEvent.set()
    # queue.put("test1")
    while not terminateThreadEvent.is_set():
        if (CreateReleaseTaggerEvent.is_set()):
            if not(DeviceIsCreated):
                try:
                    tagger = TimeTagger.createTimeTagger()
                    DeviceIsCreated=True
                    queue.put("TimeTagger Connected")
                except RuntimeError as e:
                    queue.put(e)
                    DeviceIsCreated=False
            else:
                TimeTagger.freeTimeTagger(tagger)
                DeviceIsCreated=False
                queue.put("TimeTagger was released from the thread run function again to reconnect")

            CreateReleaseTaggerEvent.clear()
        
        while (not (PauseThreadEvent.is_set()) and DeviceIsCreated):
            coinData=TimetaggerFunc.getCoincidences(tagger,measurementChannels,binWidth,countingTime)
            if(DisplayNormalisedValues):
                channel1Counts=coinData.channel1_rate
                channel2Counts=coinData.channel2_rate
                coincidences=coinData.coincidence_rate
            else:
                channel1Counts=coinData.channel1_counts
                channel2Counts=coinData.channel2_counts
                coincidences=coinData.coincidences
            contrast=coinData.contrast_CAR
            
            # This is to get a average measurement over a number of times
            # it should be very similar to increasing the measurement time
            coincidencesHistory.append(coincidences)
            contrastHistory.append(contrast)

            if len(coincidencesHistory) > numberSamples:
                coincidencesHistory.pop(0)
                contrastHistory.pop(0)
                
                coincidencesAverage = np.mean(coincidencesHistory)
                coincidencesDeviation = int(np.std(coincidencesHistory))
                contrastAverage = np.mean(contrastHistory)
                contrastDeviation = int(np.std(contrastHistory))
                
            displayCounts(measurementChannels,channel1Counts,channel2Counts,coincidences,
                        coincidencesAverage,coincidencesDeviation,
                        contrast,contrastAverage,contrastDeviation)
            
            if (GetCountsDataEvent.is_set()):
                np.copyto(countsarr_shm,np.asarray([channel1Counts,channel2Counts,coincidences,contrast]))
                GetCountsDataEvent.clear()
           
            if (SetBinWidthEvent.is_set()):
                binWidth=sharedInt.value
                SetBinWidthEvent.clear()
           
            if (SetCountTimeEvent.is_set()):
                countingTime=sharedFloat.value
                SetCountTimeEvent.clear()
           
            if (SetAvgNumOfCountMeasEvent.is_set()):
                numberSamples=sharedInt.value
                SetAvgNumOfCountMeasEvent.clear()

            if (SetTriggerLevelEvent.is_set()):
                triggerLevel=sharedFloat.value
                channel=sharedInt.value
                tagger.setTriggerLevel(channel, triggerLevel)
                actualTiggerLevel=tagger.getTriggerLevel(channel)
                sharedFloat.value=actualTiggerLevel
                SetTriggerLevelEvent.clear()

            if (SetChannelEvent.is_set()):
                NewChannel=sharedInt.value
                NewChannel_Idx=int(sharedFloat.value)
                measurementChannels[NewChannel_Idx]=NewChannel
                SetChannelEvent.clear()

            if (SetDisplayNormalisedValuesEvent.is_set()):
                temp=sharedInt.value
                if temp==0:
                    DisplayNormalisedValues=False
                else:
                    DisplayNormalisedValues=True
               
                SetDisplayNormalisedValuesEvent.clear()

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        

        
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    cv2.destroyAllWindows()

    sharedMemoryCounts.close()
    

    return

