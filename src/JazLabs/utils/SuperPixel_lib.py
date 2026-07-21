import numpy as np
def set_superpixel(arr, ix, iy, superpixel_size, phase_value):
    """
    Set all values in a given superpixel block to a new value.

    Parameters
    ----------
    arr : 2D np.ndarray
        The array to modify.
    ix, iy : int
        Superpixel indices (not pixel indices).
    superpixel_size : int
        Size of each superpixel block (square).
    value : scalar or complex
        New value to assign to that superpixel.

    Returns
    -------
    arr : 2D np.ndarray
        The modified array (same object, modified in-place).
    """
    arr_new=np.copy(arr)
    # print(superpixel_size)
    x_start = ix * superpixel_size
    x_end   = x_start + superpixel_size
    y_start = iy * superpixel_size
    y_end   = y_start + superpixel_size
 
    arr_new[y_start:y_end, x_start:x_end] = (arr[y_start:y_end, x_start:x_end])*np.exp(phase_value*1j)
    return arr_new

def make_superpixel_map(
    shape: tuple[int, int],
    n_superpixels_x: int,
    n_superpixels_y: int,
    pupil_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Divide a pupil into rectangular labelled superpixels.

    Pixels outside the pupil are labelled ``-1``. A superpixel receives a compact
    index only if at least one of its pixels overlaps the pupil.
    """
    # def _validate_shape(shape: tuple[int, int]) -> tuple[int, int]:
    # if len(shape) != 2:
    #     raise ValueError("shape must be a 2-tuple")
    # height, width = int(shape[0]), int(shape[1])
    # if height < 1 or width < 1:
    #     raise ValueError("shape dimensions must be positive")
    # return height, width

    # height, width = _validate_shape(shape)
    height, width = int(shape[0]), int(shape[1])
    if n_superpixels_x < 1 or n_superpixels_y < 1:
        raise ValueError("superpixel counts must be positive")

    if pupil_mask is None:
        valid = np.ones((height, width), dtype=bool)
    else:
        if pupil_mask.shape != (height, width):
            raise ValueError("pupil_mask shape must match shape")
        valid = np.asarray(pupil_mask) > 0

    labels = np.full((height, width), -1, dtype=int)
    y_edges = np.linspace(0, height, n_superpixels_y + 1, dtype=int)
    x_edges = np.linspace(0, width, n_superpixels_x + 1, dtype=int)

    mode_idx = 0
    for iy in range(n_superpixels_y):
        y0, y1 = y_edges[iy], y_edges[iy + 1]
        for ix in range(n_superpixels_x):
            x0, x1 = x_edges[ix], x_edges[ix + 1]
            cell_valid = valid[y0:y1, x0:x1]
            if np.any(cell_valid):
                block = labels[y0:y1, x0:x1]
                block[cell_valid] = mode_idx
                mode_idx += 1

    return labels