from Lab_Equipment.Config import config 

import io
import matplotlib
# matplotlib.use('agg')  # turn off interactive backend
import numpy as np
import matplotlib.pyplot as plt
import scipy.io
import Lab_Equipment.PlotingFunctions.ComplexPlotFunction as cmplxplt
import Lab_Equipment.OpticalSimulations.libs.OpticalOperators as OpticOp
import Lab_Equipment.OpticalSimulations.libs.CoupMatrixAndMetricAnalysisFuncitons_old as MetricCals

# NOTE you need to pass np.exp(1j*np.angle(MASK)) into the function not just MASKS
def PropergateFieldThroughMPLC(planeCount,modeCount,pixelSize,FieldsFWD,FieldsBKWD,MASKSPhaseComplx,TransferMatrixToFirstPlane,TransferMatrixBetweenPlanes,TransferMatrixAfterLastPlane):
    #Check if it is a single masks for all modes or multiple masks 
    DimsMask=np.shape(MASKSPhaseComplx)
    DimsField=np.shape(FieldsFWD)
    SingleMask4AllModes=False
    if(DimsField[0]>DimsMask[0]):
        SingleMask4AllModes=True
        
    DifferentPlaneDistances=False    
    DimsTransMat=np.shape(TransferMatrixBetweenPlanes)
    if(DimsTransMat[0]>1):
        DifferentPlaneDistances=True
    iplaneDist=0   
    for iplane in range(1,planeCount+1):
        for imode in range(modeCount):
            #Apply MASKS
            imodeMask=imode
            if(SingleMask4AllModes):
                imodeMask=0
            FieldsFWD[imode,iplane+1,:,:]= FieldsFWD[imode,iplane,:,:]*(MASKSPhaseComplx[imodeMask,iplane-1,:,:])
            FieldsBKWD[imode,iplane+1,:,:]=(FieldsBKWD[imode,iplane,:,:])*np.conj(MASKSPhaseComplx[imodeMask,-1*(iplane-1)-1,:,:])
            if (iplane==planeCount):# If you are at either end of the planes you need a different transfer function
                FieldsFWD[imode,iplane+1,:,:]=OpticOp.propagateField(FieldsFWD[imode,iplane+1,:,:],TransferMatrixAfterLastPlane)
                FieldsBKWD[imode,iplane+1,:,:]=OpticOp.propagateField((FieldsBKWD[imode,iplane+1,:,:]),np.conj(TransferMatrixToFirstPlane))
            else:# trasfer funciton for between planes
                FieldsFWD[imode,iplane+1,:,:]=OpticOp.propagateField(FieldsFWD[imode,iplane+1,:,:],TransferMatrixBetweenPlanes[iplaneDist,:,:])
                FieldsBKWD[imode,iplane+1,:,:]=OpticOp.propagateField((FieldsBKWD[imode,iplane+1,:,:]),np.conj(TransferMatrixBetweenPlanes[iplaneDist,:,:]))
        if(DifferentPlaneDistances):
            iplaneDist=iplaneDist+1
                    

    plt.figure(6)
    SimMetrics=MetricCals.CalculateCoupMatrixAndMetrics(FieldsBKWD[:,0,:,:],np.conj(FieldsFWD[:,-1,:,:]),pixelSize)
    # SimMetrics=MetricCals.CalculateCoupMatrixAndMetrics(np.conj(FieldsFWD[:,-1,:,:]),(FieldsBKWD[:,0,:,:]),pixelSize)
    # SimMetrics=MetricCals.CalculateCoupMatrixAndMetrics(np.conj(FieldsFWD[:,-1,:,:]),(FieldsFWD[:,0,:,:]),pixelSize)
    
    plt.imshow(cmplxplt.ComplexArrayToRgb(SimMetrics.CouplingMatrix));
    return FieldsFWD,FieldsBKWD,SimMetrics