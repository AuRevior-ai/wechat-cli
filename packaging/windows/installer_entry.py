"""Production-capable Windows installer executable entrypoint."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _payload_root(base_dir=None) -> Path:
    if base_dir is not None:
        root = Path(base_dir)
    elif hasattr(sys, "_MEIPASS"):
        root = Path(getattr(sys, "_MEIPASS"))
    else:
        root = Path(__file__).resolve().parent
    return root / "bootstrap_payload"


def run_installer(*, args=None, base_dir=None, runner=None) -> int:
    payload = _payload_root(base_dir)
    script = payload / "install.ps1"
    if script.is_symlink() or not script.is_file():
        raise FileNotFoundError("embedded install.ps1 is missing")
    execute = runner or subprocess.run
    completed = execute(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *(list(args or [])),
        ],
        cwd=str(payload),
        check=False,
        shell=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(run_installer(args=sys.argv[1:]))
