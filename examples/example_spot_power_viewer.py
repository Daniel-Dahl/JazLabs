"""
Open live spot-power analysis for a running JazLabs camera server.

Spot centres always use NumPy image order: ``(y, x)``.
"""

import multiprocessing as mp

import numpy as np

from JazLabs.hardware.SpotPower import SpotPowerViewer


if __name__ == "__main__":
    mp.freeze_support()

    spot_centres = np.array(
        [
            [100, 120],
            [100, 160],
            [140, 120],
            [140, 160],
        ],
        dtype=float,
    )

    viewer = SpotPowerViewer(
        host="127.0.0.1",
        command_port=50731,
        frame_pub_port=50732,
        spot_centres=spot_centres,
        aperture_radii=(3, 3),
        dark_frame_filename=None,
        refresh_ms=100,
    )
    viewer.startProcess()
    viewer.Process.join()
