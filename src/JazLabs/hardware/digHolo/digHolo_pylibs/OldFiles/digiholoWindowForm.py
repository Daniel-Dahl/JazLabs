slash= "\\"
import sys
import Lab_Equipment.Config.config as config

import matplotlib.pyplot as plt
import numpy as np
import cv2
import multiprocessing
from multiprocessing import shared_memory
import time
import copy

import Experiments.Lab_Equipment.digHolo.digHolo_pylibs.digiholoHeader_old as digH_hpy # as in header file for python... pretty clever I know (Daniel 2 seconds after writing this commment. Head slap you are a idiot )
import Lab_Equipment.digHolo.digHolo_pylibs.digholoCombinedFunction as digholoFuncWrapper

#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm
# from Lab_Equipment.Camera.CameraObject import CameraObject
from multiprocessing import Manager
import ctypes
import os
import scipy.io
import math
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [15,15]

class digholoThreads():
    def __init__(self,Cam:CamForm.GeneralCameraObject,Wavelength=810e-9,polCount=1,maxMG=1,fftWindowSizeX=256,fftWindowSizeY=256,FFTRadius=0.4):
        super().__init__() # inherit from parent class  
        self.frameCount = ((ctypes.c_int))()
        self.batchCount = ((ctypes.c_int))()
        self.polCount = ((ctypes.c_int))()
        frameCount = 1
        self.batchCount = frameCount
        self.polCount = polCount
        
        # self.shm = shared_memory.SharedMemory(create=True, size=int(self.FrameHeight* self.FrameWidth * np.dtype(np.uint8).itemsize))
        # self.FrameBuffer_SharedMem  = np.ndarray((self.FrameHeight, self.FrameWidth), dtype=self.FrameBuffer.dtype, buffer=self.shm.buf)                    
    
        #We need to set up a bunch of varibles for the threading of the camera.   
        self.digiHoloPaused = multiprocessing.Event()
        self.terminateDigholo = multiprocessing.Event()
        self.PauseDigholo = multiprocessing.Event()
        self.AutoAlginFlag = multiprocessing.Event()
        self.digholo_queue = multiprocessing.Queue()
        self.FrameObtained = multiprocessing.Value('i', 0)  # Flag to indicate when a frame is ready  
        
        
        # self.handleIdxThread = multiprocessing.Value('i', self.handleIdx)
        self.handleIdxThread = multiprocessing.Value('i', 0)
        
        self.polCountThead=multiprocessing.Value('i', self.polCount)
        self.batchCountThead=multiprocessing.Value('i', self.batchCount)
        self.resolutionMode = multiprocessing.Value('i', 0)
        
        self.fftWindowSizeX=multiprocessing.Value('i', fftWindowSizeX)
        self.fftWindowSizeY=multiprocessing.Value('i', fftWindowSizeY)
        self.FFTRadius=multiprocessing.Value('f', FFTRadius)
        
        self.maxMG=multiprocessing.Value('i', maxMG)           
        self.Wavelength=multiprocessing.Value('f', Wavelength)
        
        manager = Manager()
        self.frameBatch = manager.dict()
        self.frameBatch['shmName'] = "frameBatch_shmName"
        # self.frameBatch['FrameHeight'] = Cam.FrameHeightThread.value
        # self.frameBatch['FrameWidth'] = Cam.FrameWidthThread.value
        # self.frameBatch['batchCount'] =1
        self.frameBatch['FrameHeight'] = 1
        self.frameBatch['FrameWidth'] = 1
        self.frameBatch['batchCount'] =1
        
        
        # self.PixelSize=multiprocessing.Value('f', Cam.PixelSize)
        self.PixelSize=Cam.PixelSize
        
        
        self.shm_Cam= Cam.shm.name
        print(Cam.FrameHeightThread.value)
        print(self.shm_Cam)
        
        # Create an array that that has all the AutoAlginFlags in it  
        AutoAlginFlagsCount=5
        self.AutoAlginFlags = multiprocessing.Array('i', AutoAlginFlagsCount)
        for i in range(AutoAlginFlagsCount):
            if (i==AutoAlginFlagsCount-1):
                self.AutoAlginFlags[i]=0
            else:
                self.AutoAlginFlags[i]=1
        print(self.AutoAlginFlags)

        #Amount of detail to print to console. 0: Console off. 1: Basic info. 2:Debug mode. 3: You've got serious issues
        self.verbosity = 2
        
        self.BatchFrmae_shm = shared_memory.SharedMemory(create=True, size=int(self.frameBatch['batchCount'] * self.frameBatch['FrameHeight']*self.frameBatch['FrameWidth']  * np.dtype(np.uint8).itemsize))
        # self.BatchFrmae_shm = shared_memory.SharedMemory(create=True, size=int(1 * 1*1  * np.dtype(np.uint8).itemsize))
        
        # self.BatchFrmae_SharedMem  = np.ndarray((int(1), int(1),int(1) ), dtype=np.uint8, buffer=self.BatchFrmae_shm.buf) 
        self.BatchFrmae_SharedMem  = np.ndarray((int(self.frameBatch['batchCount']), int(self.frameBatch['FrameHeight']),int(self.frameBatch['FrameWidth']) ), dtype=np.uint8, buffer=self.BatchFrmae_shm.buf) 
        
        self.frameBatch['shmName'] =self.BatchFrmae_shm.name
        print(Cam.FrameHeightThread,Cam.FrameWidthThread)
        self.process_digholo, self.digholo_queue=self.start_digiHoloThread(Cam)
        print(Cam.Framedtype)
        
        
    def __del__(self):
        """Destructor to disconnect from camera."""
        print("Digholo Oject has been destroyed")
        self.terminateDigholo.set()# stop the camera thread
        self.process_digholo.terminate()
        self.BatchFrmae_shm.unlink()
        # int digHoloDestroy (int handleIdx) 
        # del self.handleIdx
        # self.shm.unlink() # clean up the shared memory space
    
    def start_digiHoloThread(self,Cam:CamForm.GeneralCameraObject):
        #  def start_digiHoloThread(self):
        
        self.process_digholo = multiprocessing.Process(target=digiHoloThread, args=(
            self.digholo_queue,self.terminateDigholo,self.AutoAlginFlag,
            Cam.shm.name,Cam.FrameHeightThread,Cam.FrameWidthThread,Cam.FrameObtained,Cam.GetFrameFlag,Cam.PixelSize,Cam.Framedtype,
            self.handleIdxThread,
            self.polCountThead,self.batchCountThead,
            self.fftWindowSizeX,self.fftWindowSizeY,self.FFTRadius,
            self.Wavelength,self.maxMG,self.resolutionMode,
            self.verbosity,self.AutoAlginFlags, self.frameBatch,self.digiHoloPaused
            ))
        self.AutoAlginFlag.set()
        self.process_digholo.start()
        
        return self.process_digholo, self.digholo_queue
        
    def digholoGetProps(self):

        # handleIdx=self.handleIdxThread.value
        
        # self.PixelSize= digH_hpy.digHolo.digHoloConfigGetFramePixelSize(self.handleIdxThread.value)

        # self.Wavelength.value=digH_hpy.digHolo.digHoloConfigGetWavelengthCentre(self.handleIdxThread.value)
        # self.polCountThead.value=digH_hpy.digHolo.digHoloConfigGetPolCount(self.handleIdxThread.value)
        
        # self.fftWindowSizeY.value= digH_hpy.digHolo.digHoloConfigGetfftWindowSizeY(self.handleIdxThread.value)
        # self.fftWindowSizeX.value= digH_hpy.digHolo.digHoloConfigGetfftWindowSizeX(self.handleIdxThread.value)
        # self.FFTRadius.value=digH_hpy.digHolo.digHoloConfigGetFourierWindowRadius(self.handleIdxThread.value)
        # print(self.FFTRadius.value)
        
        # self.resolutionMode.value=digH_hpy.digHolo.digHoloConfigGetIFFTResolutionMode(self.handleIdxThread.value)
        # self.maxMG.value=digH_hpy.digHolo.digHoloConfigGetBasisGroupCount(self.handleIdxThread.value)
        
        # #Defines which parameters to optimise in the AutoAlign routine. These are on by default anyways
        # self.AutoAlginFlags[0]=digH_hpy.digHolo.digHoloConfigGetAutoAlignBeamCentre(self.handleIdxThread.value)
        # self.AutoAlginFlags[1]=digH_hpy.digHolo.digHoloConfigGetAutoAlignDefocus(self.handleIdxThread.value)
        # self.AutoAlginFlags[2]=digH_hpy.digHolo.digHoloConfigGetAutoAlignTilt(self.handleIdxThread.value)
        # self.AutoAlginFlags[3]=digH_hpy.digHolo.digHoloConfigGetAutoAlignBasisWaist(self.handleIdxThread.value)
        # self.AutoAlginFlags[4]=digH_hpy.digHolo.digHoloConfigGetAutoAlignFourierWindowRadius(self.handleIdxThread.value)

        print('PixelSize= ', self.PixelSize)
        print('Wavelength= ', self.Wavelength.value) 
        print('polCountThead= ', self.polCountThead.value  ) 
        print('fftWindowSizeY= ', self.fftWindowSizeY.value  ) 
        print('fftWindowSizeX= ', self.fftWindowSizeX.value  )
        print('fftRadius= ',self.FFTRadius.value)
        print('maxMG= ', self.maxMG.value  ) 

    def SetPausePlayDigholo(self):
        if(self.digiHoloPaused.is_set()):
            self.digiHoloPaused.clear()
        else:
            self.digiHoloPaused.set()



          


