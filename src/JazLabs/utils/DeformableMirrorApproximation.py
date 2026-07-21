import numpy as np


def _actuator_count_xy(actuator_count):
    if np.isscalar(actuator_count):
        actuator_count_x = int(actuator_count)
        actuator_count_y = int(actuator_count)
    else:
        actuator_count_x = int(actuator_count[0])
        actuator_count_y = int(actuator_count[1])

    if actuator_count_x < 2 or actuator_count_y < 2:
        raise ValueError("actuator_count must be at least 2 in each direction.")

    return actuator_count_x, actuator_count_y


def _default_circular_aperture(Ny, Nx):
    x_pixels = np.arange(Nx, dtype=np.float64) - (Nx - 1) / 2.0
    y_pixels = np.arange(Ny, dtype=np.float64) - (Ny - 1) / 2.0
    X_pixels, Y_pixels = np.meshgrid(x_pixels, y_pixels)

    aperture_radius_in_pixels = min(Nx, Ny) / 2.0
    x_unit = X_pixels / aperture_radius_in_pixels
    y_unit = Y_pixels / aperture_radius_in_pixels
    radius = np.sqrt(x_unit**2 + y_unit**2)

    return radius <= 1.0, x_unit, y_unit


def _unwrap_field_phase(field_phase_radians, aperture=None, unwrap_method="auto"):
    if unwrap_method in ("auto", "skimage"):
        try:
            from skimage.restoration import unwrap_phase as skimage_unwrap_phase

            if aperture is None:
                return skimage_unwrap_phase(field_phase_radians)

            masked_phase = np.ma.array(field_phase_radians, mask=~aperture)
            unwrapped_phase = skimage_unwrap_phase(masked_phase)
            return np.asarray(unwrapped_phase.filled(0.0), dtype=np.float64)
        except ImportError:
            if unwrap_method == "skimage":
                raise

    if unwrap_method not in ("auto", "numpy"):
        raise ValueError("unwrap_method must be 'auto', 'skimage', or 'numpy'.")

    unwrapped_phase = np.unwrap(field_phase_radians, axis=1)
    unwrapped_phase = np.unwrap(unwrapped_phase, axis=0)
    return unwrapped_phase


def _phase_from_slm_profile(
    slm_profile,
    input_is_field,
    phase_scale,
    unwrap_phase=False,
    unwrap_method="auto",
    aperture=None,
):
    slm_profile = np.asarray(slm_profile)

    if slm_profile.ndim != 2:
        raise ValueError("slm_profile must have shape (Ny, Nx).")

    if input_is_field:
        field_phase_radians = np.angle(slm_profile)
        if unwrap_phase:
            field_phase_radians = _unwrap_field_phase(
                field_phase_radians,
                aperture=aperture,
                unwrap_method=unwrap_method,
            )
        return field_phase_radians / phase_scale

    return np.asarray(slm_profile, dtype=np.float64)


