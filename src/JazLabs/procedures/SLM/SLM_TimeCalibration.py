import gc
import time

import matplotlib.pyplot as plt
import numpy as np

import pwi_inst.utils.GenerateSimplePhaseMasks as slm_masks
import pwi_inst.utils.camera_utils as camera_utils


CHANNEL_INDEX_BY_NAME = {
    "Blue": 0,
    "Green": 1,
    "Red": 2,
}


def timing_stats(samples_s):
    samples_s = np.asarray(samples_s, dtype=np.float64)
    if samples_s.size == 0:
        raise ValueError("Cannot calculate timing stats for an empty sample array")

    return {
        "mean_s": float(np.mean(samples_s)),
        "std_s": float(np.std(samples_s)),
        "min_s": float(np.min(samples_s)),
        "max_s": float(np.max(samples_s)),
        "jitter_s": float(np.max(samples_s) - np.min(samples_s)),
    }


def print_timing_stats(label, stats):
    if stats is None:
        print(f"{label}: no samples")
        return

    print(label)
    print(f"  Mean:   {stats['mean_s'] * 1e3:.3f} ms")
    print(f"  Std:    {stats['std_s'] * 1e3:.3f} ms")
    print(f"  Min:    {stats['min_s'] * 1e3:.3f} ms")
    print(f"  Max:    {stats['max_s'] * 1e3:.3f} ms")
    print(f"  Jitter: {stats['jitter_s'] * 1e3:.3f} ms")


def resolve_slm_channel_index(slm, channel):
    if getattr(slm, "NumberOfChannels", 1) == 1:
        return 0

    if isinstance(channel, str):
        return CHANNEL_INDEX_BY_NAME[channel]

    return int(channel)


def make_blank_and_stripe_masks(
    phasemask,
    stripe_width,
    stripe_phase_value,
    stripe_orientation="vertical",
    mask_shape=None,
):
    if mask_shape is None:
        slm = phasemask.SLMObject
        mask_shape = (int(slm.monitor_height), int(slm.monitor_width))

    height, width = mask_shape
    blank_mask = np.zeros((height, width), dtype=np.uint8)

    stripe_phase = slm_masks.binary_stripe_phase(
        Nx=width,
        Ny=height,
        stripe_width=int(stripe_width),
        phase_value=float(stripe_phase_value),
        orientation=stripe_orientation,
    )
    stripe_mask = phasemask.convert_phase_to_uint8(arr=stripe_phase[0, 0, :, :])

    return (
        np.ascontiguousarray(blank_mask, dtype=np.uint8),
        np.ascontiguousarray(stripe_mask, dtype=np.uint8),
    )


def write_slm_frame_and_time(
    slm,
    frame,
    channel_index=0,
    wait_for_display=True,
    display_timeout_ms=10000,
):
    write_start_s = time.perf_counter()
    result = slm.WriteImageToSLM(
        frame,
        channelIdx=channel_index,
        wait=wait_for_display,
        display_timeout_ms=display_timeout_ms,
    )
    write_done_s = time.perf_counter()
    return result, write_done_s - write_start_s


def measure_slm_client_write_timing(
    slm,
    frame_count=1000,
    channel_index=0,
    wait_for_display=False,
    display_timeout_ms=10000,
    disable_gc=True,
):
    frame_count = int(frame_count)
    frame_shape = (int(slm.monitor_height), int(slm.monitor_width))
    frame = np.zeros(frame_shape, dtype=np.uint8)
    write_times_s = np.empty(frame_count, dtype=np.float64)
    loop_intervals_s = np.empty(max(0, frame_count - 1), dtype=np.float64)

    if disable_gc:
        gc.disable()

    last_loop_start_s = None
    try:
        for frame_index in range(frame_count):
            frame.fill(frame_index % 255)

            loop_start_s = time.perf_counter()
            if last_loop_start_s is not None:
                loop_intervals_s[frame_index - 1] = loop_start_s - last_loop_start_s

            slm.WriteImageToSLM(
                frame,
                channelIdx=channel_index,
                wait=wait_for_display,
                display_timeout_ms=display_timeout_ms,
            )

            write_done_s = time.perf_counter()
            write_times_s[frame_index] = write_done_s - loop_start_s
            last_loop_start_s = loop_start_s

    finally:
        if disable_gc:
            gc.enable()

    return {
        "write_times_s": write_times_s,
        "loop_intervals_s": loop_intervals_s,
        "write_stats": timing_stats(write_times_s),
        "loop_interval_stats": timing_stats(loop_intervals_s)
        if loop_intervals_s.size
        else None,
    }


