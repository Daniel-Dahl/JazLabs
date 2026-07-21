import numpy as np
def rectangular_aperture(array, width, height, center_x_idx, center_y_idx, aperture_value=1):
    """
    Creates a rectangular aperture in a given 2D array with a specified value inside the aperture.
    Ensures the aperture does not wrap around the edges of the array, using indices for center position.

    Parameters:
    - array: 2D numpy array in which the aperture will be created
    - width: Width of the rectangular aperture
    - height: Height of the rectangular aperture
    - center_x_idx: Index of the center of the aperture in the x direction (0 to array.shape[1]-1)
    - center_y_idx: Index of the center of the aperture in the y direction (0 to array.shape[0]-1)
    - aperture_value: Value to fill within the aperture (default is 1)

    Returns:
    - aperture: 2D numpy array with the aperture applied
    """
    grid_size_y, grid_size_x = array.shape

    # Calculate the index ranges for the aperture
    half_width_idx = width // 2
    half_height_idx = height // 2

    x_start = max(center_x_idx - half_width_idx, 0)
    x_end = min(center_x_idx + half_width_idx, grid_size_x - 1)
    y_start = max(center_y_idx - half_height_idx, 0)
    y_end = min(center_y_idx + half_height_idx, grid_size_y - 1)

    # Apply the rectangular aperture with the specified value
    aperture = array.copy()
    aperture[y_start:y_end, x_start:x_end] = aperture_value

    return aperture

def circular_aperture(array, radius, center_x_idx, center_y_idx, aperture_value=1):
    """
    Creates a circular aperture in a given 2D array with a specified value inside the aperture.
    Ensures the aperture does not wrap around the edges of the array, using indices for center position.

    Parameters:
    - array: 2D numpy array in which the aperture will be created
    - radius: Radius of the circular aperture
    - center_x_idx: Index of the center of the aperture in the x direction (0 to array.shape[1]-1)
    - center_y_idx: Index of the center of the aperture in the y direction (0 to array.shape[0]-1)
    - aperture_value: Value to fill within the aperture (default is 1)

    Returns:
    - aperture: 2D numpy array with the aperture applied
    """
    grid_size_y, grid_size_x = array.shape

    # Create a 2D grid with coordinates
    y, x = np.ogrid[:grid_size_y, :grid_size_x]

    # Calculate distance from the center for each point in the grid
    distance_from_center = np.sqrt((x - center_x_idx) ** 2 + (y - center_y_idx) ** 2)

    # Apply the circular aperture with the specified value
    aperture = array.copy()
    aperture[distance_from_center <= radius] = aperture_value

    return aperture