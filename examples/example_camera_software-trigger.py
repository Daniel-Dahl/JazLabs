import time
import numpy as np

### Example script for software-triggered acquisition of images from a First Light camera ###


# Select model of First Light camera to load appropriate library
# camera_model = 'FirstLightCblue2'
# camera_model = 'FirstLightCred3_2Lite'
camera_model = 'FLIR_pointgrey'

# Todo - specify camera by serial number
# Index of camera
camera_idx = 0

# Print diagnostic info from camera object?
verbose = True

# Specify required frames
num_triggers = 4
trigger_interval_s = 1

# Show plot of acquired image?
plot_image = True
auto_stretch_image = True


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

    # Acquire software-triggered frames
    acquired_frames = []
    for framenum in range(num_triggers):
        print(' ')
        print("Triggering frame {}".format(framenum))
        frame = Camobject.GetFrame()
        print('Frame received')
        print(' ')
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

    # Check all acquired frames are unique.
    for i in range(len(acquired_frames)):
        for j in range(i + 1, len(acquired_frames)):
            if np.array_equal(acquired_frames[i], acquired_frames[j]):
                raise ValueError(
                    f"Frames {i} and {j} are identical - camera may be returning cached data."
                )
