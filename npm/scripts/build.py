#!/usr/bin/env python3
"""Build wechat-cli standalone binaries with PyInstaller."""

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NPM_DIR = ROOT / "npm"
PLATFORMS_DIR = NPM_DIR / "platforms"

PLATFORM_MAP = {
    "darwin-arm64":  {"target": "macos"},
    "darwin-x64":    {"target": "macos"},
    "linux-x64":     {"target": "linux"},
    "linux-arm64":   {"target": "linux"},
    "win32-x64":     {"target": "win"},
}


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        pass
    print("[+] Installing PyInstaller...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def _resource_sep(platform: str):
    os_name, _arch = platform.split("-")
    return ";" if os_name == "win32" else ":"


def ensure_target_dependencies(target: str, module_finder=None) -> None:
    """Fail before PyInstaller when a required runtime module is unavailable."""
    if target not in {"app", "launcher"}:
        raise ValueError(f"Unknown build target: {target}")
    finder = module_finder or importlib.util.find_spec
    required = {
        "app": (
            ("click", "click"),
            ("Crypto", "pycryptodome"),
            ("zstandard", "zstandard"),
        ),
        "launcher": (
            ("click", "click"),
            ("Crypto", "pycryptodome"),
            ("zstandard", "zstandard"),
            ("webview", "pywebview"),
        ),
    }
    missing = [display for module, display in required[target] if finder(module) is None]
    if missing:
        raise RuntimeError(
            "Missing build dependencies for "
            f"{target}: {', '.join(missing)}. "
            "Install the project dependencies before building."
        )


def make_pyinstaller_command(platform: str, target: str = "app"):
    if platform not in PLATFORM_MAP:
        raise ValueError(f"Unknown platform: {platform}")
    if target not in {"app", "launcher"}:
        raise ValueError(f"Unknown build target: {target}")
    os_name, _arch = platform.split("-")
    if target == "launcher" and os_name != "win32":
        raise ValueError("The graphical launcher is currently Windows-only")

    output_dir = PLATFORMS_DIR / platform / "bin"
    sep = _resource_sep(platform)
    name = "wechat-cli" if target == "app" else "wechat-cli-launcher"
    entrypoint = ROOT / ("entry.py" if target == "app" else "launcher_entry.py")
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        name,
        "--distpath",
        str(output_dir),
        "--workpath",
        str(ROOT / "build" / f"{name}_{platform}"),
        "--specpath",
        str(ROOT / "build"),
        "--noconfirm",
        "--clean",
    ]
    if target == "launcher":
        cmd.append("--windowed")

    # Bundle C binaries for key extraction into the application only.
    bin_dir = ROOT / "wechat_cli" / "bin"
    if target == "app" and bin_dir.exists():
        for f in bin_dir.iterdir():
            if not f.name.startswith(".") and f.is_file():
                cmd.extend(["--add-binary", f"{f}{sep}wechat_cli/bin"])

    static_dir = ROOT / "wechat_cli" / "web" / "static"
    if target == "app" and static_dir.exists():
        cmd.extend(["--add-data", f"{static_dir}{sep}wechat_cli/web/static"])

    launcher_ui = ROOT / "wechat_cli" / "launcher" / "ui"
    if target == "launcher" and launcher_ui.exists():
        cmd.extend(["--add-data", f"{launcher_ui}{sep}wechat_cli/launcher/ui"])
        cmd.extend(["--collect-all", "webview"])

    hidden = ["zstandard"]
    if target == "app":
        hidden.extend(["wechat_cli.web", "wechat_cli.web.static"])
    else:
        hidden.extend(
            [
                "webview",
                "webview.platforms.edgechromium",
                "wechat_cli.launcher",
                "wechat_cli.windows.dpapi",
            ]
        )
    for module in hidden:
        cmd.extend(["--hidden-import", module])

    cmd.append(str(entrypoint))
    return [str(part) for part in cmd]


def build_platform(platform: str, targets: list[str] | None = None):
    if platform not in PLATFORM_MAP:
        raise ValueError(f"Unknown platform: {platform}")
    os_name, _arch = platform.split("-")
    ext = ".exe" if os_name == "win32" else ""
    selected_targets = (
        list(targets)
        if targets is not None
        else ["app"] + (["launcher"] if os_name == "win32" else [])
    )
    allowed_targets = {"app", "launcher"}
    if not selected_targets or any(
        target not in allowed_targets for target in selected_targets
    ):
        raise ValueError("Unknown or empty build target selection")
    if "launcher" in selected_targets and os_name != "win32":
        raise ValueError("The graphical launcher is currently Windows-only")
    expected = {
        "app": f"wechat-cli{ext}",
        "launcher": f"wechat-cli-launcher{ext}",
    }

    output_dir = PLATFORMS_DIR / platform / "bin"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Building for {platform}...")
    print(f"{'='*60}")

    for target in selected_targets:
        try:
            ensure_target_dependencies(target)
        except RuntimeError as exc:
            print(f"[-] Cannot build {target} for {platform}: {exc}")
            return False

    for target in selected_targets:
        cmd = make_pyinstaller_command(platform, target)
        print(f"[+] Running ({target}): {' '.join(cmd)}")
        try:
            subprocess.check_call(cmd, cwd=str(ROOT))
        except subprocess.CalledProcessError as exc:
            print(f"[-] {target} build failed for {platform}: {exc}")
            return False

        binary_path = output_dir / expected[target]
        if not binary_path.exists():
            print(f"[-] Binary not found: {binary_path}")
            return False
        print(f"[+] Built: {binary_path}")
        print(f"    Size: {binary_path.stat().st_size / 1024 / 1024:.1f} MB")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build standalone WeChat CLI binaries.")
    parser.add_argument("platforms", nargs="*", help="Target platform(s) to build.")
    parser.add_argument(
        "--target",
        action="append",
        choices=("app", "launcher"),
        dest="targets",
        help="Build only the selected target. May be repeated.",
    )
    args = parser.parse_args()
    platforms = list(args.platforms)

    if not platforms:
        # Default: build for current platform only
        import platform as _pf
        current = f"{_pf.system().lower()}-{_pf.machine()}"
        # Normalize
        if current == "darwin-arm64":
            platforms = ["darwin-arm64"]
        elif current == "darwin-x86_64" or current == "darwin-amd64":
            platforms = ["darwin-x64"]
        else:
            # Try to match
            platforms = []
            for p in PLATFORM_MAP:
                os_name, arch = p.split("-")
                if os_name in current and (arch in current or
                    (arch == "x64" and ("x86_64" in current or "amd64" in current))):
                    platforms = [p]
                    break
            if not platforms:
                print(f"Cannot determine platform from '{current}'")
                print(f"Usage: {sys.argv[0]} [platform...] [--target app|launcher]")
                print(f"  Platforms: {', '.join(PLATFORM_MAP.keys())}")
                sys.exit(1)

    print(f"[+] Building for: {', '.join(platforms)}")
    ensure_pyinstaller()

    results = {}
    for p in platforms:
        if p not in PLATFORM_MAP:
            print(f"[-] Unknown platform: {p}")
            results[p] = False
            continue
        results[p] = build_platform(p, targets=args.targets)

    print(f"\n{'='*60}")
    print("Build Summary:")
    for p, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {p}: {status}")
    print(f"{'='*60}")

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
