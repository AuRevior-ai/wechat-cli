"""Cryptographic primitives used by the update trust chain."""

from __future__ import annotations

import base64
import hashlib
import hmac
from pathlib import Path
from typing import Mapping

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from .errors import ErrorCode, UpdateError


class TrustedEd25519Keys:
    """Immutable key-id to Ed25519 public-key registry."""

    def __init__(self, keys: Mapping[str, bytes]) -> None:
        prepared: dict[str, ECC.EccKey] = {}
        for key_id, raw_key in keys.items():
            if not isinstance(key_id, str) or not key_id.strip():
                raise ValueError("trusted signing key IDs must be non-empty strings")
            if not isinstance(raw_key, bytes) or len(raw_key) != 32:
                raise ValueError("Ed25519 public keys must be 32 raw bytes")
            try:
                prepared[key_id] = eddsa.import_public_key(raw_key)
            except (ValueError, TypeError, IndexError) as exc:
                raise ValueError(f"invalid Ed25519 public key for {key_id!r}") from exc
        self._keys = prepared

    @classmethod
    def from_base64(cls, keys: Mapping[str, str]) -> "TrustedEd25519Keys":
        decoded: dict[str, bytes] = {}
        for key_id, encoded in keys.items():
            if not isinstance(encoded, str):
                raise ValueError("base64 public keys must be strings")
            try:
                decoded[key_id] = base64.b64decode(encoded, validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError(f"invalid base64 public key for {key_id!r}") from exc
        return cls(decoded)

    def verify(self, key_id: str, message: bytes, signature: bytes) -> None:
        key = self._keys.get(key_id)
        if key is None:
            raise UpdateError(
                ErrorCode.UPDATE_SIGNING_KEY_UNKNOWN,
                f"manifest signing key is not trusted: {key_id}",
            )
        if not isinstance(message, bytes):
            raise TypeError("signed message must be bytes")
        if not isinstance(signature, bytes) or len(signature) != 64:
            raise UpdateError(
                ErrorCode.UPDATE_SIGNATURE_INVALID,
                "Ed25519 signature must be 64 bytes",
            )
        try:
            eddsa.new(key, "rfc8032").verify(message, signature)
        except (ValueError, TypeError) as exc:
            raise UpdateError(
                ErrorCode.UPDATE_SIGNATURE_INVALID,
                "update manifest signature verification failed",
            ) from exc


def sha256_file(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_sha256(path: str | Path, expected_sha256: str) -> None:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError("expected_sha256 must contain 64 hexadecimal characters")
    try:
        int(expected_sha256, 16)
    except ValueError as exc:
        raise ValueError("expected_sha256 must be hexadecimal") from exc
    actual = sha256_file(path)
    if not hmac.compare_digest(actual, expected_sha256.lower()):
        raise UpdateError(
            ErrorCode.UPDATE_HASH_MISMATCH,
            f"package SHA-256 mismatch: expected {expected_sha256.lower()}, got {actual}",
        )
