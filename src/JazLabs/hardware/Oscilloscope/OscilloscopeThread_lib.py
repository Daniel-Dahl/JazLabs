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
import Oscilloscope_lib as Osclib

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

def OscScopeThread(ScopeID, queue, terminateThreadEvent, sharedMemoryNameOscBuffer, sharedMemoryNameTimeArrBuffer, Narr,
                   get_dataEvent, set_TimeScaleEvent, set_AutoSetEvent, Get_VoltageScaleEvent, PlaceHolder):
    """
    Thread function to interface with an oscilloscope, retrieve and display data, and handle user-triggered events.

    Args:
        ScopeID (str): Identifier for the oscilloscope device.
        queue (multiprocessing.Queue): Queue for inter-process communication.
        terminateThreadEvent (multiprocessing.Event): Event to signal thread termination.
        sharedMemoryNameOscBuffer (str): Shared memory name for oscilloscope data buffer.
        sharedMemoryNameTimeArrBuffer (str): Shared memory name for time array buffer.
        Narr (int): Number of data points in arrays.
        get_dataEvent (multiprocessing.Event): Event to trigger data retrieval.
        set_TimeScaleEvent (multiprocessing.Event): Event to trigger time scale adjustment.
        set_AutoSetEvent (multiprocessing.Event): Event to trigger the Auto Set function on the oscilloscope.
        Get_VoltageScaleEvent (multiprocessing.Event): Event to trigger voltage scale retrieval.
        PlaceHolder (multiprocessing.Value): Shared placeholder for passing parameters and storing results.
    """
    # Initialise shared memory for oscilloscope data
    shmOscBuffer = shared_memory.SharedMemory(name=sharedMemoryNameOscBuffer)
    Osc_buffer = np.ndarray((Narr), dtype=np.float64, buffer=shmOscBuffer.buf)

    shmTimeArrBuffer = shared_memory.SharedMemory(name=sharedMemoryNameTimeArrBuffer)
    TimeArr_buffer = np.ndarray((Narr), dtype=np.float64, buffer=shmTimeArrBuffer.buf)

    # Initialise the oscilloscope object
    OscScopeObj = Osclib.OscScope(ScopeID)

    # Retrieve initial data from the oscilloscope
    t_arr, Oscdata = OscScopeObj.Getdata(False, 1)

    # Set up a Matplotlib plot for live visualization
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    OscDataPlot = ax.plot(t_arr, Oscdata)[0]  # Plot the initial data
    ax.set_xlabel('x')  # Label for the x-axis
    ax.set_ylabel('y')  # Label for the y-axis
    ax.set_ylim(np.min(Oscdata) - np.abs(np.min(Oscdata)) * 0.2, np.max(Oscdata) + np.abs(np.max(Oscdata) * 0.2))
    ax.set_xlim([np.min(t_arr), np.max(t_arr)])

    # Name for the OpenCV window
    opencvWindowName = "Oscilloscope"

    # Main loop: runs until the thread termination event is triggered
    while not terminateThreadEvent.is_set():
        # Update the plot with the latest data
        OscDataPlot.set_xdata(t_arr)
        OscDataPlot.set_ydata(Oscdata)
        ax.set_xlim(min(t_arr), max(t_arr))
        ax.set_ylim(np.min(Oscdata) - np.abs(np.min(Oscdata)) * 0.2, np.max(Oscdata) + np.abs(np.max(Oscdata) * 0.2))
        fig.canvas.draw_idle()  # Redraw the figure
        imag = plot_to_opencv_img(fig)  # Convert the plot to an OpenCV-compatible image
        cv2.imshow(opencvWindowName, imag)  # Display the image in an OpenCV window

        # Retrieve updated data from the oscilloscope
        t_arr, Oscdata = OscScopeObj.Getdata(False, 1)

        # Handle data retrieval event
        if get_dataEvent.is_set():
            np.copyto(Osc_buffer, Oscdata)  # Copy oscilloscope data to shared memory
            np.copyto(TimeArr_buffer, t_arr)  # Copy time array data to shared memory
            get_dataEvent.clear()  # Clear the event flag

        # Handle time scale adjustment event
        if set_TimeScaleEvent.is_set():
            TimeScale = PlaceHolder.value  # Retrieve the desired time scale from the placeholder
            OscScopeObj.SetTimeScale(TimeScale)  # Set the oscilloscope's time scale
            set_TimeScaleEvent.clear()  # Clear the event flag

        # Handle Auto Set function event
        if set_AutoSetEvent.is_set():
            OscScopeObj.SetAutoSet()  # Automatically adjust the oscilloscope settings
            set_AutoSetEvent.clear()  # Clear the event flag

        # Handle voltage scale retrieval event
        if Get_VoltageScaleEvent.is_set():
            PlaceHolder.value = OscScopeObj.GetVoltageScale()  # Retrieve and store the voltage scale
            Get_VoltageScaleEvent.clear()  # Clear the event flag

        # Check for manual termination (e.g., pressing 'q')
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    # Clean up: Close OpenCV windows and release shared memory
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    shmOscBuffer.close()
    shmTimeArrBuffer.close()

    # Delete the oscilloscope object to release resources
    del OscScopeObj
    return


