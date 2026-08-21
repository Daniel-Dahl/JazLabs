# Instrument client examples

These examples are intentionally short. Start the corresponding JazLabs server,
edit the connection settings and requested hardware value near the top of the
file, then run the script.

- `slm_client.py`: connect, create a phase-mask object, load a `.mat` mask set,
  and display each mode.
- `camera_client.py`: exposure, frames, software/continuous triggering, and a
  temporary ROI that is reset to full frame.
- `motorised_mount_client.py`: read and move a mount axis.
- `laser_client.py`: change wavelength and read power.
- `optical_switch_client.py`: read and select a port.
- `dac_client.py`: set and read one output voltage.
- `digital_holography_viewer.py`: connect a camera, configure and auto-align
  digHolo, and launch its viewer.

The mask file used by `slm_client.py` belongs in `data/SLM/MaskFiles`. Set
`MASK_FILE` to its filename without the `.mat` extension.
