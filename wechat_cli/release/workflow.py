"""Two-phase production release helpers for privileged workflow source."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from ..launcher.trust_profile import DeploymentTrustProfile
from ..update.crypto import TrustedEd25519Keys, sha256_file
from ..update.models import UpdateManifest
from .builder import ReleaseBuildOptions, SignedRelease, build_signed_release


def _regular_file(path: str | Path, label: str) -> Path:
    source = Path(path)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"{label} must be a regular file")
    return source


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                path.unlink()
            except OSError:
                pass
        raise


def sign_release_for_workflow(
    *,
    package_path: str | Path,
    signing_key_path: str | Path,
    output_dir: str | Path,
    options: ReleaseBuildOptions,
) -> dict[str, str | int]:
    """Sign one prepared package and emit only public/safe assets for later publication."""

    package = _regular_file(package_path, "release package")
    signed = build_signed_release(package, signing_key_path, options)
    destination = Path(output_dir)
    manifest_path = destination / f"wechat-cli-update-manifest-{signed.version}.json"
    signature_path = destination / f"wechat-cli-update-manifest-{signed.version}.sig"
    metadata_path = destination / "prepared-release.json"
    metadata = {
        "release_id": signed.release_id,
        "version": signed.version,
        "channel": signed.channel,
        "signing_key_id": signed.signing_key_id,
        "manifest_sha256": signed.manifest_sha256,
        "package_sha256": signed.package_sha256,
        "package_size": signed.package_size,
        "package_name": package.name,
    }
    written: list[Path] = []
    try:
        for path, data in (
            (manifest_path, signed.manifest_bytes),
            (signature_path, signed.signature),
            (
                metadata_path,
                json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
                    "utf-8"
                ),
            ),
        ):
            _write_new(path, data)
            written.append(path)
    except Exception:
        for path in reversed(written):
            try:
                path.unlink()
            except OSError:
                pass
        raise
    return {
        "manifest": str(manifest_path),
        "signature": str(signature_path),
        "metadata": str(metadata_path),
        "manifest_sha256": signed.manifest_sha256,
        "package_sha256": signed.package_sha256,
        "package_size": signed.package_size,
    }


def load_prepared_release(
    *,
    package_path: str | Path,
    manifest_path: str | Path,
    signature_path: str | Path,
    metadata_path: str | Path,
    trust_profile_path: str | Path,
    expected_api_origin: str,
) -> SignedRelease:
    """Rehydrate and verify public prepared assets without any signing private key."""

    package = _regular_file(package_path, "release package")
    manifest_source = _regular_file(manifest_path, "release manifest")
    signature_source = _regular_file(signature_path, "release signature")
    metadata_source = _regular_file(metadata_path, "prepared release metadata")
    manifest_bytes = manifest_source.read_bytes()
    signature = signature_source.read_bytes()
    if len(manifest_bytes) == 0 or len(manifest_bytes) > 2 * 1024 * 1024:
        raise ValueError("release manifest size is invalid")
    if len(signature) != 64:
        raise ValueError("release signature must be 64 bytes")
    try:
        metadata_value: Any = json.loads(metadata_source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("prepared release metadata is invalid") from exc
    if not isinstance(metadata_value, dict):
        raise ValueError("prepared release metadata must be an object")
    metadata = metadata_value
    manifest = UpdateManifest.from_json_bytes(manifest_bytes)
    if manifest.signing is None:
        raise ValueError("prepared release manifest is unsigned")

    profile = DeploymentTrustProfile.load(trust_profile_path)
    profile.assert_private_production_contract(expected_api_origin=expected_api_origin)
    trusted = TrustedEd25519Keys.from_base64(profile.release_public_keys)
    trusted.verify(manifest.signing.key_id, manifest_bytes, signature)

    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    package_sha256 = sha256_file(package)
    package_size = package.stat().st_size
    expected = {
        "release_id": manifest.release_id,
        "version": str(manifest.version),
        "channel": manifest.channel,
        "signing_key_id": manifest.signing.key_id,
        "manifest_sha256": manifest_sha256,
        "package_sha256": package_sha256,
        "package_size": package_size,
        "package_name": package.name,
    }
    for name, value in expected.items():
        if metadata.get(name) != value:
            raise ValueError(f"prepared release metadata mismatch: {name}")
    if manifest.package.sha256 != package_sha256 or manifest.package.size != package_size:
        raise ValueError("prepared release package does not match manifest")
    if manifest.package.filename != package.name:
        raise ValueError("prepared release package filename does not match manifest")

    return SignedRelease(
        package_path=package,
        manifest_bytes=manifest_bytes,
        signature=signature,
        manifest_sha256=manifest_sha256,
        package_sha256=package_sha256,
        package_size=package_size,
        version=str(manifest.version),
        release_id=manifest.release_id,
        channel=manifest.channel,
        signing_key_id=manifest.signing.key_id,
    )
