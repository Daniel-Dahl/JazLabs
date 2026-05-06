import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

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
    mask = (x - cx)**2 + (y - cy)**2 <= radius**2
    
    masked_array = np.full_like(array, fill_value)
    masked_array[mask] = array[mask]
    return masked_array


def center_of_mass(array):
    """
    Compute the center of mass of a 2D numpy array.
    
    Parameters
    ----------
    array : np.ndarray
        2D array of values (weights). Must be non-negative if you want
        a meaningful "centre of mass".
    
    Returns
    -------
    (cy, cx) : tuple of floats
        The (row, col) coordinates of the centre of mass.
    """
    array = np.asarray(array, dtype=float)

    total = np.sum(array)
    if total == 0:
        raise ValueError("Array sum is zero; cannot compute centre of mass.")

    # coordinate grids
    rows, cols = array.shape
    y, x = np.arange(rows), np.arange(cols)
    X, Y = np.meshgrid(x, y)

    cx = np.sum(X * array) / total
    cy = np.sum(Y * array) / total

    return int(cy), cx



##################################################
# spot extraction functions
##################################################

def isolate_spot_in_frame(
    img,
    centre_yx,
    radii_px,
    angle=0.0,
    bg_value=0
):
    """
    Return a copy of the full frame with only the chosen (elliptical) spot visible.
    Everything outside the ellipse is set to bg_value.

    Parameters
    ----------
    img : ndarray (H,W) or (H,W,3)
        Input image.
    centre_yx : (float, float)
        Spot centre (y, x) in pixels.
    radii_px : float | (float, float)
        Ellipse semi-axes. If scalar -> circular aperture (ry=rx=value).
        Use (ry, rx) in pixels for elliptical aperture.
    angle : float
        Rotation of ellipse in radians (CCW). 0 aligns with image axes.
    bg_value : int/float
        Value to set outside the aperture (0=black).

    Returns
    -------
    masked_img : ndarray
        Same shape as input, but only the spot remains visible.
    mask : ndarray (H,W) bool
        True inside the aperture, False elsewhere.
    """
    arr = np.asarray(img)
    H, W = arr.shape[:2]
    cy, cx = float(centre_yx[0]), float(centre_yx[1])

    # radii handling
    if np.isscalar(radii_px):
        ry = rx = float(radii_px)
    else:
        ry, rx = float(radii_px[0]), float(radii_px[1])

    # coordinate grids
    yy, xx = np.mgrid[0:H, 0:W]
    yp = yy - cy
    xp = xx - cx

    # rotate coordinates by -angle to test in ellipse frame
    if angle != 0.0:
        ca = np.cos(angle)
        sa = np.sin(angle)
        x_rot =  xp * ca + yp * sa
        y_rot = -xp * sa + yp * ca
    else:
        x_rot, y_rot = xp, yp

    # ellipse test: (y/ry)^2 + (x/rx)^2 <= 1
    mask = (y_rot / ry) ** 2 + (x_rot / rx) ** 2 <= 1.0

    # apply mask
    masked = np.full_like(arr, bg_value)
    if arr.ndim == 2:
        masked[mask] = arr[mask]
    else:
        # apply per channel
        for c in range(arr.shape[2]):
            ch = masked[..., c]
            ch[mask] = arr[..., c][mask]
            masked[..., c] = ch

    return masked, mask

