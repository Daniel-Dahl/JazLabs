import numpy as np
import matplotlib.pyplot as plt

from scipy import io, integrate, linalg, signal
from scipy.io import savemat, loadmat
from scipy.fft import fft, fftfreq, fftshift,ifftshift, fft2,ifft2,rfft2,irfft2
# Defult Pploting properties 
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [5,5]
import pwi_inst.utils.camera_utils as cam_utils


def CalibrateOPA(CamObj,VOAObj,voltageMin=0,voltageMax=5,dvolt=0.001,UseRawCal=False,
                  ixCamCenter=None,iyCamCenter=None,
                                    x_half_width=None,
                                    y_half_width=None):
    
    voltStepCount=int(((voltageMax-voltageMin)/dvolt)+1)
    voltArr=np.linspace(voltageMin,voltageMax,voltStepCount)
    pwrArr=np.zeros(voltStepCount)
    print(voltArr[1]-voltArr[0])
    
    
    for ivolt in range(voltStepCount):
        
        VOAObj.SetVoltage(voltArr[ivolt])
        frame=CamObj.GetFrame()
        pwrArr[ivolt] = cam_utils.get_relative_power(frame=frame,centre=[ixCamCenter,iyCamCenter],x_half_width=x_half_width,y_half_width=y_half_width)
        print(ivolt,pwrArr[ivolt])
    if(UseRawCal):
        VOAObj.SetVoltage(voltArr,pwrArr)
        plt.plot(voltArr,pwrArr)
        return voltArr,pwrArr
    else:
        voltArr,pwrArrFit=VoltVsPowerFit(voltArr,pwrArr)
        VOAObj.SetVoltage(voltArr,pwrArr)
        return voltArr,pwrArr,pwrArrFit
        
    
        
def VoltVsPowerFit(voltArr,pwrArr,polyOrder=10):
    coeffs = np.polyfit(voltArr, pwrArr, deg=10)  # low-degree poly
    poly_fit = np.poly1d(coeffs)
    Fited_pwrs=poly_fit(voltArr)

    plt.plot(voltArr,pwrArr)
    plt.plot(voltArr,Fited_pwrs)
    return voltArr,Fited_pwrs