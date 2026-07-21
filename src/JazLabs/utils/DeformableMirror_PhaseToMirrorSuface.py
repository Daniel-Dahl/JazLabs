import numpy as np
import matplotlib.pyplot as plt


def make_dm_grid(pupil_radius_px, n_act_across=12):
    """
    Approximate ALPAO DM97 actuator layout:
    11x11 grid with actuators inside a circular pupil.
    """
    coords = np.linspace(-pupil_radius_px, pupil_radius_px, n_act_across)
    xx, yy = np.meshgrid(coords, coords)

    x_act = xx.ravel()
    y_act = yy.ravel()

    r = np.sqrt(x_act**2 + y_act**2)

    # Keep actuators inside circular pupil.
    # This gives approximately the DM97-style geometry.
    keep = r <= pupil_radius_px * 1.05

    return x_act[keep], y_act[keep]


def make_influence_matrix(x_act, y_act, X, Y, sigma_px, pupil_mask):
    """
    Create Gaussian influence functions for each actuator.
    Returns matrix B where each column is one actuator influence function.
    """
    pixels = np.where(pupil_mask.ravel())[0]
    B = []

    for xa, ya in zip(x_act, y_act):
        influence = np.exp(-((X - xa)**2 + (Y - ya)**2) / (2 * sigma_px**2))
        B.append(influence.ravel()[pixels])

    B = np.array(B).T
    return B, pixels


def slm_phase_to_dm_phase(
    phi_slm,
    wavelength=1.55e-6,
    pupil_mask=None,
    n_act_across=11,
    influence_sigma_actuator_pitch=0.6,
    unwrap=False,
    max_surface_stroke=None,
):
    """
    Convert an SLM phase mask into a DM-realizable phase mask.

    Parameters
    ----------
    phi_slm : 2D array
        Desired SLM phase in radians.
    wavelength : float
        Wavelength in metres.
    pupil_mask : 2D bool array
        Pupil aperture mask.
    n_act_across : int
        Number of actuators across the diameter. DM97 ~ 11.
    influence_sigma_actuator_pitch : float
        Width of Gaussian influence functions in actuator pitch units.
    max_surface_stroke : float or None
        Optional max absolute actuator surface stroke in metres.

    Returns
    -------
    phi_dm : 2D array
        DM-smoothed phase in radians.
    actuator_commands : 1D array
        Fitted actuator surface heights in metres.
    """

    Ny, Nx = phi_slm.shape

    y = np.arange(Ny) - Ny // 2
    x = np.arange(Nx) - Nx // 2
    X, Y = np.meshgrid(x, y)

    if pupil_mask is None:
        R = min(Nx, Ny) * 0.5
        pupil_mask = X**2 + Y**2 <= R**2
    else:
        R = np.sqrt(np.max((X[pupil_mask])**2 + (Y[pupil_mask])**2))

    # Unwrap phase approximately in 2D
    if unwrap:
        phi = np.unwrap(np.unwrap(phi_slm, axis=0), axis=1)
    else:
        phi=phi_slm

    # Convert phase to DM surface height.
    # Reflection: phase = 4*pi*h / wavelength
    h_target = wavelength * phi / (4 * np.pi)

    # DM actuator grid
    x_act, y_act = make_dm_grid(R, n_act_across=n_act_across)

    actuator_pitch_px = 2 * R / (n_act_across - 1)
    sigma_px = influence_sigma_actuator_pitch * actuator_pitch_px

    # Influence matrix
    B, pixels = make_influence_matrix(
        x_act, y_act, X, Y, sigma_px=sigma_px, pupil_mask=pupil_mask
    )

    y_target = h_target.ravel()[pixels]

    # Least-squares fit actuator commands
    actuator_commands, *_ = np.linalg.lstsq(B, y_target, rcond=None)

    # Optional stroke clipping
    if max_surface_stroke is not None:
        actuator_commands = np.clip(
            actuator_commands,
            -max_surface_stroke,
            max_surface_stroke
        )

    # Reconstruct DM surface
    h_fit_flat = B @ actuator_commands

    h_dm = np.zeros_like(phi_slm, dtype=float)
    h_dm.ravel()[pixels] = h_fit_flat

    # Convert back to phase
    phi_dm = 4 * np.pi * h_dm / wavelength

    return phi_dm, actuator_commands, pupil_mask



