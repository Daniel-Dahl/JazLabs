import numpy as np

try:
    import JazLabs.utils.ZernikeModuleReference as zref
except ImportError:
    import ZernikeModuleReference as zref


def make_bounds_for_modes(mode_indices, lower_limit=-0.5, upper_limit=0.5):
    """
    Return optimizer bounds for each mode coefficient.

    lower_limit and upper_limit can be scalars or arrays with one value per
    optimized mode. The returned list is in the same order as mode_indices.
    """
    mode_indices = list(mode_indices)
    mode_count = len(mode_indices)

    lower_limits = np.asarray(lower_limit, dtype=float)
    upper_limits = np.asarray(upper_limit, dtype=float)

    if lower_limits.ndim == 0:
        lower_limits = np.full(mode_count, float(lower_limits))
    if upper_limits.ndim == 0:
        upper_limits = np.full(mode_count, float(upper_limits))

    if lower_limits.shape[0] != mode_count:
        raise ValueError("lower_limit must be a scalar or have one value per optimized mode.")
    if upper_limits.shape[0] != mode_count:
        raise ValueError("upper_limit must be a scalar or have one value per optimized mode.")

    bounds = []
    for mode_number, lower, upper in zip(mode_indices, lower_limits, upper_limits):
        if lower >= upper:
            raise ValueError(f"Mode {mode_number} has lower_limit >= upper_limit.")
        bounds.append((float(lower), float(upper)))

    return bounds


def make_single_zernike_field_modes(zernikes, mode_indices, coefficients):
    """
    Build fields like:

        field_k = exp(1j * pi * coefficient_k * Z_mode_k)

    This matches the notebook pattern where only one Zernike coefficient is
    nonzero for each generated field.
    """
    mode_indices = list(mode_indices)
    coefficients = np.asarray(coefficients, dtype=float)

    if len(mode_indices) != coefficients.shape[0]:
        raise ValueError("mode_indices and coefficients must have the same length.")

    field_modes = np.zeros((len(mode_indices), zernikes.Ny, zernikes.Nx), dtype=np.complex128)

    for field_index, mode_index in enumerate(mode_indices):
        phase = coefficients[field_index] * zernikes.zernike_basis_array[mode_index]
        field = np.exp(1j * np.pi * phase)
        field_modes[field_index] = np.where(zernikes.disk_mask, field, 0.0)

    return field_modes


def field_gram_matrix(field_modes, aperture=None):
    field_modes = np.asarray(field_modes, dtype=np.complex128)

    if aperture is not None:
        field_modes = field_modes * aperture[None, :, :]

    flat_modes = field_modes.reshape(field_modes.shape[0], -1)
    norms = np.sqrt(np.sum(np.abs(flat_modes) ** 2, axis=1))

    if np.any(norms == 0):
        raise ValueError("At least one field mode has zero norm.")

    normalized_flat_modes = flat_modes / norms[:, None]
    return normalized_flat_modes.conj() @ normalized_flat_modes.T


def condition_number_score(zernikes, mode_indices, coefficients, condition_weight=1.0, overlap_weight=0.0):
    field_modes = make_single_zernike_field_modes(zernikes, mode_indices, coefficients)
    gram_matrix = field_gram_matrix(field_modes, aperture=zernikes.disk_mask)
    target_identity = np.eye(gram_matrix.shape[0], dtype=np.complex128)
    off_diagonal_gram = gram_matrix - target_identity

    condition_number = np.linalg.cond(gram_matrix)
    max_off_diagonal = np.max(np.abs(off_diagonal_gram))

    if not np.isfinite(condition_number):
        return np.inf

    return condition_weight * condition_number + overlap_weight * max_off_diagonal


def random_search_coefficients(
    zernikes,
    mode_indices,
    bounds,
    random_samples=2000,
    seed=1,
    condition_weight=1.0,
    overlap_weight=0.0,
    verbose=True,
):
    rng = np.random.default_rng(seed)
    lower_bounds = np.array([bound[0] for bound in bounds], dtype=float)
    upper_bounds = np.array([bound[1] for bound in bounds], dtype=float)

    best_coefficients = None
    best_score = np.inf

    for sample_index in range(random_samples):
        coefficients = rng.uniform(lower_bounds, upper_bounds)
        score = condition_number_score(
            zernikes,
            mode_indices,
            coefficients,
            condition_weight=condition_weight,
            overlap_weight=overlap_weight,
        )

        if score < best_score:
            best_score = score
            best_coefficients = coefficients.copy()
            if verbose:
                print(f"random sample {sample_index}: best score = {best_score:.6g}")

    return best_coefficients, best_score


