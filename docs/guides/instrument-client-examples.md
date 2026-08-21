# Instrument Client Examples

JazLabs keeps the current, minimal client examples in two matching collections:

- Python scripts: [`examples/instrument_clients`](../../examples/instrument_clients)
- Jupyter notebooks: [`notebooks/instrument_clients`](../../notebooks/instrument_clients)

The script and notebook with the same stem perform the same operations. Use a
script for a small repeatable program or the notebook when bringing hardware up
interactively. Every example assumes that its matching server or bridge is
already running. See the
[`server, viewer, and GUI launch guide`](launch-servers-viewers-and-guis.md)
before using them.

## Available examples

| Instrument | Demonstrated operations |
| --- | --- |
| SLM and phase masks | Connect an `SLMClient`, pass it into `PhaseMaskObject`, load a `.mat` mask set, and display every mode |
| Camera | Change exposure, acquire continuous and software-triggered frames, return to continuous mode, change ROI, and restore the full frame |
| Motorised mount | Connect, read all positions, move one axis, and read positions again |
| Tunable laser | Connect, change wavelength, read wavelength, and read power |
| Optical switch | Connect, read the selected port, select another port, and read it back |
| DAC/DAQ | Connect, set one channel voltage, and read it back |
| Digital holography | Connect a camera, pass it to `digholoWindow`, set FFT radius and maximum mode group, auto-align, and launch the live viewer |

## Before running an example

Open the script or notebook and edit the short settings block near the top.
Hosts and ports must match the running server. Values that move or change
physical hardware—such as mount position, wavelength, switch port, and
voltage—must be checked for the actual setup before execution.

For the SLM example, place the mask file at:

```text
data/SLM/MaskFiles/<name>.mat
```

Set `MASK_FILE` to `<name>` without the `.mat` extension. The file must contain
a MATLAB variable called `MASKS`, arranged in the shape expected by
`PhaseMaskObject`. The example reads the mode count after loading the file and
steps through it with `setmask(..., imode=mode_index)`.

The digital holography example requires the digHolo native library and a local
GUI environment in addition to the camera server. Constructing
`digholoWindow` launches the live OpenCV viewer; pressing `q` in that viewer or
closing it from the script stops the display.

## Preserved examples

Material that previously lived at the top of `examples/` and `notebooks/` has
not been discarded. It is preserved under [`examples/legacy`](../../examples/legacy)
and [`notebooks/legacy`](../../notebooks/legacy). These files remain useful as
references for longer procedures and historical lab workflows, but the minimal
instrument-client examples are the clearer starting point for new code.
