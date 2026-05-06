import numpy as np
from dataclasses import dataclass
from typing import Optional, Tuple
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt


import numpy as np

def one_over_e2_width(x, y, baseline=None):
    """
    Compute 1/e^2 width of a (possibly inverted) single Gaussian-like lobe.

    Parameters
    ----------
    x : 1D array (monotonic, not necessarily uniform)
    y : 1D array
    baseline : float or None
        If None, estimated robustly from the outer 1/8th of x on both ends.

    Returns
    -------
    x_left, x_right, width_x, i_left, i_right, width_idx
    """
    x = np.asarray(x, float).ravel()
    y = np.asarray(y, float).ravel()
    if x.size != y.size:
        raise ValueError("x and y must have same length")

    # If the user didn't give a baseline...
    if baseline is None:
        # sort the data by x (in case it's not monotonic already)
        idx = np.argsort(x)
        y_s = y[idx]

        # take about 1/8th of the points from the left and right edges
        q = max(1, len(y)//8)

        # concatenate those edge values and take the median
        baseline = float(np.median(np.r_[y_s[:q], y_s[-q:]]))

    # Peak detection around the dominant lobe (handles inverted peaks)
    dy = y - baseline
    i0 = int(np.argmax(np.abs(dy)))
    A = float(dy[i0])  # signed amplitude
    if A == 0:
        raise ValueError("Cannot determine peak amplitude.")

    # Threshold at 1/e^2 of the peak *relative to baseline*
    # y_thresh = C + A * exp(-2) (works for A>0 and A<0)
    y_thresh = baseline + A * np.exp(-2)

    # Search left crossing from the peak
    i_left = i0
    while i_left > 0 and ((y[i_left] - y_thresh) * (y[i_left-1] - y_thresh) > 0):
        i_left -= 1
    if i_left == 0 and ((y[i_left] - y_thresh) * (y[i_left+1] - y_thresh) > 0):
        raise ValueError("Left 1/e^2 crossing not found.")

    # Linear interpolate left crossing (between i_left-1 and i_left)
    def interp_cross(i1, i2):
        x1, y1 = x[i1], y[i1]
        x2, y2 = x[i2], y[i2]
        if y1 == y2:
            return 0.5*(x1 + x2)
        t = (y_thresh - y1) / (y2 - y1)
        return x1 + t*(x2 - x1)

    x_left = interp_cross(i_left-1, i_left)

    # Search right crossing from the peak
    i_right = i0
    n = len(y)
    while i_right < n-1 and ((y[i_right] - y_thresh) * (y[i_right+1] - y_thresh) > 0):
        i_right += 1
    if i_right == n-1 and ((y[i_right] - y_thresh) * (y[i_right-1] - y_thresh) > 0):
        raise ValueError("Right 1/e^2 crossing not found.")

    x_right = interp_cross(i_right, i_right+1)

    width_x = float(x_right - x_left)

    # Also report an index-width (useful if x is uniform)
    # Use fractional indices based on local linear mapping
    def frac_index(i1, i2, xc):
        # map xc linearly to a fractional index between i1 and i2
        if x[i2] == x[i1]:
            return 0.5*(i1 + i2)
        t = (xc - x[i1]) / (x[i2] - x[i1])
        return i1 + t

    iL_frac = frac_index(i_left-1, i_left, x_left)
    iR_frac = frac_index(i_right, i_right+1, x_right)
    width_idx = float(iR_frac - iL_frac)

    return x_left, x_right, width_x, i_left, i_right, width_idx


def OneOn_e_Squred_1d(values):
    max_value = np.max(values)
    threshold = max_value / np.exp(2)  # Calculate the 1/e^2 point
    # threshold = np.min(values)  # Calculate the 1/e^2 point
    
    indices = np.where(values > threshold)[0]
    
    if len(indices) < 2:
        raise ValueError("Cannot calculate 1/e^2 width: Distribution might not be unimodal.")
    min_index = indices[0]
    max_index = indices[-1]
    OneOn_e_Squred_1d_width = max_index - min_index
    return  min_index, max_index, OneOn_e_Squred_1d_width

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



def _gauss(x, A, x0, sigma, C):
    # A can be positive or negative; sigma > 0; C is baseline
    return A * np.exp(-0.5 * ((x - x0) / sigma) ** 2) + C

@dataclass
class GaussFit:
    A: float          # amplitude (can be negative)
    x0: float         # centre
    sigma: float      # standard deviation (>0)
    C: float          # offset (baseline)
    FWHM: float       # full width at half maximum = 2*sqrt(2*ln2)*sigma
    cov: Optional[np.ndarray]  # covariance matrix from curve_fit (or None)

def gaussian_widths(Gaussin_SD_sigma: float):
    """
    Given the Gaussian standard deviation sigma, return the common width measures.

    Parameters
    ----------
    sigma : float
        Standard deviation of the Gaussian.

    Returns
    -------
    GaussianWidths dataclass with:
      - FWHM (full width at half maximum)
      - one_over_e (width at 1/e intensity)
      - one_over_e2 (width at 1/e^2 intensity, common in laser optics)
    """
    FWHM = 2*np.sqrt(2*np.log(2)) * Gaussin_SD_sigma
    one_over_e = 2*np.sqrt(2) * Gaussin_SD_sigma
    one_over_e2 = 4 * Gaussin_SD_sigma
    return FWHM, one_over_e, one_over_e2

def fit_gaussian(x: np.ndarray,
                 y: np.ndarray,
                 weights: Optional[np.ndarray] = None,
                 bounds: Optional[Tuple[Tuple[float, float, float, float],
                                        Tuple[float, float, float, float]]] = None,
                 PlotResult=True) -> GaussFit:
    """
    Fit y(x) to A*exp(-0.5*((x-x0)/sigma)^2) + C.
    Handles 'upside down' Gaussians (A < 0) and returns σ and FWHM.

    Parameters
    ----------
    x, y : 1D arrays
    weights : optional 1D array of 1/σ_y (inverse stdev). If given, χ²-weighted fit is used.
    bounds : optional ((Amin,x0min,sigmamin,Cmin),(Amax,x0max,sigmamax,Cmax))

    Returns
    -------
    GaussFit dataclass with A, x0, sigma, C, FWHM, cov.
    """

    x = np.asarray(x, float).ravel()
    y = np.asarray(y, float).ravel()
    if x.size != y.size:
        raise ValueError("x and y must have the same length.")

    # Drop NaNs/Infs if present
    m = np.isfinite(x) & np.isfinite(y)
    if weights is not None:
        w = np.asarray(weights, float).ravel()
        if w.size != x.size:
            raise ValueError("weights must have same length as x and y.")
        m &= np.isfinite(w)
        w = w[m]
    x, y = x[m], y[m]

    if x.size < 4:
        raise ValueError("Need at least 4 valid points to fit a Gaussian.")

    # Heuristic initial guesses
    # Baseline from the lower-variance half of the data (robust to inverted peaks)
    # Simple and effective: use median of the outer quartiles
    idx = np.argsort(x)
    x_s, y_s = x[idx], y[idx]
    q = max(1, x_s.size // 8)
    baseline_guess = np.median(np.r_[y_s[:q], y_s[-q:]])

    # Decide if peak is up or down relative to baseline
    dy = y - baseline_guess
    i_peak = np.argmax(np.abs(dy))
    A_guess = dy[i_peak]  # retains sign (positive or negative)
    x0_guess = x[i_peak]

    # Rough sigma guess from half-power width on |dy|
    abs_dy = np.abs(dy)
    half = 0.5 * np.max(abs_dy)
    # Find points where |dy| crosses half max
    above = abs_dy >= half
    if np.any(above):
        # indices of first and last crossing region
        i_left = np.argmax(above)                 # first True
        i_right = len(above) - 1 - np.argmax(above[::-1])  # last True
        if i_right > i_left:
            sigma_guess = (x[i_right] - x[i_left]) / (2.0 * np.sqrt(2 * np.log(2)))
        else:
            sigma_guess = (np.ptp(x) or 1.0) / 6.0
    else:
        sigma_guess = (np.ptp(x) or 1.0) / 6.0

    # Bounds
    if bounds is None:
        # Let amplitude be anything; keep sigma positive and reasonable; centre within data span
        xmin, xmax = float(np.min(x)), float(np.max(x))
        span = xmax - xmin if xmax > xmin else 1.0
        bounds = ((-np.inf, xmin - 0.5 * span, 1e-12, -np.inf),
                  ( np.inf, xmax + 0.5 * span, 10 * span,  np.inf))

    p0 = [A_guess, x0_guess, max(1e-6, float(sigma_guess)), baseline_guess]

    # Fit
    if weights is not None:
        sigma_y = 1.0 / np.maximum(w, 1e-300)  # convert weights to y-uncertainties
        popt, pcov = curve_fit(_gauss, x, y, p0=p0, bounds=bounds, sigma=sigma_y, absolute_sigma=True, maxfev=20000)
    else:
        popt, pcov = curve_fit(_gauss, x, y, p0=p0, bounds=bounds, maxfev=20000)

    A, x0, sigma, C = popt
    sigma = float(abs(sigma))  # enforce positive width
    FWHM = 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma
    fit=GaussFit(A=float(A), x0=float(x0), sigma=sigma, C=float(C), FWHM=float(FWHM), cov=pcov)

    if PlotResult:
        x_fit = np.linspace(x.min(), x.max(), 1000)
        y_fit = fit.A * np.exp(-0.5 * ((x_fit - fit.x0) / fit.sigma)**2) + fit.C

        # Plot
        plt.figure(figsize=(6,4))
        plt.scatter(x, y, s=12, label="Data", color="black")
        plt.plot(x_fit, y_fit, 'r-', lw=2, label=f"Gaussian fit\nσ={fit.sigma:.3f}, FWHM={fit.FWHM:.3f}")
        plt.axvline(fit.x0, color="blue", ls="--", lw=1, label="Centre")
        plt.legend()
        plt.xlabel("x")
        plt.ylabel("y")
        plt.title("Gaussian Fit")
        plt.tight_layout()
        plt.show()

    return fit
