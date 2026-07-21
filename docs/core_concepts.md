# JazLabs Core Concepts

This document explains the reasoning behind important objects and patterns in
JazLabs. `repo_structure.md` explains where files live, and
`DesignRequirements.md` explains the broad architecture. This file explains why
some of the extra helper objects exist and what problems they are trying to
remove from day-to-day lab work.

## digHolo

digHolo is an external library by Joel Carpenter for high-speed off-axis digital
holography and modal decomposition:

`https://github.com/joelacarpenter/digHolo`

The underlying reconstruction code in JazLabs comes from that project. The
bundled `src/JazLabs/hardware/digHolo/digHolo_v1.0.0/` directory contains the
digHolo source, headers, DLL/shared-library material, examples, and the
`UserGuide.pdf` from the upstream package. JazLabs should treat that code as
vendor/upstream code rather than as a JazLabs-native implementation.

At a high level, digHolo processes frames from an off-axis holography setup. An
off-axis hologram contains interference between the beam being measured and a
tilted reference beam. From those camera frames, digHolo reconstructs the
complex optical field. It can also calculate modal decompositions, especially
Hermite-Gaussian and Laguerre-Gaussian style decompositions, when those outputs
are useful for the experiment.

JazLabs' `digHolo_pylibs/` code is a Python-facing wrapper around the upstream
digHolo library. It is not intended to replace the underlying digHolo code.
Instead, it makes the library easier to use from JazLabs notebooks, scripts,
viewers, widgets, and measurement routines. The wrapper handles practical Python
tasks such as loading the shared library, setting digHolo properties, passing
NumPy frame buffers into the library, retrieving reconstructed fields and
coefficients, plotting outputs, and connecting digHolo to live camera workflows.

There are two main ways JazLabs expects digHolo to be used.

The first is batch processing, which follows the style described in the upstream
user guide. A batch of frames from an off-axis holography setup is passed into
digHolo, and digHolo reconstructs the fields and optional modal information
from that batch. This is useful for saved measurements, repeatable processing,
and offline analysis of holography data.

The second is live operation. In this mode, frames from a camera feed are passed
through the JazLabs wrapper continuously or interactively. The live field,
Fourier plane, windowing, coefficients, and alignment metrics can then be viewed
while the optical system is being adjusted. This is useful when aligning an
off-axis holography setup, because the user can see whether the reference beam,
Fourier window, beam center, tilt, defocus, basis waist, and related settings
are producing good field reconstructions.

This is why digHolo support is split across the repository:

- `hardware/digHolo/digHolo_v1.0.0/` contains the upstream digHolo code and
  reference material.
- `hardware/digHolo/digHolo_pylibs/` contains JazLabs' Python wrapper, viewer,
  and widget code.
- `procedures/digholo/` contains higher-level workflows that use digHolo for
  batch processing, transform-matrix work, mode measurements, and related
  experiment routines.

## DAQ Controllers And Physical Instrument Abstractions

Data acquisition devices, or DAQs, are general-purpose voltage input/output
tools. In JazLabs they are often used as fast voltage setters, fast voltage
readers, or both. This makes them useful far beyond a single named instrument:
a DAQ channel might drive a variable optical attenuator, tune a stage, control a
laser input, actuate a mirror, or operate a device that has not been added to
the repository yet.

Because DAQs are so general, JazLabs treats them as a control layer that other
hardware classes can depend on. A physical device should still normally get its
own hardware abstraction, even if the actual electrical control is performed by
a DAQ. This keeps the code close to how the lab is understood physically.

For example, a variable optical attenuator is not conceptually "just a DAQ",
even if a DAQ voltage controls its attenuation. It is a VOA, so user-facing code
should expose it as a VOA. Similarly, a laser driven through a DAQ is still a
laser, and a motorised stage driven through voltage outputs is still a
motorised stage. The DAQ is the transport/control mechanism; the higher-level
hardware class describes the thing the user is actually trying to operate.

This separation makes experiment code easier to read. A procedure can say it is
changing attenuation, moving a stage, or tuning a laser, instead of exposing
every action as a raw voltage write. The DAQ class remains available underneath
for the parts of the system that need direct voltage control, calibration, or
fast low-level IO.

The current DAQ area includes vendor-specific implementations and a stack layer:

- `hardware/DAQ_Controller/NI/` contains National Instruments DAQ support.
- `hardware/DAQ_Controller/MCC/` contains MCC DAQ support.
- `hardware/DAQ_Controller/Coremorrow/` contains Coremorrow DAQ support.
- `hardware/DAQ_Controller/DAQ_stack/` contains the DAQ client/server/bridge
  and widget layer for running DAQs as part of the JazLabs virtual lab.