def extract_spot_minimal(img, centre_yx, radii_px, angle=0.0, bg_value=0, return_mask=False):
    """
    Minimal spot extractor with an elliptical aperture.

      - crops a tight square ROI around (y, x) that safely contains the ellipse
      - keeps only pixels inside the rotated ellipse (others set to bg_value)
      - returns the cropped image and the power (sum inside the ellipse)

    Parameters
    ----------
    img : ndarray (H,W) or (H,W,3)
        Image data.
    centre_yx : (float, float)
        Spot centre (y, x) in pixels.
    radii_px : float | (float, float)
        Ellipse semi-axes (ry, rx) in pixels. If a single float is given,
        a circular aperture is used (ry=rx=that value).
    angle : float
        Rotation angle of the ellipse in radians. 0 means major axes aligned
        with image axes. Positive = CCW.
    bg_value : scalar
        Fill value outside the ellipse in the crop.
    return_mask : bool
        If True, also return the boolean mask.

    Returns
    -------
    crop : ndarray
        Cropped image with only the elliptical spot visible.
    power : float
        Sum of intensities inside the ellipse (computed on grayscale if RGB).
    (mask) : ndarray bool
        Returned only if return_mask=True.
    """
    a = np.asarray(img)
    H, W = a.shape[:2]
    cy, cx = float(centre_yx[0]), float(centre_yx[1])

    # Handle radii: allow scalar (circle) or (ry, rx)
    if np.isscalar(radii_px):
        ry = rx = float(radii_px)
    else:
        ry, rx = float(radii_px[0]), float(radii_px[1])

    # Choose a conservative square ROI that contains the rotated ellipse.
    # For rotation, the ellipse fits within a circle of radius hypot(ry, rx).
    R = float(np.hypot(ry, rx)) if angle != 0 else float(max(ry, rx))

    # Clip to image bounds
    y1 = int(max(0, np.floor(cy - R)))
    y2 = int(min(H,  np.ceil (cy + R + 1)))
    x1 = int(max(0, np.floor(cx - R)))
    x2 = int(min(W,  np.ceil (cx + R + 1)))
    if y2 <= y1 or x2 <= x1:
        raise ValueError("Empty crop; check centre/radii and image bounds.")

    # ROI view
    roi = a[y1:y2, x1:x2].copy()
    h, w = roi.shape[:2]

    # Ellipse mask in ROI coordinates
    # Shift coordinates to ellipse centre
    yy, xx = np.mgrid[0:h, 0:w]
    y0 = cy - y1
    x0 = cx - x1
    yp = yy - y0
    xp = xx - x0

    if angle != 0.0:
        ca = np.cos(angle)
        sa = np.sin(angle)
        # Rotate coordinates by -angle to test in ellipse's frame
        x_rot =  xp * ca + yp * sa
        y_rot = -xp * sa + yp * ca
    else:
        x_rot, y_rot = xp, yp

    # Ellipse equation: (y/ry)^2 + (x/rx)^2 <= 1
    # (remember centre_yx ordering)
    mask = (y_rot / ry) ** 2 + (x_rot / rx) ** 2 <= 1.0

    # Compute power on a single-channel version
    if roi.ndim == 3:
        g = roi.mean(axis=2, dtype=np.float32)  # simple luminance proxy
    else:
        g = roi.astype(np.float32, copy=False)
    power = float(g[mask].sum())

    # Make output crop with background outside the ellipse
    crop = np.full_like(roi, bg_value)
    if roi.ndim == 2:
        crop[mask] = roi[mask]
    else:
        for c in range(roi.shape[2]):
            ch = crop[..., c]
            ch[mask] = roi[..., c][mask]
            crop[..., c] = ch

    return (crop, power, mask) if return_mask else (crop, power)

def plotSpots(icenter,frame,Centers,radiusApp,RelPwrOfSpots):
    singlespot_FullArr,_=isolate_spot_in_frame(
    frame,
    Centers[icenter],
    radii_px=radiusApp,
    bg_value=0
)
    singlespot,_=extract_spot_minimal(frame, Centers[icenter], radii_px=radiusApp, bg_value=0, return_mask=False)
    ispotarr=np.arange(0,RelPwrOfSpots.size)
    cx=Centers[icenter,1]
    cy=Centers[icenter,0]
    plt.figure(figsize=(10,4))

    # --- subplot 1
    ax1 = plt.subplot(1,4,1)
    ax1.imshow(singlespot_FullArr, cmap="gray")
    # ax1.add_patch(mpatches.Circle((cx, cy), R,
    #                             fill=False, edgecolor='red', linewidth=2))
    # ax1.plot(cx, cy, 'rx')  # mark the centre

    # --- subplot 2
    ax2 = plt.subplot(1,4,2)
    ax2.imshow(singlespot, cmap="gray")
    # ax2.add_patch(mpatches.Circle((cx, cy), R,
    #                             fill=False, edgecolor='red', linewidth=2))
    # ax2.plot(cx, cy, 'rx')

    # --- subplot 3
    ax3 = plt.subplot(1,4,3)
    ax3.imshow(frame, cmap="gray")
    ax3.add_patch(mpatches.Circle((cx, cy), np.max(radiusApp),
                                fill=False, edgecolor='red', linewidth=2))
    ax3.plot(cx, cy, 'rx')
    
    ax4 = plt.subplot(1,4,4)
    ax4.plot(ispotarr,RelPwrOfSpots)
    ax4.scatter(ispotarr[icenter],RelPwrOfSpots[icenter],c='red', marker='o')

    plt.tight_layout()
    plt.show()
    # plt.figure()
    # plt.subplot(1,3,1)
    # plt.imshow(singlespot_FullArr)
    # plt.subplot(1,3,2)
    # plt.imshow(singlespot)
    # plt.subplot(1,3,3)
    # plt.imshow(frame)
    # plt.plot(Centers[icenter,1],Centers[icenter,0],'r','o')