def coordinate_refine_coefficients(
    zernikes,
    mode_indices,
    bounds,
    starting_coefficients,
    starting_score,
    refinement_rounds=4,
    steps_per_round=9,
    condition_weight=1.0,
    overlap_weight=0.0,
    verbose=True,
):
    best_coefficients = np.asarray(starting_coefficients, dtype=float).copy()
    best_score = float(starting_score)

    lower_bounds = np.array([bound[0] for bound in bounds], dtype=float)
    upper_bounds = np.array([bound[1] for bound in bounds], dtype=float)
    search_widths = (upper_bounds - lower_bounds) / 4.0

    for refinement_round in range(refinement_rounds):
        improved_this_round = False

        for coefficient_index in range(best_coefficients.shape[0]):
            center_value = best_coefficients[coefficient_index]
            trial_values = np.linspace(
                max(lower_bounds[coefficient_index], center_value - search_widths[coefficient_index]),
                min(upper_bounds[coefficient_index], center_value + search_widths[coefficient_index]),
                steps_per_round,
            )

            for trial_value in trial_values:
                trial_coefficients = best_coefficients.copy()
                trial_coefficients[coefficient_index] = trial_value
                score = condition_number_score(
                    zernikes,
                    mode_indices,
                    trial_coefficients,
                    condition_weight=condition_weight,
                    overlap_weight=overlap_weight,
                )

                if score < best_score:
                    best_score = score
                    best_coefficients = trial_coefficients
                    improved_this_round = True

        search_widths *= 0.5

        if verbose:
            print(f"refinement round {refinement_round + 1}: best score = {best_score:.6g}")

        if not improved_this_round:
            break

    return best_coefficients, best_score


def scipy_differential_evolution_coefficients(
    zernikes,
    mode_indices,
    bounds,
    max_iterations=80,
    population_size=10,
    seed=1,
    condition_weight=1.0,
    overlap_weight=0.0,
    verbose=True,
):
    from scipy.optimize import differential_evolution

    def optimizer_objective(coefficients):
        return condition_number_score(
            zernikes,
            mode_indices,
            coefficients,
            condition_weight=condition_weight,
            overlap_weight=overlap_weight,
        )

    result = differential_evolution(
        optimizer_objective,
        bounds=bounds,
        maxiter=max_iterations,
        popsize=population_size,
        seed=seed,
        polish=True,
        updating="immediate",
        workers=1,
        disp=verbose,
    )

    return np.asarray(result.x, dtype=float), float(result.fun), result


def scipy_fast_local_coefficients(
    zernikes,
    mode_indices,
    bounds,
    random_starts=12,
    max_iterations=120,
    seed=1,
    condition_weight=1.0,
    overlap_weight=0.0,
    verbose=True,
):
    """
    Faster, less global optimizer than differential evolution.

    It tries a small number of random starting points, then runs L-BFGS-B from
    each one. This is usually much quicker for interactive notebook tuning.
    """
    from scipy.optimize import minimize

    rng = np.random.default_rng(seed)
    lower_bounds = np.array([bound[0] for bound in bounds], dtype=float)
    upper_bounds = np.array([bound[1] for bound in bounds], dtype=float)

    starting_points = []
    midpoint = 0.5 * (lower_bounds + upper_bounds)
    starting_points.append(midpoint)

    for _ in range(random_starts):
        starting_points.append(rng.uniform(lower_bounds, upper_bounds))

    best_coefficients = None
    best_score = np.inf
    best_result = None

    def optimizer_objective(coefficients):
        return condition_number_score(
            zernikes,
            mode_indices,
            coefficients,
            condition_weight=condition_weight,
            overlap_weight=overlap_weight,
        )

    for start_index, starting_coefficients in enumerate(starting_points):
        result = minimize(
            optimizer_objective,
            starting_coefficients,
            method="L-BFGS-B",
            bounds=bounds,
            options={
                "maxiter": max_iterations,
                "ftol": 1e-6,
            },
        )

        if result.fun < best_score:
            best_score = float(result.fun)
            best_coefficients = np.asarray(result.x, dtype=float)
            best_result = result
            if verbose:
                print(f"local start {start_index}: best score = {best_score:.6g}")

    return best_coefficients, best_score, best_result


