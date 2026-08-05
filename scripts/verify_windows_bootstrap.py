#!/usr/bin/env python3
"""Verify the Windows bootstrap installer in an isolated LOCALAPPDATA tree.

The check never touches the user's installed WeChat CLI, shortcuts, WebView2
runtime, or running processes. It exercises legacy 0.4.2 migration, 0.5.0
installation, repeated installation, current/previous pointers, executable
startup, transaction cleanup, and uninstall program-file removal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from wechat_cli.version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE_DIR = ROOT / "dist" / f"wechat-cli-web-bootstrap-win32-x64-{APP_VERSION}"
LEGACY_VERSION = "0.4.2"


class BootstrapVerificationError(RuntimeError):
    """Raised when isolated installer verification fails."""


def _powershell() -> str:
    path = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if path is None:
        raise BootstrapVerificationError("PowerShell is required on Windows")
    return path


def _run_powershell(
    script: Path,
    arguments: list[str],
    *,
    local_app_data: Path,
    timeout: int = 180,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["LOCALAPPDATA"] = str(local_app_data)
    completed = subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            *arguments,
        ],
        cwd=ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        tail = "\n".join(completed.stdout.splitlines()[-40:])
        raise BootstrapVerificationError(
            f"PowerShell script failed ({completed.returncode}): {script.name}\n{tail}"
        )
    return completed


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BootstrapVerificationError(f"invalid JSON state: {path}") from exc
    if not isinstance(value, dict):
        raise BootstrapVerificationError(f"JSON state root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _require_file(path: Path) -> Path:
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise BootstrapVerificationError(f"required installed file is missing: {path}")
    return path


def _application_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "--version"],
        cwd=executable.parent,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    output = completed.stdout.strip()
    if completed.returncode != 0 or APP_VERSION not in output:
        raise BootstrapVerificationError(
            f"installed application version check failed: exit={completed.returncode}"
        )
    return output


def verify(package_dir: Path) -> dict[str, Any]:
    if os.name != "nt":
        raise BootstrapVerificationError("Windows bootstrap verification only runs on Windows")
    if package_dir.is_symlink() or not package_dir.is_dir():
        raise BootstrapVerificationError(f"bootstrap package directory is missing: {package_dir}")
    installer = _require_file(package_dir / "install.ps1")

    with tempfile.TemporaryDirectory(prefix="wechat-cli-bootstrap-e2e-") as raw_temp:
        local_app_data = Path(raw_temp) / "LocalAppData"
        install_dir = local_app_data / "WeChatCliWeb"
        legacy_dir = install_dir / "app"
        legacy_dir.mkdir(parents=True)
        legacy_executable = legacy_dir / "wechat-cli.exe"
        legacy_executable.write_bytes(b"wechat-cli-legacy-verification-fixture\x00\x01")
        legacy_digest = _sha256(legacy_executable)

        isolated_arguments = [
            "-NoStart",
            "-NoShortcuts",
            "-SkipWebView2Check",
            "-SkipProcessStop",
        ]
        _run_powershell(
            installer,
            isolated_arguments,
            local_app_data=local_app_data,
        )

        current_path = install_dir / "state" / "current.json"
        current = _load_json(current_path)
        if current.get("current_version") != APP_VERSION:
            raise BootstrapVerificationError("installer current_version is incorrect")
        if current.get("previous_version") != LEGACY_VERSION:
            raise BootstrapVerificationError("legacy version was not selected as previous")

        migrated_legacy = _require_file(
            install_dir / "versions" / LEGACY_VERSION / "wechat-cli.exe"
        )
        installed_app = _require_file(
            install_dir / "versions" / APP_VERSION / "wechat-cli.exe"
        )
        _require_file(install_dir / "launcher" / "wechat-cli-launcher.exe")
        if _sha256(migrated_legacy) != legacy_digest:
            raise BootstrapVerificationError("legacy executable changed during migration")
        if _sha256(legacy_executable) != legacy_digest:
            raise BootstrapVerificationError("original legacy installation was modified")
        version_output = _application_version(installed_app)

        _run_powershell(
            installer,
            isolated_arguments,
            local_app_data=local_app_data,
        )
        repeated = _load_json(current_path)
        if repeated.get("current_version") != APP_VERSION:
            raise BootstrapVerificationError("reinstall changed current_version")
        if repeated.get("previous_version") != LEGACY_VERSION:
            raise BootstrapVerificationError("reinstall changed previous_version")
        if (install_dir / "state" / "install-transaction.json").exists():
            raise BootstrapVerificationError("committed installation left transaction state")

        uninstall = _require_file(install_dir / "uninstall.ps1")
        _run_powershell(
            uninstall,
            ["-Force", "-NoShortcuts"],
            local_app_data=local_app_data,
        )
        deadline = time.monotonic() + 20
        while install_dir.exists() and time.monotonic() < deadline:
            time.sleep(0.25)
        if install_dir.exists():
            raise BootstrapVerificationError("uninstall did not remove program files")

    return {
        "ok": True,
        "current_version": APP_VERSION,
        "previous_version": LEGACY_VERSION,
        "legacy_migration_verified": True,
        "legacy_source_preserved": True,
        "reinstall_idempotent": True,
        "installed_application_version": version_output,
        "transaction_cleanup_verified": True,
        "uninstall_program_files_verified": True,
        "shortcuts_and_webview2_untouched": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.package_dir.resolve()),
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
