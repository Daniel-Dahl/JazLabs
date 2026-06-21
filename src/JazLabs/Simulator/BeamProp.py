import numpy as np
from scipy.fft import fft, fftfreq, fftshift, fft2,ifft2,rfft2,irfft2

def propagate_to_focal_plane(
    pupil_field: np.ndarray,
    normalize: bool = True,
) -> np.ndarray:
    """Propagate a pupil field to a focal plane with a centred 2D FFT."""

    pupil_field = np.asarray(pupil_field, dtype=complex)
    if pupil_field.ndim != 2:
        raise ValueError("pupil_field must be 2D")

    norm = "ortho" if normalize else None
    return np.fft.fftshift(
        np.fft.fft2(np.fft.ifftshift(pupil_field), norm=norm)
    )
    

def transferFunctionOfFreeSpace(Xgrid,Ygrid,dz,wavelength):
    dims = np.shape(Xgrid);
    Ny = dims[0];
    Nx = dims[1];
    #Setup your k-space co-ordinate system
    # fs = (Nx-1)/((max(max(Xgrid))-min(min(Xgrid))))
    fs = (Nx-1)/(np.max(Xgrid)-np.min(Xgrid))
    v_x =fs*(np.linspace(-Nx/2,Nx/2-1,Nx)/Nx);
    fs = (Ny-1)/(np.max(Ygrid)-np.min(Ygrid));
    v_y =fs*(np.linspace(-Ny/2,Ny/2-1,Ny)/Ny);
    V_x,V_y = np.meshgrid(v_x,v_y);

    #Exponent for the transfer function of free-space
    tfCoef1 = complex(0.0,-1.0)*2.*np.pi*np.sqrt(wavelength**-2-(V_x)**2-V_y**2);

    ##Transfer function of free-space for propagation distance dz
    H0 = np.fft.fftshift(np.exp(tfCoef1*dz));
    return H0
    #Filter the transfer function. Removing any k-components higher than
    #kSpaceFilter*k_max.
    # TH R = np.cart2pol(x,y);
    # kSpaceFilter=1000;
    # maxR = max(max(R));
    
    # H0 = H0*(R<(kSpaceFilter.*maxR));

#propergate the wave forwards
def propagateField(Field,TransferMatrix):
    Dims=np.shape(Field)
    Ny=Dims[0]
    Nx=Dims[1]
    # Convert real-space field, to k-space field
    # FourierField=fft.fftshift(fft.fft2(Field))
    FourierField=(fft2(Field))
    # FourierField=fft.fftshift(fft.fft2(fft.fftshift(Field)))
    #Apply the transfer function of free-space
    FourierField = FourierField*TransferMatrix;
    #Convert k-space field back to real-space
    # Field = fft.fftshift(ifft.fft2(FourierField))
    Fieldnew = (ifft2(FourierField))
    # Field = fft.fftshift(fft.ifft2(fft.fftshift(FourierField)))
    return Fieldnew

import numpy as np

def pad_array(array, new_shape, value=0):
    """
    Pads a 2D array to a new size while keeping it centred.

    Parameters
    ----------
    array : ndarray
        Input 2D array.
    new_shape : tuple
        Desired output shape (Ny, Nx).
    value : scalar
        Padding value (default 0).

    Returns
    -------
    padded : ndarray
        Padded array.
    """
    old_y, old_x = array.shape
    new_y, new_x = new_shape

    if new_y < old_y or new_x < old_x:
        raise ValueError("new_shape must be larger than the input shape")

    pad_y = new_y - old_y
    pad_x = new_x - old_x

    padding = (
        (pad_y // 2, pad_y - pad_y // 2),
        (pad_x // 2, pad_x - pad_x // 2)
    )

    return np.pad(array, padding, mode="constant", constant_values=value)


def crop_array(array, crop_shape, center=None):

    """

    Crop a 2D array around a specified centre.

    Parameters

    ----------

    array : ndarray

        Input 2D array.

    crop_shape : tuple

        Desired output shape (Ny, Nx).

    center : tuple or None

        Centre of the crop (y, x) in pixel coordinates.

        If None, uses the centre of the array.

    Returns

    -------

    cropped : ndarray

        Cropped array.

    """

    ny, nx = array.shape

    crop_y, crop_x = crop_shape

    if center is None:

        center = (ny // 2, nx // 2)

    cy, cx = center

    y_start = cy - crop_y // 2

    y_end = y_start + crop_y

    x_start = cx - crop_x // 2

    x_end = x_start + crop_x

    if y_start < 0 or x_start < 0 or y_end > ny or x_end > nx:

        raise ValueError("Crop region extends outside array boundaries")

    return array[y_start:y_end, x_start:x_end]