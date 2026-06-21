#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! arch -x86_64 /usr/bin/true >/dev/null 2>&1; then
    echo "Rosetta is not available. Install it with: softwareupdate --install-rosetta"
    exit 1
fi

arch -x86_64 /usr/bin/env python3 build_macos_dylib.py --arch x86_64 "$@"
