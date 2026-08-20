"""Run the configured coarse and fine SLM centre-alignment procedure."""

import argparse
from datetime import datetime
from pathlib import Path

from JazLabs.launchers.config import load_config, merge_overrides


def build_parser():
    parser = argparse.ArgumentParser(
        description="Align the configured SLM mask centre to the incident beam."
    )
    parser.add_argument(
        "--config",
        default="default_lab",
        help="Config module name or path to a Python config file.",
    )
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=None,
        help="Override the directory used for alignment plots.",
    )
    parser.add_argument(
        "--save-plots",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Save alignment plots (configured by default).",
    )
    parser.add_argument(
        "--show-plots",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show interactive alignment plots (configured by default).",
    )
    parser.add_argument(
        "--run-beam-radius-scan",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Run the optional beam-radius scan after centre alignment.",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    alignment_config = merge_overrides(
        config.get("SLM_CENTER_ALIGNMENT_CONFIG", {}),
        {
            "output_directory": args.output_directory,
            "save_plots": args.save_plots,
            "show_plots": args.show_plots,
            "run_beam_radius_scan": args.run_beam_radius_scan,
        },
    )

    required_settings = (
        "x_beam_center_on_camera",
        "y_beam_center_on_camera",
        "x_beam_window_width",
        "y_beam_window_width",
        "slm_channel",
        "polarisation",
        "stripe_width",
        "mask_size",
        "coarse_step_count",
        "camera_host",
        "camera_command_port",
        "camera_frame_port",
        "slm_host",
        "slm_command_port",
        "slm_display_port",
        "slm_pixel_size",
        "slm_wavelength",
        "slm_refresh_time",
    )
    missing_settings = [
        setting for setting in required_settings if setting not in alignment_config
    ]
    if missing_settings:
        missing_list = ", ".join(missing_settings)
        raise ValueError(
            "SLM_CENTER_ALIGNMENT_CONFIG is missing required settings: "
            f"{missing_list}"
        )

    save_plots = alignment_config.get("save_plots", True)
    show_plots = alignment_config.get("show_plots", True)
    output_directory = Path(
        alignment_config.get("output_directory", Path.cwd())
    ).expanduser().resolve()
    plot_file_format = alignment_config.get("plot_file_format", "png").lstrip(".")
    if not plot_file_format or "/" in plot_file_format or "\\" in plot_file_format:
        raise ValueError("plot_file_format must be a file extension such as 'png'")

    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if save_plots:
        output_directory.mkdir(parents=True, exist_ok=True)
        print(f"Alignment plots will be saved in {output_directory}")

    # Delay hardware imports so --help works without the optional lab stack.
    import matplotlib.pyplot as plt
    import numpy as np

    import JazLabs.hardware.Cameras.Camera_Client as CameraClientLib
    import JazLabs.hardware.SLM.PhaseMaskClass as PhaseMaskClass
    from JazLabs.hardware.SLM.SLMStack.SLM_Client import SLMClient
    import JazLabs.procedures.SLM.SLM_CenterAlignment as SLM_CenterAlignment

    plt.style.use("dark_background")
    camera_client = None
    slm_client = None

    try:
        camera_client = CameraClientLib.CameraClient(
            host=alignment_config["camera_host"],
            command_port=alignment_config["camera_command_port"],
            frame_pub_port=alignment_config["camera_frame_port"],
            timeout_ms=alignment_config.get("camera_timeout_ms", 60000),
            client_id=alignment_config.get(
                "camera_client_id", "slm_center_alignment"
            ),
        )

        slm_client = SLMClient(
            client_id=alignment_config.get("slm_client_id"),
            host=alignment_config["slm_host"],
            command_port=alignment_config["slm_command_port"],
            display_pub_port=alignment_config["slm_display_port"],
            timeout_ms=alignment_config.get("slm_timeout_ms", 5000),
            attach_viewer_shared_memory=False,
        )
        slm_channel = alignment_config["slm_channel"]
        polarisation = alignment_config["polarisation"]
        phase_mask = PhaseMaskClass.PhaseMaskObject(
            SLMObject=slm_client,
            ActiveRGBChannels=[slm_channel],
            pixel_size=alignment_config["slm_pixel_size"],
            wavelength=alignment_config["slm_wavelength"],
        )
        if alignment_config.get("load_lut_from_file", False):
            slm_client.LoadLutFile(str(alignment_config["slm_lut_file"]))
        slm_client.SetRefreshRate(alignment_config["slm_refresh_time"])

        alignment = SLM_CenterAlignment.AlginmentObj(
            slmObjs=[phase_mask],
            CamObjs=[camera_client],
        )

        coarse_metric, _coarse_metric_log, coarse_positions = (
            alignment.SweepAcrossSLM_StripProfile(
                ObjIdx=0,
                channel=slm_channel,
                stepCount=alignment_config["coarse_step_count"],
                StartingSweepPoint=alignment_config.get(
                    "coarse_starting_sweep_point", 0
                ),
                strip_width=alignment_config["stripe_width"],
                avgFrameCount=alignment_config.get("average_frame_count", 1),
                ixCamCenter=alignment_config["y_beam_center_on_camera"],
                iyCamCenter=alignment_config["x_beam_center_on_camera"],
                x_half_width=alignment_config["x_beam_window_width"] // 2,
                y_half_width=alignment_config["y_beam_window_width"] // 2,
                MetricType=alignment_config.get(
                    "coarse_metric_type", "POWERMinusHalfRef"
                ),
            )
        )

        y_minimum_index = np.nanargmin(coarse_metric[0, :, 0])
        x_minimum_index = np.nanargmin(coarse_metric[1, :, 0])
        coarse_y_center = int(coarse_positions[0, y_minimum_index, 0])
        coarse_x_center = int(coarse_positions[1, x_minimum_index, 0])

        coarse_figure = plt.figure(figsize=(8, 5))
        plt.plot(
            coarse_positions[0, :, 0],
            coarse_metric[0, :, 0],
            ".-",
            label="Y sweep",
        )
        plt.plot(
            coarse_y_center,
            coarse_metric[0, y_minimum_index, 0],
            "ro",
            label="Y minimum",
        )
        plt.plot(
            coarse_positions[1, :, 0],
            coarse_metric[1, :, 0],
            ".-",
            label="X sweep",
        )
        plt.plot(
            coarse_x_center,
            coarse_metric[1, x_minimum_index, 0],
            "ro",
            label="X minimum",
        )
        plt.xlabel("SLM stripe curtain edge position [pixels]")
        plt.ylabel("Alignment metric")
        plt.grid(alpha=0.3)
        plt.legend()

        if save_plots:
            coarse_plot_path = (
                output_directory
                / f"{run_timestamp}_coarse_alignment.{plot_file_format}"
            )
            coarse_figure.savefig(coarse_plot_path, bbox_inches="tight")
            print(f"Saved coarse alignment plot: {coarse_plot_path}")
        if show_plots:
            plt.show()
        else:
            plt.close(coarse_figure)

        for configured_polarisation in ("H", "V"):
            phase_mask.polProps[slm_channel][
                configured_polarisation
            ].polEnabled = configured_polarisation == polarisation
        phase_mask.AllMaskProperties[slm_channel][polarisation][0].center[1] = (
            coarse_x_center
        )
        phase_mask.AllMaskProperties[slm_channel][polarisation][0].center[0] = (
            coarse_y_center
        )
        print(f"Coarse SLM centre: X={coarse_x_center}, Y={coarse_y_center}")

        fine_x_center, fine_y_center = (
            alignment.PerformCenterAlignment_GoldenSearch(
                ObjIdx=0,
                channel=slm_channel,
                pol=polarisation,
                ApplyZernike=False,
                MaskSize=alignment_config["mask_size"],
                PixelsCountFromCenters=alignment_config["coarse_step_count"],
                PlotTracking=save_plots or show_plots,
                BackgroundPhase=0,
                avgFrameCount=alignment_config.get("average_frame_count", 1),
                MetricType=alignment_config.get(
                    "fine_metric_type", "POWERMinusHalfRef"
                ),
                stripe_width=alignment_config["stripe_width"],
                ixCamCenter=alignment_config["y_beam_center_on_camera"],
                iyCamCenter=alignment_config["x_beam_center_on_camera"],
                x_half_width=alignment_config["x_beam_window_width"] // 2,
                y_half_width=alignment_config["y_beam_window_width"] // 2,
                Verbose=alignment_config.get("verbose", False),
                PlotOutputDirectory=output_directory if save_plots else None,
                PlotFilenamePrefix=f"{run_timestamp}_fine_alignment",
                PlotFileFormat=plot_file_format,
                ShowPlots=show_plots,
            )
        )
        print(f"Fine SLM centre: X={fine_x_center}, Y={fine_y_center}")

        mask_properties_filename = alignment_config.get(
            "mask_properties_filename", "SLM_CenterAlignment"
        )
        if alignment_config.get("save_mask_properties", True):
            phase_mask.saveMaskProperties(filenamePrefix=mask_properties_filename)

        if alignment_config.get("load_saved_properties_after_alignment", False):
            phase_mask.LoadMaskProperties(filenamePrefix=mask_properties_filename)

        if alignment_config.get("run_beam_radius_scan", True):
            beam_radius, beam_metric = alignment.Beam_size_scan_on_SLM(
                ObjIdx=0,
                channel=slm_channel,
                pol=polarisation,
                ApplyZernike=False,
                InitalRadius=alignment_config.get(
                    "beam_radius_scan_initial_radius", 1
                ),
                FinalRadius=alignment_config.get(
                    "beam_radius_scan_final_radius", 150
                ),
                radiusStep=alignment_config.get("beam_radius_scan_step", 1),
                avgFrameCount=alignment_config.get("average_frame_count", 1),
                PlotResults=False,
                MetricType=alignment_config.get(
                    "beam_radius_metric_type", "POWER"
                ),
                ixCamCenter=alignment_config["y_beam_center_on_camera"],
                iyCamCenter=alignment_config["x_beam_center_on_camera"],
                x_half_width=alignment_config["x_beam_window_width"] // 2,
                y_half_width=alignment_config["y_beam_window_width"] // 2,
            )
            beam_plot_path = None
            if save_plots:
                beam_plot_path = (
                    output_directory
                    / f"{run_timestamp}_beam_radius_scan.{plot_file_format}"
                )
            SLM_CenterAlignment.FindPlateauStart(
                beam_radius,
                beam_metric,
                smoothing_window=alignment_config.get(
                    "plateau_smoothing_window", 15
                ),
                plateau_tail_fraction=alignment_config.get(
                    "plateau_tail_fraction", 0.20
                ),
                PlotResults=save_plots or show_plots,
                PlotSavePath=beam_plot_path,
                ShowPlot=show_plots,
            )
            if beam_plot_path is not None:
                print(f"Saved beam-radius plot: {beam_plot_path}")
    finally:
        if slm_client is not None:
            slm_client.close()
        if camera_client is not None:
            camera_client.close()


if __name__ == "__main__":
    main()
