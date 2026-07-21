import numpy as np

def OneOn_e_Squred_1d(values):
    max_value = np.max(values)
    threshold = max_value / np.exp(2)  # Calculate the 1/e^2 point
    # threshold = np.min(values)  # Calculate the 1/e^2 point
    
    indices = np.where(values > threshold)[0]
    
    if len(indices) < 2:
        raise ValueError("Cannot calculate 1/e^2 width: Distribution might not be unimodal.")
    
    return indices[0],indices[-1] ,indices[-1] - indices[0]

def fwhm_1d(values):
    max_value = np.max(values)
    threshold = max_value / 2  # Calculate the 1/e^2 point
    # threshold = np.min(values)  # Calculate the 1/e^2 point
    
    indices = np.where(values > threshold)[0]
    
    if len(indices) < 2:
        raise ValueError("Cannot calculate 1/e^2 width: Distribution might not be unimodal.")
    
    return indices[0],indices[-1] ,indices[-1] - indices[0]

def fwhm_2d(z):
    """
    Calculate the FWHM of a 2D distribution by finding the FWHM along the x and y axes.
    
    Args:
    - x: 1D array of x-coordinates.
    - y: 1D array of y-coordinates.
    - z: 2D array of values (e.g., intensity).
    
    Returns:
    - The FWHM along the x and y axes.
    """
    # FWHM along x-axis
    z_y_sum = np.sum(z, axis=0)
    minx,maxx,fwhm_x = fwhm_1d(z_y_sum)
    # FWHM along y-axis
    z_x_sum = np.sum(z, axis=1)
    miny,maxy,fwhm_y = fwhm_1d(z_x_sum)
    
    Index_val=np.asarray([[minx,maxx],[miny,maxy]])
    return Index_val, fwhm_x, fwhm_y
# widthx,widthy=fwhm_2d(xArr, yArr, np.abs(MODES[-1,:,:]**2))
# # widthx,widthy=fwhm_2d(xArr, yArr, np.abs(ModeSumcomplex)**2)
# # widthx,widthy=fwhm_2d(xArr, yArr, ModeSum)

# print(widthx//2,widthy//2,(widthx//2+widthy//2)/2)
# # print(widthx/(2*np.sqrt(2*np.log(2))))
