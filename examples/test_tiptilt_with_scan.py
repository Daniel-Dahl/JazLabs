import sys
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from scipy.optimize import curve_fit
import time

from pwi_inst.hardware.DAQ_Controller.mcc_daq import mcc_daq_Volt_Ctrl


datadir = 'C:/Users/sail/Documents/Data_2025-2026/202603/'
darkframe_filename = 'darkframe_20260327_130811.npy'

## Select initial voltages for each channel (V) [tip, tilt]
init_volts = [-0.5, 6, 5]

## Set channel and scan parameters
scan_channel = 0 # which channel is tip/tilt?
scan_centre = -0.5 # V
scan_width = 5.5 # Vpp
num_scanposns = 10
scan_waittime = 0.1

# PSF finding method: 'com' for center-of-mass, 'gaussian' for 2D Gaussian fit
psf_method = 'gaussian'  # Change to 'com' for center-of-mass

# Enable or disable plotting
enable_plotting = True
enable_gaussfit_plot = False
fs = 2 # Figure size down-scaler
plot_pausetime = 0.1

save_output = True

# Encircled power measurement radius (pixels)
encircled_power_radius = 10.0
normalise_powers = True


def find_psf_center_of_mass(frame):
    """
    Find PSF position using center of mass method.

    Parameters
    ----------
    frame : ndarray
        2D image array containing the PSF

    Returns
    -------
    x_pos, y_pos : float
        Subpixel position of the PSF centroid
    """
    # Ensure positive values for center of mass calculation
    frame_positive = frame - np.min(frame)

    # Calculate total intensity
    total = np.sum(frame_positive)

    # Create coordinate arrays
    y_coords, x_coords = np.indices(frame_positive.shape)

    # Calculate center of mass
    x_pos = np.sum(x_coords * frame_positive) / total
    y_pos = np.sum(y_coords * frame_positive) / total

    return x_pos, y_pos


def gaussian_2d(coords, amplitude, x0, y0, sigma_x, sigma_y, offset):
    """
    2D Gaussian function for curve fitting.

    Parameters
    ----------
    coords : tuple
        (x, y) coordinate arrays
    amplitude : float
        Peak amplitude of Gaussian
    x0, y0 : float
        Center position
    sigma_x, sigma_y : float
        Standard deviations in x and y
    offset : float
        Background offset

    Returns
    -------
    ndarray
        Flattened 2D Gaussian values
    """
    x, y = coords
    gaussian = offset + amplitude * np.exp(
        -(((x - x0)**2 / (2 * sigma_x**2)) + ((y - y0)**2 / (2 * sigma_y**2)))
    )
    return gaussian.ravel()


def measure_encircled_power(frame, x_pos, y_pos, radius):
    """
    Measure the total power within a circular aperture around the PSF.

    Parameters
    ----------
    frame : ndarray
        2D image array containing the PSF
    x_pos, y_pos : float
        Center position of the PSF
    radius : float
        Radius of the circular aperture in pixels

    Returns
    -------
    power : float
        Sum of pixel values within the circular aperture
    """
    # Create coordinate grids
    y_grid, x_grid = np.indices(frame.shape)

    # Calculate distance from PSF center for each pixel
    distance = np.sqrt((x_grid - x_pos)**2 + (y_grid - y_pos)**2)

    # Create circular mask
    mask = distance <= radius

    # Sum power within the circle
    power = np.sum(frame[mask])

    return power


def find_psf_gaussian_fit(frame):
    """
    Find PSF position by fitting a 2D Gaussian.

    Parameters
    ----------
    frame : ndarray
        2D image array containing the PSF

    Returns
    -------
    x_pos, y_pos : float
        Subpixel position of the PSF center
    fit_params : tuple
        Full fitting parameters (amplitude, x0, y0, sigma_x, sigma_y, offset)
    x_grid, y_grid : ndarray
        Coordinate grids for plotting
    fitted_data : ndarray
        2D array of fitted Gaussian values
    """
    # Create coordinate grids
    y_grid, x_grid = np.indices(frame.shape)

    # Initial guess for parameters
    # Use center of mass for initial position guess
    x_guess, y_guess = find_psf_center_of_mass(frame)
    amplitude_guess = np.max(frame) - np.min(frame)
    offset_guess = np.min(frame)
    sigma_guess = 3.0  # Initial guess for width

    initial_guess = (amplitude_guess, x_guess, y_guess, sigma_guess, sigma_guess, offset_guess)

    try:
        # Perform the fit
        popt, pcov = curve_fit(
            gaussian_2d,
            (x_grid, y_grid),
            frame.ravel(),
            p0=initial_guess,
            maxfev=10000
        )

        amplitude, x_pos, y_pos, sigma_x, sigma_y, offset = popt

        # Generate fitted data for visualization
        fitted_data = gaussian_2d((x_grid, y_grid), *popt).reshape(frame.shape)

        return x_pos, y_pos, popt, x_grid, y_grid, fitted_data

    except RuntimeError as e:
        print(f"Gaussian fit failed: {e}")
        print("Falling back to center of mass method")
        x_pos, y_pos = find_psf_center_of_mass(frame)
        return x_pos, y_pos, None, x_grid, y_grid, None


