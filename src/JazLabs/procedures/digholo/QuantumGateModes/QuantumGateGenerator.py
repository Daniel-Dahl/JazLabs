import numpy as np
import matplotlib.pyplot as plt
import scipy.io
from scipy.fft import fft, fftfreq, fftshift, fft2,ifft2,rfft2,irfft2
# import MyPythonLibs.ComplexPlotFunction as cmplxplt

import GaussianBeamLib.GaussianBeamTypes as GaussBeams
import GaussianBeamLib.OpticalOperators as OpticOp
# import MyPythonLibs.OpticalOperators as OpticOp
# import MyPythonLibs.CoupMatrixAndMetricAnalysisFuncitons as MetricCals
# import MyPythonLibs.GaussianBeamBasis as GaussBeams

# Global Ploting properties and style
plt.style.use('dark_background')
plt.rcParams['figure.figsize'] = [10,10]

def GenerateLGAzthmModes(x,y,z_dist,MFD, wavelen,modeIndeices):
    modeCount=np.size(modeIndeices[0,:]);
    MAXmaxMG=np.max(modeIndeices)
    
    X_temp,Y_temp=np.meshgrid(x,y);
    Nx=np.size(x);
    Ny=np.size(y);
    pixelSize=x[1]-x[0]
    print(modeIndeices)
    Modes=np.zeros([modeCount,Nx,Ny],dtype=complex);
    for imode in range(modeCount):
        p=modeIndeices[0,imode];
        l=modeIndeices[1,imode];
        
            # InputModes[imode,:,:]=np.flip(InputModes[imode,:,:],0)
            # GenerateLGMode(MFD, wavelength, m, l, X_temp, Y_temp, z_dist, MAXmaxMG)
        Modes[imode,:,:]=(GaussBeams.GenerateLGMode(MFD, wavelen, p, l, X_temp, Y_temp, z_dist, MAXmaxMG))
        # Modes[imode,:,:]=np.flip(GaussBeams.GenerateLGMode(MFD, wavelen, p, l, pixelSize,X_temp, Y_temp, z_dist, MAXmaxMG),0)
        # Modes[imode,:,:]=np.transpose(GaussBeams.GenerateLGMode(MFD, wavelen, p, l, pixelSize,X_temp, Y_temp, z_dist, MAXmaxMG))
        
    
    return Modes

def GenerateGateModes(GateModeType,InputModes):
    if (GateModeType =='DFTGate'):
        Modes,transformMatrix=GenerateDFTGateOutput(InputModes);
    elif(GateModeType=='XGate'):
        Modes,transformMatrix=GenerateXGateOutput(InputModes);
    elif(GateModeType,'ZGate'):
        Modes,transformMatrix=GenerateZGateOutput(InputModes);
    else:
        print("You didn't select a valid ModeType")
    return Modes,transformMatrix
#Gate out generation functions
def GenerateXGateOutput(InputModes):
    Dims=np.shape(InputModes);
    modeCount=Dims[0];
    Ny=Dims[1];
    Nx=Dims[2];
    # transMode=np.zeros([modeCount,Ny,Nx],dtype=complex);
    #Make the transformed bases that is for the gate
    # transformMatrix=np.flip(np.eye(modeCount,dtype=complex),axis=1);
    transformMatrix=np.eye(modeCount,dtype=complex);
    
    for imode in range(modeCount):
        transformMatrix[:,imode]=(np.roll(transformMatrix[:,imode],shift=-1,axis=0));
        # transformMatrix[:,imode]=(np.roll(transformMatrix[:,imode],shift=-1,axis=0));
        
        
    # transMode=OpticOp.ConvertModeViaTransformMatrix(np.transpose(transformMatrix),InputModes)
    transMode=OpticOp.ConvertModeViaTransformMatrix((transformMatrix),InputModes)
    
    # transModetemp=np.zeros([modeCount,Ny,Nx],dtype=complex);
    # for i in range(modeCount):
    #     for j in range(modeCount):
    #         transModetemp[j,:,:]=transformMatrix[j,i]*InputModes[j,:,:];
        
    #     transMode[i,:,:]=np.sum(transModetemp,0)
    return transMode ,transformMatrix


def GenerateDFTGateOutput(InputModes):
    Dims=np.shape(InputModes);
    modeCount=Dims[0];
    Ny=Dims[1];
    Nx=Dims[2];
    # for imode in range(modeCount):
        # InputModes[imode,:,:]=np.flip(InputModes[imode,:,:],0)
    # transMode=np.zeros([modeCount,Ny,Nx],dtype=complex);
    #Make the transformed bases that is for the gate
    transformMatrix=(DFTMatrix(modeCount))
    transMode=OpticOp.ConvertModeViaTransformMatrix(transformMatrix,InputModes)
    
    # transModetemp=np.zeros([modeCount,Ny,Nx],dtype=complex);
    # for i in range(modeCount):
    #     for j in range(modeCount):
    #         transModetemp[j,:,:]=transformMatrix[j,i]*InputModes[j,:,:];
        
    #     transMode[i,:,:]=np.sum(transModetemp,0)
    return transMode,transformMatrix
def GenerateZGateOutput_oldway (InputModes):
    Dims=np.shape(InputModes);
    modeCount=Dims[0];
    Ny=Dims[1];
    Nx=Dims[2];
    transMode=np.zeros([modeCount,Ny,Nx],dtype=complex);
    halfModeCount=np.floor(modeCount//2);
    idxArray_temp=(np.arange(-halfModeCount,halfModeCount+1));
    if (modeCount%2==0):
        # idxArray = np.delete(idxArray_temp, int(halfModeCount))
        idxArray=(np.arange(-halfModeCount,halfModeCount));
        
    else:
        idxArray = idxArray_temp
        # idxArray
    # idxArray=np.arange(-halfModeCount,halfModeCount+1);
    
    print(idxArray)
    phase_shift=(idxArray/max(idxArray))*np.pi;
    for imode in range(modeCount):
        transMode[imode,:,:]=InputModes[imode,:,:]*np.exp(-1j*phase_shift[imode]);
    return transMode,transformMatrix

def GenerateZGateOutput(InputModes):
    Dims=np.shape(InputModes);
    modeCount=Dims[0];
    Ny=Dims[1];
    Nx=Dims[2];
    transMode=np.zeros([modeCount,Ny,Nx],dtype=complex);
    transformMatrix=np.eye(modeCount,dtype=complex);
    for imode in range(modeCount):
        transformMatrix[imode,imode]=transformMatrix[imode,imode]*(np.exp(((imode)*-1j*2*np.pi/modeCount)))
        # transMode[imode,:,:]=InputModes[imode,:,:]*(np.exp((-1j*imode*2*np.pi/modeCount)))
        
        
    # transMode=OpticOp.ConvertModeViaTransformMatrix(transformMatrix,InputModes,"Right")
    transMode=OpticOp.ConvertModeViaTransformMatrix(transformMatrix,InputModes)
    return transMode,transformMatrix
    # return transMode


def DFTMatrix(N):
    DFTmat =np.zeros([N,N],dtype=complex)
    w_val = np.exp(-1j* 2.0 * np.pi /np.single(N));
    scalerTerm=(1.0 / np.sqrt(np.single(N)))+(1j*0)
    for i in range(N):
        for j in range(N):
            DFTmat[i, j] = scalerTerm*w_val**(np.single(i*j))
    DFTmat=np.fft.fftshift(DFTmat)
    # plt.imshow(cmplxplt.ComplexArrayToRgb(DFTmat))
    return (DFTmat)