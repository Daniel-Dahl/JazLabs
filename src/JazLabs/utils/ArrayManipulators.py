import numpy as np
def apply_circular_aperture(array, center, radius, fill_value=0):
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
    # mask = (x - cx)**2 + (y - cy)**2 <= radius**2
    mask = (x - cx)**2 + (y - cy)**2 >= radius**2

    
    masked_array = np.full_like(array, fill_value)
    masked_array[mask] = array[mask]
    return masked_array