#!/usr/bin/env python3
"""Build the native arm64 digHolo shared library for macOS."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
SOURCE = SRC_DIR / "digHolo_arm64.cpp"
OUTPUT = ROOT / "bin" / "MacOS" / "libdigholo.dylib"


def build_environment() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "CPATH",
        "C_INCLUDE_PATH",
        "CPLUS_INCLUDE_PATH",
        "OBJC_INCLUDE_PATH",
        "LIBRARY_PATH",
    ):
        env.pop(key, None)
    return env


def main() -> int:
    if sys.platform != "darwin":
        raise SystemExit("This build helper is only for macOS.")
    if shutil.which("clang++") is None:
        raise SystemExit("clang++ was not found. Install Xcode Command Line Tools.")

    include_dirs = [
        SRC_DIR,
        Path("/opt/homebrew/opt/fftw/include"),
        Path("/opt/homebrew/opt/openblas/include"),
    ]
    library_dirs = [
        Path("/opt/homebrew/opt/fftw/lib"),
        Path("/opt/homebrew/opt/openblas/lib"),
    ]
    missing = [path for path in include_dirs + library_dirs if not path.exists()]
    if missing:
        raise SystemExit("Missing dependency paths: " + ", ".join(str(path) for path in missing))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "clang++",
        "-std=c++11",
        "-O2",
        "-fPIC",
        "-shared",
        "-arch",
        "arm64",
        str(SOURCE),
        "-o",
        str(OUTPUT),
    ]
    for include_dir in include_dirs:
        cmd.extend(["-I", str(include_dir)])
    for library_dir in library_dirs:
        cmd.extend(["-L", str(library_dir)])
    cmd.extend(["-lfftw3f_threads", "-lfftw3f", "-lopenblas", "-lpthread", "-lm"])

    print(" ".join(cmd))
    subprocess.run(cmd, check=True, env=build_environment())
    print(f"Built {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