class OscScopeThreadObj:
    """
    Encapsulates the functionality for interfacing with an oscilloscope in a separate thread,
    using shared memory and events for efficient data exchange and control.
    """
    def __init__(self, ScopeID='USB0::1689::931::C016906::0::INSTR'):
        """
        Initializes the oscilloscope thread object, shared memory buffers, and synchronization events.

        Args:
            ScopeID (str): The identifier for the oscilloscope device.
        """
        # Oscilloscope device identifier
        self.ScopeID = ScopeID

        # Events for synchronizing actions between the thread and the main process
        self.get_dataEvent = multiprocessing.Event()  # Signal to retrieve data
        self.set_TimeScaleEvent = multiprocessing.Event()  # Signal to set time scale
        self.set_AutoSetEvent = multiprocessing.Event()  # Signal to trigger Auto Set
        self.Get_VoltageScaleEvent = multiprocessing.Event()  # Signal to get voltage scale
        self.terminateThreadEvent = multiprocessing.Event()  # Signal to terminate thread

        # Shared placeholder value for passing parameters between processes
        self.PlaceHolder = multiprocessing.Value('f', 0.0)  # Float placeholder

        # Queue for thread communication
        self.queue = multiprocessing.Queue()

        # Make an initial connection to the oscilloscope to set up parameters
        OscScopeObj = Osclib.OscScope(self.ScopeID)

        # Determine the number of data points from the oscilloscope
        self.Narr = OscScopeObj.Ndata

        # Initialize shared memory for oscilloscope data
        self.sharedMemoryOscBuffer = shared_memory.SharedMemory(create=True, size=int(self.Narr * np.dtype(float).itemsize))
        self.sharedMemoryNameOscBuffer = self.sharedMemoryOscBuffer.name
        self.OscBuffer_shm = np.ndarray((self.Narr), dtype=np.float64, buffer=self.sharedMemoryOscBuffer.buf)

        # Initialize shared memory for time array data
        self.sharedMemoryTimeArrBuffer = shared_memory.SharedMemory(create=True, size=int(self.Narr * np.dtype(float).itemsize))
        self.sharedMemoryNameTimeArrBuffer = self.sharedMemoryTimeArrBuffer.name
        self.TimeArrBuffer_shm = np.ndarray((self.Narr), dtype=np.float64, buffer=self.sharedMemoryTimeArrBuffer.buf)

        # Clean up the temporary oscilloscope object
        del OscScopeObj

        # Start the oscilloscope thread
        self.Process = self.start_Thread()

    def __del__(self):
        """
        Destructor to clean up resources when the object is deleted.

        Ensures the thread is terminated and shared memory buffers are released.
        """
        print("Cleaning up resources...")
        self.terminateThreadEvent.set()  # Signal thread termination

        # Close shared memory buffers
        self.sharedMemoryOscBuffer.close()
        self.sharedMemoryTimeArrBuffer.close()

        # Terminate and join the thread process
        self.Process.terminate()
        self.Process.join()

        # Unlink shared memory buffers to release resources
        self.sharedMemoryOscBuffer.unlink()
        self.sharedMemoryTimeArrBuffer.unlink()

    def start_Thread(self):
        """
        Starts the oscilloscope thread process.

        Returns:
            multiprocessing.Process: The process running the oscilloscope thread.
        """
        process = multiprocessing.Process(target=OscScopeThread, args=(
            self.ScopeID,
            self.queue,
            self.terminateThreadEvent,
            self.sharedMemoryNameOscBuffer,
            self.sharedMemoryNameTimeArrBuffer,
            self.Narr,
            self.get_dataEvent,
            self.set_TimeScaleEvent,
            self.set_AutoSetEvent,
            self.Get_VoltageScaleEvent,
            self.PlaceHolder
        ))
        process.start()
        return process

    def GetData(self):
        """
        Retrieves data from the oscilloscope via shared memory.

        Returns:
            tuple: The time array and oscilloscope data from shared memory.
        """
        self.get_dataEvent.set()  # Signal to retrieve data

        # Wait until the data retrieval is complete
        while self.get_dataEvent.is_set():
            time.sleep(1e-12)

        return self.TimeArrBuffer_shm, self.OscBuffer_shm

    def SetTimeScale(self, TimeScale):
        """
        Sets the time scale on the oscilloscope.

        Args:
            TimeScale (float): The desired time scale value.
        """
        self.PlaceHolder.value = TimeScale  # Update the placeholder value
        self.set_TimeScaleEvent.set()  # Signal to update the time scale

        # Wait until the update is complete
        while self.set_TimeScaleEvent.is_set():
            time.sleep(1e-12)
        return

    def SetAutoSet(self):
        """
        Triggers the Auto Set function on the oscilloscope.
        """
        self.set_AutoSetEvent.set()  # Signal to trigger Auto Set

        # Wait until the Auto Set operation is complete
        while self.set_AutoSetEvent.is_set():
            time.sleep(1e-12)
        return

    def GetVoltageScale(self):
        """
        Retrieves the voltage scale from the oscilloscope.

        Returns:
            float: The current voltage scale of the oscilloscope.
        """
        self.Get_VoltageScaleEvent.set()  # Signal to retrieve the voltage scale

        # Wait until the voltage scale retrieval is complete
        while self.Get_VoltageScaleEvent.is_set():
            time.sleep(1e-12)

        return self.PlaceHolder.value