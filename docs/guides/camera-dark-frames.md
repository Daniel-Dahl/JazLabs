# Camera Dark Frames

A dark frame records the camera signal when no useful light reaches the
sensor. It captures the offset, hot pixels, fixed-pattern structure, and other
camera background that can be removed from later images acquired with the same
settings.

JazLabs acquires a sequence of software-triggered frames, computes their
floating-point mean, and saves the result with enough metadata to identify the
camera conditions.

## Match the acquisition settings

A dark frame is only representative when the camera configuration matches the
illuminated data. Before acquisition, set and record the same:

- exposure time and frame rate;
- region of interest and binning;
- pixel format and bit depth;
- analog or digital gain; and
- camera temperature or cooling state, when relevant.

Block the beam or fit a lens cap so that no useful light reaches the sensor.
The command asks for confirmation before it changes the trigger mode.

## Configuration

Camera connection details come from the named entry in `CAMERA_SERVERS`.
Defaults for the procedure come from `DARK_FRAME_CONFIG`. The supplied
`src/JazLabs/launchers/configs/default_lab.py` uses the `cam_slm` camera,
averages 100 frames, and writes to `data/Camera/DarkFrames/`.

For a different setup, edit a copied launcher configuration and select it with
`--config`. A minimal procedure block is:

```python
DARK_FRAME_CONFIG = {
    "camera_name": "cam_slm",
    "num_frames": 100,
    "description": "",
    "output_directory": JAZLABS_ROOT / "data" / "Camera" / "DarkFrames",
    "save_preview": True,
}
```

## Acquiring a dark frame

Start the camera server, set the camera controls, and then run:

```bash
jazlabs-server-camera --config default_lab --name cam_slm

jazlabs-camera-dark-frame \
    --config default_lab \
    --camera cam_slm \
    --num-frames 100 \
    --description "lens cap fitted"
```

Use `--yes` only for an intentionally non-interactive acquisition after the
camera has already been made dark. Other useful overrides are:

```bash
jazlabs-camera-dark-frame --config default_lab --no-save-preview
jazlabs-camera-dark-frame --config default_lab \
    --output-directory /path/to/calibration/output
```

If the camera begins in continuous mode, JazLabs temporarily selects software
triggering and restores continuous mode when acquisition finishes. It refuses
to alter an active hardware-trigger configuration because the current client
cannot reliably restore the trigger-line settings.

## Output files

Each acquisition produces files with a shared descriptive name, for example:

```text
darkframe_20260810_143005_cam_slm_exp-100us_fps-30_lens-cap-fitted.npy
darkframe_20260810_143005_cam_slm_exp-100us_fps-30_lens-cap-fitted.json
darkframe_20260810_143005_cam_slm_exp-100us_fps-30_lens-cap-fitted.png
```

The NPY file contains the `float64` mean and is the file to use for numerical
subtraction. The JSON sidecar contains the timestamp, camera connection,
measured exposure and FPS, frame count, array shape and type, summary
statistics, camera serial number, and operator description. The PNG is a
visual preview only.

### Output from `take_darkframe`

Code that calls `JazLabs.utils.camera_tools.take_darkframe` directly uses a
simpler two-file format. If `save_path` is omitted or `None`, the files are
saved in `calibrations/Camera/`. A supplied path overrides that directory.
Both files use the same timestamp:

```text
darkframe_20260810_143005.npy
darkframe_meta_20260810_143005.npy
```

The first file is the `float64` mean dark frame. The `darkframe_meta_...npy`
file contains a Python dictionary with `num_frames`, `wait_time`, `timestamp`,
`camera_type`, `camera_serial_number`, `exposure_time`, `fps`, `gain`, and
`frame_shape`. For a camera client, `camera_type` is the configured hardware
type reported by the server; direct camera objects fall back to their
model/type attribute or Python class. The serial number is read through
`GetSerialNumber()` in both cases. These settings should be checked against the
illuminated acquisition before using the dark frame.

Load a trusted metadata sidecar with:

```python
metadata = np.load(
    "calibrations/Camera/darkframe_meta_....npy",
    allow_pickle=True,
).item()
print(metadata)
```

Because this dictionary is stored as a pickled NumPy object, only load metadata
files from a trusted source. The command-line procedure described above instead
uses the JSON sidecar and optional PNG preview.

Load and inspect the calibration with NumPy:

```python
import numpy as np

dark_frame = np.load("data/Camera/DarkFrames/darkframe_....npy")
print(dark_frame.shape, dark_frame.dtype)
print(dark_frame.min(), dark_frame.mean(), dark_frame.max())
```

Subtract it from an illuminated frame using a signed or floating-point type so
that low-valued pixels do not wrap around:

```python
corrected_frame = illuminated_frame.astype(np.float64) - dark_frame
```

## Checking calibration quality

Inspect the PNG and the summary statistics before using the result. Unexpected
bright regions suggest a light leak. Saturated pixels, strong gradients, or
row and column structure may indicate unsuitable camera settings or a sensor
problem. A dark frame should be reacquired whenever relevant camera settings
or operating conditions change.
