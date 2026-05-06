import numpy as np
import matplotlib.pyplot as plt

def LensPhaseProf(focalLen,wavelength,XGrid,YGrid):
    focusFactorX=(np.pi/(wavelength*focalLen))
    focusFactorY=(np.pi/(wavelength*focalLen))
    LensProf=np.exp(1j*(( (focusFactorX)*XGrid**2) + (focusFactorY)*YGrid**2))
    return LensProf
def TiltPhaseProf(tiltXdeg,tiltYdeg,wavelength,XGrid,YGrid):
    #This function takes in degrees since it is easier to understand
    k0 = 2.0*np.pi/wavelength;
    pixelSize= XGrid[0,1]-XGrid[0,0]
    #k_i_limit=2*pixelSize/(np.pi*wavelength)
    #print(k_i_limit)
    #This is the limit that the angle can be
    theta_limit= np.arcsin(wavelength/(2.0*pixelSize))*180.0/np.pi
    print('Angle limit for pixel ',theta_limit)
    
    ky0 = k0*np.sin(tiltYdeg* np.pi/180)
    kx0 = k0*np.sin(tiltXdeg* np.pi/180) 
    tiltProf=np.exp(1j*(( (kx0)*XGrid) + (ky0)*YGrid))
    return tiltProf

def PiFlipMasks(Nx,Ny,planeCount,PlotMasks):
    if planeCount>1:
        modeCountTotal= (planeCount-1)*2
        Masks=np.ones([modeCountTotal,planeCount,Ny,Nx],dtype=np.csingle)
        PiFlipHorzt=np.ones([Ny,Nx],dtype=np.csingle)
        PiFlipVert=np.ones([Ny,Nx],dtype=np.csingle)
        # print(np.shape(PiFlipHorzt))
        PiFlipHorzt[:,0:int((Nx/2))]=PiFlipHorzt[:,0:int((Nx/2))]*np.exp(1j*np.pi/2)
        PiFlipHorzt[:,int((Nx/2)):Nx]=PiFlipHorzt[:,int((Nx/2)):Nx]*np.exp(1j*(np.pi/2+np.pi))
        PiFlipVert[0:int((Nx/2)),:]=PiFlipVert[0:int((Nx/2)),:]*np.exp(1j*np.pi/2)
        PiFlipVert[int((Ny/2)):Ny,:]=PiFlipVert[int((Ny/2)):Ny,:]*np.exp(1j*(np.pi/2+np.pi))

        imodeIdx=0
        for iplane in range(planeCount-1):
            for imode in range(2):
                if (imode==0):
                    Masks[imodeIdx,planeCount-1,:,:]=PiFlipHorzt
                    Masks[imodeIdx,iplane,:,:]=PiFlipVert
                else:
                    Masks[imodeIdx,planeCount-1,:,:]= PiFlipVert
                    Masks[imodeIdx,iplane,:,:] = PiFlipHorzt
                imodeIdx=imodeIdx+1
        if (PlotMasks):
            for imode in range(modeCountTotal):
                plt.figure(imode)
                for iplane in range(planeCount):
                    plt.subplot(1,8,iplane+1)
                    plt.imshow(np.angle(Masks[imode,iplane,:,:]))
                    plt.axis('off')  
    else:
        modeCountTotal=2
        Masks=np.ones((modeCountTotal,planeCount,Ny,Nx),dtype=np.csingle)
        top_phase = np.pi
        bottom_phase = 2*np.pi
        # Create the mask top half
        Masks[0, 0, :Ny//2, :] =Masks[0, 0, :Ny//2, :] *np.exp(1j * top_phase)
       # # Create the mask bottom half
        Masks[0, 0, Ny//2:, :] = Masks[0, 0, Ny//2:, :] *np.exp(1j * bottom_phase)
        
        # Create the mask Right half
        right_phase = np.pi
        left_phase = 2*np.pi
        Masks[1, 0, :, Nx//2:] = Masks[1, 0, :, Nx//2:]*np.exp(1j * right_phase)
        # # Create the mask left half
        Masks[1, 0, :, :Nx//2] =Masks[1, 0, :, :Nx//2]*np.exp(1j * left_phase)
        if (PlotMasks):
            for imode in range(modeCountTotal):
                plt.figure(imode)
                plt.imshow(np.angle(Masks[imode,iplane,:,:]))
                plt.axis('off')  

    return Masks

def TiltMask(tiltXdeg,tiltYdeg,wavelength,Nx,Ny,pixelSize,PlotMasks):
    ymin = (((-(Ny - 1)) / 2.0)) * pixelSize;
    ymax = (((Ny - 1) / 2.0)) * pixelSize;
    y=np.linspace(ymin,ymax,Ny)
    xmin = (((-(Nx - 1)) / 2.0)) * pixelSize;
    xmax = (((Nx - 1) / 2.0)) * pixelSize;
    x=np.linspace(xmin,xmax,Nx)
    XGrid, YGrid= np.meshgrid(x,y)
    TiltPhase=TiltPhaseProf(tiltXdeg,tiltYdeg,wavelength,XGrid,YGrid)
    norm = (np.sqrt(sum(sum(np.abs(TiltPhase)**2))*pixelSize*pixelSize))
    TiltPhase=TiltPhase/norm
    # print(np.sqrt(sum(sum(np.abs(FocalPhase)**2))*pixelSize*pixelSize))
    if (PlotMasks):
        plt.figure()
        plt.imshow((np.angle(TiltPhase)))
        plt.figure()
        plt.imshow((abs(TiltPhase)))
    Masks=np.ones((1,1,Ny,Nx),dtype=np.csingle)
    Masks[0,0,:,:]=TiltPhase
    return Masks 

def LenMask(focalLen,wavelength,Nx,Ny,pixelSize,PlotMasks):
    ymin = (((-(Ny - 1)) / 2.0)) * pixelSize;
    ymax = (((Ny - 1) / 2.0)) * pixelSize;
    y=np.linspace(ymin,ymax,Ny)
    xmin = (((-(Nx - 1)) / 2.0)) * pixelSize;
    xmax = (((Nx - 1) / 2.0)) * pixelSize;
    x=np.linspace(xmin,xmax,Nx)
    XGrid, YGrid= np.meshgrid(x,y)
    FocalPhase=LensPhaseProf(focalLen,wavelength,XGrid,YGrid)
    norm = (np.sqrt(sum(sum(np.abs(FocalPhase)**2))*pixelSize*pixelSize))
    FocalPhase=FocalPhase/norm
    # print(np.sqrt(sum(sum(np.abs(FocalPhase)**2))*pixelSize*pixelSize))
    if (PlotMasks):
        plt.figure()
        plt.imshow((np.angle(FocalPhase)))
        plt.figure()
        plt.imshow((abs(FocalPhase)))
    Masks=np.ones((1,1,Ny,Nx),dtype=np.csingle)
    Masks[0,0,:,:]=FocalPhase
    return Masks 

def SpiralMask(SpiralNum,Nx,Ny,pixelSize,PlotMasks):
    # Pixel counts of the masks and simulation in 
    # Setup mask Cartesian co-ordinates/0.5 pixel 
    ymin = (((-(Ny - 1)) / 2.0)) * pixelSize;
    ymax = (((Ny - 1) / 2.0)) * pixelSize;
    y=np.linspace(ymin,ymax,Ny)
    xmin = (((-(Nx - 1)) / 2.0)) * pixelSize;
    xmax = (((Nx - 1) / 2.0)) * pixelSize;
    x=np.linspace(xmin,xmax,Nx)
    XGrid, YGrid= np.meshgrid(x,y)
    THGrid=np.arctan2(YGrid,XGrid)

    l=SpiralNum
    spiralPhasePaten = np.empty(np.shape(XGrid), dtype=complex)
    THGrid=np.arctan2(YGrid,XGrid)
    # spiralPhasePaten=np.exp(complex(0.0,1.0) *(  l * THGrid + (l + 2 * m + 1) ));
    spiralPhasePaten=np.exp(complex(0.0,1.0) *(  l * THGrid  ));
    if (PlotMasks):
        plt.figure()
        plt.imshow((np.angle(spiralPhasePaten)))

    Masks=np.ones((1,1,Ny,Nx),dtype=np.csingle)
    Masks[0,0,:,:]=spiralPhasePaten
    return Masks

def random_superpixel_phase(Nx,Ny, superpixel_size=8):
    """
    Generate a random phase mask with super-pixels.

    Parameters
    ----------
    shape : tuple
        Final array size (rows, cols).
    superpixel_size : int
        Size of each square super-pixel block.

    Returns
    -------
    np.ndarray
        Complex array with random phases in np.csingle dtype.
    """
    
    # Number of blocks along each dimension
    blocks = (Ny//superpixel_size, Nx//superpixel_size)
    
    # Random phases for each block in [0, 2π)
    phases = 2*np.pi*np.random.rand(*blocks)
    
    # Expand to full resolution with kron
    mask = np.kron(np.exp(1j*phases), np.ones((superpixel_size, superpixel_size)))
    
    # Crop in case shape not divisible by block size
    mask = mask[:Ny, :Nx]
    Masks=np.ones((1,1,Ny,Nx),dtype=np.csingle)
    Masks[0,0,:,:]=mask
    return Masks

import numpy as np

def binary_stripe_phase(
    Nx: int,
    Ny: int,
    stripe_width: int = 8,
    phase_value: float = 0.0,
    orientation: str = "vertical",
):
    """
    Generate a binary phase mask with alternating stripes:
    [phase_value, -pi, phase_value, -pi, ...]

    Parameters
    ----------
    Nx, Ny : int
        Output size (cols, rows).
    stripe_width : int
        Stripe width in pixels.
    phase_value : float
        Phase (radians) for every second stripe.
    orientation : {"vertical", "horizontal"}
        Direction of stripes.

    Returns
    -------
    np.ndarray
        Complex mask of shape (1, 1, Ny, Nx), dtype np.csingle.
    """
    if orientation not in ("vertical", "horizontal"):
        raise ValueError("orientation must be 'vertical' or 'horizontal'")

    if orientation == "vertical":
        stripe_idx = np.arange(Nx) // stripe_width          # (Nx,)
        phases = np.where(stripe_idx % 2 == 0,
                          phase_value,
                          -np.pi)
        phase_map = np.tile(phases, (Ny, 1))                # (Ny, Nx)
    else:
        stripe_idx = np.arange(Ny) // stripe_width          # (Ny,)
        phases = np.where(stripe_idx % 2 == 0,
                          phase_value,
                          -np.pi)
        phase_map = np.tile(phases[:, None], (1, Nx))       # (Ny, Nx)

    mask = np.exp(1j * phase_map).astype(np.csingle)

    Masks = np.ones((1, 1, Ny, Nx), dtype=np.csingle)
    Masks[0, 0, :, :] = mask
    return Masks



def von_karman_phase_screen(
    N: int,
    dx: float,
    r0: float,
    L0: float = np.inf,
    seed: int | None = None,
    remove_piston: bool = False,
    remove_tilt: bool = False,
):
    """
    Generate a von Kármán phase screen phi(x,y) in radians on an NxN grid.

    N  : grid size (e.g. 512)
    dx : sample spacing in metres (e.g. 17e-6 for 17 µm)
    r0 : Fried parameter (metres) at the SAME wavelength you're modelling
    L0 : outer scale (metres). Use np.inf for pure Kolmogorov.
    """

    rng = np.random.default_rng(seed)

    # Spatial frequency grid (cycles/m -> rad/m)
    fx = np.fft.fftfreq(N, d=dx)  # cycles/m
    fy = np.fft.fftfreq(N, d=dx)
    FX, FY = np.meshgrid(fx, fy, indexing="xy")
    kx = 2 * np.pi * FX
    ky = 2 * np.pi * FY
    k = np.sqrt(kx**2 + ky**2)

    # von Kármán outer scale term
    if np.isfinite(L0):
        k0 = 2 * np.pi / L0
    else:
        k0 = 0.0

    # Phase PSD (rad^2 * m^2) in rad/m domain
    # Avoid singularity at k=0 by setting it to 0 power (we can keep piston via the random DC if desired,
    # but physical von Kármán usually has finite power; in practice DC is arbitrary piston anyway).
    PSD_phi = 0.023 * (r0 ** (-5/3)) * (k**2 + k0**2) ** (-11/6)
    PSD_phi[k == 0] = 0.0

    # Complex white noise in Fourier domain
    cn = (rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))) / np.sqrt(2.0)

    # Fourier-domain amplitude scaling:
    # ifft2 in numpy has a 1/N^2 factor, so we scale accordingly.
    delta_k = 2 * np.pi / (N * dx)  # rad/m spacing in k-space
    fourier_field = cn * np.sqrt(PSD_phi) * delta_k

    # Inverse FFT to spatial phase (real)
    phi = np.fft.ifft2(fourier_field).real * (N**2)

    # Optionally remove piston and/or tilt
    if remove_piston or remove_tilt:
        x = (np.arange(N) - (N - 1) / 2) * dx
        y = (np.arange(N) - (N - 1) / 2) * dx
        X, Y = np.meshgrid(x, y, indexing="xy")

        # Fit plane: a + bX + cY
        A = np.stack([np.ones_like(X).ravel(), X.ravel(), Y.ravel()], axis=1)
        coeff, *_ = np.linalg.lstsq(A, phi.ravel(), rcond=None)
        a, b, c = coeff
        plane = (a + b * X + c * Y)

        if remove_piston and remove_tilt:
            phi = phi - plane
        elif remove_piston and not remove_tilt:
            phi = phi - a
        elif (not remove_piston) and remove_tilt:
            phi = phi - (b * X + c * Y)

    return phi


def turbulence_complex_mask(
    N: int = 512,
    pitch_um: float = 17.0,
    r0: float = 2e-3,
    L0: float = 30.0,
    seed: int | None = None,
):
    dx = pitch_um * 1e-6
    phi = von_karman_phase_screen(N=N, dx=dx, r0=r0, L0=L0, seed=seed,
                                  remove_piston=False, remove_tilt=False)
    M = np.exp(1j * phi)  # complex unit-modulus mask
    return phi, M