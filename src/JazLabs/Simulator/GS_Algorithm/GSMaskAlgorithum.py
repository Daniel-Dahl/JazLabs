from scipy.fft import fftshift,ifftshift, fft2,ifft2#,rfft2,irfft2,fft, fftfreq
import numpy as np
import matplotlib.pyplot as plt
import JazLabs.utils.camera_utils as camutils
import JazLabs.utils.ArrayManipulators as arrmani
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

def GS_ComplexShaping_newWrong(Field_target,Field_Source,Aperture_ForMode,Aperture_ForFreeField,pixelSize,PwrForReconMode,ItterCount,
    show_progress=True,
    ROINx=None,
    ROINy=None,
    show_overlap_plot=False,
    overlap_update_every=1):
    
    # Need to make a apertured power scaled version of the target field so that when you add the far field free field it adds properly
    FieldTarget_App=Field_target*Aperture_ForMode
    # FieldTarget_App=FieldTarget_App/ (np.sqrt(((np.sum(np.abs(FieldTarget_App)**2))*pixelSize**2)/(PwrForReconMode)))
    FieldTarget_App=FieldTarget_App/ (np.sqrt(((np.sum(np.abs(FieldTarget_App)**2)))/(PwrForReconMode)))
    
    
    Ny,Nx=Field_target.shape
    ### Initalise the the field for the ifft
    FieldBackPropagated=fftshift(ifft2(ifftshift(Field_target)))
    roi_center = (Ny//2,Nx//2)
    Field_target_appForOverlap,_ = arrmani.apply_square_aperture(Field_target,roi_center,ROINx,ROINy)
    target_overlap_power = np.sum(np.abs(Field_target_appForOverlap)**2)
    overlap_power_history = []
    
    
    iteration_range = range(ItterCount)
    using_tqdm_progress = False
    if show_progress:
        try:
            from tqdm.auto import tqdm

            iteration_range = tqdm(
                iteration_range,
                total=ItterCount,
                desc="GS iterations",
            )
            using_tqdm_progress = True
        except ImportError:
            print("GS iterations: 0 /", ItterCount)

    for itime in iteration_range:
        
        PhaseMask=np.angle(FieldBackPropagated)
        SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)# It is a plus not a minus for the phase term if it is a minus the azimuthal modes get flipped
        
        # Fourier transform to take the field into the far field to allow for interference via diffraction
        FarField=np.fft.ifftshift(fft2(np.fft.fftshift(SourceWithPhaseMask)))/np.sqrt(Nx*Ny)#Scaling due to fft2
        FarField_app=FarField*Aperture_ForFreeField
        FarField_reconstructed_mode=FarField*Aperture_ForMode
        
        # Normalise so that the field outside the Aperture region is 1-PwrInApp. The PwrInApp is defined before entering the function
        # it can be though of as the amount of power that is allowed to be used for the mode construction
        # FarField_app=FarField_app/ (np.sqrt(np.sum((np.abs(FarField_app)**2))*pixelSize**2/(1-PwrForReconMode)))
        FarField_app=FarField_app/ (np.sqrt(np.sum((np.abs(FarField_app)**2))/(1-PwrForReconMode)))
        
       
        # Put the target field in the aperture to get the algorithm to try to reconstruct it.
        FieldForBackPropagation=FieldTarget_App+FarField_app
        # ifft the new target field back so that it its phase in the souce plane can be calculated and applied to the source 
        FieldBackPropagated =fftshift(ifft2(ifftshift(FieldForBackPropagation)))*np.sqrt(Nx*Ny)#Scaling due to ifft2

        should_update_overlap = (
            itime + 1 == ItterCount
            or (itime + 1) % max(1, overlap_update_every) == 0
        )
        if should_update_overlap:
            FarField_appForOverlap,_ = arrmani.apply_square_aperture(FarField_reconstructed_mode,roi_center,ROINx,ROINy)
            farfield_overlap_power = np.sum(np.abs(FarField_appForOverlap)**2)
            if farfield_overlap_power > 0 and target_overlap_power > 0:
                overlap = np.sum(np.conj(Field_target_appForOverlap)*FarField_appForOverlap)
                overlap = overlap/np.sqrt(farfield_overlap_power*target_overlap_power)
                overlap_power = np.abs(overlap)**2
            else:
                overlap = 0.0 + 0.0j
                overlap_power = 0.0
            overlap_power_history.append(overlap_power)

            if show_progress and using_tqdm_progress:
                iteration_range.set_postfix(overlap_power=f"{overlap_power:.5f}")

        if show_progress and not using_tqdm_progress and (itime + 1 == ItterCount or (itime + 1) % max(1, ItterCount // 20) == 0):
            if len(overlap_power_history) > 0:
                print("GS iterations:", itime + 1, "/", ItterCount, " | overlap power:", overlap_power_history[-1])
            else:
                print("GS iterations:", itime + 1, "/", ItterCount)
    
    
    # The itterations are finished so the lets see how it went
    # All that is happening here is that it is taking the last mask calculation from the above loop and applying it to the source field and
    # then fourier transforming it to the far field. 
    PhaseMask=np.angle(FieldBackPropagated)
    SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)
    FarField=ifftshift(fft2(fftshift(SourceWithPhaseMask)))/(np.sqrt(Nx*Ny))#Scaling due to fft2
    FarField_app=FarField*Aperture_ForMode
    
    #Need to normalise the FarField_app to 1 so that when the overlap is calculated against the Field_target it will make sense
    # FarField_app_norm=FarField_app/(np.sqrt(np.sum(np.abs(FarField_app)**2)*pixelSize**2))
    FarField_app_norm=FarField_app/(np.sqrt(np.sum(np.abs(FarField_app)**2)))
    
    # TotalPwrInFarField=np.sum(np.abs((FarField))**2*pixelSize**2)
    # PwrInReconMode=np.sum(np.abs((FarField_app))**2*pixelSize**2)
    TotalPwrInFarField=np.sum(np.abs((FarField))**2)
    PwrInReconMode=np.sum(np.abs((FarField_app))**2)
    PwrLose=PwrInReconMode/TotalPwrInFarField
    # OverlapTargetReconstFields=(np.sum(Field_target*np.conj(FarField_app_norm)))*pixelSize**2
    # OverlapTargetReconstFields=(np.sum(Field_target*np.conj(FarField_app_norm)))
    OverlapTargetReconstFields=np.sum(np.conj(Field_target)*FarField_app_norm)/np.sqrt(np.sum(np.abs(Field_target)**2)*np.sum(np.abs(FarField_app_norm)**2))
    
    
    
    print("Total Power: ",TotalPwrInFarField," Power in mode: ",PwrInReconMode , " Power lose: ",PwrLose)
    print("Overlap of Target and Reconstructed Mode: ",OverlapTargetReconstFields )

    if show_overlap_plot and len(overlap_power_history) > 0:
        overlap_iterations = np.arange(1, len(overlap_power_history) + 1)*max(1, overlap_update_every)
        overlap_iterations[-1] = ItterCount
        plt.figure()
        plt.plot(overlap_iterations, overlap_power_history)
        plt.xlabel("GS iteration")
        plt.ylabel("ROI overlap power")
        plt.title("GS overlap progress")
        plt.grid(True)
    
    return PhaseMask,FarField_app,FarField,TotalPwrInFarField,PwrInReconMode


def ApplyMaskAndPropgateField(Mask,Field_Source):
    
    Ny,Nx=Field_Source.shape
    roi_center = (Ny//2,Nx//2)
    
    PhaseMask=np.angle(Mask)
    SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)# It is a plus not a minus for the phase term if it is a minus the azimuthal modes get flipped
        
    # Fourier transform to take the field into the far field to allow for interference via diffraction
    FarField=np.fft.ifftshift(fft2(np.fft.fftshift(SourceWithPhaseMask)))/np.sqrt(Nx*Ny)#Scaling due to fft2
    # FarField_app=FarField*Aperture_ForFreeField
    # FarField_reconstructed_mode=FarField*Aperture_ForMode
        
    # Normalise so that the field outside the Aperture region is 1-PwrInApp. The PwrInApp is defined before entering the function
    # it can be though of as the amount of power that is allowed to be used for the mode construction
    # FarField_app=FarField_app/ (np.sqrt(np.sum((np.abs(FarField_app)**2))*pixelSize**2/(1-PwrForReconMode)))
    # FarField_app=FarField_app/ (np.sqrt(np.sum((np.abs(FarField_app)**2))/(1-PwrForReconMode)))
    FarField=FarField/ (np.sqrt(np.sum((np.abs(FarField)**2))))
    
    # FarField_appForOverlap,_ = arrmani.apply_square_aperture(FarField_reconstructed_mode,roi_center,ROINx,ROINy)
    # farfield_overlap_power = np.sum(np.abs(FarField_appForOverlap)**2)
    # overlap = np.sum(np.conj(Field_target_appForOverlap)*FarField_appForOverlap)
    # overlap = overlap/np.sqrt(farfield_overlap_power*target_overlap_power)
    # overlap_power = np.abs(overlap)**2
    return FarField
       
    

import JazLabs.utils.DeformableMirror_PhaseToMirrorSuface as DMPhaseConvert
def GS_ComplexShapingForDM(Field_target,Field_Source,Aperture_ForMode,Aperture_ForFreeField,pixelSize,PwrForReconMode,ItterCount,
    ROINx,ROINy,
    ApplyDM=True,
    wavelength=1.55e-6,
    pupil_mask=None,
    n_act_across=12,
    influence_sigma_actuator_pitch=0.7,
    unwrap=False,
    max_surface_stroke=1.75e-6,
    show_progress=True,
    show_overlap_plot=False,
    overlap_update_every=1):
    
    # Need to make a apertured power scaled version of the target field so that when you add the far field free field it adds properly
    FieldTarget_App=Field_target*Aperture_ForMode
    FieldTarget_App=FieldTarget_App/ (np.sqrt(((np.sum(np.abs(FieldTarget_App)**2)))/(PwrForReconMode)))
    
    Ny,Nx=Field_target.shape
    ### Initalise the the field for the ifft
    roi_center = (Ny//2,Nx//2)
    Field_target_appForOverlap,_ = arrmani.apply_square_aperture(Field_target,roi_center,ROINx,ROINy)
    target_overlap_power = np.sum(np.abs(Field_target_appForOverlap)**2)
    overlap_abs_history = []
    FieldBackPropagated=fftshift(ifft2(ifftshift(Field_target)))
    
    
    iteration_range = range(ItterCount)
    using_tqdm_progress = False
    if show_progress:
        try:
            from tqdm.auto import tqdm

            iteration_range = tqdm(
                iteration_range,
                total=ItterCount,
                desc="GS DM iterations",
            )
            using_tqdm_progress = True
        except ImportError:
            print("GS DM iterations: 0 /", ItterCount)
    
    for itime in iteration_range:
        
        PhaseMask=np.angle(FieldBackPropagated)
        if ApplyDM:
            PhaseMask_rio,_=arrmani.apply_square_aperture(PhaseMask,roi_center,ROINx,ROINy)
            PhaseMask_rio, _ , _ =DMPhaseConvert.slm_phase_to_dm_phase(PhaseMask_rio,
                                                wavelength=wavelength,
                                                pupil_mask=pupil_mask,
                                                n_act_across=n_act_across,
                                                influence_sigma_actuator_pitch=influence_sigma_actuator_pitch,
                                                unwrap=unwrap,
                                                max_surface_stroke=max_surface_stroke)
            PhaseMask=arrmani.pad_array(np.copy(PhaseMask_rio), new_shape=(Ny,Nx), value=0)
        SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)# It is a plus not a minus for the phase term if it is a minus the azimuthal modes get flipped
        
        # Fourier transform to take the field into the far field to allow for interference via diffraction
        FarField=np.fft.ifftshift(fft2(np.fft.fftshift(SourceWithPhaseMask)))/np.sqrt(Nx*Ny)#Scaling due to fft2
        FarField_app=FarField*Aperture_ForFreeField
        FarField_reconstructed_mode=FarField*Aperture_ForMode
        
        # Normalise so that the field outside the Aperture region is 1-PwrInApp. The PwrInApp is defined before entering the function
        # it can be though of as the amount of power that is allowed to be used for the mode construction
        FarField_app=FarField_app/ (np.sqrt(np.sum((np.abs(FarField_app)**2))/(1-PwrForReconMode)))
       
        # Put the target field in the aperture to get the algorithm to try to reconstruct it.
        FieldForBackPropagation=FieldTarget_App+FarField_app
        # ifft the new target field back so that it its phase in the souce plane can be calculated and applied to the source 
        FieldBackPropagated =fftshift(ifft2(ifftshift(FieldForBackPropagation)))*np.sqrt(Nx*Ny)#Scaling due to ifft2

        should_update_overlap = (
            itime + 1 == ItterCount
            or (itime + 1) % max(1, overlap_update_every) == 0
        )
        if should_update_overlap:
            FarField_appForOverlap,_ = arrmani.apply_square_aperture(FarField_reconstructed_mode,roi_center,ROINx,ROINy)
            farfield_overlap_power = np.sum(np.abs(FarField_appForOverlap)**2)
            if farfield_overlap_power > 0 and target_overlap_power > 0:
                overlap = np.sum(np.conj(Field_target_appForOverlap)*FarField_appForOverlap)
                overlap = overlap/np.sqrt(farfield_overlap_power*target_overlap_power)
                overlap_abs = np.abs(overlap)**2
            else:
                overlap = 0.0 + 0.0j
                overlap_abs = 0.0
            overlap_abs_history.append(overlap_abs)

            if show_progress and using_tqdm_progress:
                iteration_range.set_postfix(overlap_abs=f"{overlap_abs:.5f}")

        if show_progress and not using_tqdm_progress and (itime + 1 == ItterCount or (itime + 1) % max(1, ItterCount // 20) == 0):
            if len(overlap_abs_history) > 0:
                print("GS DM iterations:", itime + 1, "/", ItterCount, " | overlap abs2:", overlap_abs_history[-1])
            else:
                print("GS DM iterations:", itime + 1, "/", ItterCount)
    
    
    # The itterations are finished so the lets see how it went
    # All that is happening here is that it is taking the last mask calculation from the above loop and applying it to the source field and
    # then fourier transforming it to the far field. 
    PhaseMask=np.angle(FieldBackPropagated)
    if ApplyDM:
        PhaseMask_rio,_=arrmani.apply_square_aperture(PhaseMask,roi_center,ROINx,ROINy)
        PhaseMask_rio, _ , _ =DMPhaseConvert.slm_phase_to_dm_phase(PhaseMask_rio,
                                                wavelength=wavelength,
                                            pupil_mask=pupil_mask,
                                            n_act_across=n_act_across,
                                            influence_sigma_actuator_pitch=influence_sigma_actuator_pitch,
                                            unwrap=unwrap,
                                            max_surface_stroke=max_surface_stroke)
        PhaseMask=arrmani.pad_array(np.copy(PhaseMask_rio), new_shape=(Ny,Nx), value=0)
    SourceWithPhaseMask=Field_Source*np.exp(1j*PhaseMask)
    FarField=ifftshift(fft2(fftshift(SourceWithPhaseMask)))/(np.sqrt(Nx*Ny))#Scaling due to fft2
    FarField_app=FarField*Aperture_ForMode
    
    #Need to normalise the FarField_app to 1 so that when the overlap is calculated against the Field_target it will make sense
    FarField_app_norm=FarField_app/(np.sqrt(np.sum(np.abs(FarField_app)**2)))
    
    TotalPwrInFarField=np.sum(np.abs((FarField))**2)
    PwrInReconMode=np.sum(np.abs((FarField_app))**2)
    PwrLose=PwrInReconMode/TotalPwrInFarField
    OverlapTargetReconstFields=np.sum(np.conj(Field_target)*FarField_app_norm)/np.sqrt(np.sum(np.abs(Field_target)**2)*np.sum(np.abs(FarField_app_norm)**2))
    
    # OverlapTargetReconstFields=(np.sum(Field_target*np.conj(FarField_app_norm)))
    
    print("Total Power: ",TotalPwrInFarField," Power in mode: ",PwrInReconMode , " Power lose: ",PwrLose)
    print("Overlap of Target and Reconstructed Mode: ",OverlapTargetReconstFields )
    print("abs(overlap)^2 = ",np.abs(OverlapTargetReconstFields)**2)

    if show_overlap_plot and len(overlap_abs_history) > 0:
        overlap_iterations = np.arange(1, len(overlap_abs_history) + 1)*max(1, overlap_update_every)
        overlap_iterations[-1] = ItterCount
        plt.figure()
        plt.plot(overlap_iterations, overlap_abs_history)
        plt.xlabel("GS iteration")
        plt.ylabel("ROI overlap magnitude")
        plt.title("GS DM overlap progress")
        plt.grid(True)
    
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
