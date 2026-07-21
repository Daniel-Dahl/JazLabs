# macOS arm64 build

The native Apple Silicon build uses a separate source file:

```text
src/digHolo_arm64.cpp
```

It keeps the same exported C API as `digHolo.h`, so the existing Python wrapper
can load `bin/MacOS/libdigholo.dylib` without wrapper-level API changes.

The first arm64 port uses `digHolo_arm64_compat.h`, a scalar AVX-shaped
compatibility layer. This is intended as the correctness-first porting step.
Hot paths can be replaced with true NEON implementations inside that header
without changing the Python wrapper.

## Dependencies

Install native Homebrew dependencies:

```sh
/opt/homebrew/bin/brew install fftw openblas
```

## Build

```sh
python3 build_macos_arm64_dylib.py
```

The output is:

```text
bin/MacOS/libdigholo.dylib
```

## Test

Quick wrapper load/frame-generation test:

```sh
/opt/homebrew/bin/python3 Examples/Python/digHoloExamplePythonWrapper.py
```

Processing smoke test:

```sh
/opt/homebrew/bin/python3 Examples/Python/digHoloExamplePythonWrapper.py --full
```

The `--full` smoke test uses `DIGHOLO_AUTOALIGNMODE_ESTIMATE` so it exercises
AutoAlign, IFFT, tilt removal, overlap, and coefficient readback without running
the slow full tweak optimiser. The full optimiser still needs a real NEON
implementation before it should be treated as practical.