# Functions for spot center extraction

def _to_gray(img):
    img = np.asarray(img)
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def _auto_invert(gray8):
    p10, p50, p90 = np.percentile(gray8, [10,50,90])
    dark_spots = (p50 - p10) > (p90 - p50)
    return (255 - gray8) if dark_spots else gray8

def _dog(gray8, sig_small, sig_large):
    g1 = cv2.GaussianBlur(gray8, (0,0), sig_small, sig_small, borderType=cv2.BORDER_REFLECT)
    g2 = cv2.GaussianBlur(gray8, (0,0), sig_large, sig_large, borderType=cv2.BORDER_REFLECT)
    return cv2.subtract(g1, g2)

def _refine_centroid(img, yx, r):
    H, W = img.shape
    y0, x0 = float(yx[0]), float(yx[1])
    r = max(2.0, float(r))
    y1, y2 = max(0, int(np.floor(y0 - r))), min(H, int(np.ceil(y0 + r + 1)))
    x1, x2 = max(0, int(np.floor(x0 - r))), min(W, int(np.ceil(x0 + r + 1)))
    if y2 <= y1 or x2 <= x1:
        return y0, x0
    roi = img[y1:y2, x1:x2].astype(np.float32)
    yy, xx = np.mgrid[y1:y2, x1:x2]
    mask = (yy - y0)**2 + (xx - x0)**2 <= r**2
    if not np.any(mask):
        return y0, x0
    vals = roi.copy()
    lo, hi = np.percentile(vals[mask], [5, 99])
    hi = max(hi, lo + 1.0)
    vals = (vals - lo) / (hi - lo)
    vals[~mask] = 0.0
    w = vals.sum()
    if w <= 1e-8:
        return y0, x0
    yc = (yy * vals).sum() / w
    xc = (xx * vals).sum() / w
    return float(yc), float(xc)

def _local_maxima(R, min_radius):
    """Return candidate coords (y,x) and their scores via morphological NMS."""
    rad = max(1, int(round(0.45 * min_radius)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*rad+1, 2*rad+1))
    dil = cv2.dilate(R, kernel)
    lm = (R == dil) & (R > 0)
    ys, xs = np.nonzero(lm)
    scores = R[ys, xs]
    if len(ys) == 0:
        return np.empty((0,2), int), np.empty((0,), float)
    order = np.argsort(-scores)  # high to low
    coords = np.column_stack((ys, xs))[order]
    scores = scores[order]
    return coords, scores

def _estimate_pitch(coords, k=4):
    """Median distance to k-th nearest neighbour (robust pitch)."""
    if len(coords) < k+1:
        return None
    P = coords.astype(float)
    # pairwise squared distances
    d2 = np.sum((P[:,None,:] - P[None,:,:])**2, axis=2)
    d2.sort(axis=1)
    dk = np.sqrt(d2[:, k])  # skip d2[:,0]==0 (self); kth neighbour -> index k
    # robust median; ignore inf/nan
    dk = dk[np.isfinite(dk)]
    if len(dk) == 0:
        return None
    return float(np.median(dk))

