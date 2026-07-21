import numpy as np
def apply_circular_aperture(array, center, radius, fill_value=0,Invert=False):
    """
    Apply a circular aperture to a 2D numpy array.
    
    Parameters:
    -----------
    array : np.ndarray
        Input 2D array (e.g., image or data field).
    center : tuple of (float, float)
        (row, col) coordinates of the circle centre.
    radius : float
        Radius of the circular aperture (in pixels).
    fill_value : number, optional
        Value to assign outside the aperture (default = 0).
    
    Returns:
    --------
    masked_array : np.ndarray
        Array with circular aperture applied.
    """
    rows, cols = array.shape
    y, x = np.ogrid[:rows, :cols]
    
    cy, cx = center
    if Invert:
        mask = (x - cx)**2 + (y - cy)**2 <= radius**2
    else:
        mask = (x - cx)**2 + (y - cy)**2 >= radius**2

    
    masked_array = np.full_like(array, fill_value)
    masked_array[mask] = array[mask]
    return masked_array

def apply_square_aperture(
    frame: np.ndarray,
    centre=None,
    x_half_width=None,
    y_half_width=None,
):
    """
    Return ROI (aperture) from frame.

    Parameters
    ----------
    frame : np.ndarray
    centre : (cy, cx)
    x_half_width, y_half_width : int/float

    Returns
    -------
    roi : np.ndarray
    bounds : (y0, y1, x0, x1)
    """

    if centre is None or x_half_width is None or y_half_width is None:
        return frame, (0, frame.shape[0], 0, frame.shape[1])

    cy, cx = centre
    nrows, ncols = frame.shape

    y0 = max(int(cy - y_half_width), 0)
    y1 = min(int(cy + y_half_width), nrows)
    x0 = max(int(cx - x_half_width), 0)
    x1 = min(int(cx + x_half_width), ncols)

    roi = frame[y0:y1, x0:x1]

    return roi, (y0, y1, x0, x1)

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