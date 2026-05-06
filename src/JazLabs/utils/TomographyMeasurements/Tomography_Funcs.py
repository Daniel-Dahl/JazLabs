from Lab_Equipment.Config import config
import numpy as np
import os
from datetime import datetime
import Lab_Equipment.SLM.pyLCOS as pyLCOS

import TomographyLib as tomo

def get_tomography_data_monte_carlo(slm_properties_name, time_tagger, bin_width, delay_time, time_per_measurement, counting_time_per_sample, dims, amp_mod=False, l_step=1):
    if not time_tagger.isThreadRunning():
        raise Exception("time tagger thread needs to be running to collect tomography data")

    N_samples_per_measurement = int(time_per_measurement/counting_time_per_sample)
    
    time_tagger.setBinWidth(bin_width)
    time_tagger.setDelayTime(delay_time)
    time_tagger.setTriggerLevel(5,0.226)
    time_tagger.setTriggerLevel(6,0.226)
    time_tagger.setSingleCaptureMode()
    time_tagger.setCountingTime(counting_time_per_sample*1e12)

    for d in dims:
        if l_step == 1:
            phase_masks = np.load(
                "Masks\\tomography_masks\\tomography_masks_d{}_amp_{}.npy".format(d, amp_mod)
            )
        else:
             phase_masks = np.load(
                "Masks\\tomography_masks\\tomography_masks_d{}_amp_{}_lstep_{}.npy".format(d, amp_mod, l_step)
            )
        mode_count,mask_count,Ny,Nx = phase_masks.shape

        mask_size = (Ny, Nx)

        slm = pyLCOS.LCOS(screen=2, ActiveRGBChannels=['Red','Green'], 
                        mask_size=mask_size, MaskCount=mask_count, 
                        modeCount=mode_count)

        # SLM_WIDTH, SLM_HEIGHT = slm.LCOSsize[1], slm.LCOSsize[0]
        # SLM_PIXEL_SIZE = slm.pixel_size

        slm.GLobProps["Red"].RefreshTime=90*1e-3
        slm.GLobProps["Green"].RefreshTime=90*1e-3          
        
        counts_data = np.zeros((4, mode_count**2, N_samples_per_measurement))
        
        slm.setMaskArray("Red", phase_masks)
        # Green phase masks need to be flipped because of mirror
        phase_masks_green = np.flip(phase_masks, axis=3)
        slm.setMaskArray("Green", phase_masks_green)
        slm.LoadMaskProperties(slm_properties_name)
        
        for red_index in range(mode_count):
            slm.setmask("Red", red_index)
            
            for green_index in range(mode_count):
                slm.setmask("Green", green_index)
                measurement_index = red_index*mode_count + green_index
                
                for sample_index in range(N_samples_per_measurement):
                    counts_data[:,measurement_index,sample_index] = time_tagger.getCoincidences()
        
        date_and_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = "Data\\Tomography\\Results\\Standard\\d{}_amp_{}_{}".format(d, amp_mod, date_and_time_str)
        os.mkdir(folder)
    
        np.save(folder + "\\counts_data.npy", counts_data)
        
        with open(folder + '\\readme.md', 'w') as readme:
            readme.write("l_step:" + str(l_step) + "\n")
            readme.write("counting_time_per_sample (s): " + str(counting_time_per_sample) + "\n")
            readme.write("total_time_per_measurement (s): " + str(time_per_measurement) + "\n")
            readme.write("bin_width (ps): " + str(bin_width) + "\n")
            readme.write("delay_time (ps): " + str(delay_time) + "\n")

        del slm


def get_coincidences_for_two_photon_mask(slm, time_tagger, phase_masks):
    slm.setMaskArray("Red", phase_masks[0,:,:,:,:])
    slm.setMaskArray("Green", phase_masks[1,:,:,:,:])

    slm.setmask("Red", imode=0)
    slm.setmask("Green", imode=0)

    counts = time_tagger.getCoincidences()

    return counts[2]


def SGT(slm_properties_name, time_tagger, bin_width, delay_time, counting_time, N_iterations, computational_basis, a,A,b):
    _,_,dim = computational_basis.shape
    
    mode_count = 1
    mask_count = 1
    mask_size = (512, 512)

    slm = pyLCOS.LCOS(screen=2, ActiveRGBChannels=['Red','Green'], 
                    mask_size=mask_size, MaskCount=mask_count, 
                    modeCount=mode_count)

    slm.GLobProps["Red"].RefreshTime=90*1e-3
    slm.GLobProps["Green"].RefreshTime=90*1e-3

    slm.LCOS_Clean("Red")
    slm.LCOS_Clean("Green")
    slm.LoadMaskProperties(slm_properties_name)

    time_tagger.setSingleCaptureMode()
    time_tagger.setBinWidth(bin_width)
    time_tagger.setDelayTime(delay_time)
    time_tagger.setCountingTime(counting_time)

    two_photon_computational_basis = tomo.get_two_photon_computational_basis(computational_basis)

    rand_num_gen = np.random.default_rng()

    guess_state = (1/dim)*np.matrix(rand_num_gen.choice([-1,1], size=dim**2)).transpose()

    expected_rho = tomo.get_expected_rho(dim)

    infidelities = np.zeros(N_iterations)

    for k in range(N_iterations):
        print("Iteration:", k)
        random_real_vector = np.matrix(rand_num_gen.choice([-1,0,1], size=dim**2)).transpose()
        random_imag_vector = np.matrix(rand_num_gen.choice([-1j,0,1j], size=dim**2)).transpose()
        random_direction = random_real_vector + random_imag_vector

        s = 0.602
        t = 0.101

        alpha = a/(k + 1 + A)**s
        beta = b/(k + 1)**t

        state_to_test_plus = tomo.normalise_state(guess_state + beta*random_direction)
        state_to_test_minus = tomo.normalise_state(guess_state - beta*random_direction)

        phase_masks_plus_state = tomo.get_two_photon_mask(state_to_test_plus, two_photon_computational_basis)
        phase_masks_minus_state = tomo.get_two_photon_mask(state_to_test_minus, two_photon_computational_basis)

        coincidences_plus_state = get_coincidences_for_two_photon_mask(slm, time_tagger, phase_masks_plus_state)
        coincidences_minus_state = get_coincidences_for_two_photon_mask(slm, time_tagger, phase_masks_minus_state)

        grad = (random_direction/2*beta)*(coincidences_plus_state - coincidences_minus_state)/(coincidences_plus_state + coincidences_minus_state)

        guess_state = tomo.normalise_state(guess_state + alpha*grad)
        guess_rho = guess_state @ guess_state.getH()

        infidelities[k] = 1 - tomo.fidelity(expected_rho, guess_rho)

    return guess_rho, infidelities



