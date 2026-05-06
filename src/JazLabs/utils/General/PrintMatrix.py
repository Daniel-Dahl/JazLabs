def print_matrix(matrix, precision=4, padding=8):
    """
    Prints a 2D matrix (list of lists or NumPy array) in a nicely aligned format.

    Parameters:
    - matrix: 2D list or numpy array
    - precision: number of decimal places to show for floats
    - padding: width of each column (in characters)
    """
    matrix = np.array(matrix)
    rows, cols = matrix.shape

    for row in matrix:
        line = ""
        for val in row:
            if isinstance(val, float):
                formatted = f"{val:.{precision}f}".rjust(padding)
            else:
                formatted = str(val).rjust(padding)
            line += formatted
        print(line)