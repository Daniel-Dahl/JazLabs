from scipy.fft import fftshift,ifftshift, fft2,ifft2#,rfft2,irfft2,fft, fftfreq
import numpy as np
import matplotlib.pyplot as plt
def GS_ComplexShaping(Field_target,Field_Source,Aperture_ForMode,Aperture_ForFreeField,pixelSize,PwrForReconMode,ItterCount):
    
    # Need to make a apertured power scaled version of the target field so that when you add the far field free field it adds properly
    FieldTarget_App=Field_target*Aperture_ForMode
    FieldTarget_App=FieldTarget_App/ (np.sqrt(((np.sum(np.abs(FieldTarget_App)**2))*pixelSize**2)/(PwrForReconMode)))
    
    Ny,Nx=Field_target.shape
    ### Initalise the the field for the ifft
    FieldBackPropagated=fftshift(ifft2(ifftshift(Field_target)))
    
    
    for itime in range(ItterCount):
        
        PhaseMask=np.angle(FieldBackPropagated)
        SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)# It is a plus not a minus for the phase term if it is a minus the azimuthal modes get flipped
        
        # Fourier transform to take the field into the far field to allow for interference via diffraction
        FarField=np.fft.ifftshift(fft2(np.fft.fftshift(SourceWithPhaseMask)))/np.sqrt(Nx*Ny)#Scaling due to fft2
        FarField_app=FarField*Aperture_ForFreeField
        
        # Normalise so that the field outside the Aperture region is 1-PwrInApp. The PwrInApp is defined before entering the function
        # it can be though of as the amount of power that is allowed to be used for the mode construction
        FarField_app=FarField_app/ (np.sqrt(np.sum((np.abs(FarField_app)**2))*pixelSize**2/(1-PwrForReconMode)))
       
        # Put the target field in the aperture to get the algorithm to try to reconstruct it.
        FieldForBackPropagation=FieldTarget_App+FarField_app
        # ifft the new target field back so that it its phase in the souce plane can be calculated and applied to the source 
        FieldBackPropagated =fftshift(ifft2(ifftshift(FieldForBackPropagation)))*np.sqrt(Nx*Ny)#Scaling due to ifft2
    
    
    # The itterations are finished so the lets see how it went
    # All that is happening here is that it is taking the last mask calculation from the above loop and applying it to the source field and
    # then fourier transforming it to the far field. 
    PhaseMask=np.angle(FieldBackPropagated)
    SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)
    FarField=ifftshift(fft2(fftshift(SourceWithPhaseMask)))/(np.sqrt(Nx*Ny))#Scaling due to fft2
    FarField_app=FarField*Aperture_ForMode
    
    #Need to normalise the FarField_app to 1 so that when the overlap is calculated against the Field_target it will make sense
    FarField_app_norm=FarField_app/(np.sqrt(np.sum(np.abs(FarField_app)**2)*pixelSize**2))
    
    TotalPwrInFarField=np.sum(np.abs((FarField))**2*pixelSize**2)
    PwrInReconMode=np.sum(np.abs((FarField_app))**2*pixelSize**2)
    PwrLose=PwrInReconMode/TotalPwrInFarField
    OverlapTargetReconstFields=(np.sum(Field_target*np.conj(FarField_app_norm)))*pixelSize**2
    
    print("Total Power: ",TotalPwrInFarField," Power in mode: ",PwrInReconMode , " Power lose: ",PwrLose)
    print("Overlap of Target and Reconstructed Mode: ",OverlapTargetReconstFields )
    
    return PhaseMask,FarField_app,FarField,TotalPwrInFarField,PwrInReconMode





# def GS_AmplitudeShaping():
#     # from scipy.fft import fft, fftfreq, fftshift, fft2,ifft2,rfft2,irfft2


#     Amp_source=np.abs((Field_Source))**2
#     Amp_Target=np.abs((Field_target))**2
#     # Field_A=np.fft.fftshift(ifft2(np.fft.ifftshift(Field_target)))
#     Field_A=(ifft2((Field_target)))

#     for i in range(1000):
#         PhaseA=np.angle(Field_A)
#         B=Field_Source*np.exp(-1j*PhaseA)
#         # C=np.fft.ifftshift(fft2(np.fft.fftshift(B)))
#         C=(fft2((B)))
        
#         PhaseC=np.angle(C)
#         D=Field_target*np.exp(1j*PhaseC)
#         # Field_A=np.fft.fftshift(ifft2(np.fft.ifftshift(D)))
#         Field_A=(ifft2((D)))
        
#         # PhaseA=np.angle(Field_A)
#         # B=Amp_source*np.exp(-1j*PhaseA)
#         # C=np.fft.ifftshift(fft2(np.fft.fftshift(B)))
#         # PhaseC=np.angle(C)
#         # D=Amp_Target*np.exp(-1j*PhaseC)
#         # Field_A=np.fft.fftshift(ifft2(np.fft.ifftshift(D)))
    

#     plt.figure()
#     plt.imshow(cmplxplt.ComplexArrayToRgb(Field_A))
#     PhaseA=np.angle(Field_A)
#     # Final=Amp_source*np.exp(-1j*PhaseA)
#     Final=Field_Source*np.exp(-1j*PhaseA)
#     Final_target=(fft2((Final)))
#     # Final_target=np.fft.ifftshift(fft2(np.fft.fftshift(Final)))

#     plt.imshow(np.abs(Final_target)**2)

#     # plt.imshow(cmplxplt.ComplexArrayToRgb(Final_target))

#     # H0 = np.fft.fftshift(np.exp(tfCoef1*dz));
        
        
#     # FourierField=(fft2(Field))
#     # # FourierField=fft.fftshift(fft.fft2(fft.fftshift(Field)))
#     # #Apply the transfer function of free-space
#     # FourierField = FourierField*TransferMatrix;
#     # #Convert k-space field back to real-space
#     # # Field = fft.fftshift(ifft.fft2(FourierField))
#     # Fieldnew = (ifft2(FourierField))