def gaussian_lowpass_complex_field_fft(
    field,
    sigma_in_cycles_per_aperture=None,
    cutoff_cycles_per_aperture=None,
    aperture=None,
    renormalize_amplitude=True,
):
    """
    Smooth a complex phase field by multiplying its FFT by a Gaussian low-pass.

    This is the Fourier-domain version of blurring. It is usually better to
    filter the complex field than the wrapped phase angle, because the complex
    field does not have artificial jumps at -pi/pi.

    Use exactly one of:

        sigma_in_cycles_per_aperture
        cutoff_cycles_per_aperture

    sigma_in_cycles_per_aperture is the Gaussian sigma in spatial-frequency
    units. Smaller values blur more strongly. cutoff_cycles_per_aperture is the
    half-amplitude frequency; larger values preserve more detail.
    """
    field = np.asarray(field, dtype=np.complex128)
    if field.ndim != 2:
        raise ValueError("field must have shape (Ny, Nx).")

    if (sigma_in_cycles_per_aperture is None) == (cutoff_cycles_per_aperture is None):
        raise ValueError(
            "Specify exactly one of sigma_in_cycles_per_aperture or "
            "cutoff_cycles_per_aperture."
        )

    Ny, Nx = field.shape
    aperture_diameter_pixels = min(Nx, Ny)

    x_frequency = np.fft.fftshift(np.fft.fftfreq(Nx)) * aperture_diameter_pixels
    y_frequency = np.fft.fftshift(np.fft.fftfreq(Ny)) * aperture_diameter_pixels
    X_frequency, Y_frequency = np.meshgrid(x_frequency, y_frequency)
    radius_frequency = np.sqrt(X_frequency**2 + Y_frequency**2)

    if cutoff_cycles_per_aperture is not None:
        cutoff_cycles_per_aperture = float(cutoff_cycles_per_aperture)
        if cutoff_cycles_per_aperture <= 0:
            raise ValueError("cutoff_cycles_per_aperture must be positive.")

        sigma_in_cycles_per_aperture = cutoff_cycles_per_aperture / np.sqrt(2.0 * np.log(2.0))
    else:
        sigma_in_cycles_per_aperture = float(sigma_in_cycles_per_aperture)
        if sigma_in_cycles_per_aperture <= 0:
            raise ValueError("sigma_in_cycles_per_aperture must be positive.")

    gaussian_filter = np.exp(
        -0.5 * (radius_frequency / sigma_in_cycles_per_aperture) ** 2
    )

    field_fft = np.fft.fftshift(np.fft.fft2(field))
    filtered_field = np.fft.ifft2(np.fft.ifftshift(field_fft * gaussian_filter))

    if renormalize_amplitude:
        filtered_amplitude = np.abs(filtered_field)
        filtered_field = np.divide(
            filtered_field,
            filtered_amplitude,
            out=np.ones_like(filtered_field),
            where=filtered_amplitude > 0,
        )

    if aperture is not None:
        aperture = np.asarray(aperture, dtype=bool)
        if aperture.shape != field.shape:
            raise ValueError("aperture shape must match field shape.")
        filtered_field = np.where(aperture, filtered_field, 0.0)

    return {
        "filtered_field": filtered_field,
        "frequency_filter": gaussian_filter,
        "sigma_in_cycles_per_aperture": sigma_in_cycles_per_aperture,
        "x_frequency": x_frequency,
        "y_frequency": y_frequency,
    }


def _make_actuator_centres(actuator_count_x, actuator_count_y, use_circular_actuator_grid):
    actuator_x_positions = np.linspace(-1.0, 1.0, actuator_count_x)
    actuator_y_positions = np.linspace(-1.0, 1.0, actuator_count_y)
    actuator_X, actuator_Y = np.meshgrid(actuator_x_positions, actuator_y_positions)

    actuator_x = actuator_X.ravel()
    actuator_y = actuator_Y.ravel()

    if use_circular_actuator_grid:
        actuator_is_used = np.sqrt(actuator_x**2 + actuator_y**2) <= 1.0
        actuator_x = actuator_x[actuator_is_used]
        actuator_y = actuator_y[actuator_is_used]

    return actuator_x, actuator_y


