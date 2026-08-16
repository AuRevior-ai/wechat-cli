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

try:
    from scripts.packaging_paths import assert_outside_repository
except ModuleNotFoundError:  # Direct execution: python scripts/package_windows_app.py
    from packaging_paths import assert_outside_repository


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


def build_binary(
    *,
    targets: list[str] | None = None,
    trust_profile_path: str | Path | None = None,
    installer_payload_path: str | Path | None = None,
    source_sha: str | None = None,
) -> None:
    command = [sys.executable, str(ROOT / "npm" / "scripts" / "build.py"), PLATFORM]
    for target in targets or []:
        command.extend(["--target", target])
    if trust_profile_path is not None:
        command.extend(["--trust-profile", str(trust_profile_path)])
    if installer_payload_path is not None:
        command.extend(["--installer-payload", str(installer_payload_path)])
    if source_sha is not None:
        command.extend(["--source-sha", source_sha])
    subprocess.check_call(command, cwd=ROOT)


def _source_path(source_root: Path, relative: str) -> Path:
    path = source_root / relative
    if path.is_symlink() or not path.exists():
        raise FileNotFoundError(path)
    return path


def _binary_path(name: str, *, binary_root: Path | None = None) -> Path:
    root = binary_root or (ROOT / "npm" / "platforms" / PLATFORM / "bin")
    path = root / name
    if path.is_symlink() or not path.is_file():
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
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ValueError("launcher config must use operational schema version 2")
    allowed = {"schema_version", "port"}
    unexpected = set(value).difference(allowed)
    if unexpected:
        raise ValueError(
            "operational launcher config contains forbidden fields: "
            + ", ".join(sorted(unexpected))
        )
    port = value.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("operational launcher config port must be between 1 and 65535")
    return source


def _app_manifest(
    version: str,
    *,
    build_id: str | None = None,
    source_root: Path = ROOT,
) -> dict[str, object]:
    resolved_build_id = build_id
    if resolved_build_id is None:
        resolved_build_id = runpy.run_path(
            str(source_root / "wechat_cli" / "version.py")
        )["BUILD_ID"]
    return {
        "product": "wechat-cli-web",
        "version": version,
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": "wechat-cli.exe",
        "build_id": resolved_build_id,
    }


def copy_package_files(
    package_dir: Path,
    *,
    launcher_config_path: str | Path,
    version: str,
    build_id: str | None = None,
    source_root: Path = ROOT,
    binary_root: Path | None = None,
) -> None:
    launcher_config = _validate_launcher_config(launcher_config_path)
    launcher_dir = package_dir / "launcher"
    version_dir = package_dir / "versions" / version
    launcher_dir.mkdir(parents=True, exist_ok=True)
    version_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(
        _binary_path("wechat-cli-launcher.exe", binary_root=binary_root),
        launcher_dir / "wechat-cli-launcher.exe",
    )
    shutil.copy2(launcher_config, launcher_dir / "launcher-config.json")
    shutil.copy2(
        _binary_path("wechat-cli.exe", binary_root=binary_root),
        version_dir / "wechat-cli.exe",
    )
    (version_dir / "app-manifest.json").write_text(
        json.dumps(
            _app_manifest(version, build_id=build_id, source_root=source_root),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    for name in WINDOWS_PACKAGE_FILES:
        relative = (
            name
            if name in {"LICENSE", "THIRD_PARTY_NOTICES.md"}
            else f"packaging/windows/{name}"
        )
        source = _source_path(source_root, relative)
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
                "production_capable": False,
                "distribution_tier": "compatibility",
                "launcher": "launcher/wechat-cli-launcher.exe",
                "application": f"versions/{version}/wechat-cli.exe",
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )


def _update_archive_base(version: str, *, output_dir: Path | None = None) -> Path:
    root = DIST_DIR if output_dir is None else output_dir
    return root / f"{UPDATE_PACKAGE_STEM}-{version}-win-x64"


def _update_archive_path(version: str, *, output_dir: Path | None = None) -> Path:
    return Path(str(_update_archive_base(version, output_dir=output_dir)) + ".zip")


def create_update_package(
    version_dir: Path,
    version: str,
    *,
    allow_overwrite: bool = True,
    output_dir: Path | None = None,
) -> Path:
    archive_base = _update_archive_base(version, output_dir=output_dir)
    archive_path = _update_archive_path(version, output_dir=output_dir)
    if archive_path.exists() and not allow_overwrite:
        raise FileExistsError(f"Update archive already exists: {archive_path}")
    return Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=version_dir,
        )
    )


