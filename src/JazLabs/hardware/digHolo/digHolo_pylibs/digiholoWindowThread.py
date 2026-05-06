
import sys
import Lab_Equipment.Config.config as config

import matplotlib.pyplot as plt
import numpy as np
import cv2
import multiprocessing
from multiprocessing import shared_memory
import time
import copy

import Lab_Equipment.digHolo.digHolo_pylibs.digholoObject as digholoMod
#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm

import ctypes
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [15,15]

class digholoWindow():
    def __init__(self,CamObj:CamForm.GeneralCameraObject,Wavelength=1550e-9,polCount=1,maxMG=1,fftWindowSizeX=256,fftWindowSizeY=256,FFTRadius=0.4,TransformMat=None,TransformMatrixFilename=None,digholoProperties=None):
        super().__init__() # inherit from parent class  
        manager = multiprocessing.Manager() # this lets us share a dictionary between threads
        self.digholo_queue = multiprocessing.Queue()
        
        # Shared varibles to communicate between main thread and digholo thread properites
        self.shared_float = multiprocessing.Value("f", 0)
        self.shared_int = multiprocessing.Value('i', 0)
        self.shared_flag_int = multiprocessing.Value('i', 0)
        
        self.terminateDigholo = multiprocessing.Event()
        self.PauseDigholo = multiprocessing.Event()
        self.digiHoloPaused = multiprocessing.Event()
        self.AutoAlginFlag = multiprocessing.Event()
        self.FrameObtained = multiprocessing.Value('i', 0)  # Flag to indicate when a frame is ready  
        
        self.Update_basisType_Flag = multiprocessing.Event()
    
        self.Set_DigholoProperties_Flag = multiprocessing.Event()
        self.Get_DigholoProperties_Flag = multiprocessing.Event()
        if TransformMatrixFilename is not None:
            self.TransformMat=self.Update_basisType_Flag.set()
        else:
            if TransformMat is not None:
                self.TransformMat=TransformMat
                basisType=2
            else:
                basisType=0
            
        self.WavelengthCount=1    
        self.batchCount= 1
        # the camera frame hieght and width really shouldnt change unless the camera changes which would mean it would need to be another digholo thread created
        self.CamFrameHeight=CamObj.FrameHeight.value
        self.CamFrameWidth=CamObj.FrameWidth.value
        self.Camera_dtype=CamObj.Framedtype
        print("frame type is ", self.Camera_dtype)
        # Set up some memory space for batch files that get processed by digholo. NOTE this array will usually change size and all that is handled in the digholoWindowAutoAlgin()
        self.frameBufferBatch_shm = shared_memory.SharedMemory(create=True, size=int(self.batchCount*self.CamFrameHeight* self.CamFrameWidth * np.dtype(self.Camera_dtype).itemsize))
        self.frameBufferBatch_shmName = self.frameBufferBatch_shm.name
        self.FrameBuffer_SharedMem  = np.ndarray((self.batchCount,self.CamFrameHeight, self.CamFrameWidth), dtype=self.Camera_dtype, buffer=self.frameBufferBatch_shm.buf)     
        self.shm_digholoName = CamObj.shm_digholo.name
        self.FrameObtained = CamObj.FrameObtained
        self.GetFrameFlag_digholo = CamObj.GetFrameFlag_digholo
        # 
        self.Metrics_shm = shared_memory.SharedMemory(create=True, size=int(digholoMod.digholoMetrics.COUNT * np.dtype(np.float32).itemsize))
        self.Metrics_shmName = self.Metrics_shm.name
        self.Metrics_SharedMem  = np.ndarray((digholoMod.digholoMetrics.COUNT), dtype=np.float32, buffer=self.Metrics_shm.buf)     
        
        
        if digholoProperties is not None:
            self.digholoWindowProperties=manager.dict(digholoProperties)
        else:
            self.digholoWindowProperties = manager.dict(
                { "Wavelength": Wavelength,
                "WavelengthCount": self.WavelengthCount,          
                "polCount": polCount,
                "batchCount": 1,
                "AvgCount":1,
                "PixelSize":CamObj.PixelSize,
                "maxMG": maxMG,
                "fftWindowSizeX": fftWindowSizeX,
                "fftWindowSizeY": fftWindowSizeY,
                "FFTRadius": FFTRadius,
                "BeamCentreXPolH":0,
                "BeamCentreXPolV":0,
                "BeamCentreYPolH":0,
                "BeamCentreYPolV":0,
                "BasisWaistPolH":1,
                "BasisWaistPolV":1,
                "DefocusPolH":0,
                "DefocusPolV":0,
                "XTiltPolH":0,
                "XTiltPolV":0,
                "YTiltPolH":0,
                "YTiltPolV":0,
                "AutoAlignBeamCentre": 1,
                "AutoAlignDefocus": 1,
                "AutoAlignTilt": 1,
                "AutoAlignBasisWaist":1,
                "AutoAlignFourierWindowRadius":0,
                "goalIdx":0,
                "basisType":basisType,
                "resolutionMode":0,
                "verbosity":2,
                "TransformMatrixFilename":TransformMatrixFilename
            })
        
        print("starting thread")
        self.process_digholo, self.digholo_queue=self.start_digiHoloThread(CamObj)
        print("passed thread")

        
        
    def __del__(self):
        """Destructor to disconnect from camera."""
        print("Digholo Oject has been destroyed")
        self.terminateDigholo.set()# stop the camera thread
        self.process_digholo.terminate()
        
        self.frameBufferBatch_shm.close()
        self.frameBufferBatch_shm.unlink()
    
    def start_digiHoloThread(self,CamObj:CamForm.GeneralCameraObject):
        print('test')
        self.process_digholo = multiprocessing.Process(target=digiHoloThread, args=(
            self.digholo_queue,self.shared_float,self.shared_int,self.shared_flag_int,self.terminateDigholo,
            self.AutoAlginFlag,self.digiHoloPaused,self.digholoWindowProperties,self.Set_DigholoProperties_Flag,self.Get_DigholoProperties_Flag,
            self.Update_basisType_Flag,
            self.frameBufferBatch_shmName,self.Metrics_shmName,CamObj.PixelSize,
            CamObj.shm_digholo.name,self.Camera_dtype,self.CamFrameHeight,self.CamFrameWidth,CamObj.FrameObtained,CamObj.GetFrameFlag_digholo))
        
        self.AutoAlginFlag.set()
        self.process_digholo.start()
        
        return self.process_digholo, self.digholo_queue
        
    def Set_digholoWindowProps(self,NewDigholoProperties=None):
        if NewDigholoProperties is not None:
            self.digholoWindowProperties.update(NewDigholoProperties)
        self.Set_DigholoProperties_Flag.set()
        while self.Set_DigholoProperties_Flag.is_set():
            time.sleep(1e-12)
        return 
    
    def Get_digholoWindowProps(self):
        self.Get_DigholoProperties_Flag.set()
        while self.Get_DigholoProperties_Flag.is_set():
            time.sleep(1e-12)
        NewDigholoProperties=self.digholoWindowProperties
        return NewDigholoProperties

        
    def SetPausePlayDigholo(self):
        if(self.digiHoloPaused.is_set()):
            self.digiHoloPaused.clear()
        else:
            self.digiHoloPaused.set()

            
    def Set_digholoWindow_basisType(self,basisType=0,TransformMatrixFilename=None):
        if basisType==2:
            if TransformMatrixFilename is None:
                print("Need to give the filename without the file type to the function.")
                return
            self.digholoWindowProperties["TransformMatrixFilename"] = TransformMatrixFilename
            
        self.digholoWindowProperties["basisType"] = basisType
            
        # self.digholoWindowProperties.update(NewDigholoProperties)
        self.Update_basisType_Flag.set()
        while self.Update_basisType_Flag.is_set():
            time.sleep(1e-12)
        return 
            
    # need to clean up the shared memory as the batchCount can change depending on the number of frames captured that need to be processed. 
    def digholoWindowAutoAlgin(self,CameraFrames:np.ndarray=None):
        if CameraFrames is not None:

            # self.SetPausePlayDigholo()
            Camdims=CameraFrames.shape
            if len(Camdims)<2 or len(Camdims)>3:
                print(" AutoAlgin NOT run.\n The Camera frames that you have passed are not the correct dims. They should be [batchCount,CamHieght,CamWidth].")
                return
            if len(Camdims)==2:
                self.batchCount=1
                self.CamFrameHeight=Camdims[0]
                self.CamFrameWidth = Camdims[1]
            else:
                self.batchCount=Camdims[0]
                self.CamFrameHeight=Camdims[1]
                self.CamFrameWidth = Camdims[2]
            self.Camera_dtype =CameraFrames.dtype
            # set the shared_int value to the batch count so that the new 
            self.shared_int.value= int(self.batchCount)

            #Close and unlink the framebufferBatch_shm shared memory space. I has already been closed in the thread.
            self.frameBufferBatch_shm.close()
            self.frameBufferBatch_shm.unlink()
            # now reopen a new memory space under the same name. The name is key here it is what links the memory spaces together inside and outside the thread without
            # it there would be no way to tell the child thread what memory space to look at.
            self.frameBufferBatch_shm = shared_memory.SharedMemory(name=self.frameBufferBatch_shmName,create=True, size=int( self.batchCount*self.CamFrameHeight* self.CamFrameWidth * np.dtype(CameraFrames.dtype).itemsize))
            self.FrameBuffer_SharedMem  = np.ndarray((self.batchCount,self.CamFrameHeight, self.CamFrameWidth), dtype=CameraFrames.dtype, buffer=self.frameBufferBatch_shm.buf)     
            np.copyto(self.FrameBuffer_SharedMem, CameraFrames)
        else:
            self.shared_int.value=1
        self.AutoAlginFlag.set()
        while self.AutoAlginFlag.is_set():
            time.sleep(1e-12)
        # after the thread has done a auto Align we need to get the new properties of the digholo object  
        _=self.Get_digholoWindowProps()
        Metrics_valueArr= np.array(self.Metrics_SharedMem)
        return Metrics_valueArr


          


