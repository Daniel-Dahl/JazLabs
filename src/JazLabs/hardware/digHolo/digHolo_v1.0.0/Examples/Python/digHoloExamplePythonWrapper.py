import argparse
import ctypes
import os
from pathlib import Path
import sys

import numpy as np


REPO_SRC = Path(__file__).resolve().parents[6]
if str(REPO_SRC) not in sys.path:
    sys.path.insert(0, str(REPO_SRC))

import JazLabs.hardware.digHolo.digHolo_pylibs.digholoHeader as digHolo


def create_simulated_frames(frame_count, frame_width, frame_height, pixel_size, pol_count, lambda0):
    digHolo.digHoloFrameSimulatorCreateSimple.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_int,
        ctypes.c_float,
        ctypes.c_int,
    ]
    digHolo.digHoloFrameSimulatorCreateSimple.restype = ctypes.POINTER(ctypes.c_float)
    frame_buffer_ptr = digHolo.digHoloFrameSimulatorCreateSimple(
        frame_count,
        frame_width,
        frame_height,
        ctypes.c_float(pixel_size),
        pol_count,
        ctypes.c_float(lambda0),
        1,
    )
    if not frame_buffer_ptr:
        raise RuntimeError("digHoloFrameSimulatorCreateSimple returned NULL")
    frame_buffer = np.ctypeslib.as_array(
        frame_buffer_ptr,
        shape=(frame_count, frame_height, frame_width),
    )
    return frame_buffer_ptr, frame_buffer


def quick_smoke_test():
    frame_buffer_ptr, frame_buffer = create_simulated_frames(
        frame_count=1,
        frame_width=64,
        frame_height=64,
        pixel_size=20e-6,
        pol_count=2,
        lambda0=1565e-9,
    )
    handle_idx = digHolo.digHoloCreate()
    print(
        "digHolo quick smoke test OK: "
        f"handle={handle_idx}, frames={frame_buffer.shape}",
        flush=True,
    )
    os._exit(0)


def full_smoke_test():
    frame_count = 1
    batch_count = frame_count
    frame_width = 64
    frame_height = 64
    pixel_size = 20e-6
    lambda0 = 1565e-9
    pol_count = 2
    nx = 32
    ny = 32
    max_mg = 1

    frame_buffer_ptr, frame_buffer = create_simulated_frames(
        frame_count,
        frame_width,
        frame_height,
        pixel_size,
        pol_count,
        lambda0,
    )

    handle_idx = digHolo.digHoloCreate()
    print(f"handleIdx = {handle_idx}", flush=True)

    digHolo.digHoloConfigSetThreadCount(handle_idx, 1)
    digHolo.digHoloConfigSetVerbosity(handle_idx, 1)
    digHolo.digHoloConfigSetFramePixelSize(handle_idx, pixel_size)
    digHolo.digHoloConfigSetFrameDimensions(handle_idx, frame_width, frame_height)
    digHolo.digHoloConfigSetWavelengthCentre(handle_idx, lambda0)
    digHolo.digHoloConfigSetPolCount(handle_idx, pol_count)
    digHolo.digHoloConfigSetfftWindowSizeX(handle_idx, nx)
    digHolo.digHoloConfigSetfftWindowSizeY(handle_idx, ny)
    digHolo.digHoloConfigSetIFFTResolutionMode(handle_idx, 1)
    digHolo.digHoloConfigSetBasisGroupCount(handle_idx, max_mg)
    digHolo.digHoloConfigSetAutoAlignMode(
        handle_idx,
        digHolo.DIGHOLO_AUTOALIGNMODE_ESTIMATE,
    )
    print(
        "autoalign mode = "
        f"{digHolo.digHoloConfigGetAutoAlignMode(handle_idx)}",
        flush=True,
    )

    digHolo.digHoloSetBatch(handle_idx, batch_count, frame_buffer_ptr)
    print("batch set", flush=True)
    digHolo.digHoloAutoAlign(handle_idx)
    print("autoalign estimate complete", flush=True)

    batch_count_out = ctypes.c_int(0)
    mode_count_out = ctypes.c_int(0)
    pol_count_out = ctypes.c_int(0)
    digHolo.digHoloBasisGetCoefs.restype = ctypes.POINTER(ctypes.c_float)
    coefs_ptr = digHolo.digHoloBasisGetCoefs(
        handle_idx,
        ctypes.byref(batch_count_out),
        ctypes.byref(mode_count_out),
        ctypes.byref(pol_count_out),
    )
    coefs = np.ctypeslib.as_array(
        coefs_ptr,
        shape=(batch_count_out.value, 2 * mode_count_out.value * pol_count_out.value),
    )

    print(
        "digHolo smoke test OK: "
        f"frames={frame_buffer.shape}, coefs={coefs.shape}, "
        f"modes={mode_count_out.value}, pols={pol_count_out.value}, "
        "autoalign=estimate",
        flush=True,
    )
    os._exit(0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the full example, including AutoAlign.",
    )
    args = parser.parse_args()

    if args.full:
        full_smoke_test()
    else:
        quick_smoke_test()


if __name__ == "__main__":
    main()
