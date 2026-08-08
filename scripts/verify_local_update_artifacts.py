#!/usr/bin/env python3
"""Verify locally built bootstrap and update artifacts end to end.

This verification uses a disposable Ed25519 key generated in a temporary
folder. It validates the final ZIP bytes, signs the real update package,
verifies the signature through the client trust implementation, safely
extracts the package, and executes the extracted application version command.
No private key or credential is written into the repository or reported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Crypto.PublicKey import ECC

from wechat_cli.release.builder import ReleaseBuildOptions, build_signed_release
from wechat_cli.update.crypto import TrustedEd25519Keys, verify_file_sha256
from wechat_cli.update.models import UpdateManifest
from wechat_cli.update.package import extract_update_zip
from wechat_cli.version import APP_VERSION, LAUNCHER_VERSION, PRODUCT


DEFAULT_BOOTSTRAP_DIR = ROOT / "dist" / f"wechat-cli-web-bootstrap-win32-x64-{APP_VERSION}"
DEFAULT_BOOTSTRAP_ZIP = ROOT / "dist" / f"wechat-cli-web-bootstrap-win32-x64-{APP_VERSION}.zip"
DEFAULT_UPDATE_ZIP = ROOT / "dist" / f"wechat-cli-app-{APP_VERSION}-win-x64.zip"


class ArtifactVerificationError(RuntimeError):
    """Raised when an artifact does not satisfy the release contract."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _regular_file(path: Path, name: str) -> Path:
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise ArtifactVerificationError(f"{name} must be a non-empty regular file: {path}")
    return path


