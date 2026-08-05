"""Verification helpers for signed update manifests and packages."""

from __future__ import annotations

import base64
from pathlib import Path

from .crypto import TrustedEd25519Keys, verify_file_sha256
from .errors import ErrorCode, UpdateError
from .models import UpdateManifest


def decode_manifest_signature(signature: bytes | str) -> bytes:
    if isinstance(signature, bytes):
        decoded = signature
    elif isinstance(signature, str):
        try:
            decoded = base64.b64decode(signature, validate=True)
        except (ValueError, TypeError) as exc:
            raise UpdateError(
                ErrorCode.UPDATE_SIGNATURE_INVALID,
                "manifest signature is not valid base64",
            ) from exc
    else:
        raise UpdateError(
            ErrorCode.UPDATE_SIGNATURE_INVALID,
            "manifest signature must be bytes or base64 text",
        )
    if len(decoded) != 64:
        raise UpdateError(
            ErrorCode.UPDATE_SIGNATURE_INVALID,
            "Ed25519 signature must be 64 bytes",
        )
    return decoded


def verify_signed_manifest(
    raw_manifest: bytes,
    signature: bytes | str,
    trusted_keys: TrustedEd25519Keys,
) -> UpdateManifest:
    manifest = UpdateManifest.from_json_bytes(raw_manifest)
    if manifest.signing is None:
        raise UpdateError(
            ErrorCode.UPDATE_MANIFEST_INVALID,
            "manifest signing metadata is missing",
        )
    trusted_keys.verify(
        manifest.signing.key_id,
        raw_manifest,
        decode_manifest_signature(signature),
    )
    return manifest


def verify_manifest_package(path: str | Path, manifest: UpdateManifest) -> None:
    package_path = Path(path)
    try:
        size = package_path.stat().st_size
    except OSError as exc:
        raise UpdateError(
            ErrorCode.UPDATE_PACKAGE_INVALID,
            f"update package cannot be read: {package_path}",
        ) from exc
    if size != manifest.package.size:
        raise UpdateError(
            ErrorCode.UPDATE_HASH_MISMATCH,
            f"package size mismatch: expected {manifest.package.size}, got {size}",
        )
    verify_file_sha256(package_path, manifest.package.sha256)