def create_update_only_package(
    *,
    skip_build: bool = False,
    output_dir: Path | None = None,
    version: str | None = None,
    build_id: str | None = None,
) -> Path:
    source_version = read_version()
    selected_version = source_version if version is None else version
    if selected_version != source_version:
        raise ValueError(
            f"update package version {selected_version} must match source version {source_version}"
        )
    destination = (
        DIST_DIR
        if output_dir is None
        else assert_outside_repository(output_dir, repository_root=ROOT)
    )
    archive_path = _update_archive_path(selected_version, output_dir=destination)
    if archive_path.exists():
        raise FileExistsError(f"Update archive already exists: {archive_path}")

    if not skip_build:
        build_binary(targets=["app"])

    app_binary = _binary_path("wechat-cli.exe")
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"wechat-cli-app-{selected_version}-") as tmp:
        assembly_dir = Path(tmp)
        shutil.copy2(app_binary, assembly_dir / "wechat-cli.exe")
        (assembly_dir / "app-manifest.json").write_text(
            json.dumps(
                _app_manifest(selected_version, build_id=build_id),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return create_update_package(
            assembly_dir,
            selected_version,
            allow_overwrite=False,
            output_dir=destination,
        )


def create_bootstrap_package(
    *,
    launcher_config_path: str | Path,
    source_root: Path,
    binary_root: Path,
    output_dir: Path,
    version: str,
    build_id: str,
) -> tuple[Path, Path]:
    output_dir = assert_outside_repository(output_dir, repository_root=ROOT)
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = output_dir / f"{PACKAGE_STEM}-{version}"
    if package_dir.exists():
        raise FileExistsError(f"Bootstrap directory already exists: {package_dir}")
    package_dir.mkdir()

    copy_package_files(
        package_dir,
        launcher_config_path=launcher_config_path,
        version=version,
        build_id=build_id,
        source_root=source_root,
        binary_root=binary_root,
    )

    archive_base = output_dir / f"{PACKAGE_STEM}-{version}"
    bootstrap_zip = Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=package_dir.parent,
            base_dir=package_dir.name,
        )
    )
    return package_dir, bootstrap_zip


