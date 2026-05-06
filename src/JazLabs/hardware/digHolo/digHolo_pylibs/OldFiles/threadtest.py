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
import ctypes
import os
import scipy.io
import math
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [15,15]

class digholoObject():
    def __init__(self):
        super().__init__() # inherit from parent class  
        self.process_digholo = multiprocessing.Process(target=digiHoloThread)
        self.process_digholo.start()

        
        
    def __del__(self):
        """Destructor to disconnect from camera."""
        print("Digholo Oject has been destroyed")
        # self.terminateDigholo.set()# stop the camera thread
        # del self.handleIdx
        # self.shm.unlink() # clean up the shared memory space
    
    # def start_digiHoloThread(self,Cam:CamForm.CameraObject):
    def start_digiHoloThread(self):
        process_digholo = multiprocessing.Process(target=digiHoloThread)
        process_digholo.start()
        
        # return process_digholo, self.digholo_queue
        return process_digholo
    
def digiHoloThread():
    a=0
    time.sleep(10)
    while True:
    #     print(1)
        time.sleep(0.2)
        a=a+2