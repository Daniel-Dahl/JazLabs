import numpy as np
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

import numpy as np

def fourier_plane_coords(Nx, Ny, dx, dy, wavelength, f):
    """
    Coordinates in the focal plane of a lens performing a Fourier transform.

    Nx, Ny      : number of pixels in input field
    dx, dy      : input-plane pixel size [m]
    wavelength : wavelength [m]
    f          : lens focal length [m]

    returns Xf, Yf, xf, yf, dxf, dyf
    """

    fx = np.fft.fftshift(np.fft.fftfreq(Nx, d=dx))  # cycles/m
    fy = np.fft.fftshift(np.fft.fftfreq(Ny, d=dy))  # cycles/m

    xf = wavelength * f * fx
    yf = wavelength * f * fy

    dxf = xf[1] - xf[0]
    dyf = yf[1] - yf[0]

    Xf, Yf = np.meshgrid(xf, yf)

    return Xf, Yf, xf, yf, dxf, dyf