def create_production_installer(
    *,
    launcher_config_path: str | Path,
    trust_profile_path: str | Path,
    signing_provider,
    authenticode_verifier=None,
    output_dir: Path | None = None,
    source_sha: str | None = None,
) -> tuple[Path, Path, Path]:
    from scripts.sign_windows_artifacts import sign_and_verify_windows_artifacts
    from wechat_cli.launcher.trust_profile import DeploymentTrustProfile
    from wechat_cli.windows.authenticode import AuthenticodePolicy

    trust_profile = DeploymentTrustProfile.load(trust_profile_path)
    publisher = trust_profile.windows_publisher_policy.strip()
    private_controlled = trust_profile.distribution_profile == "private_controlled"
    destination = (
        DIST_DIR
        if output_dir is None
        else assert_outside_repository(output_dir, repository_root=ROOT)
    )
    build_id = None
    if source_sha is not None:
        from wechat_cli.version import production_build_id

        build_id = production_build_id(source_sha)
    if private_controlled:
        package_dir, legacy_zip, update_zip = create_package(
            launcher_config_path=launcher_config_path,
            trust_profile_path=trust_profile_path,
            skip_build=False,
            output_dir=None if output_dir is None else destination,
            build_id=build_id,
            source_sha=source_sha,
            allow_overwrite=output_dir is None,
        )
        policy = AuthenticodePolicy(required=False)
    else:
        if not publisher:
            raise ValueError("production installer requires a publisher policy")
        if signing_provider is None:
            raise ValueError("production installer requires a signing provider")
        package_dir, legacy_zip, update_zip = create_signed_package(
            launcher_config_path=launcher_config_path,
            trust_profile_path=trust_profile_path,
            signing_provider=signing_provider,
            authenticode_verifier=authenticode_verifier,
        )
        policy = AuthenticodePolicy(required=True, expected_subject=publisher)

    source_metadata = json.loads(
        (package_dir / "bootstrap-package.json").read_text(encoding="utf-8")
    )
    version = str(source_metadata.get("version", "")).strip()
    if not version:
        raise ValueError("bootstrap package metadata is missing version")

    with tempfile.TemporaryDirectory(prefix="wechat-cli-installer-payload-") as tmp:
        payload = Path(tmp) / "bootstrap_payload"
        shutil.copytree(package_dir, payload)
        metadata_path = payload / "bootstrap-package.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["production_capable"] = True
        metadata["distribution_tier"] = "production-installer"
        metadata_path.write_text(
            json.dumps(
                metadata,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        build_kwargs = {
            "targets": ["installer"],
            "installer_payload_path": payload,
        }
        if source_sha is not None:
            build_kwargs["source_sha"] = source_sha
        build_binary(**build_kwargs)

    installer_source = _binary_path("wechat-cli-installer.exe")
    if policy.required:
        sign_and_verify_windows_artifacts(
            [installer_source],
            provider=signing_provider,
            policy=policy,
            verifier=authenticode_verifier,
        )
    destination.mkdir(parents=True, exist_ok=True)
    final_installer = destination / f"wechat-cli-installer-{version}-win-x64.exe"
    if final_installer.exists():
        raise FileExistsError(f"installer output already exists: {final_installer}")
    shutil.copy2(installer_source, final_installer)
    return final_installer, legacy_zip, update_zip


def create_signed_package(
    *,
    launcher_config_path: str | Path,
    trust_profile_path: str | Path,
    signing_provider,
    authenticode_verifier=None,
) -> tuple[Path, Path, Path]:
    from scripts.sign_windows_artifacts import sign_and_verify_windows_artifacts
    from wechat_cli.launcher.trust_profile import DeploymentTrustProfile
    from wechat_cli.windows.authenticode import AuthenticodePolicy

    trust_profile = DeploymentTrustProfile.load(trust_profile_path)
    publisher = trust_profile.windows_publisher_policy.strip()
    if not publisher:
        raise ValueError("signed Windows package requires a publisher policy")
    policy = AuthenticodePolicy(required=True, expected_subject=publisher)

    build_binary(trust_profile_path=trust_profile_path)
    binaries = (
        _binary_path("wechat-cli.exe"),
        _binary_path("wechat-cli-launcher.exe"),
    )
    sign_and_verify_windows_artifacts(
        binaries,
        provider=signing_provider,
        policy=policy,
        verifier=authenticode_verifier,
    )
    return create_package(
        launcher_config_path=launcher_config_path,
        trust_profile_path=trust_profile_path,
        skip_build=True,
    )


def create_package(
    *,
    launcher_config_path: str | Path,
    trust_profile_path: str | Path | None = None,
    skip_build: bool = False,
    output_dir: Path | None = None,
    build_id: str | None = None,
    source_sha: str | None = None,
    allow_overwrite: bool = True,
) -> tuple[Path, Path, Path]:
    if not skip_build:
        build_kwargs = {"trust_profile_path": trust_profile_path}
        if source_sha is not None:
            build_kwargs["source_sha"] = source_sha
        build_binary(**build_kwargs)

    destination = (
        DIST_DIR
        if output_dir is None
        else assert_outside_repository(output_dir, repository_root=ROOT)
    )
    destination.mkdir(parents=True, exist_ok=True)
    version = read_version()
    package_dir = destination / f"{PACKAGE_STEM}-{version}"
    if package_dir.exists():
        if not allow_overwrite:
            raise FileExistsError(f"Bootstrap directory already exists: {package_dir}")
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)

    copy_package_files(
        package_dir,
        launcher_config_path=launcher_config_path,
        version=version,
        build_id=build_id,
    )

    archive_base = destination / f"{PACKAGE_STEM}-{version}"
    bootstrap_zip_path = Path(str(archive_base) + ".zip")
    if bootstrap_zip_path.exists() and not allow_overwrite:
        raise FileExistsError(f"Bootstrap archive already exists: {bootstrap_zip_path}")
    bootstrap_zip = Path(
        shutil.make_archive(
            str(archive_base),
            "zip",
            root_dir=package_dir.parent,
            base_dir=package_dir.name,
        )
    )
    update_zip = create_update_package(
        package_dir / "versions" / version,
        version,
        allow_overwrite=allow_overwrite,
        output_dir=destination,
    )
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
        help="Operational launcher-config.json (schema v2; non-trust fields only).",
    )
    parser.add_argument(
        "--launcher-trust-profile",
        type=Path,
        help="Explicit deployment trust profile embedded into a freshly built Launcher.",
    )
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Build/package only the application update ZIP; do not create bootstrap assets.",
    )
    parser.add_argument(
        "--bootstrap-only",
        action="store_true",
        help="Package only a bootstrap from explicit source/binary roots into external output.",
    )
    parser.add_argument(
        "--production-installer",
        action="store_true",
        help="Build the production installer directly into an external output directory.",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--binary-root", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--build-id")
    parser.add_argument("--source-sha")
    args = parser.parse_args(argv)

    selected_modes = sum(
        bool(value)
        for value in (args.update_only, args.bootstrap_only, args.production_installer)
    )
    if selected_modes > 1:
        parser.error(
            "--update-only, --bootstrap-only, and --production-installer are mutually exclusive"
        )

    if args.update_only:
        update_zip = create_update_only_package(
            skip_build=args.skip_build,
            output_dir=args.output_dir,
            version=args.version,
            build_id=args.build_id,
        )
        print(f"[+] Update archive: {update_zip}")
        return

    if args.production_installer:
        required = {
            "--launcher-config": args.launcher_config,
            "--launcher-trust-profile": args.launcher_trust_profile,
            "--output-dir": args.output_dir,
            "--source-sha": args.source_sha,
        }
        missing = [flag for flag, value in required.items() if value is None]
        if missing:
            parser.error(f"--production-installer requires {' '.join(missing)}")
        installer, bootstrap_zip, update_zip = create_production_installer(
            launcher_config_path=args.launcher_config,
            trust_profile_path=args.launcher_trust_profile,
            signing_provider=None,
            output_dir=args.output_dir,
            source_sha=args.source_sha,
        )
        print(f"[+] Production installer: {installer}")
        print(f"[+] Bootstrap archive: {bootstrap_zip}")
        print(f"[+] Update archive: {update_zip}")
        return

    if args.bootstrap_only:
        required = {
            "--launcher-config": args.launcher_config,
            "--source-root": args.source_root,
            "--binary-root": args.binary_root,
            "--output-dir": args.output_dir,
            "--version": args.version,
            "--build-id": args.build_id,
        }
        missing = [flag for flag, value in required.items() if value is None]
        if missing:
            parser.error(f"--bootstrap-only requires {' '.join(missing)}")
        package_dir, bootstrap_zip = create_bootstrap_package(
            launcher_config_path=args.launcher_config,
            source_root=args.source_root,
            binary_root=args.binary_root,
            output_dir=args.output_dir,
            version=args.version,
            build_id=args.build_id,
        )
        print(f"[+] Bootstrap directory: {package_dir}")
        print(f"[+] Bootstrap archive: {bootstrap_zip}")
        return

    if args.launcher_config is None:
        parser.error("--launcher-config is required unless --update-only is used")
    if not args.skip_build and args.launcher_trust_profile is None:
        parser.error("--launcher-trust-profile is required when building the Launcher")

    package_dir, bootstrap_zip, update_zip = create_package(
        launcher_config_path=args.launcher_config,
        trust_profile_path=args.launcher_trust_profile,
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
