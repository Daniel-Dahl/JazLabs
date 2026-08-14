# SLM phase calibration from the terminal

These scripts reproduce the practical workflow in
`notebooks/SLMPhaseCalibration.ipynb` without requiring Jupyter. The method
displays a binary strip grating, measures the zeroth and both first diffraction
orders while grey level is swept from 0 to 255, fits a monotonic phase response,
and uses that response to construct a new SLM LUT.

Run all commands below from the `JazLabs` repository directory. Install the
package in editable mode first if necessary:

```powershell
python -m pip install -e .
```

## Before starting

Edit `examples/PhaseCalibration/phase_calibration_config.py`. In particular,
check the server host and ports, SLM channel and polarisation, mask-properties
filename, starting LUT, grating settings, camera aperture size, output paths,
and fit settings.

Start the camera server, SLM server, and camera viewer in separate terminals.
The exact camera name and SLM-side configuration depend on the lab setup. For a
configured JazLabs installation, the commands have this form:

```powershell
jazlabs-server-camera --name <camera-name>
jazlabs-server-slm
jazlabs-view-camera --name <camera-name>
```

If the camera or SLM is attached to another computer, start its server or bridge
there and set `SERVER_HOST` and the ports to the address exposed to the scripts.
The physical laser interlock, SLM power limits, and normal lab procedures remain
authoritative.

## Workflow and scripts

### 1. Configure and connect

```powershell
python examples/PhaseCalibration/01_check_hardware_connections.py
```

This checks both server connections, prints camera and SLM properties, loads the
saved SLM mask centres, and loads `INITIAL_LUT_FILE`. Resolve connection, LUT,
or centre-alignment errors before continuing.

### 2. Display the binary grating and locate the orders

```powershell
python examples/PhaseCalibration/02_locate_diffraction_orders.py
```

The script first clears the SLM. Read the zeroth-order `(x, y)` position from
the live camera viewer and press Enter. It then displays the binary grating;
read the `+1` and `-1` positions. The script clears the SLM when it exits, even
after an error or Ctrl+C.

To save an annotated check while the grating is still displayed, leave script
02 waiting at its second prompt and run script 03 from another terminal.

### 3. Enter and confirm the camera coordinates

Convert viewer `(x, y)` values to `[row, column] = [y, x]` and edit
`DIFFRACTION_ORDER_CENTERS` in `phase_calibration_config.py`. Then run:

```powershell
python examples/PhaseCalibration/03_confirm_coordinates.py
```

This captures a camera frame, checks that all centres are inside it, draws the
three integration apertures, and saves `diffraction_order_centers.png`. Confirm
that each rectangle encloses only its intended order and does not clip the spot.

### 4. Acquire and save the grey-level sweep

```powershell
python examples/PhaseCalibration/04_acquire_calibration.py
```

The script loads `INITIAL_LUT_FILE`, scans grey levels in ascending order from
0 to 255, averages `CAMERA_FRAME_AVERAGES` frames at every level, and measures
the three configured apertures. The last value in each saved array is a
cleared-SLM reference. The raw arrays and JSON metadata are saved to
`RAW_DATA_FILE`; `raw_diffraction_order_power.png` is saved in
`RESULTS_DIRECTORY`. The procedure restores continuous camera acquisition and
clears the SLM before the clients close.

Do not interrupt the scan unless necessary. Ascending acquisition avoids the
large 255-to-0 transition that can compromise an SLM calibration.

### 5. Fit and inspect the phase response

```powershell
python examples/PhaseCalibration/05_fit_phase_response.py
```

This is an offline step: it does not connect to hardware. It loads
`RAW_DATA_FILE`, jointly fits the zeroth order and the sum of the first orders,
and saves the recovered phase and fit arrays to `FIT_DATA_FILE`. Inspect
`phase_response_fit.png` in `RESULTS_DIRECTORY`.

If the fit is poor, edit the `FIT_*` settings and rerun only this script. Accept
the fit only when it follows both measured power curves and the recovered phase
is smooth, monotonic, and physically plausible.

### 6. Explicitly approve and generate the LUT

Set `BASE_LUT_FILE` to the LUT used for the acquisition. Set
`NEW_LUT_PREFIX` to a new, unused prefix, then run:

```powershell
python examples/PhaseCalibration/06_generate_lut.py --accept-fit
```

