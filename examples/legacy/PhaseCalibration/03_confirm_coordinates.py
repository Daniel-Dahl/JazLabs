"""Save a camera frame annotated with the configured diffraction apertures."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import JazLabs.hardware.Cameras.Camera_Client as CameraClientLib

import phase_calibration_config as config


def main():
    camera_client = None

    try:
        camera_client = CameraClientLib.CameraClient(
            host=config.SERVER_HOST,
            command_port=config.CAMERA_COMMAND_PORT,
            frame_pub_port=config.CAMERA_FRAME_PORT,
            timeout_ms=60000,
            client_id="slm_phase_calibration_coordinate_check",
        )
        frame = camera_client.GetFrame(WaitForNewFrame=True)
    finally:
        if camera_client is not None:
            camera_client.close()

    frame_rows, frame_columns = frame.shape[:2]
    figure, axis = plt.subplots(figsize=(9, 7))
    axis.imshow(frame)

    for order_label, center_row_column in config.DIFFRACTION_ORDER_CENTERS.items():
        center_row, center_column = center_row_column
        if not (0 <= center_row < frame_rows and 0 <= center_column < frame_columns):
            raise ValueError(
                f"{order_label} center {center_row_column} is outside frame "
                f"shape {(frame_rows, frame_columns)}"
            )

        rectangle = Rectangle(
            (
                center_column - config.APERTURE_HALF_WIDTH_X,
                center_row - config.APERTURE_HALF_WIDTH_Y,
            ),
            2 * config.APERTURE_HALF_WIDTH_X,
            2 * config.APERTURE_HALF_WIDTH_Y,
            fill=False,
            linewidth=1.5,
            label=f"{order_label}: {center_row_column}",
        )
        axis.add_patch(rectangle)

    axis.set_title("Configured diffraction-order apertures")
    axis.set_xlabel("Camera column [pixels]")
    axis.set_ylabel("Camera row [pixels]")
    axis.legend()
    figure.tight_layout()

    config.RESULTS_DIRECTORY.mkdir(parents=True, exist_ok=True)
    output_path = config.RESULTS_DIRECTORY / "diffraction_order_centers.png"
    figure.savefig(output_path, dpi=160)
    plt.close(figure)

    print("Configured camera centres [row, column]:")
    for order_label, center_row_column in config.DIFFRACTION_ORDER_CENTERS.items():
        print(f"  {order_label}: {center_row_column}")
    print(f"Saved coordinate check: {output_path}")


if __name__ == "__main__":
    main()
