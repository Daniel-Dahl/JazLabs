import matplotlib.pyplot as plt
plt.ion()
import numpy as np
from datetime import datetime
from scipy.optimize import curve_fit
import time

# from pwi_inst.hardware.DAQ_Controller.mcc_daq import mcc_daq_Volt_Ctrl


class TTAttenCalibrator:
    """Calibrates tip-tilt attenuation by scanning DAC voltages and measuring PSF metrics."""

    def __init__(self,
                 camera_object,
                 dac_controller,
                 darkframe,
                 datadir,
                 init_volts=None,
                 scan_mode='2d',
                 scan_channel=1,
                 scan_width=5.5,
                 num_scanposns=10,
                 scan_waittime=0.1,
                 psf_method='gaussian',
                 enable_plotting=True,
                 enable_gaussfit_plot=False,
                 fs=2,
                 plot_pausetime=0.1,
                 save_output=False,
                 encircled_power_radius=10.0,
                 normalise_powers=True):
        """
        Parameters
        ----------
        camera_object : object
            Camera instance with a GetFrame() method that returns a 2D numpy array.
        dac_controller : object
            DAC controller instance with a SetVoltage(channel, voltage) method.
        darkframe : ndarray
            Pre-loaded dark frame (2D float array) subtracted from each acquired frame.
        datadir : str
            Directory for saving output files. Only used when save_output=True.
        init_volts : list of float, optional
            Starting voltages for each DAC channel, e.g. [-0.5, 6, 2]. The scan
            is centred on these values, and they are restored after the scan.
            Defaults to [-0.5, 6, 2].
        scan_mode : str
            '1d' to scan a single channel, '2d' to scan a grid over channels 0 and 1.
        scan_channel : int
            Channel index to scan in '1d' mode (0=x, 1=y). Ignored in '2d' mode.
        scan_width : float
            Total voltage range to scan in volts (peak-to-peak), centred on init_volts.
        num_scanposns : int
            Number of scan positions per axis. In '2d' mode the grid is
            num_scanposns x num_scanposns.
        scan_waittime : float
            Seconds to wait after setting each DAC voltage before acquiring a frame,
            to allow the mirror to settle.
        psf_method : str
            PSF centroid method: 'gaussian' for 2D Gaussian fit, 'com' for
            centre-of-mass.
        enable_plotting : bool
            If True, display a live frame plot at each scan position.
        enable_gaussfit_plot : bool
            If True, also show a three-panel Gaussian fit diagnostic plot at each
            position. Only used when psf_method='gaussian'.
        fs : int
            Figure size down-scaler. Figure widths/heights are divided by this value,
            so larger fs gives smaller figures.
        plot_pausetime : float
            Seconds passed to plt.pause() between scan positions, controlling how
            long each plot is displayed.
        save_output : bool
            If True, save PSF positions, powers, and DAC voltages as .npy files
            in datadir.
        encircled_power_radius : float
            Radius in pixels of the circular aperture used to measure encircled power.
        normalise_powers : bool
            If True, normalise all measured powers to their maximum value before
            returning/saving.
        """
        self.camera_object = camera_object
        self.dac_controller = dac_controller
        self.darkframe = darkframe
        self.datadir = datadir
        self.init_volts = init_volts if init_volts is not None else [-0.5, 6, 2]
        self.scan_mode = scan_mode
        self.scan_channel = scan_channel
        self.scan_width = scan_width
        self.num_scanposns = num_scanposns
        self.scan_waittime = scan_waittime
        self.psf_method = psf_method
        self.enable_plotting = enable_plotting
        self.enable_gaussfit_plot = enable_gaussfit_plot
        self.fs = fs
        self.plot_pausetime = plot_pausetime
        self.save_output = save_output
        self.encircled_power_radius = encircled_power_radius
        self.normalise_powers = normalise_powers

    def run(self):
        """Perform the scan according to scan_mode. Returns scan results."""
        if self.scan_mode == '1d':
            print(f"Starting 1D scan on channel {self.scan_channel}")
            return self._do_scan_1d()
        elif self.scan_mode == '2d':
            print("Starting 2D scan over channels 0 and 1")
            return self._do_scan_2d()
        else:
            raise ValueError(f"Unknown scan_mode: {self.scan_mode}. Choose '1d' or '2d'.")

    # ------------------------------------------------------------------
    # PSF analysis helpers
    # ------------------------------------------------------------------

    def _find_psf_center_of_mass(self, frame):
        frame_positive = frame - np.min(frame)
        total = np.sum(frame_positive)
        y_coords, x_coords = np.indices(frame_positive.shape)
        x_pos = np.sum(x_coords * frame_positive) / total
        y_pos = np.sum(y_coords * frame_positive) / total
        return x_pos, y_pos

    @staticmethod
    def _gaussian_2d(coords, amplitude, x0, y0, sigma_x, sigma_y, offset):
        x, y = coords
        gaussian = offset + amplitude * np.exp(
            -(((x - x0)**2 / (2 * sigma_x**2)) + ((y - y0)**2 / (2 * sigma_y**2)))
        )
        return gaussian.ravel()

    def _measure_encircled_power(self, frame, x_pos, y_pos, radius):
        y_grid, x_grid = np.indices(frame.shape)
        distance = np.sqrt((x_grid - x_pos)**2 + (y_grid - y_pos)**2)
        mask = distance <= radius
        return np.sum(frame[mask])

    def _find_psf_gaussian_fit(self, frame):
        y_grid, x_grid = np.indices(frame.shape)
        frame_height, frame_width = frame.shape

        max_idx = np.unravel_index(np.argmax(frame), frame.shape)
        y_max, x_max = max_idx
        x_com, y_com = self._find_psf_center_of_mass(frame)

        max_val = frame[y_max, x_max]
        median_val = np.median(frame)
        if max_val > median_val + 3 * np.std(frame):
            x_guess, y_guess = x_max, y_max
        else:
            x_guess, y_guess = x_com, y_com

        amplitude_guess = np.max(frame) - np.median(frame)
        offset_guess = np.percentile(frame, 10)
        sigma_guess = 3.0

        initial_guess = (amplitude_guess, x_guess, y_guess, sigma_guess, sigma_guess, offset_guess)
        bounds = (
            [0, -20, -20, 0.5, 0.5, -np.inf],
            [np.max(frame) * 2, frame_width + 20, frame_height + 20,
             min(frame_width, frame_height) / 2, min(frame_width, frame_height) / 2,
             np.max(frame)]
        )

        try:
            popt, _ = curve_fit(
                self._gaussian_2d,
                (x_grid, y_grid),
                frame.ravel(),
                p0=initial_guess,
                bounds=bounds,
                maxfev=10000
            )
            fitted_data = self._gaussian_2d((x_grid, y_grid), *popt).reshape(frame.shape)
            amplitude, x_pos, y_pos, sigma_x, sigma_y, offset = popt
            return x_pos, y_pos, popt, x_grid, y_grid, fitted_data
        except RuntimeError as e:
            print(f"Gaussian fit failed: {e}")
            print("Falling back to center of mass method")
            x_pos, y_pos = self._find_psf_center_of_mass(frame)
            return x_pos, y_pos, None, x_grid, y_grid, None

    def _plot_psf_position(self, frame, x_pos, y_pos, method='com', fit_data=None,
                           enable_gaussfit_plot=True, encircled_radius=None):
        fs = self.fs
        plt.figure(1, figsize=(10//fs, 8//fs))
        plt.clf()
        plt.imshow(frame, origin='lower', cmap='viridis')
        plt.colorbar(label='Intensity')

        cross_size = 20
        plt.plot([x_pos - cross_size, x_pos + cross_size], [y_pos, y_pos],
                 'r-', linewidth=2, label=f'Detected Position ({method.upper()})')
        plt.plot([x_pos, x_pos], [y_pos - cross_size, y_pos + cross_size],
                 'r-', linewidth=2)
        plt.plot(x_pos, y_pos, 'rx', markersize=15, markeredgewidth=2)

        if encircled_radius is not None:
            circle = plt.Circle((x_pos, y_pos), encircled_radius, color='cyan',
                               fill=False, linestyle='--', linewidth=1,
                               label=f'Encircled aperture (r={encircled_radius:.1f} px)')
            plt.gca().add_patch(circle)

        plt.title(f'PSF Detection (Method: {method.upper()})\nPosition: x={x_pos:.2f}, y={y_pos:.2f}')
        plt.xlabel('X (pixels)')
        plt.ylabel('Y (pixels)')
        plt.legend()
        plt.pause(0.001)

        if method == 'gaussian' and fit_data is not None and enable_gaussfit_plot:
            x_grid, y_grid, fitted_data, params = fit_data
            if fitted_data is not None:
                amplitude, x0, y0, sigma_x, sigma_y, offset = params

                plt.close(2)
                fig, axes = plt.subplots(1, 3, num=2, figsize=(18//fs, 5//fs))

                im0 = axes[0].imshow(frame, origin='lower', cmap='viridis')
                axes[0].set_title('Original Data')
                axes[0].set_xlabel('X (pixels)')
                axes[0].set_ylabel('Y (pixels)')
                plt.colorbar(im0, ax=axes[0], label='Intensity')

                im1 = axes[1].imshow(fitted_data, origin='lower', cmap='viridis')
                axes[1].set_title(f'Fitted 2D Gaussian\nσx={sigma_x:.2f}, σy={sigma_y:.2f}')
                axes[1].set_xlabel('X (pixels)')
                axes[1].set_ylabel('Y (pixels)')
                plt.colorbar(im1, ax=axes[1], label='Intensity')

                residuals = frame - fitted_data
                im2 = axes[2].imshow(residuals, origin='lower', cmap='RdBu_r',
                                    vmin=-np.max(np.abs(residuals)),
                                    vmax=np.max(np.abs(residuals)))
                axes[2].set_title('Residuals (Data - Fit)')
                axes[2].set_xlabel('X (pixels)')
                axes[2].set_ylabel('Y (pixels)')
                plt.colorbar(im2, ax=axes[2], label='Intensity')

                plt.pause(0.001)

        plt.show()

    # ------------------------------------------------------------------
    # Frame processing
    # ------------------------------------------------------------------

    def _process_frame(self, frame):
        """Find PSF position/amplitude in a frame and optionally plot.

        Returns
        -------
        x_pos, y_pos : float
        amplitude : float
            Gaussian fit amplitude, or 0.0 if using COM method or fit failed.
        """
        print(f"\nFinding PSF position using {self.psf_method.upper()} method...")
        amplitude = 0.0

        if self.psf_method == 'com':
            x_pos, y_pos = self._find_psf_center_of_mass(frame)
            print(f"PSF position (center-of-mass): x={x_pos:.3f}, y={y_pos:.3f} pixels")
            if self.enable_plotting:
                self._plot_psf_position(frame, x_pos, y_pos, method='com',
                                       encircled_radius=self.encircled_power_radius)

        elif self.psf_method == 'gaussian':
            x_pos, y_pos, popt, x_grid, y_grid, fitted_data = self._find_psf_gaussian_fit(frame)
            print(f"PSF position (Gaussian fit): x={x_pos:.3f}, y={y_pos:.3f} pixels")
            if popt is not None:
                amplitude, x0, y0, sigma_x, sigma_y, offset = popt
                print(f"  Amplitude: {amplitude:.2f}")
                print(f"  Sigma X: {sigma_x:.3f} pixels")
                print(f"  Sigma Y: {sigma_y:.3f} pixels")
                print(f"  Offset: {offset:.2f}")
                if self.enable_plotting:
                    self._plot_psf_position(frame, x_pos, y_pos, method='gaussian',
                                           fit_data=(x_grid, y_grid, fitted_data, popt),
                                           enable_gaussfit_plot=self.enable_gaussfit_plot,
                                           encircled_radius=self.encircled_power_radius)
            else:
                if self.enable_plotting:
                    self._plot_psf_position(frame, x_pos, y_pos, method='gaussian',
                                           enable_gaussfit_plot=self.enable_gaussfit_plot,
                                           encircled_radius=self.encircled_power_radius)
        else:
            raise ValueError(f"Unknown PSF method: {self.psf_method}. Choose 'com' or 'gaussian'.")

        return x_pos, y_pos, amplitude

    # ------------------------------------------------------------------
    # Scan methods
    # ------------------------------------------------------------------

    def _do_scan_1d(self):
        scan_centre = self.init_volts[self.scan_channel]
        all_scanvolts = np.linspace(scan_centre - self.scan_width / 2,
                                    scan_centre + self.scan_width / 2,
                                    self.num_scanposns)
        all_xyvals = np.zeros((self.num_scanposns, 2))
        all_powers_gaussfit = np.zeros((self.num_scanposns, 1))
        all_powers_encirc = np.zeros((self.num_scanposns, 1))
        all_dac_volts = np.zeros((self.num_scanposns, 2))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        for k in range(self.num_scanposns):
            print(f"Setting scan voltage to {all_scanvolts[k]:.2f} V on channel {self.scan_channel}")
            self.dac_controller.SetVoltage(channel=self.scan_channel, voltage=all_scanvolts[k])

            all_dac_volts[k, self.scan_channel] = all_scanvolts[k]
            all_dac_volts[k, 1 - self.scan_channel] = self.init_volts[1 - self.scan_channel]

            time.sleep(self.scan_waittime)

            print(f"Acquiring frame {k+1}/{self.num_scanposns}...")
            rawframe = self.camera_object.GetFrame().astype(np.float64)
            frame = rawframe - self.darkframe

            x_pos, y_pos, amplitude = self._process_frame(frame)

            encircled_power = self._measure_encircled_power(frame, x_pos, y_pos, self.encircled_power_radius)
            all_powers_encirc[k] = encircled_power
            all_powers_gaussfit[k] = amplitude
            print(f"Encircled power (r={self.encircled_power_radius:.1f} px): {encircled_power:.2f}")

            all_xyvals[k, :] = [x_pos, y_pos]
            print(f"Sleeping for {self.plot_pausetime} seconds...")
            plt.pause(self.plot_pausetime)

        print('Setting DAC back to initial voltages.')
        for l in range(len(self.init_volts)):
            self.dac_controller.SetVoltage(channel=l, voltage=self.init_volts[l])

        if self.normalise_powers:
            print('Normalising measured powers wrt maximum')
            all_powers_encirc = all_powers_encirc / np.max(all_powers_encirc)
            all_powers_gaussfit = all_powers_gaussfit / np.max(all_powers_gaussfit)

        if self.save_output:
            xy_outfilename = 'all_xyvals_' + timestamp + '.npy'
            print('Saving xyvals to ' + xy_outfilename)
            np.save(self.datadir + xy_outfilename, all_xyvals)

            power_outfilename = 'all_powers' + timestamp + '.npy'
            print('Saving powers to ' + power_outfilename)
            np.save(self.datadir + power_outfilename, np.hstack((all_powers_gaussfit, all_powers_encirc)))

        if self.num_scanposns > 1:
            fs = self.fs
            plt.figure(3, figsize=(10//fs, 6//fs))
            plt.clf()
            plt.title('PSF position vs scan voltage')
            plt.plot(all_scanvolts, all_xyvals[:, 0], '-o')
            plt.plot(all_scanvolts, all_xyvals[:, 1], '-o')
            plt.xlabel(f'Voltage on channel {self.scan_channel} (V)')
            plt.ylabel('PSF position (pixels)')
            plt.legend(['x', 'y'])
            plt.tight_layout()

            plt.figure(4, figsize=(10//fs, 6//fs))
            plt.clf()
            plt.title('PSF power vs scan voltage')
            plt.plot(all_scanvolts, all_powers_gaussfit, '-o', label='Gaussian fit')
            plt.plot(all_scanvolts, all_powers_encirc, '-s',
                     label=f'Encircled (r={self.encircled_power_radius:.1f} px)')
            plt.xlabel(f'Voltage on channel {self.scan_channel} (V)')
            plt.ylabel('PSF power')
            plt.legend()
            plt.tight_layout()

        return all_xyvals, all_powers_gaussfit, all_powers_encirc, all_dac_volts, timestamp

    def _do_scan_2d(self):
        scan_centre_ch0 = self.init_volts[0]
        scan_centre_ch1 = self.init_volts[1]

        scanvolts_ch0 = np.linspace(scan_centre_ch0 - self.scan_width / 2,
                                    scan_centre_ch0 + self.scan_width / 2,
                                    self.num_scanposns)
        scanvolts_ch1 = np.linspace(scan_centre_ch1 - self.scan_width / 2,
                                    scan_centre_ch1 + self.scan_width / 2,
                                    self.num_scanposns)

        total_posns = self.num_scanposns * self.num_scanposns
        all_xyvals = np.zeros((total_posns, 2))
        all_powers_gaussfit = np.zeros((total_posns, 1))
        all_powers_encirc = np.zeros((total_posns, 1))
        all_dac_volts = np.zeros((total_posns, 2))

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        k = 0
        for i, volt_ch0 in enumerate(scanvolts_ch0):
            for j, volt_ch1 in enumerate(scanvolts_ch1):
                print(f"Setting voltages: CH0={volt_ch0:.2f} V, CH1={volt_ch1:.2f} V")
                self.dac_controller.SetVoltage(channel=0, voltage=volt_ch0)
                self.dac_controller.SetVoltage(channel=1, voltage=volt_ch1)

                all_dac_volts[k, :] = [volt_ch0, volt_ch1]

                time.sleep(self.scan_waittime)

                print(f"Acquiring frame {k+1}/{total_posns}...")
                rawframe = self.camera_object.GetFrame().astype(np.float64)
                frame = rawframe - self.darkframe

                x_pos, y_pos, amplitude = self._process_frame(frame)

                encircled_power = self._measure_encircled_power(frame, x_pos, y_pos, self.encircled_power_radius)
                all_powers_encirc[k] = encircled_power
                all_powers_gaussfit[k] = amplitude
                print(f"Encircled power (r={self.encircled_power_radius:.1f} px): {encircled_power:.2f}")

                all_xyvals[k, :] = [x_pos, y_pos]
                print(f"Sleeping for {self.plot_pausetime} seconds...")
                plt.pause(self.plot_pausetime)

                k += 1

        print('Setting DAC back to initial voltages.')
        for l in range(len(self.init_volts)):
            self.dac_controller.SetVoltage(channel=l, voltage=self.init_volts[l])

        if self.normalise_powers:
            print('Normalising measured powers wrt maximum')
            all_powers_encirc = all_powers_encirc / np.max(all_powers_encirc)
            all_powers_gaussfit = all_powers_gaussfit / np.max(all_powers_gaussfit)

        if self.save_output:
            xy_outfilename = 'all_xyvals_2d_' + timestamp + '.npy'
            print('Saving xyvals to ' + xy_outfilename)
            np.save(self.datadir + xy_outfilename, all_xyvals)

            power_outfilename = 'all_powers_2d_' + timestamp + '.npy'
            print('Saving powers to ' + power_outfilename)
            np.save(self.datadir + power_outfilename, np.hstack((all_powers_gaussfit, all_powers_encirc)))

            dac_outfilename = 'all_dac_volts_2d_' + timestamp + '.npy'
            print('Saving DAC voltages to ' + dac_outfilename)
            np.save(self.datadir + dac_outfilename, all_dac_volts)

        if total_posns > 1:
            fs = self.fs
            powers_gaussfit_grid = all_powers_gaussfit.reshape((self.num_scanposns, self.num_scanposns))
            powers_encirc_grid = all_powers_encirc.reshape((self.num_scanposns, self.num_scanposns))

            plt.figure(3, figsize=(10//fs, 8//fs))
            plt.clf()
            plt.scatter(all_xyvals[:, 0], all_xyvals[:, 1], c=all_powers_encirc.ravel(),
                       s=100, cmap='viridis', marker='o', edgecolors='black', linewidths=1)
            plt.colorbar(label='Encircled power')
            plt.xlabel('PSF X position (pixels)')
            plt.ylabel('PSF Y position (pixels)')
            plt.title('Measured PSF positions (2D scan)')
            plt.grid(True, alpha=0.3)
            plt.axis('equal')
            plt.tight_layout()

            plt.figure(4, figsize=(12//fs, 5//fs))
            plt.clf()

            plt.subplot(1, 2, 1)
            im1 = plt.imshow(powers_gaussfit_grid.T, origin='lower', aspect='auto',
                            extent=[scanvolts_ch0[0], scanvolts_ch0[-1],
                                   scanvolts_ch1[0], scanvolts_ch1[-1]],
                            cmap='viridis')
            plt.colorbar(im1, label='Power')
            plt.xlabel('Channel 0 voltage (V)')
            plt.ylabel('Channel 1 voltage (V)')
            plt.title('PSF power (Gaussian fit)')

            plt.subplot(1, 2, 2)
            im2 = plt.imshow(powers_encirc_grid.T, origin='lower', aspect='auto',
                            extent=[scanvolts_ch0[0], scanvolts_ch0[-1],
                                   scanvolts_ch1[0], scanvolts_ch1[-1]],
                            cmap='viridis')
            plt.colorbar(im2, label='Power')
            plt.xlabel('Channel 0 voltage (V)')
            plt.ylabel('Channel 1 voltage (V)')
            plt.title(f'PSF power (Encircled r={self.encircled_power_radius:.1f} px)')

            plt.tight_layout()

        return all_xyvals, all_powers_gaussfit, all_powers_encirc, all_dac_volts, timestamp