Without `--accept-fit`, no LUT is generated. Existing `.lut` or `.blt` outputs
are not overwritten. The script writes both formats beside `NEW_LUT_PREFIX`
and saves diagnostic plots/data in `RESULTS_DIRECTORY`.

If the SLM server is on another computer, copy the generated `.lut` to that
computer before starting the next measurement. `INITIAL_LUT_FILE` must be a path
visible to the SLM server, not merely a path visible to the computer running
these scripts.

### 7. Repeat scripts 04, 05, and 06 with the new LUT

There is deliberately no separate validation script. Each newly generated LUT
becomes the starting LUT for the next normal acquisition and fit:

1. Set `INITIAL_LUT_FILE` and `BASE_LUT_FILE` to the most recently generated LUT.
2. Choose new `RAW_DATA_FILE`, `FIT_DATA_FILE`, `RESULTS_DIRECTORY`, and
   `NEW_LUT_PREFIX` values so the previous iteration remains recoverable.
3. Run script 04 to acquire a new grey-level sweep using that LUT.
4. Run script 05 and inspect the new `phase_response_fit.png`. A successful LUT
   should make the recovered phase closely follow the dashed linear reference.
5. If the response is sufficiently linear, keep that LUT and stop. Otherwise,
   accept the new fit and run script 06 to generate the next LUT iteration.

Repeat scripts 04, 05, and 06 until the fitted response is sufficiently linear
for the experiment.

## Expected results and troubleshooting

With grey level zero, both halves of the binary grating have the same value, so
the pattern is effectively uniform: the zeroth order should be strong and the
first orders weak. As the relative phase between alternating strips approaches
pi, power should move out of the zeroth order and into the first orders. The
zeroth-order and summed-first-order curves should therefore be complementary.

The `+1` and `-1` curves should have similar shapes. They do not need identical
absolute powers, but a large disagreement can indicate an incorrect centre,
clipped spot, unequal aperture, optical asymmetry, or saturation. A flat curve
usually means the wrong order is being measured, the SLM is not updating, or
the camera signal has insufficient dynamic range.

Before LUT correction, the recovered phase should be smooth and monotonic but
may be visibly nonlinear with grey level. Its stroke must cover the requested
`PHASE_STROKE`; otherwise the generated LUT will run out of usable voltage
range. When script 05 is rerun with a successful LUT, the recovered phase should
follow the dashed linear reference from approximately 0 to 2 pi. Small smooth
residuals are normal; discontinuities, reversals, or a plateau before grey level
255 indicate that the fit or voltage range needs attention.

Also check the LUT-generation diagnostic output. The new voltage values should
remain monotonic, the minimum voltage gradient should not be negative, and the
selected phase region should span the target phase stroke.

## Calibration result figures

This section is intentionally arranged as a results record. Copy selected PNGs
from `RESULTS_DIRECTORY` into `examples/PhaseCalibration/images/`, rename them
as shown below, and remove the italic placeholder below each image when the
calibration is documented.

### Diffraction-order locations and apertures

![Diffraction-order locations](images/01_diffraction_order_locations.png)

*Insert the annotated camera frame here. Each rectangle should be centred on a
single diffraction order without clipping it or including a neighbouring spot.*

### Raw zeroth- and first-order powers

![Raw diffraction-order powers](images/02_raw_diffraction_order_powers.png)

*Insert the raw grey-level sweep here. Expect complementary zeroth-order and
summed-first-order behaviour, with similarly shaped +1 and -1 curves.*

### Recovered phase before LUT correction

![Initial phase-response fit](images/03_initial_phase_response_fit.png)

*Insert the accepted fit here. The fitted power curves should track the data and
the recovered phase should be smooth and monotonic.*

### Generated LUT diagnostics

![Generated LUT diagnostics](images/04_generated_lut_diagnostics.png)

*Insert the voltage/phase diagnostic plot here. Check voltage monotonicity and
that the selected response spans the requested phase stroke.*

### Phase response after LUT correction

![Corrected phase-response fit](images/05_corrected_phase_response_fit.png)

*Insert the final script-05 fit here. The recovered phase should closely track
the dashed linear-phase reference across grey levels 0 to 255.*

### Calibration notes

- SLM identifier:
- Wavelength and polarisation:
- Calibration date:
- Starting/base LUT:
- Installed LUT:
- Camera exposure and frame averages:
- Diffraction-order centres `[row, column]`:
- Fit settings:
- Recovered phase stroke before correction:
- Recovered phase stroke after correction:
- Deviations, rejected iterations, or other observations:
