"""Console launcher for the bundled LiDMaS+ executable."""

from __future__ import annotations

import os
import subprocess
import sys
from importlib.resources import files
from pathlib import Path


def _binary_name() -> str:
    return "lidmas.exe" if os.name == "nt" else "lidmas"


def _binary_path() -> Path:
    return Path(files("lidmas")).joinpath("_bin", _binary_name())


def main() -> int:
    exe = _binary_path()
    if not exe.exists():
        print(
            f"LiDMaS executable not found at '{exe}'. "
            "Reinstall the package or build from source.",
            file=sys.stderr,
        )
        return 1

    cmd = [str(exe), *sys.argv[1:]]
    if os.name == "nt":
        return subprocess.call(cmd)

    os.execv(cmd[0], cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

