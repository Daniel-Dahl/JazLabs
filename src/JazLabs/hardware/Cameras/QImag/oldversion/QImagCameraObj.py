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
import Lab_Equipment.Camera.CameraObject as CamForm   
from CameraSoftware.QImagCam.qcam import Camera as QImagCamObj
from CameraSoftware.QImagCam.calibration import get_position, to_wavelength, to_raman 

# Function to convert a matplotlib plot to an OpenCV image
def plot_to_opencv_img(fig):
    canvas = FigureCanvas(fig)
    canvas.draw()
    buf = np.frombuffer(canvas.tostring_rgb(), dtype=np.uint8)
    buf = buf.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    return cv2.cvtColor(buf, cv2.COLOR_RGB2BGR)

class QImagCamraObject():
    def __init__(self,PixelSize=6.45e-6):
            super().__init__() # inherit from parent class  
            
            # We are just going to go through and grab a bunch of properties from the camera
            # and get 1 frame to set up the shared memory space
            cam = QImagCamObj()
            cameraOpened = cam.connect_to_camera()
            result, model = cam.get_camera_model()
            if result != 0:  # Replace with your actual success value
                print(f"Failed to get camera model with error {result}")
            else:
                print(f"Camera model: {model}")

            # Display Info & Parameters
            cam.setup_camera()
            print(list(cam.info.values()))
            print(list(cam.parameters.values()))
            for name, param in cam.parameters.items():
                print(f"For parameter {name}: min_value is {param.min_value}, max_value is {param.max_value}")
            
            
            self.Ny = cam.QCam_GetInfo(cam.INFO_KEYS["Image Height"])[1]
            self.Nx =cam.QCam_GetInfo(cam.INFO_KEYS["Image Width"])[1]
            Exposure=cam.QCam_GetParam(cam.PARAM_KEYS["Exposure"])[1]
            Gain=cam.QCam_GetParam(cam.PARAM_KEYS["Gain"])[1]
            Offset=cam.QCam_GetParam(cam.PARAM_KEYS["Offset"])[1]
            Exposure=cam.QCam_GetParam(cam.PARAM_KEYS["Exposure"])[1]

            print('Exposure ',Exposure)
            print('Gain ',Gain)
            print('Offset ',Offset)
            print(self.Ny,self.Nx)    

            #Get a frame and see what the size of the frame is
            Rawframe = cam.grab_frame()
            pBuffer = ctypes.cast(Rawframe.pBuffer, ctypes.POINTER(ctypes.c_char * Rawframe.size))
            # Then we create a numpy array from the buffer
            RawFame_data = np.frombuffer(pBuffer.contents, dtype=np.uint8)
            # Now reshape it into the correct shape
            frame = RawFame_data.reshape(Rawframe.height, Rawframe.width) 

            FrameBuffer =CamForm.adjust_array_dimensions(np.squeeze( frame))
            FrameDim=FrameBuffer.shape
            FrameHeight = int(FrameDim[0])
            FrameWidth = int(FrameDim[1])
            Framedtype=FrameBuffer.dtype
            # self.PixelSize=PixelSize
            cam.close_camera()
            cam.release_driver()

            # START the camera Thead
            self.CamObject=CamForm.GeneralCameraObject("QImagCamera",self.Nx,self.Ny,FrameWidth,FrameHeight,FrameDim,Framedtype,FrameBuffer,PixelSize,Exposure,Offset,Gain)
            self.CamProcess= CamForm.start_FrameCaptureThread(self.CamObject,QImagCamFrameCaptureThread)
            
            
            # self.opencv_display_format = PixelFormat.Bgr8
        
    def __del__(self):
        """Destructor to disconnect from camera."""
        print(self.CamObject.CameraType +" Class has been destroyed")
        self.CamObject.terminateCamera.set()# stop the camera thread
        self.CamObject.shm.close() # close access to shared memory
        # self.CamProcess.terminate()
        self.CamObject.shm.unlink() # clean up the shared memory space
        # cam = QImagCamObj()
        # cam.close_camera()
        # cam.release_driver()
        time.sleep(5)
        # cam.close_camera()
        # cam.release_driver()
    
