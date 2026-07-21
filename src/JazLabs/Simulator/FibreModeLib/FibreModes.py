import numpy as np
from scipy.special import jn, kn, jn_zeros

# Multi core fibre array
def MultiCoreFibreHexGridCenters(n_rings, spacing=1.0):
    """
    Generate a symmetric hexagonally-shaped array (a perfect hexagonal grid cut into a hexagon),
    centered at (0, 0), built from concentric hexagonal rings.

    Parameters:
        n_rings (int): Number of hexagonal rings around the center (0 = just the center).
        spacing (float): Distance between nearest-neighbour spots.

    Returns:
        coords (ndarray): Array of (x, y) positions, ordered by ring and clockwise from +Y.
    """
    coords = []

    # Hex lattice basis vectors (axial coordinates)
    for q in range(-n_rings, n_rings + 1):
        r_min = max(-n_rings, -q - n_rings)
        r_max = min(n_rings, -q + n_rings)
        for r in range(r_min, r_max + 1):
            # Convert axial hex coords (q, r) to cartesian (x, y)
            x = spacing * (np.sqrt(3) * q + np.sqrt(3)/2 * r)
            y = spacing * (3/2 * r)
            coords.append((x, y))

    coords = np.array(coords)

    # Now sort by ring number (distance from centre in hex coords)
    def hex_distance(xy):
        x, y = xy
        # convert back to axial coords
        q = (np.sqrt(3)/3 * x - 1/3 * y) / spacing
        r = (2/3 * y) / spacing
        s = -q - r
        return int(round(max(abs(q), abs(r), abs(s))))

    # And then clockwise angle from +Y axis
    def clockwise_angle(xy):
        angle = np.arctan2(xy[0], xy[1])  # NOTE: x and y swapped
        return angle % (2 * np.pi)

    # Final sort: first by ring distance, then clockwise angle
    coords = sorted(coords, key=lambda xy: (hex_distance(xy), clockwise_angle(xy)))
    return np.array(coords)

# the defult values are based on a SMF-28 fibre for 1550nm
def SingleModeFibreArray(spot_centers,XGrid,YGrid, wavelength=1550e-9,core_radius=5.2e-6, n_core=1.452, n_clad=1.447):
    spotCount=spot_centers.shape[0]
    Nx,Ny=XGrid.shape
    TotalSpotArray=np.zeros((spotCount,Ny,Nx),dtype=complex)
    for ispot in range(spotCount):
        XGrid_shifted=XGrid+spot_centers[ispot,0]
        YGrid_shifted=YGrid+spot_centers[ispot,1]
        
        # TotalSpotArray[ispot,:,:]=GaussBeams.GenerateLGMode(SMF_mfd, wavelength, 0,0, pixel_size,XGrid_shifted, YGrid_shifted, 0, 0)
        TotalSpotArray[ispot,:,:]=LPMode(0, 1,'a', XGrid_shifted, YGrid_shifted, 
                      core_radius, wavelength, n_core, n_clad)
    return TotalSpotArray

import numpy as np
from scipy.special import jn, jn_zeros