def find_spot_centres_targetN(
    img,
    expected_count,
    min_diam_px=4,
    max_diam_px=40,
    num_scales=15,
    start_percentile=85,    # loosen automatically if not enough candidates
    min_percentile=55,
    return_radii=True,
    visualise=False,
    annotate=False
):
    """
    Detect approximately 'expected_count' blob centres on a hex/grid pattern.
    Returns (centres, radii[, overlay]) with centres in (y, x), float.
    """
    gray = _to_gray(img)
    # scale to uint8 for processing
    g = gray.astype(np.float32)
    g = 255.0 * (g - float(np.min(g))) / (float(np.ptp(g)) + 1e-6)
    g8 = g.astype(np.uint8)
    g8 = _auto_invert(g8)  # make spots bright

    rmin, rmax = min_diam_px/2.0, max_diam_px/2.0

    # background flattening
    sig_small = max(0.6, 0.5 * rmin)
    sig_large = max(sig_small * 1.4, 2.2 * rmax)
    bp = _dog(g8, sig_small, sig_large)

    # multi-scale (LoG-like) stack
    sigmas = np.geomspace(max(0.8, rmin/np.sqrt(2)),
                          max(1.2, rmax/np.sqrt(2)),
                          num_scales)
    stack = []
    for s in sigmas:
        blur = cv2.GaussianBlur(bp, (0,0), s, s, borderType=cv2.BORDER_REFLECT)
        lap  = cv2.Laplacian(blur, cv2.CV_32F, ksize=3, scale=1, borderType=cv2.BORDER_REFLECT)
        stack.append((s**2) * (-lap))
    R = np.stack(stack, axis=0)
    Rmax = R.max(axis=0)
    arg  = R.argmax(axis=0)
    best_sigma = sigmas[arg]
    init_r_map = np.sqrt(2.0) * best_sigma  # ~radius per pixel

    # adapt threshold until we get ≥ expected_count candidates
    perc = float(start_percentile)
    coords = np.empty((0,2), int); scores = np.empty((0,), float)
    while perc >= float(min_percentile):
        thr = np.percentile(Rmax, perc)
        Rth = np.where(Rmax >= thr, Rmax, 0.0).astype(np.float32)
        coords, scores = _local_maxima(Rth, rmin)
        if len(coords) >= expected_count:
            break
        perc -= 5.0  # loosen
    # if still too few, take whatever we have
    if len(coords) == 0:
        print('too few points')
        if visualise:
            base8 = gray if gray.dtype == np.uint8 else (255.0*(gray-gray.min())/(float(np.ptp(gray))+1e-6)).astype(np.uint8)
            return (np.zeros((0,2), float), (np.zeros((0,), float), cv2.cvtColor(base8, cv2.COLOR_GRAY2BGR))[0]) if return_radii else (np.zeros((0,2), float), cv2.cvtColor(base8, cv2.COLOR_GRAY2BGR))
        return (np.zeros((0,2), float), np.zeros((0,), float))[0 if not return_radii else slice(0,2)]

    # estimate pitch -> separation
    pitch = _estimate_pitch(coords, k=4)
    if pitch is None:
        pitch = max(3.0, 2.5*rmin)
    sep = 0.70 * pitch  # initial minimum separation
    sep2 = float(sep**2)

    # greedy top-N with separation; relax sep if needed
    def select_with_sep(coords, scores, N, sep2):
        chosen_idx = []
        pts = coords.astype(float)
        for i in range(len(coords)):
            if len(chosen_idx) >= N: break
            p = pts[i]
            ok = True
            for j in chosen_idx:
                q = pts[j]
                if (p[0]-q[0])**2 + (p[1]-q[1])**2 < sep2:
                    ok = False; break
            if ok: chosen_idx.append(i)
        return chosen_idx

    N = int(expected_count)
    picked = select_with_sep(coords, scores, N, sep2)
    relax_steps = 0
    while len(picked) < N and relax_steps < 6:
        sep2 *= 0.8  # relax 20%
        picked = select_with_sep(coords, scores, N, sep2)
        relax_steps += 1

    # if still not enough, just take top-N
    if len(picked) < N:
        picked = list(range(min(N, len(coords))))

    sel = coords[picked]
    # radii from map at those pixels
    init_r = init_r_map[sel[:,0], sel[:,1]]

    # sub-pixel refine on band-passed image
    centres = []
    radii = []
    for (y, x), r in zip(sel, init_r):
        yc, xc = _refine_centroid(bp, (float(y), float(x)), r*0.9)
        centres.append((yc, xc))
        radii.append(float(r))
    centres = np.asarray(centres, float)
    radii   = np.asarray(radii,  float)

    # pack outputs
    if visualise:
        print("test")
        base8 = gray if gray.dtype == np.uint8 else (255.0*(gray-gray.min())/(float(np.ptp(gray))+1e-6)).astype(np.uint8)
        # base8 = _display8(gray, p_low=1, p_high=99, blur_sigma=0.3)
        vis = cv2.cvtColor(base8, cv2.COLOR_GRAY2BGR)
        r_draw = int(max(3, np.median(radii) if len(radii) else rmin))
        for i, (y, x) in enumerate(centres):
            cv2.circle(vis, (int(round(x)), int(round(y))), r_draw, (0,255,0), 1)
            # cv2.drawMarker(vis, (int(round(x)), int(round(y))), (255,200,0),
            #                markerType=cv2.MARKER_TILTED_CROSS, markerSize=8, thickness=1)
            if annotate:
                cv2.putText(vis, str(i), (int(x)+3, int(y)-3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255,0,0), 1, cv2.LINE_AA)
        if return_radii:
            return centres, radii, vis
        else:
            return centres, vis

    if return_radii:
        return centres, radii
    return centres