def QImagCamFrameCaptureThread(queue,Cam_Calibtation,SetCalibrationEvent,
                               GetFrameFlag,GetFrameFlag_digholo,terminateCamFlag,FrameObtained,shared_memory_name,shared_memory_name_digholo,FrameHeight,FrameWidth,
                               SetGainFlag,SetOffsetFlag,SetExposureFlag,
                               LogPlot,ContinuesMode,SingleFrameMode,
                                shared_float,shared_int,shared_flag_int):
    # Setup Shared memory
    shm = shared_memory.SharedMemory(name=shared_memory_name)
    frame_buffer = np.ndarray((FrameHeight, FrameWidth), dtype=np.uint8, buffer=shm.buf) 
    
    shm_digholo = shared_memory.SharedMemory(name=shared_memory_name_digholo)
    frame_buffer_digholo = np.ndarray((FrameHeight, FrameWidth), dtype=np.uint8, buffer=shm_digholo.buf) 
    
    
    ContinuesMode.set()
    cam = QImagCamObj()
    cameraOpenedErrorCode = cam.connect_to_camera()
    cam.setup_camera()
    figScale=FrameWidth/FrameHeight
    figsize=10

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

    opencvWindowName="QImag Camera Image"
    while not terminateCamFlag.is_set():
        
        if (ContinuesMode.is_set()):
            Rawframe=cam.grab_frame()
            """
            Convert frame buffer to image array
            Windows doesn't like it (i.e. throws a fatal exception)
            when this takes place in qcam.py for some reason!
            """
            # First we need to cast the void pointer to a pointer to a char array
            pBuffer = ctypes.cast(Rawframe.pBuffer, ctypes.POINTER(ctypes.c_char * Rawframe.size))
            # Then we create a numpy array from the buffer
            RawFame_data = np.frombuffer(pBuffer.contents, dtype=np.uint8)
            # Now reshape it into the correct shape
            frame = RawFame_data.reshape(Rawframe.height, Rawframe.width) 
            Frame_int =CamForm.adjust_array_dimensions(np.squeeze( frame))  
            if (LogPlot.is_set()):   
                Frame_toplot=np.log10(Frame_int+1)   #Need to add 1 so that np.log10 doesnt get a divide by zero error
            else:
                Frame_toplot=Frame_int 
            cameraFrameFigure.set_data(Frame_toplot)
            # cameraFrameFigure.set_clim(Frame_toplot.min(), Frame_toplot.max())
            cameraFrameFigure.set_clim(0, Frame_toplot.max())
            fig.canvas.draw_idle()
            imag=plot_to_opencv_img(fig)
            cv2.imshow(opencvWindowName,imag)

            if ( GetFrameFlag.is_set() ):
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
                # this was the queue way but it isn't consistant interms of when a frame is obatined
                # so I have moved to shared memory space method.
                # frame_bytes = Frame_int.tobytes()
                # queue.put(frame_bytes)
            if ( GetFrameFlag_digholo.is_set() ):
                np.copyto(frame_buffer_digholo, Frame_int)
                GetFrameFlag_digholo.clear()
                
        elif(SingleFrameMode.is_set()):
            if ( GetFrameFlag.is_set() ):
                Rawframe = cam.grab_frameSingle()    
                """
                Convert frame buffer to image array
                Windows doesn't like it (i.e. throws a fatal exception)
                when this takes place in qcam.py for some reason!
                """
                # First we need to cast the void pointer to a pointer to a char array
                pBuffer = ctypes.cast(Rawframe.pBuffer, ctypes.POINTER(ctypes.c_char * Rawframe.size))
                # Then we create a numpy array from the buffer
                RawFame_data = np.frombuffer(pBuffer.contents, dtype=np.uint8)
                # Now reshape it into the correct shape
                frame = RawFame_data.reshape(Rawframe.height, Rawframe.width) 
                Frame_int =CamForm.adjust_array_dimensions(np.squeeze( frame))                    
                cv2.imshow(opencvWindowName, Frame_int)
                np.copyto(frame_buffer, Frame_int)
                FrameObtained.value=1
                GetFrameFlag.clear()
            # I am not really worried about getting the latest frame just want to see something updating on the digholo
                if ( GetFrameFlag_digholo.is_set() ):
                    np.copyto(frame_buffer_digholo, Frame_int)
                    GetFrameFlag_digholo.clear()

        if(SetExposureFlag.is_set()):
            Exposure=shared_float.value
            if ( (Exposure)>=10 and (Exposure)<=1073741823 ):
                cam.set_camera_param("Exposure", int(Exposure))
            shared_float.value=int(cam.QCam_GetParam(cam.PARAM_KEYS["Exposure"])[1])
            shared_flag_int.value=1
            SetExposureFlag.clear()

        if(SetGainFlag.is_set()):
            Gain=shared_float.value
            if ( (Gain)>=115 and (Gain)<=4095):
                cam.set_camera_param("Gain", int(Gain))
            shared_float.value=int(cam.QCam_GetParam(cam.PARAM_KEYS["Gain"])[1])
            shared_flag_int.value=1
            SetGainFlag.clear()

        if(SetOffsetFlag.is_set()):
            Offset=shared_float.value
            if ( (Offset)>=0 and (Offset)<=4095):
                cam.set_camera_param("Offset", int(Offset))
            shared_float.value=int(cam.QCam_GetParam(cam.PARAM_KEYS["Offset"])[1])
            shared_flag_int.value=1
            SetOffsetFlag.clear()
        if(SetCalibrationEvent.is_set()):
            CalibrationFile=Cam_Calibtation['CalibrationFile']
            if os.path.exists(CalibrationFile):
                shared_int.value=0
            else:
                shared_int.value=-1
            # I am not sure how to set the calibration file on this camera i will work it out when i need to
            shared_int.value=-1
            SetCalibrationEvent.clear()
            

            
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    cv2.destroyAllWindows()
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    shm.close()
    cam.close_camera()
    cam.release_driver()
 