from Lab_Equipment.Config import config
import numpy as np
import time
import multiprocessing
from multiprocessing import shared_memory
import cv2
from moku.instruments import PIDController
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import ctypes

"""Important notes: 
 The process function cannot be a method in a class. When a process
is created, there is a bunch of memory that has to be duplicated
in a procedure called pickling. If self is an argument to the 
function, then the process manager has to pickle the class
which might not be pickleable.

See https://dannyvanpoucke.be/parallel-python-classes-pickle/.
"""
# Function to convert a matplotlib plot to an OpenCV image
def plot_to_opencv_img(fig):
    canvas = FigureCanvas(fig)
    canvas.draw()
    buf = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
    buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    return cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)

class MokuObject():
    def __init__(self,MokuID='[fe80::7269:79ff:feb7:d15]'):
            super().__init__() # inherit from parent class  
            self.MokuID=MokuID
            self.pid_input_offset = multiprocessing.Value('f', -0.2) # in ps int(1e-9 *1e12)
            self.pid_int_crossover = multiprocessing.Value('f', 468e-3) # in ps int(1e-9 *1e12)
            self.pid_channel= multiprocessing.Value('i', 1)
            self.pid_input_gain1= multiprocessing.Value('f', 1.0)
            self.pid_input_gain2= multiprocessing.Value('f', 0.0)
            self.pid_output_low_limit= multiprocessing.Value('f', 0.0)
            self.pid_output_high_limit= multiprocessing.Value('f', 1.0)
    
            self.pid_enable_input= multiprocessing.Value('i', 1)
            self.pid_enable_output_sig= multiprocessing.Value(ctypes.c_bool, True)
            self.pid_enable_output_out= multiprocessing.Value(ctypes.c_bool, True)
            self.timebase_t1=multiprocessing.Value('f', -1)
            self.timebase_t2=multiprocessing.Value('f', 1)
            
            # stuff for graph update
            self.GraphlimitX= multiprocessing.Array('f',2)
            self.GraphlimitX[0]=self.timebase_t1.value
            self.GraphlimitX[1]=self.timebase_t2.value
            self.GraphlimitY= multiprocessing.Array('f',2)
            self.GraphlimitY[0]=0.0
            self.GraphlimitY[1]=0.3
            self.set_GraphLimitEvent= multiprocessing.Event()
            
            self.terminateThreadEvent = multiprocessing.Event()
            self.continuousCaptureMode = multiprocessing.Event()
            self.singleCaptureMode = multiprocessing.Event()
            
            self.set_enable_outputEvent = multiprocessing.Event()
            self.set_int_crossOverEvent = multiprocessing.Event()
            self.set_input_offsetEvent = multiprocessing.Event()
            
            self.set_timebaseEvent = multiprocessing.Event()
            self.get_Osc_dataEvent = multiprocessing.Event()
            
            self.queue=multiprocessing.Queue()
            
            # using Shared memory here because it is more effiecent for larger arrays then just using multiprocessing.Array
            # the memory size here is set to 1024 as that is what the moku can output
            self.Narr=1024
            self.sharedMemory_DataOsc = shared_memory.SharedMemory(create=True,size=int(2*self.Narr*np.dtype(float).itemsize))
            self.sharedMemory_DataOscName = self.sharedMemory_DataOsc.name
            self.shmDataOsc = np.ndarray((2,self.Narr), dtype=np.dtype(float), buffer=self.sharedMemory_DataOsc.buf)
            # START the Moku PID Thead
            self.MokuProcess= self.start_MokuCaptureThread(MokuCaptureThreadCaptureThread)
         
            
            
        
    def __del__(self):
        """Destructor to disconnect from camera."""
        print("Moku Class has been destroyed")
        self.terminateThreadEvent.set()# stop the camera thread
        self.sharedMemory_DataOsc.close() # close access to shared memory
        self.MokuProcess.terminate()
        self.sharedMemory_DataOsc.unlink() # clean up the shared memory space
        # cam.close_camera()
        # cam.release_driver()
    def start_MokuCaptureThread(self,MokuCaptureThreadCaptureThread):
        Process = multiprocessing.Process(target=MokuCaptureThreadCaptureThread, args=(
            self.MokuID,
            self.queue,
            self.terminateThreadEvent,
            self.continuousCaptureMode,
            self.singleCaptureMode,
            self.set_int_crossOverEvent,
            self.set_input_offsetEvent,
            self.set_timebaseEvent,
            self.set_enable_outputEvent,
            self.set_GraphLimitEvent,
            self.get_Osc_dataEvent,
            self.GraphlimitX,self.GraphlimitY,
            self.pid_channel,
            self.sharedMemory_DataOscName,
            self.Narr,
            self.timebase_t1,
            self.timebase_t2,
            self.pid_input_offset,
            self.pid_int_crossover,
            self.pid_channel,
            self.pid_input_gain1,
            self.pid_input_gain2,
            self.pid_output_low_limit,
            self.pid_output_high_limit,
            self.pid_enable_input,
            self.pid_enable_output_sig,
            self.pid_enable_output_out
            ))
        Process.start()
        return Process
    
    def SetTimebase(self,t1,t2):
        self.timebase_t1.value=t1
        self.timebase_t2.value=t2
        self.set_timebaseEvent.set()
        # need to wait here until the thread has actually set the value
        while self.set_timebaseEvent.is_set():
            time.sleep(1e-12)    
        self.GraphlimitX[:]=[t1,t2]
        self.SetGraphLimits()
            
    def SetInputOffset(self,InputOffset):
        self.pid_input_offset.value=InputOffset
        self.set_input_offsetEvent.set()
        # need to wait here until the thread has actually set the value
        while self.set_input_offsetEvent.is_set():
            time.sleep(1e-12)    
        self.SetGraphLimits()
        
             
    def SetEnablePID(self):
        self.pid_enable_output_out.value=not(self.pid_enable_output_out.value)
        self.set_enable_outputEvent.set()
        # need to wait here until the thread has actually set the value
        while self.set_enable_outputEvent.is_set():
            time.sleep(1e-12)
        self.SetGraphLimits()
            
            
    def SetInt_crossover(self,int_crossover):
        self.pid_int_crossover.value=int_crossover
        self.set_int_crossOverEvent.set()
        # need to wait here until the thread has actually set the value
        while self.set_int_crossOverEvent.is_set():
            time.sleep(1e-12)  
        self.SetGraphLimits()
               
              
    def SetSingleCapMode(self):
        self.continuousCaptureMode.clear()
        self.singleCaptureMode.set()
        
    def SetContinousCapMode(self):
        self.singleCaptureMode.clear()
        self.continuousCaptureMode.set()
        
    def Getdata_Osc(self):
        self.get_Osc_dataEvent.set()
        while self.get_Osc_dataEvent.is_set():
            time.sleep(1e-12)
        #Pull the data from the shared buffer and save it to a different array 
        OscData= np.array(self.shmDataOsc)  # Make a copy of the data
        return  OscData   
    
    def SetGraphLimits(self):
        self.SetSingleCapMode()
        data=self.Getdata_Osc()
        self.SetContinousCapMode()
        ymax=np.max(data[1,:])
        ymin=np.min(data[1,:])
        self.GraphlimitX[:]=[self.timebase_t1.value,self.timebase_t2.value]
        yScaler=1.5
        yminVal=ymin-((ymax-ymin)*(yScaler))
        ymaxVal=ymax+((ymax-ymin)*(yScaler))
        self.GraphlimitY[:]=[yminVal,ymaxVal]#self.OscData_ymin_ymax*1.1
        self.set_GraphLimitEvent.set()
        while self.set_GraphLimitEvent.is_set():
            time.sleep(1e-12)
       
    
    