def _display8(gray, p_low=1, p_high=99, blur_sigma=0.0):
    """Map any grayscale array -> uint8 nicely for viewing (no speckly snow)."""
    g = np.asarray(gray, float)
    # Robust range from percentiles
    lo, hi = np.percentile(g[np.isfinite(g)], [p_low, p_high])
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.nanmin(g)), float(np.nanmax(g)+1e-6)
    g = (g - lo) / (hi - lo)
    g = np.clip(g, 0, 1)
    if blur_sigma and blur_sigma > 0:
        g = cv2.GaussianBlur(g, (0,0), blur_sigma, blur_sigma, borderType=cv2.BORDER_REFLECT)
    return (255.0*g).astype(np.uint8)

def enforce_column_pitch(centres, expected_cols=None, expected_rows=None):
    """
    Snap detected centres onto a rect/hex-like grid with uniform column pitch.
    
    Parameters
    ----------
    centres : (N,2) array of (y, x) floats
    expected_cols : int or None
        If known, number of columns in the hex array. Helps with grouping.
    expected_rows : int or None
        If known, number of rows. Optional.
    
    Returns
    -------
    centres_grid : (N,2) array of (y, x) floats
        Adjusted positions, same order as input.
    pitch_x : float
        Estimated uniform column pitch.
    pitch_y : float
        Estimated row pitch.
    """
    pts = np.asarray(centres, float)
    # First, sort by x (columns)
    order = np.argsort(pts[:,1])
    pts_sorted = pts[order]

    # cluster columns by x coordinate (K-means 1D)
    from sklearn.cluster import KMeans
    ncol = expected_cols if expected_cols else int(round(np.sqrt(len(pts))))
    km = KMeans(n_clusters=ncol, n_init=10, random_state=0)
    labels = km.fit_predict(pts_sorted[:,1:2])
    col_centres = km.cluster_centers_.ravel()
    col_order = np.argsort(col_centres)

    # map each point to a column index
    col_idx = np.array([np.where(col_order==lab)[0][0] for lab in labels])

    # enforce uniform column x positions
    pitch_x = np.median(np.diff(np.sort(col_centres)))
    x0 = np.min(col_centres)
    col_x_positions = x0 + np.arange(ncol)*pitch_x
    adjusted = []
    for (y,x), ci in zip(pts_sorted, col_idx):
        newx = col_x_positions[ci]
        adjusted.append((y, newx))
    adjusted = np.array(adjusted)

    # (optional) enforce uniform row pitch per column
    pitch_y = None
    if expected_rows:
        # cluster within each column
        all_adj = []
        for ci in range(ncol):
            ycol = adjusted[col_idx==ci,0]
            if len(ycol) < 2: continue
            y0 = np.min(ycol)
            pitch_y = np.median(np.diff(np.sort(ycol)))
            y_positions = y0 + np.arange(len(ycol))*pitch_y
            y_positions = np.sort(y_positions)
            # snap each to nearest
            snapped = []
            for yy in ycol:
                j = np.argmin(np.abs(y_positions-yy))
                snapped.append(y_positions[j])
            mask = (col_idx==ci)
            adjusted[mask,0] = snapped
        all_adj = adjusted

    # unsort back to original order
    centres_grid = np.empty_like(pts)
    centres_grid[order] = adjusted
    return centres_grid, pitch_x, pitch_y
