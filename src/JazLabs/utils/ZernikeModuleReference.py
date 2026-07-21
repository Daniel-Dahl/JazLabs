import numpy as np
from math import factorial
from enum import IntEnum


class ZernCoefs(IntEnum):
    PISTON = 0
    TILTX = 1
    TILTY = 2
    ASTIGX = 3
    DEFOCUS = 4
    ASTIGY = 5
    TREFOILX = 6
    COMAX = 7
    COMAY = 8
    TREFOILY = 9
    SPHERICAL = 12


def make_unit_disk_coordinates(Nx=256, Ny=256, aperture_radius_in_pixels=None):
    """
    Build a pixel-centred coordinate grid with rho=1 at the aperture radius.

    The returned disk_mask must be used for inner products. Zernike
    orthogonality is defined over the unit disk, not over the full square.
    """
    if aperture_radius_in_pixels is None:
        aperture_radius_in_pixels = min(Nx, Ny) / 2.0

    x_pixels = np.arange(Nx, dtype=np.float64) - (Nx - 1) / 2.0
    y_pixels = np.arange(Ny, dtype=np.float64) - (Ny - 1) / 2.0
    X_pixels, Y_pixels = np.meshgrid(x_pixels, y_pixels)

    x = X_pixels / aperture_radius_in_pixels
    y = Y_pixels / aperture_radius_in_pixels
    rho = np.sqrt(x**2 + y**2)
    theta = np.arctan2(y, x)
    disk_mask = rho <= 1.0

    return rho, theta, disk_mask