def plot_psf_position(frame, x_pos, y_pos, method='com', fit_data=None, enable_gaussfit_plot=True, encircled_radius=None):
    """
    Plot the frame with detected PSF position overlaid.

    Parameters
    ----------
    frame : ndarray
        2D image array
    x_pos, y_pos : float
        Detected PSF position
    method : str
        Method used ('com' or 'gaussian')
    fit_data : tuple or None
        If method='gaussian', tuple of (x_grid, y_grid, fitted_data, params)
    encircled_radius : float or None
        If provided, plot a circle showing the encircled power aperture
    """
    # Main plot: frame with detected position
    plt.figure(1, figsize=(10//fs, 8//fs))
    plt.clf()
    plt.imshow(frame, origin='lower', cmap='viridis')
    plt.colorbar(label='Intensity')

    # Plot crosshair at detected position
    cross_size = 20
    plt.plot([x_pos - cross_size, x_pos + cross_size], [y_pos, y_pos],
             'r-', linewidth=2, label=f'Detected Position ({method.upper()})')
    plt.plot([x_pos, x_pos], [y_pos - cross_size, y_pos + cross_size],
             'r-', linewidth=2)
    plt.plot(x_pos, y_pos, 'rx', markersize=15, markeredgewidth=2)

    # Plot encircled power aperture if radius provided
    if encircled_radius is not None:
        circle = plt.Circle((x_pos, y_pos), encircled_radius, color='cyan',
                           fill=False, linestyle='--', linewidth=1,
                           label=f'Encircled aperture (r={encircled_radius:.1f} px)')
        plt.gca().add_patch(circle)

    plt.title(f'PSF Detection (Method: {method.upper()})\nPosition: x={x_pos:.2f}, y={y_pos:.2f}')
    plt.xlabel('X (pixels)')
    plt.ylabel('Y (pixels)')
    plt.legend()
    plt.tight_layout()
    plt.pause(0.001)

    # If Gaussian fit, create comparison plot
    if method == 'gaussian' and fit_data is not None and enable_gaussfit_plot:
        x_grid, y_grid, fitted_data, params = fit_data
        if fitted_data is not None:
            amplitude, x0, y0, sigma_x, sigma_y, offset = params

            plt.close(2)
            fig, axes = plt.subplots(1, 3, num=2, figsize=(18//fs, 5//fs))

            # Original data
            im0 = axes[0].imshow(frame, origin='lower', cmap='viridis')
            axes[0].set_title('Original Data')
            axes[0].set_xlabel('X (pixels)')
            axes[0].set_ylabel('Y (pixels)')
            plt.colorbar(im0, ax=axes[0], label='Intensity')

            # Fitted Gaussian
            im1 = axes[1].imshow(fitted_data, origin='lower', cmap='viridis')
            axes[1].set_title(f'Fitted 2D Gaussian\nσx={sigma_x:.2f}, σy={sigma_y:.2f}')
            axes[1].set_xlabel('X (pixels)')
            axes[1].set_ylabel('Y (pixels)')
            plt.colorbar(im1, ax=axes[1], label='Intensity')

            # Residuals
            residuals = frame - fitted_data
            im2 = axes[2].imshow(residuals, origin='lower', cmap='RdBu_r',
                                vmin=-np.max(np.abs(residuals)),
                                vmax=np.max(np.abs(residuals)))
            axes[2].set_title('Residuals (Data - Fit)')
            axes[2].set_xlabel('X (pixels)')
            axes[2].set_ylabel('Y (pixels)')
            plt.colorbar(im2, ax=axes[2], label='Intensity')

            plt.tight_layout()
            plt.pause(0.001)

    plt.show()



if __name__ == '__main__':
    # Initialize PSF camera (camera index 1) with start_display=False for headless operation
    Cam_PSF = FLForm.FirstLightCameraObject(1, start_display=False)
    Cam_PSF.CamObject.Setfps(30)
    Cam_PSF.CamObject.SetExposure(100)  # microseconds

    # Load existing dark frame
    darkframe_path = Path(datadir) / darkframe_filename
    darkframe = np.load(darkframe_path)
    print(f"Loaded dark frame from: {darkframe_path}")

    # Initialize DAC controller
    DAC_Controller = mcc_daq_Volt_Ctrl()
    for l in range(len(init_volts)):
        DAC_Controller.SetVoltage(channel=l, voltage=init_volts[l])



    all_scanvolts = np.linspace(scan_centre-scan_width/2,scan_centre+scan_width/2,num_scanposns)
    all_xyvals = np.zeros((num_scanposns,2))
    all_powers_gaussfit = np.zeros((num_scanposns,1))
    all_powers_encirc = np.zeros((num_scanposns, 1))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    for k in range(num_scanposns):
        print(f"Setting scan voltage to {all_scanvolts[k]:.2f} V")
        DAC_Controller.SetVoltage(channel=scan_channel, voltage=all_scanvolts[k])
        time.sleep(scan_waittime)

        print(f"Acquiring frame {k+1}/{num_scanposns}...")
        # Acquire frame
        rawframe = Cam_PSF.CamObject.GetFrame().astype(np.float64)
        frame = rawframe - darkframe

        # Find PSF position using selected method
        print(f"\nFinding PSF position using {psf_method.upper()} method...")

        if psf_method == 'com':
            x_pos, y_pos = find_psf_center_of_mass(frame)
            print(f"PSF position (center-of-mass): x={x_pos:.3f}, y={y_pos:.3f} pixels")
            if enable_plotting:
                plot_psf_position(frame, x_pos, y_pos, method='com', encircled_radius=encircled_power_radius)

        elif psf_method == 'gaussian':
            x_pos, y_pos, popt, x_grid, y_grid, fitted_data = find_psf_gaussian_fit(frame)
            print(f"PSF position (Gaussian fit): x={x_pos:.3f}, y={y_pos:.3f} pixels")

            if popt is not None:
                amplitude, x0, y0, sigma_x, sigma_y, offset = popt
                print(f"  Amplitude: {amplitude:.2f}")
                print(f"  Sigma X: {sigma_x:.3f} pixels")
                print(f"  Sigma Y: {sigma_y:.3f} pixels")
                print(f"  Offset: {offset:.2f}")
                if enable_plotting:
                    plot_psf_position(frame, x_pos, y_pos, method='gaussian',
                                    fit_data=(x_grid, y_grid, fitted_data, popt),
                                    enable_gaussfit_plot=enable_gaussfit_plot,
                                    encircled_radius=encircled_power_radius)
                all_powers_gaussfit[k] = amplitude
            else:
                if enable_plotting:
                    plot_psf_position(frame, x_pos, y_pos, method='gaussian',
                                    enable_gaussfit_plot=enable_gaussfit_plot,
                                    encircled_radius=encircled_power_radius)

        else:
            raise ValueError(f"Unknown PSF method: {psf_method}. Choose 'com' or 'gaussian'.")

        # Measure encircled power
        encircled_power = measure_encircled_power(frame, x_pos, y_pos, encircled_power_radius)
        all_powers_encirc[k] = encircled_power
        print(f"Encircled power (r={encircled_power_radius:.1f} px): {encircled_power:.2f}")

        all_xyvals[k,:]=[x_pos,y_pos]
        print(f"Sleeping for {plot_pausetime} seconds...")
        plt.pause(plot_pausetime)

    print('Setting DAC back to initial voltages.')
    for l in range(len(init_volts)):
        DAC_Controller.SetVoltage(channel=l, voltage=init_volts[l])

    if normalise_powers:
        print('Normalising measured powers wrt maximum')
        all_powers_encirc = all_powers_encirc / np.max(all_powers_encirc)
        all_powers_gaussfit = all_powers_gaussfit / np.max(all_powers_gaussfit)

    if save_output:
        xy_outfilename = 'all_xyvals_' + timestamp + '.npy'
        print('Saving xyvals to ' + xy_outfilename)
        np.save(datadir + xy_outfilename, all_xyvals)

        power_outfilename = 'all_powers' + timestamp + '.npy'
        print('Saving powers to ' + power_outfilename)
        all_powers_arr = np.hstack((all_powers_gaussfit, all_powers_encirc))
        np.save(datadir + power_outfilename, all_powers_arr)


    if num_scanposns > 1:
        plt.figure(3, figsize=(10//fs, 6//fs))
        plt.clf()
        plt.title('PSF position')
        plt.plot(all_scanvolts, all_xyvals[:,0],'-o')
        plt.plot(all_scanvolts, all_xyvals[:,1],'-o')
        plt.xlabel('Voltage (V)')
        plt.ylabel('PSF position (pixels)')
        plt.legend(['x','y'])
        plt.tight_layout()

        plt.figure(4, figsize=(10//fs, 6//fs))
        plt.clf()
        plt.title('PSF power')
        plt.plot(all_scanvolts, all_powers_gaussfit,'-o', label='Gaussian fit')
        plt.plot(all_scanvolts, all_powers_encirc,'-s', label=f'Encircled (r={encircled_power_radius:.1f} px)')
        plt.xlabel('Voltage (V)')
        plt.ylabel('PSF power')
        plt.legend()
        plt.tight_layout()


