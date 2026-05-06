"""Example script: calibrate tip-tilt attenuation by scanning DAC voltages."""

from pathlib import Path
import numpy as np

from pwi_inst.hardware.DAQ_Controller.mcc_daq import mcc_daq_Volt_Ctrl
from pwi_inst.procedures.TipTiltMirror.calibration_scan_TTmirror import TTAttenCalibrator

datadir = '../temp/'
darkframe_filename = 'darkframe_20260415_180343.npy'
camera_model = 'FirstLightCred3_2Lite'
camera_idx = 2
verbose = True
exp_time_us = 100 # microseconds
roi_geometry = [288,176,128,128]

n_daq_channels = 3
refresh_rate = 0.001
board_number = 0

if camera_model == 'FirstLightCred3_2Lite':
    import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCred3_2Lite as CamLib
elif camera_model == 'FirstLightCblue2':
    import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCblue2 as CamLib
else:
    raise ValueError('Unknown camera model specified')

camera_object = CamLib.CameraObject(CameraIdx=camera_idx, verbose=verbose)
camera_object.SetSoftwareTriggerMode()
camera_object.SetROI(*roi_geometry, snap_values=False, enable=True)
camera_object.SetExposureTime(exp_time_us)  # microseconds

darkframe_path = Path(datadir) / darkframe_filename
darkframe = np.load(darkframe_path)
print(f"Loaded dark frame from: {darkframe_path}")

dac_controller = mcc_daq_Volt_Ctrl(RefreshTime=refresh_rate,
                                   boardNumber=board_number,
                                   ChannelCount=n_daq_channels)

calibrator = TTAttenCalibrator(
    camera_object=camera_object,   # camera instance with GetFrame() method
    dac_controller=dac_controller, # DAC instance with SetVoltage(channel, voltage) method
    darkframe=darkframe,           # pre-loaded dark frame subtracted from each acquired frame
    datadir=datadir,               # directory for saving output files (only used if save_output=True)

    save_output=True,
    scan_waittime=0.2
    ### Optional arguments and their defaults are below:
    # init_volts=[-0.5, 6, 2],    # starting voltages per DAC channel; scan centred here, restored after
    # scan_mode='2d',              # '1d' scans a single channel; '2d' scans a grid over channels 0 and 1
    # scan_channel=1,              # channel to scan in '1d' mode (0=x, 1=y); ignored in '2d' mode
    # scan_width=5.5,              # total voltage range to scan in volts (peak-to-peak)
    # num_scanposns=10,            # positions per axis; '2d' mode produces num_scanposns x num_scanposns grid
    # scan_waittime=0.1,           # seconds to wait after each voltage set, to allow mirror to settle
    # psf_method='gaussian',       # PSF centroid method: 'gaussian' for 2D Gaussian fit, 'com' for centre-of-mass
    # enable_plotting=True,        # display a live frame plot at each scan position
    # enable_gaussfit_plot=False,  # show Gaussian fit diagnostic plot at each position (gaussian mode only)
    # fs=2,                        # figure size down-scaler (figure dimensions divided by this value)
    # plot_pausetime=0.1,          # seconds passed to plt.pause() between positions
    # save_output=False,           # save PSF positions, powers, and DAC voltages as .npy files in datadir
    # encircled_power_radius=10.0, # radius in pixels of circular aperture for encircled power measurement
    # normalise_powers=True,       # normalise all measured powers to their maximum before returning/saving
)

results = calibrator.run()
print("Scan complete!")

dac_controller.shutdown(zero=False)
