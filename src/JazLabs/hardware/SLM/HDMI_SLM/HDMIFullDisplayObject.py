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

from screeninfo import get_monitors


class SLMObject:
    """
    Encapsulates a multiprocessing thread for real-time data processing and visualization.

    This class handles the creation of shared memory buffers, synchronization events,
    and the management of a background thread that performs operations such as 
    generating sine wave data and updating parameters dynamically.
    """

    def __init__(self,monitor_index=1,RefreshRate=500e-3):
        
        self.NumberOfChannels=3
        
        """
        Initializes the thread object, shared memory buffers, and synchronization events.
        """
        # Events for synchronizing actions between processes
        self.UpdateDisplay = multiprocessing.Event()  # Signal to retrieve data
        self.Doorbell = multiprocessing.Event()  # Signal to update parameters
        self.terminateThreadEvent = multiprocessing.Event()  # Signal to terminate thread
        # Queue for thread communication
        self.queue = multiprocessing.Queue()

        self.monitor_x,self.monitor_y,self.monitor_height, self.monitor_width=_opencv_display_on_monitor(monitor_index)

        # Shared memory buffer for oscilloscope data
        self.sharedMemoryDisplayBuffer = shared_memory.SharedMemory(create=True, size=int(self.monitor_height* self.monitor_width* 3 * np.dtype(np.uint8).itemsize))
        self.sharedMemoryDisplayBufferName = self.sharedMemoryDisplayBuffer.name
        self.DisplayBuffer_arr_shm = np.ndarray((self.monitor_height, self.monitor_width, 3), dtype=np.uint8, buffer=self.sharedMemoryDisplayBuffer.buf)
        self.RefreshRate=RefreshRate
        self.DisplayBuffer_arr_shm.fill(0)
      
        # Start the thread process
        self.Process = self.start_Thread()



    def __del__(self):
        self.shutdown()

    def shutdown(self):
        """
        Clean up child process and shared memory.
        """
        try:
            print("Cleaning up resources...")
            if hasattr(self, "terminateThreadEvent"):
                self.terminateThreadEvent.set()
            if hasattr(self, "Doorbell"):
                self.Doorbell.set()
            time.sleep(0.2)
            if hasattr(self, "Process") and self.Process is not None:
                if self.Process.is_alive():
                    self.Process.join(timeout=2)
                if self.Process.is_alive():
                    self.Process.terminate()
                    self.Process.join(timeout=1)
            if hasattr(self, "sharedMemoryDisplayBuffer"):
                try:
                    self.sharedMemoryDisplayBuffer.close()
                except Exception:
                    pass
                try:
                    self.sharedMemoryDisplayBuffer.unlink()
                except Exception:
                    pass
            print("Destroyed SLMObject and cleaned up resources.")
        except Exception as e:
            print(f"Error during shutdown: {e}")
            
            

    def start_Thread(self):
        """
        Starts the background thread process.

        The thread runs the `HelloWorldThread` function with required parameters.
        """
        process = multiprocessing.Process(target=SLMScreenDisplayThread, args=(
            self.queue,
            self.terminateThreadEvent,
            self.Doorbell,
            self.UpdateDisplay,
            self.sharedMemoryDisplayBufferName,
             self.monitor_x,
             self.monitor_y,
             self.monitor_height, 
             self.monitor_width
        ))
        process.start()  # Start the process
        return process

    def WriteImageToSLM(self,NewImage=None,channelIdx=0):
        if NewImage is not None:
            NewImage.shape
            if  (NewImage.shape[0] == self.monitor_height and NewImage.shape[1]== self.monitor_width):
                
                np.copyto(self.DisplayBuffer_arr_shm[:,:,channelIdx],NewImage)
                self.UpdateDisplay.set()
                self.Doorbell.set()
                
                if self.RefreshRate > 0:
                    time.sleep(self.RefreshRate)
            else:
                print("New image incorrect dimensions for screen display. Display not updated")
        else:
            print("No image sent")
            return 
             
        
            
    def SetRefreshRate(self,NewRefreshRate):
        self.RefreshRate=NewRefreshRate
    def LoadLutFile(self, *args, **kwargs):
        print("LUT loading not supported for HDMI SLM")
    def GetSLMTemperature(self):
        print("Temperature readback not supported for HDMI SLM")
        return None
    def SetTriggerOutput(self, *args, **kwargs):
        print("Trigger output not supported for HDMI SLM")
        
def _opencv_display_on_monitor(monitor_index=0):
    # Retrieve information about all connected monitors
    monitors = get_monitors()
    if monitor_index >= len(monitors):
        print(f"Monitor index {monitor_index} out of range. Using primary monitor instead.")
        monitor = monitors[0]
    else:
        monitor = monitors[monitor_index]

    # Get the monitor's position and dimensions
    monitor_x = monitor.x
    monitor_y = monitor.y
    monitor_width = monitor.width
    monitor_height = monitor.height
    print(f"Using monitor {monitor_index}: x={monitor_x}, y={monitor_y}, width={monitor_width}, height={monitor_height}")
    return monitor_x,monitor_y,monitor_height, monitor_width

def SLMScreenDisplayThread(queue, terminateThreadEvent,Doorbell,UpdateDisplay, sharedMemoryNameDisplayBuffer,
                           monitor_x,monitor_y,monitor_height, monitor_width):
    """
    A multiprocessing thread function to generate and display a sine wave.
    """
    # Access shared memory buffers
    DisplayBuffer = shared_memory.SharedMemory(name=sharedMemoryNameDisplayBuffer)
    DisplayBuffer_arr_shm = np.ndarray((monitor_height, monitor_width, 3), dtype=np.uint8, buffer=DisplayBuffer.buf)
    opencvWindowName = "SLMFullScreen"
    # Create a window that we can position manually
    cv2.namedWindow(opencvWindowName, cv2.WINDOW_NORMAL)

    # Set window to full screen mode if desired
    cv2.setWindowProperty(opencvWindowName, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    # Move the window to the monitor's position
    cv2.moveWindow(opencvWindowName, monitor_x, monitor_y)
    cv2.imshow(opencvWindowName, DisplayBuffer_arr_shm)
    cv2.waitKey(1)
    

    # Main loop for updating and displaying the sine wave
    while not terminateThreadEvent.is_set():
        Doorbell.wait()
        Doorbell.clear()
        if terminateThreadEvent.is_set():
            break
        if UpdateDisplay.is_set():
            cv2.imshow(opencvWindowName, DisplayBuffer_arr_shm)
            UpdateDisplay.clear()
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Clean up OpenCV windows and shared memory
    try:
        cv2.destroyWindow(opencvWindowName)
        cv2.waitKey(1)
    except Exception:
        pass
    try:
        cv2.destroyAllWindows()
        cv2.waitKey(1)
    except Exception:
        pass
    
    DisplayBuffer.close()

    return