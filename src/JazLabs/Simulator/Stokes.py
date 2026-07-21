import time

import numpy as np

def make_stokes_input_states(num_modes):
    """
    Creates known input states:
    1. single modes
    2. pairwise superpositions with phases 0, pi/2, pi, 3pi/2
    """
    states = []
    labels = []

    # Single-mode measurements
    for i in range(num_modes):
        a = np.zeros(num_modes, dtype=complex)
        a[i] = 1.0
        states.append(a)
        labels.append(("single", i))

    phases = [0, np.pi / 2, np.pi, 3 * np.pi / 2]

    # Pairwise interference measurements
    for i in range(num_modes):
        for j in range(i + 1, num_modes):
            for phi in phases:
                a = np.zeros(num_modes, dtype=complex)
                a[i] = 1 / np.sqrt(2)
                a[j] = np.exp(1j * phi) / np.sqrt(2)
                states.append(a)
                labels.append(("pair", i, j, phi))

    return np.array(states), labels

def make_minimal_stokes_input_states(num_modes):
    """
    Minimal high-dimensional Stokes input states.

    Total states:
        N single modes
        2 phases for each pair: 0 and pi/2

    Total = N + 2 * N(N-1)/2 = N^2
    """
    states = []
    labels = []

    # Single-mode measurements
    for i in range(num_modes):
        a = np.zeros(num_modes, dtype=complex)
        a[i] = 1.0
        states.append(a)
        labels.append(("single", i))

    # Minimal pairwise phase measurements
    phases = [0, np.pi / 2]

    for i in range(num_modes):
        for j in range(i + 1, num_modes):
            for phi in phases:
                a = np.zeros(num_modes, dtype=complex)
                a[i] = 1 / np.sqrt(2)
                a[j] = np.exp(1j * phi) / np.sqrt(2)
                states.append(a)
                labels.append(("pair", i, j, phi))

    return np.array(states), labels

def reconstruct_T_from_powers(
    powers,
    input_states,
    show_progress=True,
    progress_every=None,
):
    """
    Reconstructs T up to an arbitrary phase per output row.

    powers shape: (num_outputs, num_measurements)
    input_states shape: (num_measurements, num_modes)
    """
    num_outputs, num_measurements = powers.shape
    num_modes = input_states.shape[1]

    if progress_every is None:
        progress_every = max(1, num_outputs // 100)

    # Build linear system:
    # P_m = a_m^H Q a_m
    # where Q = t^H t
    A = np.zeros((num_measurements, num_modes * num_modes), dtype=complex)

    for m, a in enumerate(input_states):
        A[m, :] = np.outer(np.conj(a), a).reshape(-1)

    T_rec = np.zeros((num_outputs, num_modes), dtype=complex)
    progress_t0 = time.time()

    for k in range(num_outputs):
        if show_progress and (
            k == 0
            or k == num_outputs - 1
            or k % int(progress_every) == 0
        ):
            completed = k
            progress = completed / num_outputs if num_outputs else 1.0
            elapsed_s = time.time() - progress_t0
            eta_s = (
                elapsed_s * (1.0 - progress) / progress
                if progress > 0
                else float("nan")
            )
            print(
                f"reconstruct_T_from_powers {k}/{num_outputs - 1} "
                f"({100.0 * progress:5.1f}%) | "
                f"elapsed {elapsed_s / 60.0:6.1f} min | "
                f"ETA {eta_s / 60.0:6.1f} min"
            )

        p = powers[k]

        # Solve for Q_k
        q_vec, *_ = np.linalg.lstsq(A, p, rcond=None)
        Q = q_vec.reshape(num_modes, num_modes)

        # Clean numerical noise
        Q = 0.5 * (Q + Q.conj().T)

        # Since Q = t^H t, it should be rank 1.
        eigvals, eigvecs = np.linalg.eigh(Q)
        idx = np.argmax(eigvals)

        t = np.sqrt(np.maximum(eigvals[idx], 0)) * eigvecs[:, idx].conj()

        T_rec[k] = t

    if show_progress:
        elapsed_s = time.time() - progress_t0
        print(
            f"reconstruct_T_from_powers complete: {num_outputs}/{num_outputs} "
            f"(100.0%) | elapsed {elapsed_s / 60.0:6.1f} min"
        )

    return T_rec


def reconstruct_T_from_powers_fast(
    powers,
    input_states,
    rcond=1e-12,
    output_block_size=None,
    show_progress=True,
    progress_every=None,
):
    """
    Faster version of reconstruct_T_from_powers.

    The measurement matrix A only depends on input_states, so this function
    computes its pseudoinverse once and reuses it for every output row.

    powers shape: (num_outputs, num_measurements)
    input_states shape: (num_measurements, num_modes)
    """
    num_outputs, num_measurements = powers.shape
    num_modes = input_states.shape[1]

    if input_states.shape[0] != num_measurements:
        raise ValueError(
            "powers.shape[1] must match input_states.shape[0] "
            f"({num_measurements} != {input_states.shape[0]})"
        )

    if progress_every is None:
        progress_every = max(1, num_outputs // 100)

    progress_t0 = time.time()

    if show_progress:
        print("building Stokes reconstruction matrix")

    A = (
        np.conj(input_states)[:, :, None]
        * input_states[:, None, :]
    ).reshape(num_measurements, num_modes * num_modes)

    if show_progress:
        elapsed_s = time.time() - progress_t0
        print(f"computing pseudoinverse of A | elapsed {elapsed_s / 60.0:6.1f} min")

    A_pinv = np.linalg.pinv(A, rcond=rcond)
    T_rec = np.zeros((num_outputs, num_modes), dtype=complex)

    if output_block_size is None:
        output_block_size = num_outputs
    output_block_size = int(output_block_size)
    if output_block_size <= 0:
        raise ValueError("output_block_size must be positive")

    for block_start in range(0, num_outputs, output_block_size):
        block_stop = min(block_start + output_block_size, num_outputs)
        q_vecs = powers[block_start:block_stop] @ A_pinv.T

        for block_idx, k in enumerate(range(block_start, block_stop)):
            if show_progress and (
                k == 0
                or k == num_outputs - 1
                or k % int(progress_every) == 0
            ):
                completed = k
                progress = completed / num_outputs if num_outputs else 1.0
                elapsed_s = time.time() - progress_t0
                eta_s = (
                    elapsed_s * (1.0 - progress) / progress
                    if progress > 0
                    else float("nan")
                )
                print(
                    f"reconstruct_T_from_powers_fast {k}/{num_outputs - 1} "
                    f"({100.0 * progress:5.1f}%) | "
                    f"elapsed {elapsed_s / 60.0:6.1f} min | "
                    f"ETA {eta_s / 60.0:6.1f} min"
                )

            Q = q_vecs[block_idx].reshape(num_modes, num_modes)
            Q = 0.5 * (Q + Q.conj().T)

            eigvals, eigvecs = np.linalg.eigh(Q)
            idx = np.argmax(eigvals)

            T_rec[k] = (
                np.sqrt(np.maximum(eigvals[idx], 0))
                * eigvecs[:, idx].conj()
            )

    if show_progress:
        elapsed_s = time.time() - progress_t0
        print(
            f"reconstruct_T_from_powers_fast complete: "
            f"{num_outputs}/{num_outputs} (100.0%) | "
            f"elapsed {elapsed_s / 60.0:6.1f} min"
        )

    return T_rec
