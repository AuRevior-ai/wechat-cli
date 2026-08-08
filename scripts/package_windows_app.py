#!/usr/bin/env python3
"""Create the Windows bootstrap installer and signed-update application ZIP."""

from __future__ import annotations

import argparse
import json
import runpy
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
PLATFORM = "win32-x64"
PACKAGE_STEM = "wechat-cli-web-bootstrap-win32-x64"
UPDATE_PACKAGE_STEM = "wechat-cli-app"
LEGACY_BOOTSTRAP_VERSION = "0.4.2"
WINDOWS_TEMPLATES = ROOT / "packaging" / "windows"
WINDOWS_PACKAGE_FILES = (
    "install-and-start.bat",
    "install.ps1",
    "start-wechat-cli-web.bat",
    "repair-wechat-cli-web.bat",
    "uninstall-wechat-cli-web.bat",
    "uninstall.ps1",
    "README-APP.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
)


def read_version() -> str:
    runtime = runpy.run_path(str(ROOT / "wechat_cli" / "version.py"))["APP_VERSION"]
    with open(ROOT / "pyproject.toml", "rb") as stream:
        project = tomllib.load(stream)["project"]["version"]
    if runtime != project:
        raise RuntimeError(
            f"Version mismatch: wechat_cli/version.py={runtime}, pyproject.toml={project}"
        )
    return str(runtime)


def build_manifest(version: str | None = None) -> list[str]:
    selected = version or read_version()
    return [
        *WINDOWS_PACKAGE_FILES,
        "launcher/wechat-cli-launcher.exe",
        "launcher/launcher-config.json",
        f"versions/{selected}/wechat-cli.exe",
        f"versions/{selected}/app-manifest.json",
        "bootstrap-package.json",
    ]


def build_binary(*, targets: list[str] | None = None) -> None:
    command = [sys.executable, str(ROOT / "npm" / "scripts" / "build.py"), PLATFORM]
    for target in targets or []:
        command.extend(["--target", target])
    subprocess.check_call(command, cwd=ROOT)


def _binary_path(name: str) -> Path:
    path = ROOT / "npm" / "platforms" / PLATFORM / "bin" / name
    if not path.is_file():
        raise FileNotFoundError(f"Missing binary: {path}")
    return path


def _validate_launcher_config(path: str | Path) -> Path:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError("launcher config must be an existing regular file")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("launcher config must be valid UTF-8 JSON") from exc
    required = {
        "schema_version",
        "api_base_url",
        "port",
        "channel",
        "fingerprint_salt",
        "release_public_keys",
        "lease_public_keys",
    }
    if not isinstance(value, dict) or not required.issubset(value):
        raise ValueError("launcher config is missing required fields")
    return source


def _app_manifest(version: str) -> dict[str, object]:
    return {
        "product": "wechat-cli-web",
        "version": version,
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": "wechat-cli.exe",
        "build_id": runpy.run_path(str(ROOT / "wechat_cli" / "version.py"))["BUILD_ID"],
    }


def copy_package_files(
    package_dir: Path,
    *,
    launcher_config_path: str | Path,
    version: str,
) -> None:
    launcher_config = _validate_launcher_config(launcher_config_path)
    launcher_dir = package_dir / "launcher"
    version_dir = package_dir / "versions" / version
    launcher_dir.mkdir(parents=True, exist_ok=True)
    version_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(
        _binary_path("wechat-cli-launcher.exe"),
        launcher_dir / "wechat-cli-launcher.exe",
    )
    shutil.copy2(launcher_config, launcher_dir / "launcher-config.json")
    shutil.copy2(
        _binary_path("wechat-cli.exe"),
        version_dir / "wechat-cli.exe",
    )
    (version_dir / "app-manifest.json").write_text(
        json.dumps(
            _app_manifest(version),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    for name in WINDOWS_PACKAGE_FILES:
        source = (
            ROOT / name
            if name in {"LICENSE", "THIRD_PARTY_NOTICES.md"}
            else WINDOWS_TEMPLATES / name
        )
        if not source.is_file():
            raise FileNotFoundError(f"Missing package template: {source}")
        shutil.copy2(source, package_dir / name)

    (package_dir / "bootstrap-package.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "product": "wechat-cli-web",
                "version": version,
                "legacy_version": LEGACY_BOOTSTRAP_VERSION,
                "platform": "windows",
                "architecture": "x86_64",
                "launcher": "launcher/wechat-cli-launcher.exe",
                "application": f"versions/{version}/wechat-cli.exe",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _update_archive_base(version: str) -> Path:
    return DIST_DIR / f"{UPDATE_PACKAGE_STEM}-{version}-win-x64"


def _update_archive_path(version: str) -> Path:
    return Path(str(_update_archive_base(version)) + ".zip")


def create_update_package(
    version_dir: Path,
    version: str,
    *,
    allow_overwrite: bool = True,
) -> Path:
    archive_base = _update_archive_base(version)
    archive_path = _update_archive_path(version)
    if archive_path.exists() and not allow_overwrite:
        raise FileExistsError(f"Update archive already exists: {archive_path}")
    return Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=version_dir,
        )
    )


def create_update_only_package(*, skip_build: bool = False) -> Path:
    version = read_version()
    archive_path = _update_archive_path(version)
    if archive_path.exists():
        raise FileExistsError(f"Update archive already exists: {archive_path}")

    if not skip_build:
        build_binary(targets=["app"])

    app_binary = _binary_path("wechat-cli.exe")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"wechat-cli-app-{version}-") as tmp:
        assembly_dir = Path(tmp)
        shutil.copy2(app_binary, assembly_dir / "wechat-cli.exe")
        (assembly_dir / "app-manifest.json").write_text(
            json.dumps(
                _app_manifest(version),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return create_update_package(
            assembly_dir,
            version,
            allow_overwrite=False,
        )


def create_package(
    *,
    launcher_config_path: str | Path,
    skip_build: bool = False,
) -> tuple[Path, Path, Path]:
    if not skip_build:
        build_binary()

    version = read_version()
    package_dir = DIST_DIR / f"{PACKAGE_STEM}-{version}"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    copy_package_files(
        package_dir,
        launcher_config_path=launcher_config_path,
        version=version,
    )

    archive_base = DIST_DIR / f"{PACKAGE_STEM}-{version}"
    bootstrap_zip = Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=package_dir.parent,
            base_dir=package_dir.name,
        )
    )
    update_zip = create_update_package(package_dir / "versions" / version, version)
    return package_dir, bootstrap_zip, update_zip


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Build the Windows bootstrap and application update packages."
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Reuse npm/platforms/win32-x64/bin binaries.",
    )
    parser.add_argument(
        "--launcher-config",
        type=Path,
        help="Validated launcher-config.json containing API URL and public keys.",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Build/package only the application update ZIP; do not create bootstrap assets.",
    )
    args = parser.parse_args(argv)

    if args.update_only:
        update_zip = create_update_only_package(skip_build=args.skip_build)
        print(f"[+] Update archive: {update_zip}")
        return

    if args.launcher_config is None:
        parser.error("--launcher-config is required unless --update-only is used")

    package_dir, bootstrap_zip, update_zip = create_package(
        launcher_config_path=args.launcher_config,
        skip_build=args.skip_build,
    )
    print(f"[+] Bootstrap directory: {package_dir}")
    print(f"[+] Bootstrap archive: {bootstrap_zip}")
    print(f"[+] Update archive: {update_zip}")
    print("[+] Bootstrap manifest:")
    for item in build_manifest():
        print(f"    {item}")


if __name__ == "__main__":
    main()