def MokuCaptureThreadCaptureThread(MokuID,queue,terminateThreadEvent,continuousCaptureMode,singleCaptureMode,
                                   set_int_crossOverEvent,set_input_offsetEvent,set_timebaseEvent,set_enable_outputEvent,
                                   set_GraphLimitEvent,get_Osc_dataEvent,
                                   GraphlimitX,GraphlimitY,
                                   channel,sharedMemoryName,Narr,timebase_t1,timebase_t2,
                                   pid_input_offset,pid_int_crossover,pid_channel,pid_input_gain1,pid_input_gain2,
                                   pid_output_low_limit,pid_output_high_limit,pid_enable_input,
                                   pid_enable_output_sig,pid_enable_output_out):
    
    queue.put("test0")
  
    scalevalue=3.162
    # Setup Shared memory
    shm = shared_memory.SharedMemory(name=sharedMemoryName)
    Osc_buffer = np.ndarray((2,Narr), dtype=np.dtype(float), buffer=shm.buf) 
    Oscdata=np.zeros((2,Narr))
    continuousCaptureMode.set()
    #singleCaptureMode.set()
    pid = PIDController(MokuID, force_connect=True) 
    pid.set_control_matrix(channel=pid_channel.value,input_gain1=pid_input_gain1.value,input_gain2=pid_input_gain2.value)
    pid.set_by_frequency(channel=pid_channel.value,int_crossover=pid_int_crossover.value*scalevalue)
    pid.set_input_offset(channel=pid_channel.value,offset=pid_input_offset.value)
    pid.set_output_limit(channel=pid_channel.value,enable=True,low_limit=pid_output_low_limit.value, high_limit=pid_output_high_limit.value)
    
    # I dont think I need to specfiy these values
    # pid.set_control_matrix(2,input_gain1=0,input_gain2=0)# not sure we need this
    # pid.set_output_offset(1,offset=0)

    pid.enable_input(pid_channel.value,enable=True)
    pid.enable_output(pid_channel.value,signal=pid_enable_output_sig.value,output=pid_enable_output_out.value)   #change last argument to toggle between enable/disable
    pid.set_monitor(pid_channel.value,'Input1')
    
    # pid.enable_rollmode(roll=False)
    pid.set_timebase(timebase_t1.value, timebase_t2.value)
    # data=pid.get_data(wait_reacquire=True,wait_complete=True)
    # timedata_temp=data['time']
    # timedata=np.linspace(timebase_t1.value,timebase_t2.value,Narr*6)

    pid.enable_rollmode(roll=True)
    opencvWindowName="PID Osc"
    #Initialise the figure to display data need to call the plt.plot before the while loop 
    # data=pid.get_data(wait_reacquire=True,wait_complete=True)
    # ch1data=np.zeros(Narr*6)
    data=pid.get_data(wait_reacquire=True)
    ch1data_temp=np.asarray(data['ch1'])
    timedata_temp=np.asarray(data['time'])
    
    #  Need to make a array that will be close the correct size to show the data between the user timebase points
    # This is not super accrate as the timemax and timemin seem to change each time you call get_dat with rollmode 
    # on, but it is close enough for ploting purposes.
    timemax=np.max(timedata_temp)
    timemin=np.min(timedata_temp)
    dtime=timemax-timemin
    NarrPlot=Narr*int(np.round(timebase_t2.value-timebase_t1.value/dtime))
    queue.put(dtime)
    timedata=np.linspace(timebase_t1.value,timebase_t2.value,NarrPlot)
    ch1data=np.zeros(NarrPlot)
    
    ch1data_Filttered = ch1data_temp[ch1data_temp != None]
    ch1data[-(len(ch1data_Filttered)):]=ch1data_Filttered  
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))
    # OscDataPlot=ax.plot(data['time'], data['ch1'])[0]
    OscDataPlot=ax.plot(timedata,ch1data)[0]
    # queue.put("test4")
    
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Voltage (V)')
    ax.set_ylim([GraphlimitY[0],GraphlimitY[1]])
    ax.set_xlim([GraphlimitX[0],GraphlimitX[1]])
    queue.put("test5")
    
    # plt.ion()
#     pid.start_streaming()
# data = i.get_stream_data()
# Print out the data
# print(data['time'], data['ch1'], data['ch2'])
    while not terminateThreadEvent.is_set():
        
        if (continuousCaptureMode.is_set()):
            pid.enable_rollmode(True,True)
            data=pid.get_data(wait_reacquire=False,wait_complete=False)# get the data as quick as possible
            ch1data_temp=np.asarray(data['ch1'])
            ch1data_Filttered = ch1data_temp[ch1data_temp != None]
            ch1data=np.roll(ch1data, -len(ch1data_Filttered), axis=None)
            ch1data[-(len(ch1data_Filttered)):]=ch1data_Filttered
            # update the plot for the cv2 live window
            OscDataPlot.set_xdata(timedata)
            OscDataPlot.set_ydata(ch1data)
            fig.canvas.draw_idle()
            imag=plot_to_opencv_img(fig)
            cv2.imshow(opencvWindowName,imag)
            # This will get the current data and allow it to be accessed outside the thread
            if ( get_Osc_dataEvent.is_set() ):
                # pid.enable_rollmode(False,False)
                data=pid.get_data(wait_reacquire=True,wait_complete=False)
                # pid.enable_rollmode(roll=True)
                Oscdata[0,:]=data['time']
                Oscdata[1,:]=data['ch1']
                # Oscdata[0,:]=timedata
                # Oscdata[1,:]=ch1data
                np.copyto(Osc_buffer, Oscdata)
                get_Osc_dataEvent.clear()
           
        elif(singleCaptureMode.is_set()):
            if ( get_Osc_dataEvent.is_set() ):
                pid.enable_rollmode(False,False)
                pid.set_timebase(timebase_t1.value, timebase_t2.value)
                data=pid.get_data(wait_reacquire=True,wait_complete=True)
                Oscdata[0,:]=data['time']
                Oscdata[1,:]=data['ch1']
                np.copyto(Osc_buffer, Oscdata)
                # update the plot for the cv2 live window
                OscDataPlot.set_xdata(data['time'])
                OscDataPlot.set_ydata(data['ch1'])
                fig.canvas.draw_idle()
                imag=plot_to_opencv_img(fig)
                cv2.imshow(opencvWindowName,imag)
                get_Osc_dataEvent.clear()

        # These conditional statements are so that the user can change properties of the PID outside of the thread
        if(set_int_crossOverEvent.is_set()):
            pid.set_by_frequency(channel.value,int_crossover=pid_int_crossover.value*scalevalue)
            # let the PID update itself by calling get data so the next go around the loop fixes itself
            # pid.enable_rollmode(roll=False)
            # data=pid.get_data(wait_reacquire=True,wait_complete=True)
            # pid.enable_rollmode(roll=True)
            set_int_crossOverEvent.clear()
        if(set_input_offsetEvent.is_set()):
            pid.set_input_offset(channel.value,offset=pid_input_offset.value)
             # let the PID update itself by calling get data so the next go around the loop fixes itself
            # data=pid.get_data(wait_reacquire=True,wait_complete=True)
            set_input_offsetEvent.clear()
        if(set_timebaseEvent.is_set()):
            if(continuousCaptureMode.is_set()):
                pid.enable_rollmode(True,True)
                data=pid.get_data(wait_reacquire=False,wait_complete=False)
                ch1data_temp=np.asarray(data['ch1'])
                timedata_temp=np.asarray(data['time'])
                #  Need to make a array that will be close the correct size to show the data between the user timebase points
                # This is not super accrate as the timemax and timemin seem to change each time you call get_dat with rollmode 
                # on, but it is close enough for ploting purposes.
                timemax=np.max(timedata_temp)
                timemin=np.min(timedata_temp)
                dtime=timemax-timemin
                NarrPlot=int(timebase_t2.value-timebase_t1.value/dtime)
                timedata=np.linspace(timebase_t1.value,timebase_t2.value,NarrPlot)
                ch1data=np.zeros(NarrPlot)
                
            else:       
                pid.enable_rollmode(False,False)
                pid.set_timebase(timebase_t1.value, timebase_t2.value)
            # data=pid.get_data(wait_reacquire=True,wait_complete=True)
            # timedata=data['time']
            # pid.enable_rollmode(roll=True)
            set_timebaseEvent.clear()
        if(set_enable_outputEvent.is_set()):
            pid.enable_output(pid_channel.value,True,pid_enable_output_out.value)
             # let the PID update itself by calling get data so the next go around the loop fixes itself
            # pid.enable_rollmode(roll=False)
            # data=pid.get_data(wait_reacquire=True,wait_complete=True)
            # pid.enable_rollmode(roll=True)
            # timedata=np.linspace()
            ch1data.fill(0)
            set_enable_outputEvent.clear()
        if(set_GraphLimitEvent.is_set()):
            ax.set_ylim([GraphlimitY[0],GraphlimitY[1]])
            ax.set_xlim([GraphlimitX[0],GraphlimitX[1]])
            set_GraphLimitEvent.clear()
        
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    shm.close()
    pid.relinquish_ownership()

