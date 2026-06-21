#!/usr/bin/env python3
"""
Build the digHolo shared library for macOS.

The upstream digHolo source uses AVX2/FMA x86 intrinsics, so it cannot build as
a native Apple Silicon arm64 dylib without porting the SIMD code. On Apple
Silicon, use an x86_64 Python/toolchain under Rosetta and pass --arch x86_64.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
SOURCE = SRC_DIR / "digHolo.cpp"
HEADER = SRC_DIR / "digHolo.h"
OUTPUT_DIR = ROOT / "bin" / "MacOS"
OUTPUT = OUTPUT_DIR / "libdigholo.dylib"


def default_include_dirs(arch: str) -> list[Path]:
    if arch == "x86_64":
        return [
            Path("/usr/local/opt/fftw/include"),
            Path("/usr/local/opt/openblas/include"),
        ]
    return [Path("/opt/homebrew/include"), Path("/usr/local/include")]


def default_library_dirs(arch: str) -> list[Path]:
    if arch == "x86_64":
        return [
            Path("/usr/local/opt/fftw/lib"),
            Path("/usr/local/opt/openblas/lib"),
        ]
    return [Path("/opt/homebrew/lib"), Path("/usr/local/lib")]


def existing_dirs(paths: list[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def find_header(name: str, include_dirs: list[Path]) -> Path | None:
    for include_dir in include_dirs:
        header = include_dir / name
        if header.exists():
            return header
    return None


def find_library(names: list[str], library_dirs: list[Path]) -> Path | None:
    for library_dir in library_dirs:
        for name in names:
            library = library_dir / name
            if library.exists():
                return library
    return None


def library_matches_arch(library: Path, arch: str) -> bool:
    result = subprocess.run(
        ["lipo", "-info", str(library)],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and arch in result.stdout


def validate_dependencies(arch: str, include_dirs: list[Path], library_dirs: list[Path]) -> None:
    missing = []
    for header in ("fftw3.h", "lapack.h", "cblas.h"):
        if find_header(header, include_dirs) is None:
            missing.append(f"header {header}")

    libraries = {
        "fftw3f_threads": ["libfftw3f_threads.dylib", "libfftw3f_threads.a"],
        "fftw3f": ["libfftw3f.dylib", "libfftw3f.a"],
        "openblas": ["libopenblas.dylib", "libopenblas.a"],
    }
    for label, names in libraries.items():
        library = find_library(names, library_dirs)
        if library is None:
            missing.append(f"library {label}")
        elif not library_matches_arch(library, arch):
            missing.append(f"{library} is not {arch}")

    if not missing:
        return

    paths = ", ".join(str(path) for path in include_dirs + library_dirs)
    raise SystemExit(
        "Cannot build digHolo for macOS yet. Missing or mismatched dependencies: "
        + "; ".join(missing)
        + f". Searched: {paths}"
    )


def build_command(
    source: Path,
    output: Path,
    arch: str,
    include_dirs: list[Path],
    library_dirs: list[Path],
) -> list[str]:
    validate_dependencies(arch, include_dirs, library_dirs)

    cmd = [
        "clang++",
        "-std=c++11",
        "-O3",
        "-fPIC",
        "-shared",
        "-arch",
        arch,
        "-mavx2",
        "-mfma",
        str(source),
        "-o",
        str(output),
        "-I",
        str(SRC_DIR),
    ]
    for include_dir in include_dirs:
        cmd.extend(["-idirafter", str(include_dir)])
    for library_dir in library_dirs:
        cmd.extend(["-L", str(library_dir)])

    cmd.extend(["-lfftw3f_threads", "-lfftw3f", "-lopenblas", "-lpthread", "-lm"])
    return cmd


def write_macos_source(path: Path) -> None:
    source = SOURCE.read_text()
    source = source.replace("#define MKL_ENABLE", "// #define MKL_ENABLE")
    source = source.replace(
        "cgesvd(&jobu, &jobv, &M, &N, (BLAS_COMPLEXTYPE*)a, &LDA, s, "
        "(BLAS_COMPLEXTYPE*)U, &LDU, (BLAS_COMPLEXTYPE*)VT, &LDVT, "
        "(BLAS_COMPLEXTYPE*)WORK, &LWORK, RWORK, &info);",
        "cgesvd(&jobu, &jobv, &M, &N, (BLAS_COMPLEXTYPE*)a, &LDA, s, "
        "(BLAS_COMPLEXTYPE*)U, &LDU, (BLAS_COMPLEXTYPE*)VT, &LDVT, "
        "(BLAS_COMPLEXTYPE*)WORK, &LWORK, RWORK, &info, (size_t)1, (size_t)1);",
    )
    source = source.replace(
        "sgels(&trans, &m, &n, &nrhs, a, &lda, b, &ldb, work, &lwork, &info);",
        "sgels(&trans, &m, &n, &nrhs, a, &lda, b, &ldb, work, &lwork, &info, (size_t)1);",
    )
    path.write_text(source)


def write_macos_header(path: Path) -> None:
    header = HEADER.read_text(encoding="latin-1")
    header = header.replace(
        '#define EXT_C\n#endif\n#else\n#define EXT_C',
        '#define EXT_C extern "C"\n#endif\n#else\n#define EXT_C',
    )
    path.write_text(header, encoding="latin-1")


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
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arch",
        choices=("x86_64", "arm64"),
        default=platform.machine(),
        help="macOS architecture to build for.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--include-dir", type=Path, action="append", default=[])
    parser.add_argument("--library-dir", type=Path, action="append", default=[])
    args = parser.parse_args()

    if sys.platform != "darwin":
        raise SystemExit("This build helper is only for macOS.")

    if args.arch == "arm64":
        raise SystemExit(
            "digHolo.cpp uses AVX2/FMA x86 intrinsics and cannot build as arm64. "
            "Run this under Rosetta with --arch x86_64, or port the SIMD code."
        )

    if shutil.which("clang++") is None:
        raise SystemExit("clang++ was not found. Install Xcode Command Line Tools.")

    include_dirs = existing_dirs(args.include_dir + default_include_dirs(args.arch))
    library_dirs = existing_dirs(args.library_dir + default_library_dirs(args.arch))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        patched_source = tmp_dir / "digHolo_macos.cpp"
        patched_header = tmp_dir / "digHolo.h"
        write_macos_source(patched_source)
        write_macos_header(patched_header)
        cmd = build_command(patched_source, args.output, args.arch, include_dirs, library_dirs)
        print(" ".join(cmd))
        subprocess.run(cmd, check=True, env=build_environment())

    print(f"Built {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