def optimize_single_zernike_field_coefficients(
    max_zernike_radial_number=7,
    Nx=256,
    Ny=256,
    optimization_Nx=None,
    optimization_Ny=None,
    lower_limit=-0.5,
    upper_limit=0.5,
    mode_indices=None,
    include_piston=False,
    aperture_radius_in_pixels=None,
    normalize=True,
    method="auto",
    random_samples=2000,
    random_starts=12,
    refinement_rounds=4,
    steps_per_round=9,
    max_iterations=80,
    population_size=10,
    seed=1,
    condition_weight=1.0,
    overlap_weight=0.0,
    verbose=True,
):
    """
    Find one coefficient per single-Zernike field to improve Gram conditioning.

    The default optimizes modes 1..zernCount-1, which excludes piston. Pass
    mode_indices explicitly if you want a smaller or custom set.

    Set optimization_Nx/optimization_Ny to a smaller grid, such as 64x64, for
    much faster coefficient search. The returned field_modes and gram_matrix
    are always rebuilt at Nx/Ny.
    """
    if optimization_Nx is None:
        optimization_Nx = Nx
    if optimization_Ny is None:
        optimization_Ny = Ny

    optimization_zernikes = zref.ReferenceZernikes(
        max_zernike_radial_number=max_zernike_radial_number,
        Nx=optimization_Nx,
        Ny=optimization_Ny,
        aperture_radius_in_pixels=aperture_radius_in_pixels,
        normalize=normalize,
    )

    if mode_indices is None:
        first_mode = 0 if include_piston else 1
        mode_indices = list(range(first_mode, optimization_zernikes.zernCount))
    else:
        mode_indices = list(mode_indices)

    bounds = make_bounds_for_modes(
        mode_indices,
        lower_limit=lower_limit,
        upper_limit=upper_limit,
    )

    scipy_result = None
    if method in ("auto", "fast"):
        try:
            best_coefficients, best_score, scipy_result = scipy_fast_local_coefficients(
                optimization_zernikes,
                mode_indices,
                bounds,
                random_starts=random_starts,
                max_iterations=max_iterations,
                seed=seed,
                condition_weight=condition_weight,
                overlap_weight=overlap_weight,
                verbose=verbose,
            )
        except ImportError:
            if verbose:
                print("scipy is not available; using random search plus coordinate refinement.")
            best_coefficients, best_score = random_search_coefficients(
                optimization_zernikes,
                mode_indices,
                bounds,
                random_samples=random_samples,
                seed=seed,
                condition_weight=condition_weight,
                overlap_weight=overlap_weight,
                verbose=verbose,
            )
            best_coefficients, best_score = coordinate_refine_coefficients(
                optimization_zernikes,
                mode_indices,
                bounds,
                best_coefficients,
                best_score,
                refinement_rounds=refinement_rounds,
                steps_per_round=steps_per_round,
                condition_weight=condition_weight,
                overlap_weight=overlap_weight,
                verbose=verbose,
            )
    elif method == "scipy":
        try:
            best_coefficients, best_score, scipy_result = scipy_differential_evolution_coefficients(
                optimization_zernikes,
                mode_indices,
                bounds,
                max_iterations=max_iterations,
                population_size=population_size,
                seed=seed,
                condition_weight=condition_weight,
                overlap_weight=overlap_weight,
                verbose=verbose,
            )
        except ImportError:
            raise
    elif method == "random":
        best_coefficients, best_score = random_search_coefficients(
            optimization_zernikes,
            mode_indices,
            bounds,
            random_samples=random_samples,
            seed=seed,
            condition_weight=condition_weight,
            overlap_weight=overlap_weight,
            verbose=verbose,
        )
        best_coefficients, best_score = coordinate_refine_coefficients(
            optimization_zernikes,
            mode_indices,
            bounds,
            best_coefficients,
            best_score,
            refinement_rounds=refinement_rounds,
            steps_per_round=steps_per_round,
            condition_weight=condition_weight,
            overlap_weight=overlap_weight,
            verbose=verbose,
        )
    else:
        raise ValueError("method must be 'auto', 'fast', 'scipy', or 'random'.")

    zernikes = zref.ReferenceZernikes(
        max_zernike_radial_number=max_zernike_radial_number,
        Nx=Nx,
        Ny=Ny,
        aperture_radius_in_pixels=aperture_radius_in_pixels,
        normalize=normalize,
    )

    field_modes = make_single_zernike_field_modes(zernikes, mode_indices, best_coefficients)
    gram_matrix = field_gram_matrix(field_modes, aperture=zernikes.disk_mask)
    off_diagonal_gram = gram_matrix - np.eye(gram_matrix.shape[0], dtype=np.complex128)

    coefficient_by_mode = np.zeros(zernikes.zernCount, dtype=float)
    for mode_index, coefficient in zip(mode_indices, best_coefficients):
        coefficient_by_mode[mode_index] = coefficient

    return {
        "zernikes": zernikes,
        "mode_indices": mode_indices,
        "coefficients": best_coefficients,
        "coefficient_by_mode": coefficient_by_mode,
        "field_modes": field_modes,
        "gram_matrix": gram_matrix,
        "condition_number": np.linalg.cond(gram_matrix),
        "max_off_diagonal": np.max(np.abs(off_diagonal_gram)),
        "score": best_score,
        "bounds": bounds,
        "optimization_Nx": optimization_Nx,
        "optimization_Ny": optimization_Ny,
        "scipy_result": scipy_result,
    }


if __name__ == "__main__":
    result = optimize_single_zernike_field_coefficients(
        max_zernike_radial_number=7,
        Nx=256,
        Ny=256,
        lower_limit=-0.5,
        upper_limit=0.5,
        method="auto",
        random_samples=500,
        verbose=True,
    )

    print()
    print("Best coefficients by optimized mode:")
    for mode_index, coefficient in zip(result["mode_indices"], result["coefficients"]):
        n, m = result["zernikes"].nm_sequence[mode_index]
        print(f"mode {mode_index:2d} (n={n}, m={m}): {coefficient:.8f}")

    print()
    print(f"condition number: {result['condition_number']:.8g}")
    print(f"max off diagonal: {result['max_off_diagonal']:.8g}")