# NOTE that you have to create the Digholo c obejct in the multiprocess.
# This is because the Digholo c obejct makes a whole bunch of varibles that you cant keep
# track of in the multiprocess. If you initalise it in the multiprocess it is a lot easier to handle
def digiHoloThread(queue,shared_float,shared_int,shared_flag_int,terminateDigholo,
                   AutoAlginFlag,digiHoloPaused,digholoWindowProperties,Set_DigholoProperties_Flag,Get_DigholoProperties_Flag,
                   Update_basisType_Flag,
                   frameBufferBatch_shmName,Metrics_shmName,PixelSize,
                   Cam_digholoshmName,Framedtype,FrameHeight,FrameWidth,FrameObtained,GetFrameFlag_digholo):
        

        # Set up the raws camera frame that is to be read into the digholo
        Cam_digholo_shm = shared_memory.SharedMemory(name=Cam_digholoshmName)
        CamFrame_digholoFromshm = np.ndarray((FrameHeight, FrameWidth), dtype=np.dtype(Framedtype), buffer=Cam_digholo_shm.buf)
        frame_buffer_int = np.zeros((FrameHeight, FrameWidth), dtype=np.dtype(Framedtype))
        
        Metrics_shm = shared_memory.SharedMemory(name=Metrics_shmName)
        MetricValuesArr_shm = np.ndarray((digholoMod.digholoMetrics.COUNT), dtype=np.dtype(np.float32), buffer=Metrics_shm.buf)
        Metric_valueArr = np.zeros((digholoMod.digholoMetrics.COUNT), dtype=np.dtype(np.float32))
        
        # make a digholo object inside the thread.
        # frame=CamObject.GetFrame(ConvertToFloat32=True)
        GetFrameFlag_digholo.set()
        while GetFrameFlag_digholo.is_set():
            time.sleep(1e-120)   
        #Once the frame has been grabbed it can be converted to a float32 to then be processed by digholo 
        np.copyto(frame_buffer_int, CamFrame_digholoFromshm)
        frameBuffer=frame_buffer_int.astype(np.float32)
        digiholoObj=digholoMod.digholoObject(IntialCameraFrame=frameBuffer,PixelSize=PixelSize)
        windowName_digHoloViewPort='digHolo_Viewport'
        windowName_Coefs='digHolo_Coefs'
        shared_int.value = 1
        while not terminateDigholo.is_set(): 
            if(not digiHoloPaused.is_set()):
                # CalculateMetrics=False
                GetFrameFlag_digholo.set()
                while GetFrameFlag_digholo.is_set():
                    time.sleep(1e-120)   
                #Once the frame has been grabbed it can be converted to a float32 to then be processed by digholo 
                np.copyto(frame_buffer_int, CamFrame_digholoFromshm)
                frameBuffer=frame_buffer_int.astype(np.float32)
                
                if (AutoAlginFlag.is_set()):
                    if shared_int.value == 1:
                        # do the AutoAglin with what ever the batch is
                        _,_=digiholoObj.digHolo_AutoAlign(frameBuffer)

                    else:   
                        # You have to open a new memory space each time you do a autoAlign if the batchCount changes
                        shm_frameBufferBatch = shared_memory.SharedMemory(name=frameBufferBatch_shmName)
                        frameBufferBatch_shm = np.ndarray((shared_int.value,FrameHeight, FrameWidth), dtype=np.dtype(Framedtype), buffer=shm_frameBufferBatch.buf)
                        
                        # array that the data gets moved into could probably remove it but i am not sure until i test everything I think you could probably just use frameBufferBatch_shm
                        frameBufferBatch = np.zeros((shared_int.value,FrameHeight, FrameWidth), dtype=np.dtype(Framedtype)) 
                        np.copyto(frameBufferBatch, frameBufferBatch_shm) # move into a local array
                        # close the shared memory space so that it can be recreated and resized inside and outside the thread. 
                        # Rememeber unlink is done in the main as that is the place that should be cleaning up memory 
                        shm_frameBufferBatch.close()
                        # do the AutoAglin with what ever the batch is
                        _,Metric_valueArr=digiholoObj.digHolo_AutoAlign(frameBufferBatch)
                        
                        #Move the Metric values into the shared memory space so the values can be accessed outside the thread
                        np.copyto(Metric_valueArr, MetricValuesArr_shm)
                        CoefsImage,MetricsText=digiholoObj.GetCoefAndMetricsForOutput()
                
                        # Make the viewport for the coefs
                        # Create a resizable window
                        cv2.namedWindow(windowName_Coefs, cv2.WINDOW_NORMAL)
                        # Resize the window to your desired size (width, height)
                        cv2.resizeWindow(windowName_Coefs, 800, 600)
                        canvasToDispla_Coefs=digiholoObj.DisplayWindow_GraphWithText(CoefsImage,MetricsText)
                        cv2.imshow(windowName_Coefs, canvasToDispla_Coefs)
                        # CalculateMetrics=False
                    
                    AutoAlginFlag.clear()
                    
                if(Update_basisType_Flag.is_set()):
                    digiholoObj.digholo_SetProps()
                    if digiholoObj.digholoProperties["basisType"]==2:
                        digiholoObj.loadTransformMatrix(digiholoObj.digholoProperties["TransformMatrixFilename"])
                    Update_basisType_Flag.clear()
                    
                if(Set_DigholoProperties_Flag.is_set()):
                    digiholoObj.digholoProperties.update(digholoWindowProperties)
                    digiholoObj.digholo_SetProps()
                    Set_DigholoProperties_Flag.clear()
                    
                if(Get_DigholoProperties_Flag.is_set()):
                    PropsTemp=digiholoObj.digholo_GetProps()
                    digholoWindowProperties.update(PropsTemp)
                    Get_DigholoProperties_Flag.clear()       
                             
                ##### Process a batch so that the viewport updates    
                queue.put("test2")
                queue.put(frameBuffer.dtype)
                _,_=digiholoObj.digHolo_ProcessBatch(frameBuffer,CalculateMetrics=False)
                Fullimage,_, WindowSting=digiholoObj.GetViewport_arr(frameBuffer)
                queue.put("test3")
                
                # Make the viewport for the camera,FFT,FFTWindow and Field
                # Create a resizable window
                cv2.namedWindow(windowName_digHoloViewPort, cv2.WINDOW_NORMAL)
                # Resize the window to your desired size (width, height)
                cv2.resizeWindow(windowName_digHoloViewPort, 800, 600)  # Change the width and height as needed
                canvasToDispla_viewPort=digiholoObj.DisplayWindow_GraphWithText(Fullimage,WindowSting)
                cv2.imshow(windowName_digHoloViewPort, canvasToDispla_viewPort)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cv2.destroyAllWindows()
        cv2.waitKey(1)
        cv2.destroyAllWindows()
        Cam_digholo_shm.close()
        Metrics_shm.close()

        del digiholoObj
        return 0
