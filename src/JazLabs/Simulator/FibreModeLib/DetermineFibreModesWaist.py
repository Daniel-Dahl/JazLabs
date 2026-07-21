import sys
import numpy as np
# sys.path.append('/Users/danieldahl/Documents/Code/Virital_Lab/')
# sys.path.append('/Users/s4356803/Documents/USyd/Code/Virital_Lab/')

# Gaussian Free space Beams
import  JazLabs.Simulator.FibreModeLib.FibreModes as fibreModes
import JazLabs.Simulator.FibreModeLib.GaussianBeamBasis as GaussBeams
import JazLabs.Simulator.FibreModeLib.CoupMatrixAndMetricAnalysisFuncitons as CouplingMetricslib
import JazLabs.Simulator.FibreModeLib.OpticalOperators as OpticOp

import JazLabs.utils.AlignmentFunctions as AlignmentFunc
from scipy.optimize import minimize 
from enum import IntEnum


class Metrics(IntEnum):
    IL = 0
    MDL = 1
    DIAG = 2
    SNRAVG = 3
    AVGOVERLAP=4
    VolumePres=5
    test=6

# import  Lab_Equipment.OpticalSimulations.libs.GaussianBeamBasis as GaussBeams
# import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignmentFunc
# import Lab_Equipment.OpticalSimulations.libs.OpticalOperators as OpticOp

# import Lab_Equipment.OpticalSimulations.libs.CoupMatrixAndMetricAnalysisFuncitons as CouplingMetricslib

# import Lab_Equipment.FibreModeLib.FibreModes as fibreModes



def field_overlap(E1, E2, dx):
    """
    Calculate the complex spatial overlap (fidelity) between two fields.

    Parameters:
        E1, E2 : complex 2D numpy arrays (same shape)
        dx     : spatial step size (assumes square pixels)

    Returns:
        overlap : float, value between 0 and 1
    """
    num = np.sum(np.conj(E1) * E2) * dx**2
    denom = np.sqrt(np.sum(np.abs(E1)**2) * np.sum(np.abs(E2)**2)) * dx**2
    overlap = (num / denom)
    return abs(overlap)**2

def Intensity_overlap(E1, E2, dx):
    """
    Calculate the complex spatial overlap (fidelity) between two fields.

    Parameters:
        E1, E2 : complex 2D numpy arrays (same shape)
        dx     : spatial step size (assumes square pixels)

    Returns:
        overlap : float, value between 0 and 1
    """
    num = np.sum((E1) * E2) * dx**2
    denom = np.sqrt(np.sum(np.abs(E1)**2) * np.sum(np.abs(E2)**2)) * dx**2
    overlap = (num / denom)
    return abs(overlap)**2

