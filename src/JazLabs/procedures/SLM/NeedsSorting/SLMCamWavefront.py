from Lab_Equipment.Config import config
import numpy as np
import Lab_Equipment.SLM.pyLCOS as pyLCOS
import Lab_Equipment.ZernikeModule.ZernikeModule as zernMod

#Camera Libs
import Lab_Equipment.Camera.CameraObject as CamForm

# Alginment Functions
import  Lab_Equipment.AlignmentRoutines.AlignmentFunctions as AlignFunc
import Lab_Equipment.SpotArrayAnalysis.SpotArrayAnalysis as SpotAnlys_lib
from typing import List


def CourseSweepAcrossSLMPowerMeter(slm:pyLCOS.LCOS,channel,CamObjs: CamForm.GeneralCameraObject,flipCount=25):


def FindFactors(num):
    # find factor of number
    factors=np.array([num])
    for i in range(num-1,0,-1):
        if(num % i) == 0:
            #print(i)
            factors=np.append(factors,[i])
    #print(factors)
    return factors

def set_superpixel(arr, ix, iy, superpixel_size, phase_value):
    """
    Set all values in a given superpixel block to a new value.

    Parameters
    ----------
    arr : 2D np.ndarray
        The array to modify.
    ix, iy : int
        Superpixel indices (not pixel indices).
    superpixel_size : int
        Size of each superpixel block (square).
    value : scalar or complex
        New value to assign to that superpixel.

    Returns
    -------
    arr : 2D np.ndarray
        The modified array (same object, modified in-place).
    """
    # print(superpixel_size)
    x_start = ix * superpixel_size
    x_end   = x_start + superpixel_size
    y_start = iy * superpixel_size
    y_end   = y_start + superpixel_size
 
    arr[y_start:y_end, x_start:x_end] = arr[y_start:y_end, x_start:x_end]*np.exp(phase_value*1j)

    return arr
 




def ChangePiFlipTakePower(self,xVal):  
        
        # Nx=self.slm.masksize[0]
        # Ny=self.slm.masksize[1]
        MaskSize=self.slmObjs[self.ObjIdx].polProps[self.channel][self.pol].masksize
        y_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[0])
        x_center_Input=int(self.slmObjs[self.ObjIdx].AllMaskProperties[self.channel][self.pol][self.imask].center[1])
        
        Nx=MaskSize[0]
        Ny=MaskSize[1]
    
        # need to put a blank mask with zernikes that are currelty on the masks. this is a little bit tedious but it works. I might but this as function in SLM module 
        # as maybe this is all people want to do
        MASK=np.ones((Nx,Ny),dtype=complex)
        MASK=set_superpixel(MASK, ix_shift,iy_shift , superpixel_size=superpixel_size, value=np.pi/2)

        #apply superPixel

        if (self.ApplyZernike):
            MASK_PlussZernike=self.slmObjs[self.ObjIdx].ApplyZernikesToSingleMask(self.channel,(MASK),imask=self.imask,pol=self.pol,imode=0)
        
        MASK_PlussZernike=(MASK)
        MASKTODisplay_cmplx=self.slmObjs[self.ObjIdx].Draw_Single_Mask( x_center_Input,y_center_Input, MASK_PlussZernike)
        
        self.slmObjs[self.ObjIdx].FullScreenBuffer_int=self.slmObjs[self.ObjIdx].convert_phase_to_uint8(MASKTODisplay_cmplx) # Note if nothing is passed it will use the self.FullScreenBuffer_cmplx array as the array it is going to convert      
        self.slmObjs[self.ObjIdx].Write_To_Display(self.slmObjs[self.ObjIdx].FullScreenBuffer_int,self.channel)

        # get the power from the power metter
        
        RefSigPWR = self.CamObjs[self.ObjIdx].GetRelativePower()
        RefSigPWR_log = 10 * np.log10(RefSigPWR / self.RefPWR)
        
        return xVal,RefSigPWR_log






def RunSuperPixelSweep(slm:pyLCOS.LCOS,CamObjs: CamForm.GeneralCameraObject,
                       superpixel_size=16,ispot=0,RadiusApp=6):

    Nx=256
    Ny=256
    PixelBoxSizes=FindFactors(Ny)
    NumOfItterations = np.size(PixelBoxSizes)
    print(PixelBoxSizes[1:NumOfItterations])
    Firstloop=1
    phase_masks=np.ones([Ny,Nx],dtype=np.csingle)

    superpixel_size=PixelBoxSizes[1]
    xShiftCount=int(np.round(Nx/superpixel_size))
    yShiftCount=int(np.round(Ny/superpixel_size))
    ifig=1
    for (ix_shift) in range(xShiftCount):
        for (iy_shift) in range(yShiftCount):


            phaseAdjusted=set_superpixel(np.angle(phase_masks[:,:]), ix_shift,iy_shift , superpixel_size=superpixel_size, value=np.pi/2)
        