def approximate_slm_phase_with_dm_actuators(
    slm_profile,
    actuator_count,
    aperture=None,
    input_is_field=True,
    phase_scale=np.pi,
    unwrap_phase=False,
    unwrap_method="auto",
    remove_phase_piston=True,
    influence_width_in_actuator_pitch=0.75,
    use_circular_actuator_grid=True,
    fit_pixel_step=1,
    actuator_command_limit=None,
    regularization=1e-6,
):
    """
    Approximate an SLM phase profile with a finite-actuator deformable mirror.

    slm_profile can be either:

        complex field: exp(1j * phase_scale * phase)
        real phase:    phase

    If input_is_field=True, the phase is taken as angle(slm_profile) / phase_scale.
    Set unwrap_phase=True when the field came from a wrapped SLM mask and you
    want the DM to fit the smooth continuous phase rather than the 2*pi jumps.
    The returned dm_phase uses the same phase units as the input phase. For a
    Zernike field made with exp(1j*pi*phase), this means dm_phase is in the same
    units as zern.make_zernike_phase().

    The DM is modelled as a sum of Gaussian actuator influence functions.
    actuator_count can be an integer for a square grid, or (Nx_act, Ny_act).
    """
    slm_profile = np.asarray(slm_profile)
    if slm_profile.ndim != 2:
        raise ValueError("slm_profile must have shape (Ny, Nx).")

    Ny, Nx = slm_profile.shape

    if aperture is None:
        aperture, x_unit, y_unit = _default_circular_aperture(Ny, Nx)
    else:
        aperture = np.asarray(aperture, dtype=bool)
        if aperture.shape != slm_profile.shape:
            raise ValueError("aperture shape must match slm_profile shape.")

        x_pixels = np.arange(Nx, dtype=np.float64) - (Nx - 1) / 2.0
        y_pixels = np.arange(Ny, dtype=np.float64) - (Ny - 1) / 2.0
        X_pixels, Y_pixels = np.meshgrid(x_pixels, y_pixels)
        aperture_radius_in_pixels = min(Nx, Ny) / 2.0
        x_unit = X_pixels / aperture_radius_in_pixels
        y_unit = Y_pixels / aperture_radius_in_pixels

    desired_phase = _phase_from_slm_profile(
        slm_profile,
        input_is_field=input_is_field,
        phase_scale=phase_scale,
        unwrap_phase=unwrap_phase,
        unwrap_method=unwrap_method,
        aperture=aperture,
    )

    if remove_phase_piston:
        desired_phase = desired_phase - np.mean(desired_phase[aperture])

    actuator_count_x, actuator_count_y = _actuator_count_xy(actuator_count)
    actuator_x, actuator_y = _make_actuator_centres(
        actuator_count_x,
        actuator_count_y,
        use_circular_actuator_grid=use_circular_actuator_grid,
    )

    if actuator_count_x == 1:
        actuator_pitch_x = 2.0
    else:
        actuator_pitch_x = 2.0 / (actuator_count_x - 1)

    if actuator_count_y == 1:
        actuator_pitch_y = 2.0
    else:
        actuator_pitch_y = 2.0 / (actuator_count_y - 1)

    mean_actuator_pitch = 0.5 * (actuator_pitch_x + actuator_pitch_y)
    influence_sigma = influence_width_in_actuator_pitch * mean_actuator_pitch

    if influence_sigma <= 0:
        raise ValueError("influence_width_in_actuator_pitch must be positive.")

    if fit_pixel_step < 1:
        raise ValueError("fit_pixel_step must be >= 1.")

    fit_mask = np.zeros_like(aperture, dtype=bool)
    fit_mask[::fit_pixel_step, ::fit_pixel_step] = True
    fit_mask = fit_mask & aperture

    fit_x = x_unit[fit_mask]
    fit_y = y_unit[fit_mask]
    target_phase = desired_phase[fit_mask]

    influence_matrix = np.zeros((target_phase.size, actuator_x.size), dtype=np.float64)
    for actuator_index in range(actuator_x.size):
        distance_squared = (
            (fit_x - actuator_x[actuator_index]) ** 2
            + (fit_y - actuator_y[actuator_index]) ** 2
        )
        influence_matrix[:, actuator_index] = np.exp(
            -0.5 * distance_squared / influence_sigma**2
        )

    if regularization is None or regularization == 0:
        actuator_commands, residuals, rank, singular_values = np.linalg.lstsq(
            influence_matrix,
            target_phase,
            rcond=None,
        )
    else:
        regularization = float(regularization)
        augmented_matrix = np.vstack(
            [
                influence_matrix,
                np.sqrt(regularization) * np.eye(actuator_x.size),
            ]
        )
        augmented_target = np.concatenate(
            [
                target_phase,
                np.zeros(actuator_x.size, dtype=np.float64),
            ]
        )
        actuator_commands, residuals, rank, singular_values = np.linalg.lstsq(
            augmented_matrix,
            augmented_target,
            rcond=None,
        )

    if actuator_command_limit is not None:
        command_limit = abs(float(actuator_command_limit))
        actuator_commands = np.clip(actuator_commands, -command_limit, command_limit)

    dm_phase = np.zeros_like(desired_phase, dtype=np.float64)
    for actuator_index in range(actuator_x.size):
        distance_squared = (
            (x_unit - actuator_x[actuator_index]) ** 2
            + (y_unit - actuator_y[actuator_index]) ** 2
        )
        influence_function = np.exp(-0.5 * distance_squared / influence_sigma**2)
        dm_phase += actuator_commands[actuator_index] * influence_function

    dm_phase = np.where(aperture, dm_phase, 0.0)
    desired_phase = np.where(aperture, desired_phase, 0.0)
    dm_field = np.where(aperture, np.exp(1j * phase_scale * dm_phase), 0.0)

    phase_error = np.where(aperture, desired_phase - dm_phase, 0.0)
    rms_phase_error = np.sqrt(np.mean(phase_error[aperture] ** 2))
    peak_to_valley_phase_error = np.max(phase_error[aperture]) - np.min(phase_error[aperture])

    return {
        "dm_phase": dm_phase,
        "dm_field": dm_field,
        "desired_phase": desired_phase,
        "phase_error": phase_error,
        "rms_phase_error": rms_phase_error,
        "peak_to_valley_phase_error": peak_to_valley_phase_error,
        "actuator_commands": actuator_commands,
        "actuator_x": actuator_x,
        "actuator_y": actuator_y,
        "actuator_count_x": actuator_count_x,
        "actuator_count_y": actuator_count_y,
        "influence_sigma": influence_sigma,
        "fit_pixel_step": fit_pixel_step,
        "rank": rank,
        "singular_values": singular_values,
        "residuals": residuals,
    }


