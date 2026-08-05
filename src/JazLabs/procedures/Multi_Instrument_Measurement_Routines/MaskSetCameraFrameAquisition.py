import ctypes
import os
import shutil
import time
from pathlib import Path
from typing import Sequence

import numpy as np


def _get_available_ram_bytes() -> int:
    """Return the operating system's current estimate of available RAM."""
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_physical", ctypes.c_ulonglong),
                ("available_physical", ctypes.c_ulonglong),
                ("total_page_file", ctypes.c_ulonglong),
                ("available_page_file", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("available_virtual", ctypes.c_ulonglong),
                ("available_extended_virtual", ctypes.c_ulonglong),
            ]

        memory_status = MemoryStatus()
        memory_status.length = ctypes.sizeof(MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory_status)):
            raise OSError("GlobalMemoryStatusEx could not determine the available RAM")
        return int(memory_status.available_physical)

    page_size = os.sysconf("SC_PAGE_SIZE")
    available_pages = os.sysconf("SC_AVPHYS_PAGES")
    return int(page_size * available_pages)


def measure_mask_set_camera_frames(
    phase_mask_object,
    mask_filename,
    cameras: Sequence,
    slm_properties_filename,
    avg_frame_count: int = 1,
    camera_names: Sequence[str] | None = None,
    output_directory=None,
    channel: str = "Red",
    polarisation: str = "H",
    maximum_ram_fraction: float = 0.5,
):
    """Display every mask and acquire an averaged frame from every camera.

    The mask file and output arrays are kept in RAM when their estimated memory
    footprint fits within ``maximum_ram_fraction`` of the currently available
    RAM. Otherwise the mask file is read in chunks and the acquired frames are
    written to memory-mapped ``.npy`` files in ``output_directory``.

    Parameters
    ----------
    phase_mask_object:
        A ``PhaseMask``-like object with ``setMaskArray``,
        ``LoadMaskProperties``, and ``setmask`` methods.
    mask_filename:
        Path to a NumPy ``.npy`` mask array. Its first dimension is the mode.
    cameras:
        Ordered sequence of camera clients. Each camera must provide
        ``GetFrame``, ``SetSoftwareTriggerMode``, ``FireSoftwareTrigger``, and
        ``SetContinuousMode``.
    slm_properties_filename:
        Filename prefix passed to ``LoadMaskProperties``.
    avg_frame_count:
        Number of frames to average for each camera and mask mode.
    camera_names:
        Optional names used as result keys and disk filenames. Defaults to
        ``camera_0``, ``camera_1``, and so on.
    output_directory:
        Directory for disk-backed output. Defaults to the mask file's parent.
    maximum_ram_fraction:
        Fraction of currently available RAM that this measurement may use.

    Returns
    -------
    dict
        Contains ``frames`` (a camera-name to array mapping), ``storage_mode``
        (``"memory"`` or ``"disk"``), and ``output_files``. Disk-backed frame
        arrays are ``numpy.memmap`` instances and are flushed before return.
    """
    mask_path = Path(mask_filename).expanduser().resolve()
    if mask_path.suffix.lower() != ".npy":
        raise ValueError("mask_filename must be an uncompressed .npy file")
    if not mask_path.is_file():
        raise FileNotFoundError(mask_path)

    cameras = list(cameras)
    if not cameras:
        raise ValueError("cameras must contain at least one camera")
    if not isinstance(avg_frame_count, int) or avg_frame_count < 1:
        raise ValueError("avg_frame_count must be a positive integer")
    if not 0.0 < maximum_ram_fraction < 1.0:
        raise ValueError("maximum_ram_fraction must be between 0 and 1")
    if polarisation not in ("H", "V"):
        raise ValueError("polarisation must be either 'H' or 'V'")

    if camera_names is None:
        camera_names = [f"camera_{index}" for index in range(len(cameras))]
    else:
        camera_names = list(camera_names)
    if len(camera_names) != len(cameras):
        raise ValueError("camera_names must have the same length as cameras")
    if len(set(camera_names)) != len(camera_names):
        raise ValueError("camera_names must be unique")
    invalid_filename_characters = set('<>:"/\\|?*')
    if any(
        not isinstance(name, str)
        or not name
        or name in (".", "..")
        or any(character in invalid_filename_characters for character in name)
        for name in camera_names
    ):
        raise ValueError("camera_names must be non-empty filename-safe names")

    masks_on_disk = np.load(mask_path, mmap_mode="r", allow_pickle=False)
    if masks_on_disk.ndim != 4:
        raise ValueError(
            "The mask array must have shape (mode, mask, height, width); "
            f"received {masks_on_disk.shape}"
        )
    mode_count = int(masks_on_disk.shape[0])
    if mode_count == 0:
        raise ValueError("The mask array contains no modes")

    sample_frames = [np.asarray(camera.GetFrame()) for camera in cameras]
    for camera_name, sample_frame in zip(camera_names, sample_frames):
        if sample_frame.ndim != 2:
            raise ValueError(
                f"Camera {camera_name!r} returned a {sample_frame.ndim}-D frame; "
                "2-D frames are required"
            )

    output_bytes = sum(mode_count * frame.nbytes for frame in sample_frames)
    # PhaseMaskClass keeps complex MaskCmplx and MaskPlusZern arrays in addition
    # to the loaded input array. Include all three in the decision so a compact
    # real-valued mask file cannot accidentally cause a much larger allocation.
    internal_mask_bytes = 2 * masks_on_disk.size * np.dtype(np.complex128).itemsize
    estimated_ram_bytes = masks_on_disk.nbytes + internal_mask_bytes + output_bytes
    available_ram_bytes = _get_available_ram_bytes()
    ram_budget_bytes = int(available_ram_bytes * maximum_ram_fraction)
    use_memory = estimated_ram_bytes <= ram_budget_bytes

    storage_mode = "memory" if use_memory else "disk"
    print(
        f"Acquiring {mode_count} modes using {storage_mode} storage "
        f"(estimated {estimated_ram_bytes / 2**30:.2f} GiB, "
        f"RAM budget {ram_budget_bytes / 2**30:.2f} GiB)."
    )

    output_files = {camera_name: None for camera_name in camera_names}
    frames_by_camera = {}
    if use_memory:
        masks = np.load(mask_path, allow_pickle=False)
        for camera_name, sample_frame in zip(camera_names, sample_frames):
            frames_by_camera[camera_name] = np.empty(
                (mode_count, *sample_frame.shape), dtype=sample_frame.dtype
            )
        chunk_size = mode_count
    else:
        output_path = (
            Path(output_directory).expanduser().resolve()
            if output_directory is not None
            else mask_path.parent
        )
        output_path.mkdir(parents=True, exist_ok=True)
        required_disk_bytes = output_bytes
        available_disk_bytes = shutil.disk_usage(output_path).free
        if required_disk_bytes > available_disk_bytes:
            raise OSError(
                f"The output needs {required_disk_bytes / 2**30:.2f} GiB, but "
                f"only {available_disk_bytes / 2**30:.2f} GiB is free in {output_path}"
            )

        for camera_name, sample_frame in zip(camera_names, sample_frames):
            camera_output_file = output_path / f"{mask_path.stem}_{camera_name}.npy"
            output_files[camera_name] = camera_output_file
            frames_by_camera[camera_name] = np.lib.format.open_memmap(
                camera_output_file,
                mode="w+",
                dtype=sample_frame.dtype,
                shape=(mode_count, *sample_frame.shape),
            )

        masks = masks_on_disk
        input_bytes_per_mode = masks_on_disk[0].nbytes
        internal_bytes_per_mode = (
            2 * masks_on_disk[0].size * np.dtype(np.complex128).itemsize
        )
        working_bytes_per_mode = input_bytes_per_mode + internal_bytes_per_mode
        chunk_size = max(1, min(mode_count, ram_budget_bytes // working_bytes_per_mode))

    cameras_in_software_trigger_mode = []
    measurement_start = time.time()
    try:
        for camera in cameras:
            camera.SetSoftwareTriggerMode()
            cameras_in_software_trigger_mode.append(camera)

        for chunk_start in range(0, mode_count, chunk_size):
            chunk_stop = min(chunk_start + chunk_size, mode_count)
            if use_memory:
                mask_chunk = masks
            else:
                print(f"Loading mask chunk {chunk_start}:{chunk_stop}")
                mask_chunk = np.array(masks[chunk_start:chunk_stop], copy=True)

            phase_mask_object.setMaskArray(
                channel=channel,
                MASKS=mask_chunk,
                PolSelector=polarisation,
            )
            phase_mask_object.LoadMaskProperties(
                filenamePrefix=slm_properties_filename,
                channel=channel,
                PolSelector=polarisation,
            )
            other_polarisation = "V" if polarisation == "H" else "H"
            phase_mask_object.polProps[channel][other_polarisation].polEnabled = False

            for local_mode, global_mode in enumerate(range(chunk_start, chunk_stop)):
                elapsed_seconds = time.time() - measurement_start
                completed_modes = global_mode
                progress = completed_modes / mode_count
                eta_seconds = (
                    elapsed_seconds * (1.0 - progress) / progress
                    if progress > 0.0
                    else float("nan")
                )
                print(
                    f"mode {global_mode}/{mode_count - 1} "
                    f"({100.0 * progress:5.1f}%) | "
                    f"elapsed {elapsed_seconds / 60.0:6.1f} min | "
                    f"ETA {eta_seconds / 60.0:6.1f} min"
                )

                if polarisation == "H":
                    phase_mask_object.setmask(channel=channel, imode_H=local_mode)
                else:
                    phase_mask_object.setmask(channel=channel, imode_V=local_mode)

                accumulated_frames = [
                    np.zeros(frame.shape, dtype=np.result_type(frame.dtype, np.uint64))
                    for frame in sample_frames
                ]
                for _ in range(avg_frame_count):
                    for camera in cameras:
                        camera.FireSoftwareTrigger()
                    for camera_index, camera in enumerate(cameras):
                        acquired_frame = np.asarray(camera.GetFrame())
                        if acquired_frame.shape != sample_frames[camera_index].shape:
                            raise ValueError(
                                f"Camera {camera_names[camera_index]!r} changed frame shape "
                                f"from {sample_frames[camera_index].shape} to {acquired_frame.shape}"
                            )
                        accumulated_frames[camera_index] += acquired_frame

                for camera_index, camera_name in enumerate(camera_names):
                    frames_by_camera[camera_name][global_mode] = (
                        accumulated_frames[camera_index] / avg_frame_count
                    ).astype(sample_frames[camera_index].dtype, copy=False)

            if not use_memory:
                for camera_frames in frames_by_camera.values():
                    camera_frames.flush()
                del mask_chunk
    finally:
        for camera in cameras_in_software_trigger_mode:
            camera.SetContinuousMode()
        if not use_memory:
            for camera_frames in frames_by_camera.values():
                camera_frames.flush()

    return {
        "frames": frames_by_camera,
        "storage_mode": storage_mode,
        "output_files": output_files,
    }
