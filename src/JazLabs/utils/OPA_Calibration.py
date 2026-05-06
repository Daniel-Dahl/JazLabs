from Lab_Equipment.Config import config

# import tomography.standard as standard
# import tomography.masks as masks

# Python Libs
import cv2
import numpy as np
import matplotlib.pyplot as plt
import ctypes
import copy
from IPython.display import display, clear_output
import ipywidgets
import multiprocessing
import time
import scipy.io

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]

# Power Meter Libs
import  Lab_Equipment.PowerMeter.PowerMeter_Thorlabs_lib as PMLib

import Lab_Equipment.OpticalPowerAttenuator.OpticalPowerAttenuator as OPALib


# Alginment Functions
# import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignFunc

def CalibrateOPA(PWRObj:PMLib.PowerMeterObj,OPAObj:OPALib.Thorlabs_VOA,voltageMin=0,voltageMax=5,dvolt=0.001,UseRawCal=False):
    voltStepCount=int(((voltageMax-voltageMin)/dvolt)+1)
    voltArr=np.linspace(voltageMin,voltageMax,voltStepCount)
    pwrArr=np.zeros(voltStepCount)
    print(voltArr[1]-voltArr[0])
    
    
    for ivolt in range(voltStepCount):
        
        OPAObj.SetVoltValue(voltArr[ivolt])
        pwrArr[ivolt]=PWRObj.GetPower()
        print(ivolt,pwrArr[ivolt])
    if(UseRawCal):
        OPAObj.SetVoltPwrCal(voltArr,pwrArr)
        plt.plot(voltArr,pwrArr)
        return voltArr,pwrArr
    else:
        voltArr,pwrArrFit=VoltVsPowerFit(voltArr,pwrArr)
        OPAObj.SetVoltPwrCal(voltArr,pwrArr)
        return voltArr,pwrArr,pwrArrFit
        
    
        
def VoltVsPowerFit(voltArr,pwrArr,polyOrder=10):
    coeffs = np.polyfit(voltArr, pwrArr, deg=10)  # low-degree poly
    poly_fit = np.poly1d(coeffs)
    Fited_pwrs=poly_fit(voltArr)

    plt.plot(voltArr,pwrArr)
    plt.plot(voltArr,Fited_pwrs)
    return voltArr,Fited_pwrs