def measure_slm_direct_shm_write_timing(
    slm,
    frame_count=1000,
    wait_for_display=False,
    display_timeout_ms=10000,
    disable_gc=True,
):
    from pyMilk.interfacing.isio_shmlib import SHM

    frame_count = int(frame_count)
    shm = SHM(slm.shm_name, autoSqueeze=False)
    image_cube_shape = tuple(slm.image_shape)
    write_times_s = np.empty(frame_count, dtype=np.float64)
    loop_intervals_s = np.empty(max(0, frame_count - 1), dtype=np.float64)

    if disable_gc:
        gc.disable()

    last_loop_start_s = None
    try:
        for frame_index in range(frame_count):
            image_cube = np.random.randint(
                0,
                256,
                image_cube_shape,
                dtype=np.uint8,
            )

            loop_start_s = time.perf_counter()
            if last_loop_start_s is not None:
                loop_intervals_s[frame_index - 1] = loop_start_s - last_loop_start_s

            shm.set_data(image_cube)
            shm_counter = int(shm.get_counter())

            if wait_for_display:
                slm.WaitForSLMDisplayAck(
                    shm_counter=shm_counter,
                    timeout_ms=display_timeout_ms,
                )

            write_done_s = time.perf_counter()
            write_times_s[frame_index] = write_done_s - loop_start_s
            last_loop_start_s = loop_start_s

    finally:
        if disable_gc:
            gc.enable()
        shm.close()

    return {
        "write_times_s": write_times_s,
        "loop_intervals_s": loop_intervals_s,
        "write_stats": timing_stats(write_times_s),
        "loop_interval_stats": timing_stats(loop_intervals_s)
        if loop_intervals_s.size
        else None,
    }


def plot_slm_write_timing(timing_result, title="SLM write timing"):
    write_times_ms = timing_result["write_times_s"] * 1e3
    loop_intervals_ms = timing_result["loop_intervals_s"] * 1e3

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))

    axes[0].plot(write_times_ms, ".")
    axes[0].set_title("Write call")
    axes[0].set_xlabel("Frame")
    axes[0].set_ylabel("ms")
    axes[0].grid(True)

    axes[1].plot(loop_intervals_ms, ".")
    axes[1].set_title("Loop interval")
    axes[1].set_xlabel("Frame")
    axes[1].set_ylabel("ms")
    axes[1].grid(True)

    axes[2].hist(loop_intervals_ms, bins=80)
    axes[2].set_title("Loop interval histogram")
    axes[2].set_xlabel("ms")
    axes[2].set_ylabel("count")
    axes[2].grid(True)

    fig.suptitle(title)
    fig.tight_layout()
    return fig, axes


