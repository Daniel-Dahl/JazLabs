# macOS Rosetta build

The digHolo C++ source uses Intel AVX2/FMA intrinsics, so the quick macOS path
is to build and run it as `x86_64` under Rosetta.

This means the whole Python process that loads digHolo must also be `x86_64`.
Do not mix an arm64 Python with an x86_64 `libdigholo.dylib`.

## One-time setup

Install Rosetta if it is not already available:

```sh
softwareupdate --install-rosetta
```

Install the Intel Homebrew dependencies under `/usr/local`:

```sh
arch -x86_64 /usr/local/bin/brew install fftw openblas python@3.11
```

`openblas` provides the BLAS/LAPACK headers and libraries needed by the digHolo
source. If your local OpenBLAS install lives somewhere other than
`/usr/local`, pass that path to the build script with `--include-dir` and
`--library-dir`.

## Build

From this directory:

```sh
./build_macos_rosetta.sh
```

The output is:

```text
bin/MacOS/libdigholo.dylib
```

## Smoke test

Run the wrapper example with an Intel Python:

```sh
arch -x86_64 /usr/local/bin/python3 Examples/Python/digHoloExamplePythonWrapper.py
```

If you want to load a library from another location, set:

```sh
export DIGHOLO_LIBRARY_PATH=/path/to/libdigholo.dylib
```
