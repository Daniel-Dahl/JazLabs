import time
import numpy as np
import pwi_inst.utils.camera_tools as camtools

### Example script for taking and using darkframes for software-triggered acquisition of images from a camera ###

take_dark_frames = True # If False, load the darkframe specified below
darkframe_save_path = '../temp/' # None to not save a frame
num_dark_frames = 100 # Number of frames to average

darkframe_load_file = '../temp/darkframe_20260413_184147.npy'

# Select model of First Light camera to load appropriate library
# camera_model = 'FirstLightCblue2'
# camera_model = 'FirstLightCred3_2Lite'
camera_model = 'FLIR_pointgrey'

# Todo - specify camera by serial number
# Index of camera
camera_idx = 0

# Set key camera settings
exp_time_us = 100 # microseconds

# Print diagnostic info from camera object?
verbose = True

# Specify required frames
num_triggers = 4
trigger_interval_s = 1

# Show plot of acquired image?
plot_image = True
auto_stretch_image = False


if __name__ == '__main__':
    # Import camera library based on model
    if camera_model == 'FirstLightCred3_2Lite':
        import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCred3_2Lite as CamLib
    elif camera_model == 'FirstLightCblue2':
        import pwi_inst.hardware.Cameras.FirstlightCameras.FirstLightCblue2 as CamLib
    elif camera_model == "FLIR_pointgrey":
        import pwi_inst.hardware.Cameras.FLIRPointGreyCameras.FLIR_PointGrey as CamLib
    else:
        raise ValueError('Unknown camera model specified')

    Camobject = CamLib.CameraObject(CameraIdx=camera_idx, verbose=verbose)

    # Set camera settings
    Camobject.SetSoftwareTriggerMode()
    Camobject.SetExposureTime(exp_time_us)

    if take_dark_frames:
        # Now take a darkframe
        print("Ready to take darkframes - *** Make sure camera is dark!! ***")
        input("Press Enter to continue...")
        dark = camtools.take_darkframe(Camobject, num_frames=num_dark_frames, save_path=darkframe_save_path, wait_time=None)
        print("Darkframes done.")
    else:
        print('Loading darkframe from ' + darkframe_load_file)
        dark = np.load(darkframe_load_file)

    input("Press Enter to take new frames...")
    # Acquire software-triggered frames
    acquired_frames = []
    for framenum in range(num_triggers):
        frame = Camobject.GetFrame() - dark
        acquired_frames.append(frame.copy())

        if plot_image:
            import matplotlib.pyplot as plt
            plt.ion()
            if auto_stretch_image:
                p1, p99 = np.percentile(frame, [1, 99])
                frame = np.clip(frame, p1, p99)
            plt.clf()
            plt.imshow(frame, cmap='gray')
            plt.colorbar()
            plt.title('Frame {}'.format(framenum))
            plt.pause(0.001)

        time.sleep(trigger_interval_s)
