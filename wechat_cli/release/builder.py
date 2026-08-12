"""Build and sign deterministic update manifests for private releases."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from ..update.crypto import sha256_file
from ..update.models import UpdateManifest
from ..update.package import AppPackageMetadata, extract_update_zip
from ..update.versioning import SemanticVersion
from ..version import PRODUCT, UPDATE_SCHEMA_VERSION


@dataclass(frozen=True)
class ReleaseBuildOptions:
    release_id: str
    channel: str
    published_at: datetime
    minimum_app_version: str
    minimum_launcher_version: str
    signing_key_id: str
    release_summary: str = ""
    release_notes_url: str | None = None
    health_timeout_seconds: int = 30
    rollout_percentage: int = 100
    rollout_seed: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.release_id, str) or not self.release_id.strip():
            raise ValueError("release_id is required")
        if self.channel not in {"stable", "beta"}:
            raise ValueError("channel must be stable or beta")
        if self.published_at.tzinfo is None:
            raise ValueError("published_at must include a timezone")
        SemanticVersion.parse(self.minimum_app_version)
        SemanticVersion.parse(self.minimum_launcher_version)
        if not isinstance(self.signing_key_id, str) or not self.signing_key_id.strip():
            raise ValueError("signing_key_id is required")
        if not isinstance(self.release_summary, str) or len(self.release_summary) > 4096:
            raise ValueError("release_summary is invalid")
        if self.release_notes_url is not None:
            if not isinstance(self.release_notes_url, str) or not self.release_notes_url:
                raise ValueError("release_notes_url must be null or non-empty text")
        if not 1 <= self.health_timeout_seconds <= 300:
            raise ValueError("health_timeout_seconds must be between 1 and 300")
        if not 0 <= self.rollout_percentage <= 100:
            raise ValueError("rollout_percentage must be between 0 and 100")
        if self.rollout_seed is not None and not self.rollout_seed:
            raise ValueError("rollout_seed must be null or non-empty text")


@dataclass(frozen=True)
class SignedRelease:
    package_path: Path
    manifest_bytes: bytes
    signature: bytes
    manifest_sha256: str
    package_sha256: str
    package_size: int
    version: str
    release_id: str
    channel: str
    signing_key_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "package_path", Path(self.package_path))
        if len(self.signature) != 64:
            raise ValueError("release signature must be 64 bytes")
        for digest in (self.manifest_sha256, self.package_sha256):
            if len(digest) != 64:
                raise ValueError("release digests must contain 64 hexadecimal characters")
            int(digest, 16)
        if self.package_size <= 0:
            raise ValueError("package_size must be positive")
        SemanticVersion.parse(self.version)

    def registration_payload(
        self,
        *,
        github_repository: str,
        github_release_id: str,
        github_asset_id: str,
        github_asset_name: str,
        operation_nonce: str,
        rollout_percentage: int = 100,
        distribution_backend: str = "github",
        distribution_object_key: str | None = None,
    ) -> dict[str, Any]:
        """Return the Worker admin registration body without any private key."""

        import base64

        return {
            "release_id": self.release_id,
            "version": self.version,
            "channel": self.channel,
            "manifest_content_base64": base64.b64encode(self.manifest_bytes).decode("ascii"),
            "manifest_signature_base64": base64.b64encode(self.signature).decode("ascii"),
            "manifest_sha256": self.manifest_sha256,
            "package_sha256": self.package_sha256,
            "package_size": self.package_size,
            "github_repository": github_repository,
            "github_release_id": github_release_id,
            "github_asset_id": github_asset_id,
            "github_asset_name": github_asset_name,
            "distribution_backend": distribution_backend,
            "distribution_object_key": distribution_object_key,
            "rollout_percentage": rollout_percentage,
            "operation_nonce": operation_nonce,
        }


def load_ed25519_private_key(
    path: str | Path,
    *,
    passphrase: str | bytes | None = None,
) -> ECC.EccKey:
    source = Path(path)
    try:
        if source.is_symlink() or not source.is_file():
            raise ValueError("release signing key path must be a regular file")
        if source.stat().st_size > 1024 * 1024:
            raise ValueError("release signing key file is unexpectedly large")
        raw = source.read_bytes()
    except OSError as exc:
        raise ValueError(f"release signing key cannot be read: {source}") from exc
    try:
        key = ECC.import_key(raw, passphrase=passphrase)
    except (ValueError, TypeError, IndexError) as exc:
        raise ValueError("release signing key is invalid or passphrase is wrong") from exc
    if key.curve != "Ed25519" or not key.has_private():
        raise ValueError("release signing key must be an Ed25519 private key")
    return key


def _read_package_metadata(package: Path) -> AppPackageMetadata:
    try:
        with zipfile.ZipFile(package, "r") as archive:
            try:
                info = archive.getinfo("app-manifest.json")
            except KeyError as exc:
                raise ValueError("release package is missing app-manifest.json") from exc
            if info.is_dir() or info.file_size > 1024 * 1024:
                raise ValueError("release package app-manifest.json is invalid")
            with archive.open(info, "r") as stream:
                raw = stream.read(1024 * 1024 + 1)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ValueError("release package is not a readable ZIP file") from exc
    if len(raw) > 1024 * 1024:
        raise ValueError("release package app-manifest.json is too large")
    return AppPackageMetadata.from_bytes(raw)


def _validate_package(package: Path, metadata: AppPackageMetadata) -> None:
    temporary_root = Path(tempfile.mkdtemp(prefix="wechat-cli-release-validate-"))
    extracted: Path | None = None
    try:
        extracted = extract_update_zip(
            package,
            temporary_root,
            expected_product=metadata.product,
            expected_version=str(metadata.version),
            expected_platform=metadata.platform,
            expected_architecture=metadata.architecture,
            expected_entrypoint=metadata.entrypoint,
        )
    finally:
        if extracted is not None and extracted.exists():
            shutil.rmtree(extracted, ignore_errors=True)
        shutil.rmtree(temporary_root, ignore_errors=True)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def build_signed_release(
    package_path: str | Path,
    signing_key_path: str | Path,
    options: ReleaseBuildOptions,
    *,
    signing_key_passphrase: str | bytes | None = None,
) -> SignedRelease:
    package = Path(package_path)
    if package.is_symlink() or not package.is_file():
        raise ValueError("release package path must be a regular file")
    if package.suffix.lower() != ".zip":
        raise ValueError("release package must be a ZIP file")
    metadata = _read_package_metadata(package)
    if metadata.product != PRODUCT:
        raise ValueError(
            f"release package product must be {PRODUCT!r}, got {metadata.product!r}"
        )
    _validate_package(package, metadata)

    minimum_app = SemanticVersion.parse(options.minimum_app_version)
    if minimum_app > metadata.version:
        raise ValueError("minimum_app_version cannot exceed the release version")
    package_sha256 = sha256_file(package)
    package_size = package.stat().st_size
    rollout_seed = options.rollout_seed or options.release_id
    manifest: dict[str, Any] = {
        "schema_version": UPDATE_SCHEMA_VERSION,
        "product": metadata.product,
        "release_id": options.release_id,
        "version": str(metadata.version),
        "channel": options.channel,
        "published_at": _format_timestamp(options.published_at),
        "platform": metadata.platform,
        "architecture": metadata.architecture,
        "package": {
            "filename": package.name,
            "size": package_size,
            "sha256": package_sha256,
            "format": "zip",
        },
        "compatibility": {
            "minimum_app_version": options.minimum_app_version,
            "minimum_launcher_version": options.minimum_launcher_version,
            "maximum_launcher_version": None,
        },
        "install": {
            "entrypoint": metadata.entrypoint,
            "health_endpoint": "/api/health",
            "health_timeout_seconds": options.health_timeout_seconds,
        },
        "rollout": {
            "enabled": True,
            "percentage": options.rollout_percentage,
            "seed": rollout_seed,
            "paused": False,
        },
        "update_policy": {
            "forced": False,
            "force_after": None,
            "minimum_allowed_version": None,
        },
        "launcher_update": None,
        "release_notes": {
            "summary": options.release_summary,
            "url": options.release_notes_url,
        },
        "signing": {
            "algorithm": "Ed25519",
            "key_id": options.signing_key_id,
        },
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    parsed = UpdateManifest.from_json_bytes(manifest_bytes)
    if str(parsed.version) != str(metadata.version):
        raise ValueError("release manifest version validation failed")

    key = load_ed25519_private_key(
        signing_key_path,
        passphrase=signing_key_passphrase,
    )
    signature = eddsa.new(key, "rfc8032").sign(manifest_bytes)
    return SignedRelease(
        package_path=package,
        manifest_bytes=manifest_bytes,
        signature=signature,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        package_sha256=package_sha256,
        package_size=package_size,
        version=str(metadata.version),
        release_id=options.release_id,
        channel=options.channel,
        signing_key_id=options.signing_key_id,
    )
