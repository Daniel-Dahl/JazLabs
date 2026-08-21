# Intensity-Based SLM Centre Alignment

This guide describes the **intensity-based** process used by JazLabs to locate
the centre of the beam incident on a spatial light modulator (SLM). The
resulting position is stored in the phase-mask properties. Accurate centering
matters because later masks, apertures, and phase corrections are positioned
relative to this coordinate.

This process uses camera intensity measurements from the zeroth diffraction
order. It does not reconstruct the optical phase or complex field. A separate
guide will describe SLM alignment using digHolo when that workflow is added.

## Intensity-based measurement principle

The procedure observes the zeroth diffraction order with a camera while a
binary phase grating is moved across the SLM. After subtracting the median
background, JazLabs sums the pixel intensities inside a selected measurement
window to obtain a scalar relative-power measurement. The grating sends
illuminated light into higher diffraction orders, so the measured zeroth-order
power falls as the grating covers the beam.

The camera measurement window must contain the zeroth order and exclude the
first order. JazLabs compares the intensity-derived power with half the
unobstructed reference power. The grating-edge position that minimizes this
difference is an estimate of the beam centre along the scanned axis. No phase
reconstruction is used in this calculation.

Alignment has three stages:

1. A coarse stripe sweep estimates the X and Y centres over a broad area.
2. Golden-section searches approach the beam from both sides of each axis.
   Averaging the two minima reduces sensitivity to beam asymmetry and stripe
   imperfections.
3. An optional circular-aperture scan estimates beam radius from the point at
   which the measured power reaches its final plateau.

The fine X and Y coordinates are written into the active phase-mask
properties. By default those properties and timestamped diagnostic plots are
also saved.

## Before running

The camera server and the SLM bridge must already be running. With the
default configuration:

```bash
jazlabs-server-camera --config default_lab --name cam_slm
jazlabs-bridge-slm --config default_lab
```

Use the camera viewer to locate the zeroth order and choose a measurement
window that does not include the first order:

```bash
jazlabs-view-camera --config default_lab --name cam_slm
```

Review `SLM_CENTER_ALIGNMENT_CONFIG` in
`src/JazLabs/launchers/configs/default_lab.py` before operating the hardware.
In particular, confirm:

- the camera window centre and width;
- camera and SLM hosts, ports, and shared-memory name;
- SLM channel, polarization, pixel size, and wavelength;
- the mask size, stripe width, and scan ranges; and
- whether the LUT, saved mask properties, plots, and radius scan are wanted.

For another setup, copy the configuration module, adjust it, and pass its
module name or file path to `--config`.

## Running the intensity-based alignment

After installing JazLabs, run:

```bash
jazlabs-slm-center-alignment --config default_lab
```

Useful overrides include:

```bash
jazlabs-slm-center-alignment --config default_lab --no-show-plots
jazlabs-slm-center-alignment --config default_lab --no-run-beam-radius-scan
jazlabs-slm-center-alignment --config default_lab \
    --output-directory /path/to/alignment-plots
```

The command prints the coarse and fine coordinates. With the default settings,
plots are written to `data/SLM/CenterAlignment/`, mask properties are written
under `data/SLM/MaskProperties/`, and timestamped names keep successive runs
separate.

## Interpreting the intensity-based results

The coarse plot should show a distinct minimum for each axis. A flat or noisy
trace usually means that the camera window includes the wrong diffraction
order, the SLM pattern is not reaching the display, the beam lies outside the
scan, or the camera exposure is unsuitable.

The fine plot contains two searches per axis. Their minima should be reasonably
close. A large separation can indicate an asymmetric or clipped beam, an
incorrect coarse centre, or a stripe width that is poorly matched to the beam.

The optional radius curve should rise and settle into a plateau. Treat the
reported intersection as a practical aperture-size estimate, not a hard
physical beam boundary.

## Common problems

- A connection timeout means the named camera server, SLM bridge, or
  SLM server and bridge chain is unavailable at the configured address.
- A missing shared-memory error means the SLM bridge has not created the SLM
  stream yet, or the configured names differ.
- Implausible coordinates usually point to an incorrect camera measurement
  window or a scan range that does not cover the beam.
- If saved plots are needed on a headless machine, use `--no-show-plots` while
  leaving plot saving enabled.

The lower-level wiring is also preserved in
`examples/legacy/example_slm_mask_center_alignment.py`.
