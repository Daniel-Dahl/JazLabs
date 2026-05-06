from Lab_Equipment.Config import config 
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import multiprocessing
from multiprocessing import shared_memory
import copy
import cv2
import time
import ctypes
import os
import Lab_Equipment.Camera.CameraObject as CamForm   
# I am not sure if i need to do this but just in case I am going to load the dll in python
camdllpath=config.CAMERA_LIB_PATH+"CameraSoftware\\NiTcamera\\NITLibrary_x64.dll"
NiTCamdll= ctypes.cdll.LoadLibrary(camdllpath)
import Lab_Equipment.Camera.CameraSoftware.NiTcamera.NITLibrary_x64_360_py310  as NITLibrary

# Function to convert a matplotlib plot to an OpenCV image
def plot_to_opencv_img(fig):
    canvas = FigureCanvas(fig)
    canvas.draw()
    buf = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
    buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    return cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)

class NiTCamraObject():
    def __init__(self,PixelSize=15e-6):
            super().__init__() # inherit from parent class  
            # We are just going to go through and grab a bunch of properties from the camera
            # and get 1 frame to set up the shared memory space
            nm = NITLibrary.NITManager.getInstance()
            dev = nm.openOneDevice()
            self.Ny =  dev.sensorHeight()
            self.Nx = dev.sensorWidth() 
            observer=CustomObserver(self.Ny,self.Nx)
            dev << observer # this is to overload the functions and be able to save the frame into a numpy array
            # Display Info of camera
            print( nm.listDevices() )
            serialNum="SN"+dev.serialNumber()
            # NUCFolderLocation=config.CAMERA_LIB_PATH+"CameraSoftware\\NiTcamera\\"+serialNum
            # if os.path.exists(NUCFolderLocation):
            #     print("NUC file directory Found for Camera "+serialNum + ". It will be loaded")
            #     dev.setNucDirectory(NUCFolderLocation)
                
            self.Ny =  dev.sensorHeight()
            self.Nx = dev.sensorWidth() 
            Exposure=dev.paramValueOf("Exposure Time")
            SensorResponse=dev.paramValueOf("Sensor Response")
            Gain=dev.paramValueOf("Analog Gain")
            capturemode=dev.paramValueOf("Mode")
            print('Exposure ',Exposure)
            print('Gain ',Gain)
            print('Captrue mode ',capturemode)
            print ('Sensor Response ',SensorResponse)
            print('sensor height ',self.Ny,' sensor width ',self.Nx) 
            dev.captureNFrames(1) # Seems like you need to grab 3 frames to be sure it is getting the most upto date frame the buffer on the camera doesnt empty it self
            dev.waitEndCapture()
            frame = observer.frametemp
            FrameBuffer =CamForm.adjust_array_dimensions(np.squeeze( frame))
            FrameDim=FrameBuffer.shape
            FrameHeight = int(FrameDim[0])
            FrameWidth = int(FrameDim[1])
            Framedtype=FrameBuffer.dtype
  
            # # cut the connection to the camera
            # I am not sure why but any time you want to kill the connection you should wait a little bit to make sure no threads are runnning
            # hence the 3 sec sleep. I dont think they are being thread safe in their back end
            time.sleep(3)
            nm.reset()
        

            # START the camera Thead
            self.CamObject=CamForm.GeneralCameraObject("NiTCamera",self.Nx,self.Ny,FrameWidth,FrameHeight,FrameDim,Framedtype,FrameBuffer,PixelSize,Exposure,Gain=Gain,CaptureMode=capturemode)
            self.CamProcess= CamForm.start_FrameCaptureThread(self.CamObject,NiTCamFrameCaptureThread)
            print('Thread launched')
            
    def __del__(self):
        """Destructor to disconnect from camera."""
        print(self.CamObject.CameraType +" Class has been destroyed")
        self.CamObject.terminateCamera.set()# stop the camera thread
        self.CamObject.shm.close() # close access to shared memory
        self.CamObject.shm.unlink() # clean up the shared memory space
        time.sleep(5) # just wait for all the threads to be killed before starting a new one
##############################################        
# Ok so because the software engineers behind this camera are super dumb you need to make your own onNewFrame function that is NITLibrary.NITUserFilter class
# this overloads the onNewFrame function and allows you to actually pull a frame by copy the frame into a temp np array
###############################################
class CustomObserver(NITLibrary.NITUserFilter):
    def __init__(self,Ny,Nx):
        NITLibrary.NITUserObserver.__init__(self)
        # self.isCaptureStarted = 0
        # self.frametemp = np.zeros((Ny,Nx),dtype=np.uint8)
        self.frametemp = np.zeros((Ny,Nx))
        self.currentFrameId = -1
    def onNewFrame(self, frame): 
        # print(self.currentFrameId)
        self.frametemp =copy.deepcopy(frame.data())
        # self.frametemp =np.copy(frame.data())
        self.currentFrameId = frame.id()
        # print(self.currentFrameId)

def NiTCamFrameCaptureThread(queue,Cam_Calibtation,SetCalibrationEvent,
                             GetFrameFlag,GetFrameFlag_digholo,terminateCamFlag,FrameObtained,shared_memory_name,shared_memory_name_digholo,
                             FrameHeight,FrameWidth,
                             SetGainFlag,SetExposureFlag,SetCaptureModeFlag,
                             LogPlot,ContinuesMode,SingleFrameMode,
                             shared_float,shared_int,shared_flag_int):
   
    # Setup Shared memory
    shm = shared_memory.SharedMemory(name=shared_memory_name)
    frame_buffer = np.ndarray((FrameHeight, FrameWidth), dtype=np.float64, buffer=shm.buf) 
    
    shm_digholo = shared_memory.SharedMemory(name=shared_memory_name_digholo)
    frame_buffer_digholo = np.ndarray((FrameHeight, FrameWidth), dtype=np.float64, buffer=shm_digholo.buf) 
    ContinuesMode.set()
    #make a connection to the camera
    nm = NITLibrary.NITManager.getInstance()
    dev = nm.openOneDevice()

    serialNum="SN"+dev.serialNumber()
    # NUCFolderLocation=config.CAMERA_LIB_PATH+"CameraSoftware\\NiTcamera\\"+serialNum
    # if os.path.exists(NUCFolderLocation):
    #     print("NUC file directory Found for Camera "+serialNum + ". It will be loaded")
        # dev.setNucDirectory(NUCFolderLocation)

    Ny =  dev.sensorHeight()
    Nx = dev.sensorWidth() 
    observer=CustomObserver(Ny,Nx)
    dev << observer # this is to overload the functions and be able to save the frame into a numpy array
    # hard coding the Sensor Response value to linear could be changed to log which would be 0 instead of 1 whcih is linear
    dev.setParamValueOf("Sensor Response", 1)
    dev.updateConfig()
    figScale=FrameWidth/FrameHeight
    figsize=5

    # fig, ax = plt.subplots(1, 1,figsize=( int(figScale*FrameHeight), int(figScale*FrameWidth)))
    fig, ax = plt.subplots(1, 1,figsize=(int(figScale*figsize), figsize))

    cameraFrameFigure=ax.imshow(np.zeros((FrameHeight, FrameWidth),dtype=np.uint8),cmap='gray')
    cameraFrameFigure.set_cmap('gray')
    ax.axis('off')
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(x=0, y=0)
    plt.tight_layout()
    # ax.set_colorbar()
    # fig.colorbar(cameraFrameFigure, ax=ax, orientation='vertical')  # You can change orientation to 'horizontal' if preferred
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0) 
    restartContinuousMode=True

    opencvWindowName="NiT Camera Image"
    while not terminateCamFlag.is_set():
        
        if (ContinuesMode.is_set()):
            # In the live feed i dont really care if i am droping frames and i think it will be 
            # faster to just capture frames in continuous mode.
            if (restartContinuousMode):
                restartContinuousMode=False
                dev.start()
            # dev.captureNFrames(1) # Seems like you need to grab 3 frames to be sure it is getting the most upto date frame the buffer on the camera doesnt empty it self
            # dev.waitEndCapture() 
            frame = observer.frametemp
            
            Frame_int =CamForm.adjust_array_dimensions(np.squeeze( frame))
            
            if (LogPlot.is_set()):   
                Frame_toplot=np.log10(Frame_int+1)   #Need to add 1 so that np.log10 doesnt get a divide by zero error
            else:
                Frame_toplot=Frame_int 
            cameraFrameFigure.set_data(Frame_toplot)
            cameraFrameFigure.set_clim(0, Frame_toplot.max())
            fig.canvas.draw_idle()
            imag=plot_to_opencv_img(fig)
            cv2.imshow(opencvWindowName,imag)

            if ( GetFrameFlag.is_set() ):
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
            if ( GetFrameFlag_digholo.is_set() ):
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
                # this was the queue way but it isn't consistant interms of when a frame is obatined
                # so I have moved to shared memory space method.
                # frame_bytes = Frame_int.tobytes()
                # queue.put(frame_bytes)
        elif(SingleFrameMode.is_set()):
            #Turn off continuous mode of camera and reset the flag to turn it back on
            if (restartContinuousMode==False):
                dev.stop()
                restartContinuousMode=True
            if ( GetFrameFlag.is_set() ):
                dev.captureNFrames(3) # Seems like you need to grab 3 frames to be sure it is getting the most upto date frame the buffer on the camera doesnt empty it self
                dev.waitEndCapture() 
                frame = observer.frametemp
                Frame_int =CamForm.adjust_array_dimensions(np.squeeze( frame))                 
                cv2.imshow(opencvWindowName, Frame_int)
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
            # I am not really worried about getting the latest frame just want to see something updating on the digholo
            if ( GetFrameFlag_digholo.is_set() ): 
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
            
        
        # NOTE exposure is pretty safe in that you can pass it any vlaue and library will handle it all
        if(SetExposureFlag.is_set()):
            Exposure=shared_float.value
            dev.setParamValueOf("Exposure Time",(Exposure))
            dev.updateConfig()
            shared_float.value=dev.paramValueOf("Exposure Time")
            shared_flag_int.value=1
            SetExposureFlag.clear()

        # NOTE the Gain can only be set to certain value like high or low and it also depends on the 
        # Sensor Response setting. I dont really understand why but it is kind of explained in the documentation
        # so if you want to go and try and understand that peice of shit documnet be my guest. 
        # Future Daniel here and I laugh at this, very good past Daniel.
        if(SetGainFlag.is_set()):
            Gain=shared_float.value
            if (int(dev.paramValueOf("Sensor Response"))==1):# linear mode gain can only be 1 or 3
                if(int(Gain)==0 or int(Gain)==3):
                    dev.setParamValueOf("Analog Gain",int(Gain))
                    dev.updateConfig()
            elif (int(dev.paramValueOf("Sensor Response"))==0):#log mode gain can be or 2
                if(int(Gain)==1 or int(Gain)==2):
                    dev.setParamValueOf("Analog Gain",int(Gain))
                    dev.updateConfig()
            
            shared_float.value=dev.paramValueOf("Analog Gain")
            shared_flag_int.value=1
            SetGainFlag.clear()

        if(SetCaptureModeFlag.is_set()):
            CaptureMode=shared_float.value
            if ( (CaptureMode)>=0 and (CaptureMode)<=2):
                dev.setParamValueOf("Mode",int(CaptureMode))
                dev.updateConfig()
            shared_float.value=(dev.paramValueOf("Mode"))
            shared_flag_int.value=1
            SetCaptureModeFlag.clear()
        if(SetCalibrationEvent.is_set()):
            CalibrationFile=Cam_Calibtation['CalibrationFile']
            if os.path.exists(CalibrationFile):
                print("NUC file directory Found for Camera "+serialNum + ". It will be loaded")
                dev.setNucDirectory(CalibrationFile)
                shared_int.value=0
            else:
                shared_int.value=-1
            SetCalibrationEvent.clear()

            
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    shm.close()
    shm_digholo.close()
    time.sleep(3)
    nm.reset()
 