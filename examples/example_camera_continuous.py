
### Example script for continuous acquisition of images from a First Light camera, with ROI cropping ###


# Select model of First Light camera to load appropriate library
# camera_model = 'FirstLightCblue2'
# camera_model = 'FirstLightCred3_2Lite'
camera_model = 'FLIR_pointgrey'


# Todo - specify camera by serial number
# Index of camera
camera_idx = 0

# Set key camera settings
exp_time_us = 100 # microseconds

# Todo - note allowed intervals for rows and column selections
# Specify region of interest (ROI) [offset_x, offset_y, width, height],
# or None for full frame.
# roi_geometry = [150,200,256,256]
roi_geometry = [288,176,128,128]
# roi_geometry = None

# When setting ROI, snap to nearest allowed value?
snap_values = False

# Print diagnostic info from camera object?
verbose = True

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
    Camobject.SetContinuousMode()
    Camobject.SetExposureTime(exp_time_us)

    # Get camera settings
    exp_time_reported = Camobject.GetExposureTime()
    print(f'Exposure time reported as {exp_time_reported} microseconds')

    # Set ROI (crop) mode
    if roi_geometry is not None:
        Camobject.SetROI(*roi_geometry, snap_values=snap_values, enable=True)
    else:
        Camobject.SetROI(enable=False)

    # Get the latest frame from the buffer
    frame=Camobject.GetFrame()

    if plot_image:
        import matplotlib.pyplot as plt
        if auto_stretch_image:
            import numpy as np
            p1, p99 = np.percentile(frame, [1, 99])
            frame = np.clip(frame, p1, p99)
        plt.imshow(frame, cmap='gray')
        plt.colorbar()
        plt.show()
        plt.savefig("CamFrameDeleteMe.png", dpi=300, bbox_inches="tight")