def LPMode_free(l=0, m=1, ab='a',
                XGrid=None, YGrid=None,
                core_radius=None,xcenter=0,ycenter=0):     # "
    """
    Generate a complex index-free LP_lm^a / LP_lm^b mode (no refractive indices).

    This is similar to LPMode(...) but:
      - Ignores wavelength, n_core, n_clad (no fibre V-number).
      - Uses only J_l with the m-th zero u_lm to set the radial structure.
      - Optionally tapered smoothly beyond core_radius instead of a true cladding tail.

    Parameters:
        l, m        : mode indices
        ab          : 'a' -> cos(lθ), 'b' -> sin(lθ)
        XGrid,YGrid : meshgrid arrays (same units; typically metres)
        core_radius : sets the radial scale (same units as XGrid/YGrid)
        wavelength, n_core, n_clad : accepted but ignored (kept for drop-in use)

    Returns:
        fieldNorm   : complex-valued LP_lm field, L2 normalised on the grid
    """
    if XGrid is None or YGrid is None:
        raise ValueError("XGrid and YGrid must be provided.")
    if core_radius is None:
        raise ValueError("core_radius must be provided (just a size scale here).")

    pixelSize = XGrid[0, 1] - XGrid[0, 0]

    r = np.sqrt((XGrid+xcenter)**2 + (YGrid+ycenter)**2)
    theta = np.arctan2(YGrid, XGrid)

    # Convert to higher precision
    r = np.double(r)
    theta = np.double(theta)

    # Bessel zero for this (l, m)
    u_lm = jn_zeros(l, m)[-1]

    # Pure core-like radial profile (no cladding physics)
    core_field = jn(l, u_lm * r / core_radius)

    # Smooth taper outside the "core" so it doesn't just hard-cut:
    # (you can comment this out if you want a strict top-hat core)
    taper = np.exp(-(r / (1.0 * core_radius + 1e-32))**8)
    # taper =1# np.exp(-(r / (1.1 * core_radius + 1e-32))**8)

    radial = core_field * taper

    # Angular dependence with explicit π phase jumps (LP_lm^a / LP_lm^b)
    if l == 0:
        if ab == 'a':
            angular = np.ones_like(XGrid, dtype=np.complex64)  # constant phase
        elif ab == 'b':
            raise ValueError("LP_0m has no 'b' variant (no angular dependence).")
    else:
        if ab == 'a':
            # cos(lθ) = (e^{i lθ} + e^{-i lθ}) / 2
            angular = 0.5 * (np.exp(1j * l * theta) + np.exp(-1j * l * theta))
        elif ab == 'b':
            # sin(lθ) = (e^{i lθ} - e^{-i lθ}) / (2i)
            angular = 0.5j * (np.exp(1j * l * theta) - np.exp(-1j * l * theta))
        else:
            raise ValueError("ab must be 'a' or 'b'.")

    # Optional extra scaling (as in your original code)
    angular *= 0.5

    field = (radial * angular).astype(np.complex64)

    # L2 normalisation on the continuous grid
    norm = np.sqrt(np.sum(np.abs(field)**2) * pixelSize**2 + 1e-32)
    fieldNorm = field / norm

    return fieldNorm

def LPMode(l=0, m=1,ab='a', XGrid=None, YGrid=None, 
           core_radius=None, wavelength=None, n_core=None, n_clad=None):
    """
    Generate a complex LP_lm mode with π phase jumps between lobes.

    Parameters:
        l, m       : mode indices
        x, y       : meshgrid arrays
        core_radius: fibre core radius (m)
        wavelength : operating wavelength (m)
        n_core     : core index
        n_clad     : cladding index
        variant    : 'a' for cos(lθ), 'b' for sin(lθ)
    Returns:
        Complex-valued LP_lm field
    """
    pixelSize=XGrid[0,1]-XGrid[0,0]
    r = np.sqrt(XGrid**2 + YGrid**2)
    theta = np.arctan2(YGrid, XGrid)
    # convet to higher precsion
    r=np.double(r)
    theta=np.double(theta)
    
    k0 = 2 * np.pi / wavelength
    V = k0 * core_radius * np.sqrt(n_core**2 - n_clad**2)

    # Find the u_lm zero of the Bessel function J_l
    u_lm = jn_zeros(l, m)[-1]
    w_lm = np.sqrt(V**2 - u_lm**2)

    # Amplitude matching (same as before)
    Jl_u = jn(l, u_lm)
    Kl_w = kn(l, w_lm)
    a_lm = 1.0
    print(Kl_w)
    print(Jl_u)
    if Kl_w==0 or Jl_u==0:
        b_lm=0
    else:
        b_lm = a_lm * Jl_u / Kl_w

    core_field = a_lm * jn(l, u_lm * r / core_radius)
    clad_field = b_lm * kn(l, w_lm * r / core_radius)
    radial = np.where(r <= core_radius, core_field, clad_field)

    # Angular dependence with explicit π phase jumps
    if l == 0:
        if ab == 'a':
            angular = np.ones_like(XGrid, dtype=np.complex64)  # constant phase
        elif ab == 'b':
            raise ValueError("LP modes have no 'b' variant (no angular dependence)")
    else:
        if ab == 'a':
            angular = 0.5 * (np.exp(1j * l * theta) + np.exp(-1j * l * theta))  # cos(lθ)
        elif ab == 'b':
            angular = 0.5j * (np.exp(1j * l * theta) - np.exp(-1j * l * theta))  # sin(lθ)
        else:
            raise ValueError("variant must be 'a' or 'b'")

    angular *= 0.5  # scale for true cos/sin

    field = (radial * angular).astype(np.complex64)
    # field.astype(np.complex64)
    fieldNorm=field/np.sqrt(np.sum(np.abs(field)**2)*pixelSize**2)
    return fieldNorm