When adding a new DAQ-controlled device, prefer this split:

- put reusable voltage IO and vendor-specific DAQ details in
  `hardware/DAQ_Controller/`
- put the physical device abstraction in its own hardware family, such as
  `hardware/VOA/`, `hardware/Lasers/`, or `hardware/MotorisedStages/`
- let the device abstraction depend on a DAQ object or DAQ client when that is
  how the real device is controlled

## SLM Phase Masks

`src/JazLabs/hardware/SLM/PhaseMaskClass.py` provides the phase-mask object used
to make SLM pattern loading feel more like manipulating optical masks and less
like manually building full-screen display arrays.

In practice, a user often does not want to load a full mask that is the same
size as the SLM display. A lot of the time the useful pattern is much smaller
than the physical SLM, and the important operation is placing that small mask at
the correct location on the display. The phase-mask object gives each mask a
center position, so the mask can be moved naturally by changing its center
rather than rebuilding the whole SLM array by hand.

That centered-mask idea is also useful for alignment. Center alignment routines
can shift masks around through their stored center positions, instead of
managing low-level array slicing and display-coordinate bookkeeping directly.
The same idea helps phase calibration routines, because the calibration logic
can operate on named masks, planes, centers, and Zernike terms rather than only
raw image arrays.

## Complex Masks And Physical Addition

Masks passed into the phase-mask object should be complex arrays when they are
intended to combine physically. The object can then add masks, Zernike
corrections, and other phase profiles in a way that matches the optics: the
phase terms are imposed together rather than one pattern replacing another.

For example, a loaded mask may already perform a useful transformation. A
Zernike correction can then be applied on top of that mask. "On top" does not
mean the Zernike pattern takes over or removes the original mask. It means the
Zernike contribution is added into the phase profile, so the resulting SLM
pattern contains both the original transform and the Zernike correction.

Internally, the phase-mask object builds a full complex representation of the
SLM display. After all selected masks, centers, Zernikes, and other corrections
have been combined, that full display field is converted into the format the SLM
requires. At the moment, most of the supported SLM workflows use 8-bit SLMs, so
the final complex phase array is converted into a `uint8` array before being
sent to the SLM.

## Zernike Corrections

The phase-mask object includes Zernike handling so common optical corrections
can be applied directly to masks. A user can load or set Zernike weights, and
the object applies those weights as additional phase structure on the selected
mask or masks.

This is especially useful when the SLM pattern already has a purpose, such as a
beam transform, coupling correction, or mode-generation mask. Zernikes can be
used as alignment or aberration-control terms without requiring the user to
manually regenerate the base mask.

## Multi-Plane Light Conversion

The phase-mask object is also intended to support multi-plane light converter
systems. In an MPLC setup, the beam reflects from the SLM multiple times. Each
reflection sees a different phase mask, and the combination of phase change and
propagation between masks transforms the beam.

For that reason, the object is built around multiple masks or planes. Each plane
can have its own center and can be controlled individually. This makes MPLC
alignment and control more natural: instead of treating the SLM as one flat
image, the code can treat it as a set of optical planes that happen to be drawn
onto one physical SLM display.

The same object can still support simpler single-mask systems. A single phase
mask that converts one beam into another can be treated as a one-plane case,
while a multi-pass MPLC system can use several planes at once.

## Mask Sets And Mode Indices

Many experiments need to switch between related masks. For example:

- different generated spatial modes in an MPLC system
- different beam transforms in a single-mask system
- different on-sky or atmosphere-like phase screens
- different time steps in a changing phase-screen sequence

The phase-mask object supports this through mask sets and mode indices. Instead
of repeatedly loading a brand-new mask system from scratch, masks can be stored
as a NumPy array with one index selecting the current mode or phase screen. The
user can then move to the next mask in the set by changing the active mode
index.

This is useful for fast interactive work and for scripted measurements. The
experiment can keep the same SLM object, centers, calibration settings, and
plane layout, while stepping through modes or phase screens as the measurement
requires.

## Separation From The SLM Hardware Layer

The SLM server or hardware object should focus on displaying arrays and
communicating with the device. The phase-mask object should focus on the optical
meaning of those arrays: masks, centers, planes, Zernikes, mode sets, and
conversion to the final display format.

Keeping those responsibilities separate makes the rest of the project easier to
work with. Procedures can reason about optical masks and alignment parameters,
while the SLM stack handles the mechanics of getting the final `uint8` image
onto the display.