import numpy as np

def order_spot_centres(centres, row_tol=0.5):
    """
    Order spot centres into a consistent row-by-row, left-to-right order.

    Parameters
    ----------
    centres : (N,2) array-like
        List/array of (y, x) positions.
    row_tol : float
        Tolerance for grouping rows, as a fraction of the median vertical pitch.
        e.g. 0.5 means centres within 50% of pitch in y are considered one row.

    Returns
    -------
    ordered : (N,2) ndarray
        Centres sorted row by row (top-to-bottom, left-to-right).
    rows : list of arrays
        Row-wise groups of centres (each a subarray of ordered).
    """
    pts = np.asarray(centres, float)
    if len(pts) == 0:
        return pts, []

    # 1. Estimate vertical pitch
    ys = np.sort(pts[:,0])
    dy = np.diff(ys)
    pitch_y = np.median(dy[dy>0]) if np.any(dy>0) else 1.0

    # 2. Group into rows by y coordinate
    sorted_idx = np.argsort(pts[:,0])
    rows = []
    current_row = [sorted_idx[0]]
    for i in sorted_idx[1:]:
        if abs(pts[i,0] - pts[current_row[-1],0]) < row_tol*pitch_y:
            current_row.append(i)
        else:
            rows.append(current_row)
            current_row = [i]
    rows.append(current_row)

    # 3. Sort each row by x coordinate
    ordered_idx = []
    for row in rows:
        row_sorted = sorted(row, key=lambda j: pts[j,1])
        ordered_idx.extend(row_sorted)

    ordered = pts[ordered_idx]
    row_groups = [pts[row] for row in rows]

    return ordered, row_groups

def order_spot_centres_by_column_lattice(centres, expected_cols=None):
    """
    Robust column-major ordering for (y, x) spot centres.

    - Fits a uniform grid in x: x ≈ off + k * pitch  (k ∈ Z)
    - Assigns each point to nearest column index k
    - Sorts columns left→right and rows top→bottom

    Parameters
    ----------
    centres : (N,2) array-like of (y, x)
    expected_cols : int or None
        If known, the number of columns. Helps when there are gaps/outliers.

    Returns
    -------
    ordered : (N,2) float
        Centres sorted column-by-column (then by y).
    columns : list[np.ndarray]
        List of per-column arrays (each sorted by y).
    info : dict
        {'pitch_x','offset_x','column_index','residuals','ncols_est'}
    """
    pts = np.asarray(centres, float)
    if pts.size == 0:
        return pts, [], {'pitch_x': np.nan, 'offset_x': np.nan, 'ncols_est': 0,
                         'column_index': np.array([], int), 'residuals': np.array([], float)}

    y = pts[:, 0]
    x = pts[:, 1]

    # --- robust pitch estimate in x ---
    xs = np.sort(x)
    dx = np.diff(xs)
    dx = dx[dx > 0]
    if dx.size == 0:
        pitch = 1.0
    else:
        # ignore large gaps; take median of smaller spacings
        q = np.quantile(dx, 0.6)
        small = dx[dx <= q]
        pitch = float(np.median(small if small.size else dx))
        pitch = max(pitch, 1.0)

    # rough columns count from span if not provided
    span = xs[-1] - xs[0] if xs.size else 0.0
    ncols_est = int(round(span / pitch)) + 1 if span > 0 else 1
    if expected_cols is not None:
        ncols_est = int(expected_cols)

    # --- search best offset in [xmin, xmin + pitch) to minimise L1 residual ---
    offs = np.linspace(xs[0], xs[0] + pitch, 121, endpoint=False)
    def score(off):
        k = np.floor((x - off) / pitch + 0.5)  # nearest integer index
        r = x - (off + k * pitch)
        return np.median(np.abs(r))
    off = float(offs[np.argmin([score(o) for o in offs])])

    # assign integer column indices
    k = np.floor((x - off) / pitch + 0.5).astype(int)
    k -= k.min()  # start from 0
    residuals = x - (off + k * pitch)

    # small local repair: if a point is > ~0.35*pitch from its column, push to neighbour
    bad = np.abs(residuals) > 0.35 * pitch
    if np.any(bad):
        k[bad] += np.sign(residuals[bad]).astype(int)
        residuals = x - (off + k * pitch)

    # --- final ordering: by column (k asc), then by y (asc) ---
    order_idx = np.lexsort((y, k))
    ordered = pts[order_idx]

    # build per-column groups (each sorted by y)
    columns = []
    for col in range(k.min(), k.max() + 1):
        idx = np.where(k == col)[0]
        idx = idx[np.argsort(y[idx])]
        if idx.size:
            columns.append(pts[idx])

    info = {
        'pitch_x': pitch,
        'offset_x': off,
        'ncols_est': ncols_est,
        'column_index': k,
        'residuals': residuals
    }
    return ordered, columns, info

