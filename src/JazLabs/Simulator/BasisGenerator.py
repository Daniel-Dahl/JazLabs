import numpy as np
def make_hadamard_basis(n_modes: int) -> tuple[np.ndarray, np.ndarray]:
    """Return unnormalised and unit-norm Hadamard bases with entries +-1.

    ``n_modes`` must be a positive power of two. Padding can be added later when
    needed, but raising here keeps the measurement dimension explicit.
    """

    if n_modes < 1:
        raise ValueError("n_modes must be positive")
    if n_modes & (n_modes - 1):
        raise ValueError("n_modes must be a power of two for Hadamard modes")

    basis = np.array([[1]], dtype=int)
    while basis.shape[0] < n_modes:
        basis = np.block([[basis, basis], [basis, -basis]])
    return basis, basis.astype(float) / np.sqrt(n_modes)