def measure_slm_camera_delay_response(
    slm,
    phasemask,
    camera,
    camera_roi_center,
    camera_roi_half_width,
    camera_roi_half_height,
    delay_count=10,
    delay_min_s=0.0,
    delay_max_s=0.1,
    measurement_count=1,
    channel="Red",
    stripe_width=12,
    stripe_phase_value=np.pi / 3,
    stripe_orientation="vertical",
    initial_settle_s=0.1,
    wait_for_display=True,
    display_timeout_ms=10000,
    restore_continuous_camera=True,
):
    channel_index = resolve_slm_channel_index(slm, channel)
    delay_values_s = np.linspace(float(delay_min_s), float(delay_max_s), int(delay_count))
    metric_values = np.zeros((int(measurement_count), delay_values_s.size), dtype=np.float64)
    reblank_power_values = np.zeros_like(metric_values)
    write_durations_s = []

    blank_mask, stripe_mask = make_blank_and_stripe_masks(
        phasemask=phasemask,
        stripe_width=stripe_width,
        stripe_phase_value=stripe_phase_value,
        stripe_orientation=stripe_orientation,
        mask_shape=(int(slm.monitor_height), int(slm.monitor_width)),
    )

    camera.SetSoftwareTriggerMode()
    try:
        _, write_duration_s = write_slm_frame_and_time(
            slm,
            blank_mask,
            channel_index=channel_index,
            wait_for_display=wait_for_display,
            display_timeout_ms=display_timeout_ms,
        )
        write_durations_s.append(write_duration_s)
        slm.SetRefreshRate(float(initial_settle_s))
        camera.FireSoftwareTrigger()
        blank_frame = camera.GetFrame()
        blank_power = camera_utils.get_relative_power(
            frame=blank_frame,
            centre=camera_roi_center,
            x_half_width=camera_roi_half_width,
            y_half_width=camera_roi_half_height,
        )
        if blank_power == 0:
            raise ValueError(
                "Blank SLM ROI power is zero; adjust the camera ROI or exposure "
                "before calculating stripe / blank power ratios"
            )

        _, write_duration_s = write_slm_frame_and_time(
            slm,
            stripe_mask,
            channel_index=channel_index,
            wait_for_display=wait_for_display,
            display_timeout_ms=display_timeout_ms,
        )
        write_durations_s.append(write_duration_s)
        time.sleep(float(initial_settle_s))
        camera.FireSoftwareTrigger()
        stripe_reference_frame = camera.GetFrame()
        stripe_reference_power = camera_utils.get_relative_power(
            frame=stripe_reference_frame,
            centre=camera_roi_center,
            x_half_width=camera_roi_half_width,
            y_half_width=camera_roi_half_height,
        )

        for delay_index, delay_s in enumerate(delay_values_s):
            print(f"SLM-to-camera delay: {delay_s * 1e3:.3f} ms")
            slm.SetRefreshRate(delay_s)  # Force SLM to update the display immediately
            

            for measurement_index in range(int(measurement_count)):
                if delay_index == 0 and measurement_index == 0:
                    print(f"Initial stripe power: {stripe_reference_power}")
                    print(f"Initial blank power: {blank_power}")
                    print(
                        "Initial stripe / blank power: "
                        f"{stripe_reference_power / blank_power}"
                    )
                    initalmetric_value = stripe_reference_power / blank_power

                _, write_duration_s = write_slm_frame_and_time(
                    slm,
                    stripe_mask,
                    channel_index=channel_index,
                    wait_for_display=wait_for_display,
                    display_timeout_ms=display_timeout_ms,
                )
                write_durations_s.append(write_duration_s)
                # time.sleep(float(delay_s))
                camera.FireSoftwareTrigger()
                stripe_frame = camera.GetFrame()
                stripe_power = camera_utils.get_relative_power(
                    frame=stripe_frame,
                    centre=camera_roi_center,
                    x_half_width=camera_roi_half_width,
                    y_half_width=camera_roi_half_height,
                )

                _, write_duration_s = write_slm_frame_and_time(
                    slm,
                    blank_mask,
                    channel_index=channel_index,
                    wait_for_display=wait_for_display,
                    display_timeout_ms=display_timeout_ms,
                )
                write_durations_s.append(write_duration_s)
                # time.sleep(float(delay_s))
                camera.FireSoftwareTrigger()
                reblank_frame = camera.GetFrame()
                reblank_power = camera_utils.get_relative_power(
                    frame=reblank_frame,
                    centre=camera_roi_center,
                    x_half_width=camera_roi_half_width,
                    y_half_width=camera_roi_half_height,
                )

                metric_values[measurement_index, delay_index] = abs(stripe_power / blank_power - initalmetric_value)
                reblank_power_values[measurement_index, delay_index] = reblank_power / blank_power

            print(np.mean(metric_values[:, delay_index]))

    finally:
        camera.SetContinuousMode()

    write_durations_s = np.asarray(write_durations_s, dtype=np.float64)
    return {
        "delay_values_s": delay_values_s,
        "metric_values": metric_values,
        "reblank_power_values": reblank_power_values,
        "blank_mask": blank_mask,
        "stripe_mask": stripe_mask,
        "blank_power": blank_power,
        "stripe_reference_power": stripe_reference_power,
        "write_durations_s": write_durations_s,
        "write_stats": timing_stats(write_durations_s),
    }


def plot_slm_camera_delay_response(result):
    delay_values_ms = result["delay_values_s"] * 1e3
    metric_values = result["metric_values"]

    fig, ax = plt.subplots(figsize=(6, 4))
    for measurement_index in range(metric_values.shape[0]):
        ax.plot(delay_values_ms, metric_values[measurement_index], ".-", alpha=0.8)

    ax.set_xlabel("SLM-to-camera delay [ms]")
    ax.set_ylabel("Stripe / blank power")
    ax.grid(True)
    fig.tight_layout()
    return fig, ax
