#!/usr/bin/env python3
"""Create a Windows portable app package for WeChat CLI Web."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
PLATFORM = "win32-x64"
PACKAGE_STEM = "wechat-cli-web-app-win32-x64"
WINDOWS_TEMPLATES = ROOT / "packaging" / "windows"
WINDOWS_PACKAGE_FILES = (
    "install-and-start.bat",
    "install.ps1",
    "start-wechat-cli-web.bat",
    "README-APP.md",
    "LICENSE",
    "app/wechat-cli.exe",
)


def build_manifest():
    return list(WINDOWS_PACKAGE_FILES)


def read_version():
    with open(ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def build_binary():
    subprocess.check_call([sys.executable, str(ROOT / "npm" / "scripts" / "build.py"), PLATFORM], cwd=ROOT)


def copy_package_files(package_dir):
    app_dir = package_dir / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    binary = ROOT / "npm" / "platforms" / PLATFORM / "bin" / "wechat-cli.exe"
    if not binary.exists():
        raise FileNotFoundError(f"Missing binary: {binary}")
    shutil.copy2(binary, app_dir / "wechat-cli.exe")

    for name in ("install-and-start.bat", "install.ps1", "start-wechat-cli-web.bat", "README-APP.md"):
        shutil.copy2(WINDOWS_TEMPLATES / name, package_dir / name)
    shutil.copy2(ROOT / "LICENSE", package_dir / "LICENSE")


def create_package(skip_build=False):
    if not skip_build:
        build_binary()

    version = read_version()
    package_dir = DIST_DIR / f"{PACKAGE_STEM}-{version}"
    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    copy_package_files(package_dir)

    archive_base = DIST_DIR / f"{PACKAGE_STEM}-{version}"
    zip_path = Path(shutil.make_archive(str(archive_base), "zip", root_dir=package_dir.parent, base_dir=package_dir.name))
    return package_dir, zip_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Windows portable app package.")
    parser.add_argument("--skip-build", action="store_true", help="Reuse npm/platforms/win32-x64/bin/wechat-cli.exe")
    args = parser.parse_args(argv)

    package_dir, zip_path = create_package(skip_build=args.skip_build)
    print(f"[+] Package directory: {package_dir}")
    print(f"[+] Zip archive: {zip_path}")
    print("[+] Manifest:")
    for item in build_manifest():
        print(f"    {item}")


if __name__ == "__main__":
    main()