# NOTE that you have to create the Digholo c obejct in the multiprocess.
# This is because the Digholo c obejct makes a whole bunch of varibles that you cant keep
# track of in the multiprocess. If you initalise it in the multiprocess it is a lot easier to handle
def digiHoloThread(queue,terminateDigholo,AutoAlginFlag,
                CamshmName,FrameHeight,FrameWidth,FrameObtained,GetFrameFlag,PixelSize,Framedtype,
                handleIdxThread,
                polCountThead,batchCountThead,
                fftWindowSizeX, fftWindowSizeY,FFTRadius,
                Wavelength,maxMG,resolutionMode,
                verbosity,AutoAlginFlags,frameBatch,digiHoloPaused
                ):

        shm = shared_memory.SharedMemory(name=CamshmName)
        # CamFrameFromshm = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.uint8, buffer=shm.buf)
        # frame_buffer_int = np.zeros((FrameHeight.value, FrameWidth.value), dtype=np.uint8)
        CamFrameFromshm = np.ndarray((FrameHeight.value, FrameWidth.value), dtype=np.dtype(Framedtype), buffer=shm.buf)
        frame_buffer_int = np.zeros((FrameHeight.value, FrameWidth.value), dtype=np.dtype(Framedtype))
        #Start up the digholo
        handleIdxThread.value=digH_hpy.digHolo.digHoloCreate()
        digH_hpy.digHolo.digHoloConfigSetFrameDimensions(handleIdxThread.value,FrameWidth.value,FrameHeight.value)
        digH_hpy.digHolo.digHoloConfigSetFramePixelSize(handleIdxThread.value,PixelSize)
        digH_hpy.digHolo.digHoloConfigSetBatchCount(handleIdxThread.value,batchCountThead.value) 

        digholoFuncWrapper.digholoSetProps(handleIdxThread.value,polCountThead.value,
                                            fftWindowSizeX.value,fftWindowSizeY.value,FFTRadius.value,
                                            Wavelength.value,resolutionMode.value,maxMG.value,AutoAlginFlags)


        windowName='digholoviewport'
        # queue.put("test4")
        while not terminateDigholo.is_set(): 
            if(not digiHoloPaused.is_set()):
                GetFrameFlag.set()
                while FrameObtained.value==0:
                    time.sleep(1e-120)
                FrameObtained.value = 0    
                #Once the frame has been grabbed it can be converted to a float32 to then be processed by digholo 
                np.copyto(frame_buffer_int, CamFrameFromshm)
                frameBuffer=frame_buffer_int.astype(np.float32)
                
                frameBufferPtr = frameBuffer.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
                if (AutoAlginFlag.is_set()):
                    AutoAlginFlag.clear()
                    # queue.put("test5")
                    digholoFuncWrapper.digholo_AutoAlginBatch(handleIdxThread.value,batchCountThead.value,polCountThead.value,
                                                        fftWindowSizeX.value,fftWindowSizeY.value,FFTRadius.value,
                                                        Wavelength.value,maxMG.value,resolutionMode.value,verbosity,
                                                        AutoAlginFlags,frameBufferPtr)
                    
                    # Wavelength.value,polCountThead.value,fftWindowSizeY.value,fftWindowSizeX.value,FFTRadius.value,resolutionMode.value,maxMG.value,
                    # AutoAlginFlags[0],AutoAlginFlags[1],AutoAlginFlags[2],AutoAlginFlags[3],AutoAlginFlags[4]\
                    # =digholoFuncWrapper.digholoGetProps(handleIdxThread.value)
                    
                    # Wavelength.value,polCountThead.value,fftWindowSizeY.value,fftWindowSizeX.value,FFTRadius.value,resolutionMode.value,maxMG.value,\
                    # AutoAlginFlags[0],AutoAlginFlags[1],AutoAlginFlags[2],AutoAlginFlags[3],AutoAlginFlags[4]\
                    # =digholoFuncWrapper.digholoGetProps(handleIdxThread.value)
                    
                    frameBatch_shm = shared_memory.SharedMemory(name=frameBatch['shmName'])
                    FrameBatch_array = np.ndarray((frameBatch['batchCount'],frameBatch['FrameHeight'],frameBatch['FrameWidth']), dtype=np.uint8, buffer=frameBatch_shm.buf)
                    FrameBatch_array_thread = np.zeros((frameBatch['batchCount'],frameBatch['FrameHeight'],frameBatch['FrameWidth']), dtype=np.uint8)
                    np.copyto(FrameBatch_array_thread, FrameBatch_array)
                    frameBatch_shm.close()
                    queue.put(frameBatch['shmName'])

                digholoFuncWrapper.ProcessBatchOfFrames(handleIdxThread.value,batchCountThead.value,frameBuffer)
                Fullimage,cam_rgb, WindowSting=digholoFuncWrapper.GetViewport_arr(handleIdxThread.value,frameBuffer)
                
                
                # Create a resizable window
                cv2.namedWindow(windowName, cv2.WINDOW_NORMAL)
                # Set the window to full screen (optional)
                # cv2.setWindowProperty('Resizable Window', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                # Resize the window to your desired size (width, height)
                cv2.resizeWindow(windowName, 800, 600)  # Change the width and height as needed
                Fullimage_rgb = cv2.cvtColor(Fullimage, cv2.COLOR_BGR2RGB)# this is to get the correct colour for opencv matplotlib doesnt have this problem
                cv2.imshow(windowName, Fullimage_rgb)
                # plt.imshow(Fullimage_rgb)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
        cv2.destroyAllWindows()
        cv2.waitKey(1)
        cv2.destroyAllWindows()
        shm.close()
        ErrorCode=digH_hpy.digHolo.digHoloDestroy(handleIdxThread.value) 
        print(ErrorCode)
        return 0