def Vnumber(core_radius, wavelength, n_core, n_clad,Na=None):
    """Calculate V number for LP mode (l, m)"""
    k0 = 2 * np.pi / wavelength
    if Na is not None:
        V = k0 * core_radius * Na
    else:
        V = k0 * core_radius * np.sqrt(n_core**2 - n_clad**2)
        
    return V
    # u_lm = jn_zeros(l, m)[-1]  # m-th zero of J_l
    # return V * u_lm / (k0 * core_radius)


def SortLPModesByModeGroupMLAB(modes):
    """
    Sort LP mode dictionaries by mode_group, then m, then l, then ab.

    Parameters:
        modes: iterable of dictionaries with keys 'mode_group', 'l', 'm', and 'ab'

    Returns:
        sorted_modes: list of mode dictionaries in the requested order
    """
    return sorted(
        modes,
        key=lambda mode: (
            mode['mode_group'],
            mode['m'],
            mode['l'],
            mode['ab'],
        )
    )


def AllowedLPModes(core_radius, wavelength, n_core, n_clad,Na=None, max_l=6, max_m=4):
    """
    Return a list of guided LP modes for a given fibre.

    Parameters:
        core_radius : float (in metres)
        wavelength  : float (in metres)
        n_core      : core refractive index
        n_clad      : cladding refractive index
        max_l       : maximum azimuthal index to check
        max_m       : maximum radial index to check

    Returns:
        modes: list of dictionaries with keys:
               'l', 'm', 'mode_group', 'V_cutoff', 'guided'
    """
    V = Vnumber(core_radius, wavelength, n_core, n_clad,Na)
    modes = []
    modeCount = 0
    for l in range(0, max_l + 1):
        zeros = jn_zeros(l, max_m)
        for m, u_lm in enumerate(zeros, start=1):
            V_cutoff = u_lm
            guided = V > V_cutoff
            mode_group = l + 2 * (m - 1)
            if guided:
                modes.append({
                    'l': l,
                    'm': m,
                    'ab':'a',
                    'mode_group': mode_group,
                    'V_cutoff': V_cutoff,
                    'V': V,
                    'guided': guided
                })
                modeCount += 1
                if l != 0:
                    modes.append({
                    'l': l,
                    'm': m,
                    'ab':'b',
                    'mode_group': mode_group,
                    'V_cutoff': V_cutoff,
                    'V': V,
                    'guided': guided
                })
                    modeCount += 1
                    
    modes = SortLPModesByModeGroupMLAB(modes)
    return modes, modeCount

# Limitations for BPM stability 
def fresnel_number_per_step(w0, wavelength, dz):
    """
    Compute the Fresnel number per BPM step.

    Parameters:
        w0        : beam waist [m] (beam waist of LP01)
        wavelength: wavelength [m]
        dz        : propagation step size [m]

    Returns:
        Fresnel number (dimensionless)
    """
    fresnelNum = (w0 ** 2) / (wavelength * dz)
    dz_fresnelNum15000 = w0**2/(wavelength * 15000)

    return fresnelNum,dz_fresnelNum15000

def max_stable_dz(dx, wavelength, n0):
    """
    Compute the maximum dz step size to ensure BPM stability.

    Parameters:
        dx        : Transvers spatial step size [m]
        wavelength: wavelength [m]
        n0        : reference refractive index

    Returns:
        Maximum dz [m] for stable propagation
    """
    return (n0 * dx**2) / wavelength

def field_overlap(E1, E2, dx):
    """
    Calculate the complex spatial overlap (fidelity) between two fields.

    Parameters:
        E1, E2 : complex 2D numpy arrays (same shape)
        dx     : spatial step size (assumes square pixels)

    Returns:
        overlap : float, value between 0 and 1
    """
    num = np.sum(np.conj(E1) * E2) * dx**2
    denom = np.sqrt(np.sum(np.abs(E1)**2) * np.sum(np.abs(E2)**2)) * dx**2
    overlap_normed = (num / denom)
    overlap = (num )

    return overlap,overlap_normed