def approximate_field_stack_with_dm_actuators(
    fields,
    actuator_count,
    aperture=None,
    phase_scale=np.pi,
    unwrap_phase=False,
    unwrap_method="auto",
    remove_phase_piston=True,
    influence_width_in_actuator_pitch=0.55,
    use_circular_actuator_grid=True,
    fit_pixel_step=1,
    actuator_command_limit=None,
    regularization=1e-6,
):
    """
    Apply approximate_slm_phase_with_dm_actuators to a stack of complex fields.

    fields must have shape (field_count, Ny, Nx). The returned dm_fields and
    dm_phases keep that same leading field_count dimension.
    """
    fields = np.asarray(fields)
    if fields.ndim != 3:
        raise ValueError("fields must have shape (field_count, Ny, Nx).")

    results = []
    dm_phases = np.zeros(fields.shape, dtype=np.float64)
    dm_fields = np.zeros(fields.shape, dtype=np.complex128)
    actuator_commands = []
    rms_phase_errors = np.zeros(fields.shape[0], dtype=np.float64)

    for field_index in range(fields.shape[0]):
        result = approximate_slm_phase_with_dm_actuators(
            fields[field_index],
            actuator_count=actuator_count,
            aperture=aperture,
            input_is_field=True,
            phase_scale=phase_scale,
            unwrap_phase=unwrap_phase,
            unwrap_method=unwrap_method,
            remove_phase_piston=remove_phase_piston,
            influence_width_in_actuator_pitch=influence_width_in_actuator_pitch,
            use_circular_actuator_grid=use_circular_actuator_grid,
            fit_pixel_step=fit_pixel_step,
            actuator_command_limit=actuator_command_limit,
            regularization=regularization,
        )
        results.append(result)
        dm_phases[field_index] = result["dm_phase"]
        dm_fields[field_index] = result["dm_field"]
        actuator_commands.append(result["actuator_commands"])
        rms_phase_errors[field_index] = result["rms_phase_error"]

    return {
        "dm_phases": dm_phases,
        "dm_fields": dm_fields,
        "actuator_commands": actuator_commands,
        "rms_phase_errors": rms_phase_errors,
        "single_field_results": results,
    }