def order_spot_centres_by_column(centres, col_tol=0.5):
    """
    Order spot centres column by column (left-to-right),
    and within each column top-to-bottom.

    Parameters
    ----------
    centres : (N,2) array-like
        Array of (y, x) positions.
    col_tol : float
        Tolerance for grouping columns, as a fraction of the median horizontal pitch.

    Returns
    -------
    ordered : (N,2) ndarray
        Centres sorted column-by-column.
    cols : list of arrays
        Column-wise groups of centres.
    """
    pts = np.asarray(centres, float)
    if len(pts) == 0:
        return pts, []

    # 1. Estimate horizontal pitch
    xs = np.sort(pts[:,1])
    dx = np.diff(xs)
    pitch_x = np.median(dx[dx > 0]) if np.any(dx > 0) else 1.0

    # 2. Group into columns by x coordinate
    sorted_idx = np.argsort(pts[:,1])
    cols = []
    current_col = [sorted_idx[0]]
    for i in sorted_idx[1:]:
        if abs(pts[i,1] - pts[current_col[-1],1]) < col_tol*pitch_x:
            current_col.append(i)
        else:
            cols.append(current_col)
            current_col = [i]
    cols.append(current_col)

    # 3. Sort each column by y coordinate
    ordered_idx = []
    for col in cols:
        col_sorted = sorted(col, key=lambda j: pts[j,0])
        ordered_idx.extend(col_sorted)

    ordered = pts[ordered_idx]
    col_groups = [pts[col] for col in cols]

    return ordered, col_groups
def swap_centres(centres, oldIdx, newIdx):
    """
    Swap two entries in a (N,2) centres array.

    Parameters
    ----------
    centres : ndarray (N,2)
        Array of (y, x) coordinates.
    i, j : int
        Indices of the two rows to swap.

    Returns
    -------
    swapped : ndarray (N,2)
        Copy of centres with i and j swapped.
    """
    centresold = np.asarray(centres).copy()
    centres[newIdx,:]=centresold[oldIdx,:]
    centres[oldIdx,:]=centresold[newIdx,:]
    
    return centres
def PowerOfEachSpot(frame,SpotCenters,radiusApp=6):
    spotCount=SpotCenters.shape[0]
    RelativePowerOfEachSpot=np.zeros(spotCount)
    Totalpwr=0
    for ispot in range(spotCount):
        singlespot,spotpwr=extract_spot_minimal(frame,SpotCenters[ispot], radii_px=radiusApp)
        RelativePowerOfEachSpot[ispot]=spotpwr
        Totalpwr=Totalpwr+spotpwr
    RelativePowerOfEachSpot=RelativePowerOfEachSpot/Totalpwr
    return RelativePowerOfEachSpot,Totalpwr