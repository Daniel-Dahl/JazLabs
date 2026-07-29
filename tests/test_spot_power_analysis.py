import numpy as np
import pytest

from JazLabs.hardware.SpotPower.SpotPower_Viewer import (
    load_spot_centres_file,
    save_spot_centres_file,
)
from JazLabs.hardware.SpotPower.SpotPower_Analysis import (
    analyse_spot_powers,
    average_spot_power_history,
    parse_spot_centres,
    prepare_analysis_frame,
)


def test_parse_spot_centres_accepts_commas_spaces_and_comments():
    centres = parse_spot_centres(
        """
        # y, x
        2, 3
        5.5 7.25  # second spot
        """
    )

    np.testing.assert_allclose(centres, [[2, 3], [5.5, 7.25]])


def test_dark_subtraction_avoids_unsigned_wraparound():
    frame = np.array([[2, 10]], dtype=np.uint16)
    dark = np.array([[5, 3]], dtype=np.uint16)

    corrected = prepare_analysis_frame(frame, dark, use_dark_frame=True)

    np.testing.assert_array_equal(corrected, [[0, 7]])
    assert corrected.dtype == np.float32


def test_dark_frame_must_match_camera_frame_shape():
    with pytest.raises(ValueError, match="does not match"):
        prepare_analysis_frame(
            np.zeros((4, 4)),
            np.zeros((3, 4)),
            use_dark_frame=True,
        )


def test_analyse_spot_powers_returns_absolute_relative_and_total_power():
    frame = np.zeros((9, 12), dtype=float)
    frame[4, 3] = 4
    frame[4, 8] = 12

    absolute, relative, total, aperture_views = analyse_spot_powers(
        frame,
        spot_centres=[[4, 3], [4, 8]],
        aperture_radii=1,
    )

    np.testing.assert_allclose(absolute, [4, 12])
    np.testing.assert_allclose(relative, [0.25, 0.75])
    assert total == 16
    assert len(aperture_views) == 2


def test_zero_total_power_produces_finite_zero_relative_powers():
    absolute, relative, total, _ = analyse_spot_powers(
        np.zeros((5, 5)),
        spot_centres=[[2, 2]],
        aperture_radii=1,
    )

    np.testing.assert_array_equal(absolute, [0])
    np.testing.assert_array_equal(relative, [0])
    assert total == 0


@pytest.mark.parametrize("suffix", [".npy", ".npz", ".csv", ".txt"])
def test_saved_spot_centres_can_be_loaded_again(tmp_path, suffix):
    centres = np.array([[1.25, 2.5], [10, 20]], dtype=float)
    filename = tmp_path / f"centres{suffix}"

    save_spot_centres_file(filename, centres)

    np.testing.assert_allclose(load_spot_centres_file(filename), centres)


def test_average_spot_power_history_averages_raw_and_recomputes_relative_power():
    absolute, relative, total = average_spot_power_history(
        [
            [2, 6],
            [4, 10],
            [6, 14],
        ]
    )

    np.testing.assert_allclose(absolute, [4, 10])
    np.testing.assert_allclose(relative, [2 / 7, 5 / 7])
    assert total == 14
