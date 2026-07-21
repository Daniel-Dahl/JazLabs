import numpy as np

from JazLabs.simulator import BeamGenerator as BeamGen


def _gram_matrix(modes):
    flat = modes.reshape(modes.shape[0], -1)
    flat = flat / np.sqrt(np.sum(np.abs(flat) ** 2, axis=1))[:, None]
    return flat.conj() @ flat.T


def test_equal_area_circular_superpixel_labels_have_equal_pixel_counts():
    labels = BeamGen.make_equal_area_circular_superpixel_labels(
        shape=(64, 64),
        n_superpixels_x=4,
        n_superpixels_y=4,
        radius=28,
    )
    counts = np.bincount(labels[labels >= 0])

    assert labels.shape == (64, 64)
    assert counts.shape == (16,)
    assert np.all(counts == counts[0])


def test_circular_hadamard_phase_profiles_are_orthogonal_after_pupil():
    fields = BeamGen.make_circular_hadamard_phase_profiles(
        shape=(64, 64),
        n_superpixels_x=4,
        n_superpixels_y=4,
        radius=28,
    )
    gram = _gram_matrix(fields)

    assert fields.shape == (16, 64, 64)
    assert np.allclose(gram, np.eye(16), atol=1e-12)