class AlginmentObj_Gaussian():
    def __init__(self,
                 FibreModes,
                FibreLP01mode,
                wasitGuess,
                wavelength,
                pixelSize,
                XGrid,
                YGrid,
                maxModeGroup):
        super().__init__()
        self.FibreModes=FibreModes
        self.FibreLP01mode=FibreLP01mode
        self.wasitGuess=wasitGuess
        self.wavelength=wavelength
        self.pixelSize=pixelSize
        self.XGrid=XGrid
        self.YGrid=YGrid
        self.maxModeGroup=maxModeGroup


    def calculateOverlapWithGaussian(self,wasit):

        GaussianBeam= GaussBeams.GenerateHGMode(wasit, self.wavelength,0,0, 
                                                self.pixelSize,self.XGrid,self.YGrid, 0, 0)
        overlap=field_overlap(self.FibreLP01mode,GaussianBeam,self.pixelSize)
        metric=-overlap
        return wasit,metric
    
    def DetermineOptGaussianWasit(self,dspace_Tol=1):
        BoundMin=self.wasitGuess-100*self.pixelSize
        BoundMax=self.wasitGuess+100*self.pixelSize

        avg_x, avg_f=AlignmentFunc.GoldenSectionSearchContinuous(BoundMin,BoundMax,dspace_Tol=dspace_Tol,FuncToMinamise=self.calculateOverlapWithGaussian)
        return avg_x, avg_f
    
    def calculateIntesityOverlapHGmodeLPMode(self,wasit):

        # GaussianBeam= GaussBeams.GenerateHGMode(wasit, self.wavelength,0,0, 
        #                                         self.pixelSize,self.XGrid,self.YGrid, 0, 0)
        Ny,Nx=self.XGrid.shape
        maxModeGroup=self.maxModeGroup
        modeCountHG=np.sum(np.arange(maxModeGroup+1))
        HGmodes=np.zeros((modeCountHG,Ny,Nx),dtype=np.complex128)
        z_dist=0
        modeIndices=np.zeros((2,modeCountHG))
        imode=0
        for mgIdx in range(maxModeGroup):
            #zero-based index of the mode-group
            mgIDX = mgIdx;
            #For every mode in this group (there will be mgIdx of them)
            for modeIdx in range(mgIdx+1):
                #m+n should equal mgIDX.
                #Go through each m,n combo in this group starting with max m
                n = mgIDX-(modeIdx);
                m = mgIDX-n;
                l=m-n;
                p=min([n,m]);
                modeIndices[0,imode]=n
                modeIndices[1,imode]=m
                HGmodes[imode,:,:]= GaussBeams.GenerateHGMode(wasit, self.wavelength,n,m, self.pixelSize,self.XGrid,self.YGrid, z_dist, 0)
                
                imode=imode+1
        
        # Overlap of the intensity sum of the fields        
        TotalSuperposMode=np.sum(abs(HGmodes)**2,0)
        TotalSuperposMode_LP=np.sum(abs(self.FibreModes)**2,0)
        overlap,overlapNorm=fibreModes.field_overlap(TotalSuperposMode, TotalSuperposMode_LP, self.pixelSize)
        
        # Couopling matix calculation
        modeCountFibre=self.FibreModes[:,:,:].shape[0]
        
        TransformMatrix=np.zeros([modeCountFibre,modeCountHG],dtype=complex)
        for i in range(modeCountFibre):
            for j in range(modeCountHG):
                # HG_transMatrix[i,j]= np.sum(np.sum((HGmodes[j,:,:])*np.conj(Modes2Transform[i,:,:])));
                # TransformMatrix[i,j]= np.sum(np.sum((FibreModes[i,:,:])*np.conj(HGmodes[j,:,:])));
                TransformMatrix[i,j],_=fibreModes.field_overlap(self.FibreModes[i,:,:], HGmodes[j,:,:], self.pixelSize)
                
        CouplingMetrics=CouplingMetricslib.CalculateMetrics(TransformMatrix)
        
        transMode=OpticOp.ConvertModeViaTransformMatrix(TransformMatrix,HGmodes)
       
        
        CouplingModesMatrix=np.zeros([modeCountFibre,modeCountHG],dtype=complex)
        for i in range(modeCountFibre):
            for j in range(modeCountFibre):
                # HG_transMatrix[i,j]= np.sum(np.sum((HGmodes[j,:,:])*np.conj(Modes2Transform[i,:,:])));
                # TransformMatrix[i,j]= np.sum(np.sum((FibreModes[i,:,:])*np.conj(HGmodes[j,:,:])));
                CouplingModesMatrix[i,j],_=fibreModes.field_overlap(self.FibreModes[i,:,:], transMode[j,:,:], self.pixelSize)
        # plt.imshow(cmplxplt.ComplexArrayToRgb(CouplingModesMatrix))

        CouplingMetrics=CouplingMetricslib.CalculateMetrics(CouplingModesMatrix)
        
        # CouplingMetrics.SNR
        # TotalSuperposMode=np.sum(HGmodes,1)
        
        # overlap=Intensity_overlap(self.FibreLP01mode,GaussianBeam,self.pixelSize)
        metric=-overlapNorm
        metric=CouplingMetrics.IL
        # metric=CouplingMetrics.MDL
        # metric=-CouplingMetrics.SNR
        # metric=-np.sum(np.abs(CouplingModesMatrix)**2)

        
        
        return wasit,metric
    
    
    def calculateIntesityOverlapFieldsLPMode(self,wasit):

        # GaussianBeam= GaussBeams.GenerateHGMode(wasit, self.wavelength,0,0, 
        #                                         self.pixelSize,self.XGrid,self.YGrid, 0, 0)
        Ny,Nx=self.XGrid.shape
        modeCount=len(self.GuidedModes_props)
        Modes=np.zeros((modeCount,Ny,Nx),dtype=np.complex128)
        z_dist=0
        imode=0
        for mode in self.GuidedModes_props:
            # print(f"l={mode['l']}, m={mode['m']},ab={mode['ab']} mode_group={mode['mode_group']}, V_cutoff={mode['V_cutoff']:.2f}, V={mode['V']:.2f}, guided={mode['guided']}")
            Modes[imode,:,:]=fibreModes.LPMode_free(mode['l'], mode['m'],mode['ab'], self.XGrid, self.YGrid,wasit)
    # FibreModes[imode,:,:]=fibreModes.LPMode(mode['l'], mode['m'],mode['ab'], XGrid, YGrid, 
    #                   core_radius, wavelength, n_core, n_clad)
            imode+=1
        TotalSuperposMode_LP=np.sum(abs(Modes)**2,0)
        TotalSuperposMode=np.sum(abs(self.FibreModes)**2,0)
        
        overlap,overlapNorm=fibreModes.field_overlap(TotalSuperposMode, TotalSuperposMode_LP, self.pixelSize)
        metric=-overlapNorm
        
    
        return wasit,metric

    def calculateILFieldsandLPModes(self,wasit):

        # GaussianBeam= GaussBeams.GenerateHGMode(wasit, self.wavelength,0,0, 
        #                                         self.pixelSize,self.XGrid,self.YGrid, 0, 0)
        Ny,Nx=self.XGrid.shape
        modeCount=len(self.GuidedModes_props)
        Modes=np.zeros((modeCount,Ny,Nx),dtype=np.complex128)
        z_dist=0
        imode=0
        for mode in self.GuidedModes_props:
            Modes[imode,:,:]=fibreModes.LPMode_free(mode['l'], mode['m'],mode['ab'], self.XGrid, self.YGrid,wasit)
            imode+=1
        
        metricsCoup=CouplingMetricslib.CalculateCoupMatrixAndMetrics(self.FibreModes,Modes,self.pixelSize,UseNorm=True)

        metric=metricsCoup.IL
        # metric=-metricsCoup.VolumePres
        # metric=metricsCoup.MDL
        # metric=CouplingMetrics.MDL
        # metric=-CouplingMetrics.SNR
        # metric=-np.sum(np.abs(metricsCoup.CouplingMatrix)**2)


        
    
        return wasit,metric
    
    def objectiveFunc_centerswasit(self,x):
        xcenter = x[0]
        ycenter = x[1]

        wasit = x[2]
        Ny,Nx=self.XGrid.shape
        modeCount=len(self.GuidedModes_props)
        Modes=np.zeros((modeCount,Ny,Nx),dtype=np.complex128)
        z_dist=0
        imode=0
        for mode in self.GuidedModes_props:
            Modes[imode,:,:]=fibreModes.LPMode_free(mode['l'], mode['m'],mode['ab'], self.XGrid, self.YGrid,wasit,xcenter,ycenter)
            imode+=1
        
        metricsCoup=CouplingMetricslib.CalculateCoupMatrixAndMetrics(self.FibreModes,Modes,self.pixelSize,UseNorm=True)
        # CouplingMatrix=CouplingMetricslib.CalculateCouplingMatrix_WithNorm(self.FibreModes,Modes,self.pixelSize)

        if self.selected_metric == Metrics.IL:
            metric=metricsCoup.IL
        elif self.selected_metric == Metrics.MDL:
            metric=metricsCoup.MDL
        elif self.selected_metric == Metrics.SNRAVG:
            metric=-metricsCoup.SNR
        elif self.selected_metric == Metrics.AVGOVERLAP:
            metric=-np.sum(np.abs(metricsCoup.CouplingMatrix)**2)
            # metric=-np.sum(np.abs(CouplingMatrix)**2)
        elif self.selected_metric == Metrics.VolumePres:
            metric=-metricsCoup.VolumePres
        elif self.selected_metric == Metrics.test:
            metric=metricsCoup.IL*metricsCoup.SNR
            
        


        # metric=CouplingMetrics.MDL
        # metric=-CouplingMetrics.SNR
        # metric=-np.sum(np.abs(metricsCoup.CouplingMatrix)**2)
        return metric

  
    
    def DetermineOptMFDmodeGroup(self,dspace_Tol=1):
        BoundMin=self.wasitGuess-10*self.pixelSize
        BoundMax=self.wasitGuess+10*self.pixelSize

        avg_x, avg_f=AlignmentFunc.GoldenSectionSearchContinuous(BoundMin,BoundMax,dspace_Tol=dspace_Tol,FuncToMinamise=self.calculateIntesityOverlapHGmodeLPMode)
        return avg_x, avg_f
    
    def DetermineOptLPWaist(self,dspace_Tol=1,FieldModes=None,GuidedModes_props=None):
        self.FibreModes=FieldModes
        self.GuidedModes_props=GuidedModes_props
        BoundMin=self.wasitGuess-100*self.pixelSize
        BoundMax=self.wasitGuess+100*self.pixelSize

        # avg_x, avg_f=AlignmentFunc.GoldenSectionSearchContinuous(BoundMin,BoundMax,dspace_Tol=dspace_Tol,FuncToMinamise=self.calculateIntesityOverlapFieldsLPMode)
        avg_x, avg_f=AlignmentFunc.GoldenSectionSearchContinuous(BoundMin,BoundMax,dspace_Tol=dspace_Tol,FuncToMinamise=self.calculateILFieldsandLPModes)
       
        
        return avg_x, avg_f
    
    def MultiDimOpt_waistCenters(self,FieldModes,GuidedModes_props,inital_val,selected_metric):
        self.FibreModes=FieldModes
        self.GuidedModes_props=GuidedModes_props
        self.selected_metric=selected_metric
        BoundMin_wasit=inital_val[2]-50*self.pixelSize
        BoundMax_wasit=inital_val[2]+50*self.pixelSize

        BoundMin_xCenter=inital_val[0]-50*self.pixelSize
        BoundMax_xCenter=inital_val[0]+50*self.pixelSize

        BoundMin_yCenter=inital_val[1]-50*self.pixelSize
        BoundMax_yCenter=inital_val[1]+50*self.pixelSize
        bounds=((BoundMin_xCenter,BoundMax_xCenter),(BoundMin_yCenter,BoundMax_yCenter),(BoundMin_wasit,BoundMax_wasit))

        res = minimize(self.objectiveFunc_centerswasit,
                        np.asarray(inital_val, dtype=float), 
                       bounds=bounds,
                           options={
        "ftol": 1e-4,   # stop when objective value changes less than this
        "xtol": 1e-8,   # stop when parameters change less than this
        "maxiter": 100000,
    })

        print("Best results")
        bestmetric=self.objectiveFunc_centerswasit(res.x)
        stringResults="Best Xcenter= "+str(res.x[0]) +" Best Ycenter= "+str(res.x[1]) +" Best waist= "+str(res.x[2])
        print(stringResults)

        return res.x, res, bestmetric