def zernike_radial_polynomial(rho, n, m):
    m_abs = abs(m)
    if n < 0 or m_abs > n or (n - m_abs) % 2 != 0:
        return np.zeros_like(rho, dtype=np.float64)

    radial = np.zeros_like(rho, dtype=np.float64)
    for k in range((n - m_abs) // 2 + 1):
        numerator = (-1) ** k * factorial(n - k)
        denominator = (
            factorial(k)
            * factorial((n + m_abs) // 2 - k)
            * factorial((n - m_abs) // 2 - k)
        )
        radial += (numerator / denominator) * rho ** (n - 2 * k)

    return radial


def zernike_polynomial(rho, theta, disk_mask, n, m, normalize=True):
    """
    Return the real-valued Zernike mode Z_n^m on the unit disk.

    Sign convention matches the existing ZernikeModule:
    m < 0 uses sin(abs(m) * theta), and m > 0 uses cos(m * theta).
    With normalize=True these modes are orthonormal in the continuous
    unit-disk inner product (1/pi) * integral_disk Zi * Zj dA.
    """
    radial = zernike_radial_polynomial(rho, n, m)

    if m < 0:
        mode = radial * np.sin(abs(m) * theta)
    elif m > 0:
        mode = radial * np.cos(m * theta)
    else:
        mode = radial

    if normalize:
        if m == 0:
            mode = mode * np.sqrt(n + 1)
        else:
            mode = mode * np.sqrt(2 * (n + 1))

    mode = np.where(disk_mask, mode, 0.0)
    return mode


def zernike_nm_sequence(max_zernike_radial_number):
    nm_sequence = []
    for n in range(max_zernike_radial_number + 1):
        for m in range(-n, n + 1, 2):
            nm_sequence.append((n, m))
    return nm_sequence


class ReferenceZernikes:
    """
    Small reference implementation for comparing against ZernikeModule.py.

    Use `zernike_basis_array` for mathematical orthogonality checks. Use
    `make_zernike_field()` only when you really want a complex phase field.
    """

    def __init__(
        self,
        max_zernike_radial_number=4,
        Nx=256,
        Ny=256,
        aperture_radius_in_pixels=None,
        normalize=True,
    ):
        self.max_zernike_radial_number = max_zernike_radial_number
        self.Nx = Nx
        self.Ny = Ny
        self.normalize = normalize

        self.rho, self.theta, self.disk_mask = make_unit_disk_coordinates(
            Nx=Nx,
            Ny=Ny,
            aperture_radius_in_pixels=aperture_radius_in_pixels,
        )

        self.nm_sequence = zernike_nm_sequence(max_zernike_radial_number)
        self.zernCount = len(self.nm_sequence)
        self.zernike_basis_list = []
        self.zernike_basis_array = np.zeros((self.zernCount, Ny, Nx), dtype=np.float64)

        for mode_index, (n, m) in enumerate(self.nm_sequence):
            mode = zernike_polynomial(
                self.rho,
                self.theta,
                self.disk_mask,
                n,
                m,
                normalize=normalize,
            )
            self.zernike_basis_list.append([mode, n, m])
            self.zernike_basis_array[mode_index] = mode

        self.zern_coefs = np.zeros(self.zernCount, dtype=np.float64)

    def make_zernike_phase(self):
        phase = np.zeros((self.Ny, self.Nx), dtype=np.float64)
        for mode_index in range(self.zernCount):
            phase += self.zern_coefs[mode_index] * self.zernike_basis_array[mode_index]
        return np.where(self.disk_mask, phase, 0.0)

    def make_zernike_field(self):
        phase = self.make_zernike_phase()
        field = np.exp(1j * np.pi * phase)
        return np.where(self.disk_mask, field, 0.0)


def gram_matrix_from_modes(modes, aperture=None):
    modes = np.asarray(modes)
    if aperture is not None:
        modes = modes * aperture[None, :, :]

    flat_modes = modes.reshape(modes.shape[0], -1).astype(np.complex128)
    mode_norms = np.sqrt(np.sum(np.abs(flat_modes) ** 2, axis=1))
    flat_modes = flat_modes / mode_norms[:, None]
    return flat_modes.conj() @ flat_modes.T


def decompose_field_phase_into_zernikes(
    fields,
    zernikes,
    mode_indices=None,
    aperture=None,
    phase_scale=np.pi,
):
    """
    Fit the phase of one or more complex fields with the Zernike basis.

    fields can have shape (Ny, Nx) or (field_count, Ny, Nx). The returned
    coefficients have the full zernikes.zernCount length, so they can be copied
    straight into zernikes.zern_coefs.

    This fits:

        angle(field) / phase_scale ~= sum_k coef[k] * Z_k

    For fields made by make_zernike_field(), phase_scale should stay as pi.
    """
    fields = np.asarray(fields)
    single_field_input = fields.ndim == 2

    if single_field_input:
        fields = fields[None, :, :]

    if fields.ndim != 3:
        raise ValueError("fields must have shape (Ny, Nx) or (field_count, Ny, Nx).")

    if fields.shape[1:] != (zernikes.Ny, zernikes.Nx):
        raise ValueError("field shape does not match the zernike grid size.")

    if mode_indices is None:
        mode_indices = list(range(1, zernikes.zernCount))
    else:
        mode_indices = list(mode_indices)

    if aperture is None:
        aperture = zernikes.disk_mask
    else:
        aperture = np.asarray(aperture, dtype=bool)

    basis_matrix = zernikes.zernike_basis_array[mode_indices, :, :]
    basis_matrix = basis_matrix[:, aperture].T

    all_coefficients = np.zeros((fields.shape[0], zernikes.zernCount), dtype=np.float64)
    residual_sums = np.zeros(fields.shape[0], dtype=np.float64)
    ranks = np.zeros(fields.shape[0], dtype=int)
    singular_values_by_field = []

    for field_index in range(fields.shape[0]):
        field_phase = np.angle(fields[field_index]) / phase_scale
        measured_phase_values = field_phase[aperture]

        coefficients, residuals, rank, singular_values = np.linalg.lstsq(
            basis_matrix,
            measured_phase_values,
            rcond=None,
        )

        for coefficient, mode_index in zip(coefficients, mode_indices):
            all_coefficients[field_index, mode_index] = coefficient

        if residuals.size > 0:
            residual_sums[field_index] = residuals[0]

        ranks[field_index] = rank
        singular_values_by_field.append(singular_values)

    if single_field_input:
        return all_coefficients[0], residual_sums[0], ranks[0], singular_values_by_field[0]

    return all_coefficients, residual_sums, ranks, singular_values_by_field


def make_phase_from_zernike_coefficients(zernikes, coefficients):
    coefficients = np.asarray(coefficients, dtype=np.float64)

    if coefficients.shape[0] != zernikes.zernCount:
        raise ValueError("coefficients must have length zernikes.zernCount.")

    phase = np.zeros((zernikes.Ny, zernikes.Nx), dtype=np.float64)
    for mode_index in range(zernikes.zernCount):
        phase += coefficients[mode_index] * zernikes.zernike_basis_array[mode_index]

    return np.where(zernikes.disk_mask, phase, 0.0)


def make_field_from_zernike_coefficients(zernikes, coefficients, phase_scale=np.pi):
    phase = make_phase_from_zernike_coefficients(zernikes, coefficients)
    field = np.exp(1j * phase_scale * phase)
    return np.where(zernikes.disk_mask, field, 0.0)


def print_reference_orthogonality_report(max_zernike_radial_number=4, Nx=256, Ny=256):
    zernikes = ReferenceZernikes(
        max_zernike_radial_number=max_zernike_radial_number,
        Nx=Nx,
        Ny=Ny,
        normalize=True,
    )

    polynomial_gram = gram_matrix_from_modes(
        zernikes.zernike_basis_array,
        aperture=zernikes.disk_mask,
    )
    polynomial_off_diagonal = polynomial_gram - np.eye(zernikes.zernCount)

    phase_fields = np.zeros((zernikes.zernCount, Ny, Nx), dtype=np.complex128)
    for mode_index in range(zernikes.zernCount):
        zernikes.zern_coefs[:] = 0.0
        zernikes.zern_coefs[mode_index] = 1.0
        phase_fields[mode_index] = zernikes.make_zernike_field()

    field_gram = gram_matrix_from_modes(phase_fields, aperture=zernikes.disk_mask)
    field_off_diagonal = field_gram - np.eye(zernikes.zernCount)

    print("Mode ordering:")
    for mode_index, (n, m) in enumerate(zernikes.nm_sequence):
        print(f"{mode_index:2d}: n={n}, m={m}")

    print()
    print("Real Zernike polynomial basis on disk:")
    print(f"max abs off-diagonal = {np.max(np.abs(polynomial_off_diagonal)):.6e}")

    print()
    print("Complex exp(1j*pi*Zernike) fields on disk:")
    print(f"max abs off-diagonal = {np.max(np.abs(field_off_diagonal)):.6e}")
    print("These phase fields are not expected to be an orthogonal Zernike basis.")


if __name__ == "__main__":
    print_reference_orthogonality_report()