def _load_json(path: Path, name: str) -> dict[str, Any]:
    _regular_file(path, name)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactVerificationError(f"{name} is not valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ArtifactVerificationError(f"{name} root must be an object")
    return value


def _verify_bootstrap_directory(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_dir():
        raise ArtifactVerificationError(f"bootstrap directory is missing: {path}")
    metadata = _load_json(path / "bootstrap-package.json", "bootstrap metadata")
    expected = {
        "schema_version": 1,
        "product": PRODUCT,
        "version": APP_VERSION,
        "legacy_version": "0.4.2",
        "platform": "windows",
        "architecture": "x86_64",
        "launcher": "launcher/wechat-cli-launcher.exe",
        "application": f"versions/{APP_VERSION}/wechat-cli.exe",
    }
    for name, expected_value in expected.items():
        if metadata.get(name) != expected_value:
            raise ArtifactVerificationError(
                f"bootstrap metadata {name!r} mismatch: {metadata.get(name)!r}"
            )

    required = (
        "install-and-start.bat",
        "install.ps1",
        "repair-wechat-cli-web.bat",
        "uninstall-wechat-cli-web.bat",
        "uninstall.ps1",
        "launcher/wechat-cli-launcher.exe",
        "launcher/launcher-config.json",
        f"versions/{APP_VERSION}/wechat-cli.exe",
        f"versions/{APP_VERSION}/app-manifest.json",
    )
    for relative in required:
        _regular_file(path / relative, relative)

    app_manifest = _load_json(
        path / "versions" / APP_VERSION / "app-manifest.json",
        "application package metadata",
    )
    expected_app = {
        "product": PRODUCT,
        "version": APP_VERSION,
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": "wechat-cli.exe",
    }
    for name, expected_value in expected_app.items():
        if app_manifest.get(name) != expected_value:
            raise ArtifactVerificationError(
                f"application metadata {name!r} mismatch: {app_manifest.get(name)!r}"
            )
    if not isinstance(app_manifest.get("build_id"), str) or not app_manifest["build_id"]:
        raise ArtifactVerificationError("application metadata build_id is missing")
    return metadata


def _verify_bootstrap_zip(path: Path, directory: Path) -> None:
    _regular_file(path, "bootstrap ZIP")
    expected_root = directory.name + "/"
    with zipfile.ZipFile(path, "r") as archive:
        names = set(archive.namelist())
        if not names:
            raise ArtifactVerificationError("bootstrap ZIP is empty")
        if any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names):
            raise ArtifactVerificationError("bootstrap ZIP contains an unsafe member path")
        for relative in (
            "bootstrap-package.json",
            "install.ps1",
            "launcher/wechat-cli-launcher.exe",
            f"versions/{APP_VERSION}/wechat-cli.exe",
        ):
            if expected_root + relative not in names:
                raise ArtifactVerificationError(
                    f"bootstrap ZIP is missing {expected_root + relative}"
                )


def _execute_version(executable: Path) -> str:
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
        raise ArtifactVerificationError(
            f"extracted executable version check failed: exit={completed.returncode}"
        )
    return output


def _verify_update_zip(update_zip: Path) -> dict[str, Any]:
    _regular_file(update_zip, "update ZIP")

    with tempfile.TemporaryDirectory(prefix="wechat-cli-artifact-verify-") as raw_temp:
        temporary = Path(raw_temp)
        private_key = ECC.generate(curve="Ed25519")
        private_key_path = temporary / "release-signing-key.pem"
        private_key_path.write_text(
            private_key.export_key(format="PEM"),
            encoding="ascii",
        )
        try:
            private_key_path.chmod(0o600)
        except OSError:
            pass

        signed = build_signed_release(
            update_zip,
            private_key_path,
            ReleaseBuildOptions(
                release_id=f"local-artifact-{APP_VERSION}",
                channel="stable",
                published_at=datetime.now(timezone.utc),
                minimum_app_version=APP_VERSION,
                minimum_launcher_version=LAUNCHER_VERSION,
                signing_key_id="local-artifact-ephemeral",
                release_summary="Local artifact verification",
                rollout_percentage=100,
            ),
        )
        manifest = UpdateManifest.from_json_bytes(signed.manifest_bytes)
        if manifest.signing is None:
            raise ArtifactVerificationError("signed manifest omitted signing metadata")
        if str(manifest.version) != APP_VERSION:
            raise ArtifactVerificationError(
                f"update manifest version mismatch: {manifest.version}"
            )
        public_key = private_key.public_key().export_key(format="raw")
        if not isinstance(public_key, bytes):
            raise ArtifactVerificationError("Ed25519 public key export failed")
        trusted = TrustedEd25519Keys({manifest.signing.key_id: public_key})
        trusted.verify(manifest.signing.key_id, signed.manifest_bytes, signed.signature)
        manifest.validate_target(
            product=PRODUCT,
            platform="windows",
            architecture="x86_64",
            current_app_version=APP_VERSION,
            launcher_version=LAUNCHER_VERSION,
        )
        verify_file_sha256(update_zip, manifest.package.sha256)

        staging_root = temporary / "staging"
        extracted = extract_update_zip(
            update_zip,
            staging_root,
            expected_product=manifest.product,
            expected_version=str(manifest.version),
            expected_platform=manifest.platform,
            expected_architecture=manifest.architecture,
            expected_entrypoint=manifest.install.entrypoint,
        )
        try:
            version_output = _execute_version(extracted / manifest.install.entrypoint)
        finally:
            shutil.rmtree(extracted, ignore_errors=True)

    return {
        "update_zip_sha256": _sha256(update_zip),
        "update_zip_size": update_zip.stat().st_size,
        "manifest_signature_verified": True,
        "safe_extraction_verified": True,
        "extracted_application_version": version_output,
    }


def verify_update_only(*, update_zip: Path) -> dict[str, Any]:
    return {
        "ok": True,
        "product": PRODUCT,
        "version": APP_VERSION,
        "launcher_version": LAUNCHER_VERSION,
        **_verify_update_zip(update_zip),
    }


def verify(
    *,
    bootstrap_dir: Path,
    bootstrap_zip: Path,
    update_zip: Path,
) -> dict[str, Any]:
    bootstrap_metadata = _verify_bootstrap_directory(bootstrap_dir)
    _verify_bootstrap_zip(bootstrap_zip, bootstrap_dir)
    update_evidence = _verify_update_zip(update_zip)

    return {
        "ok": True,
        "product": bootstrap_metadata["product"],
        "version": bootstrap_metadata["version"],
        "legacy_version": bootstrap_metadata["legacy_version"],
        "launcher_version": LAUNCHER_VERSION,
        "bootstrap_zip_sha256": _sha256(bootstrap_zip),
        **update_evidence,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-dir", type=Path, default=DEFAULT_BOOTSTRAP_DIR)
    parser.add_argument("--bootstrap-zip", type=Path, default=DEFAULT_BOOTSTRAP_ZIP)
    parser.add_argument("--update-zip", type=Path, default=DEFAULT_UPDATE_ZIP)
    parser.add_argument(
        "--update-only",
        action="store_true",
        help="Verify only the application update ZIP and skip bootstrap checks.",
    )
    args = parser.parse_args(argv)
    if args.update_only:
        result = verify_update_only(update_zip=args.update_zip.resolve())
    else:
        result = verify(
            bootstrap_dir=args.bootstrap_dir.resolve(),
            bootstrap_zip=args.bootstrap_zip.resolve(),
            update_zip=args.update_zip.resolve(),
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
