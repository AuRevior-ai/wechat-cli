"""Encrypted current-user storage for license and launcher secrets."""

from __future__ import annotations

import base64
import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..update.errors import ErrorCode, UpdateError
from ..windows.dpapi import DataProtector
from .lease import TrustedTimeState

_FILE_MAGIC = b"WCLIC1\x00"
_ENTROPY = b"wechat-cli-license-state-v1"


def _required_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_bytes(value: Any, name: str, *, minimum_length: int = 1) -> bytes:
    if not isinstance(value, bytes) or len(value) < minimum_length:
        raise ValueError(f"{name} must contain at least {minimum_length} bytes")
    return value


def _encode_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode_bytes(data: Mapping[str, Any], name: str, *, minimum_length: int = 1) -> bytes:
    encoded = data.get(name)
    if not isinstance(encoded, str) or not encoded:
        raise ValueError(f"{name} must be non-empty base64 text")
    try:
        value = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be valid base64") from exc
    return _required_bytes(value, name, minimum_length=minimum_length)


@dataclass(frozen=True)
class LocalLicenseState:
    """All persistent authorization secrets for one Windows user."""

    license_id: str
    license_key: str = field(repr=False)
    device_id: str
    device_token: str = field(repr=False)
    lease_content: bytes = field(repr=False)
    lease_signature: bytes = field(repr=False)
    local_launch_key: bytes = field(repr=False)
    trusted_time: TrustedTimeState

    def __post_init__(self) -> None:
        _required_string(self.license_id, "license_id")
        _required_string(self.license_key, "license_key")
        _required_string(self.device_id, "device_id")
        _required_string(self.device_token, "device_token")
        _required_bytes(self.lease_content, "lease_content")
        _required_bytes(self.lease_signature, "lease_signature")
        _required_bytes(self.local_launch_key, "local_launch_key", minimum_length=32)
        if not isinstance(self.trusted_time, TrustedTimeState):
            raise ValueError("trusted_time must be a TrustedTimeState")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "license_id": self.license_id,
            "license_key": self.license_key,
            "device_id": self.device_id,
            "device_token": self.device_token,
            "lease_content_base64": _encode_bytes(self.lease_content),
            "lease_signature_base64": _encode_bytes(self.lease_signature),
            "local_launch_key_base64": _encode_bytes(self.local_launch_key),
            "trusted_time": {
                "last_server_time": self.trusted_time.last_server_time,
                "last_wall_clock": self.trusted_time.last_wall_clock,
            },
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LocalLicenseState":
        if not isinstance(data, Mapping):
            raise ValueError("license state must be an object")
        if data.get("schema_version") != 1:
            raise ValueError("unsupported local license state schema")
        trusted = data.get("trusted_time")
        if not isinstance(trusted, Mapping):
            raise ValueError("trusted_time must be an object")
        return cls(
            license_id=_required_string(data.get("license_id"), "license_id"),
            license_key=_required_string(data.get("license_key"), "license_key"),
            device_id=_required_string(data.get("device_id"), "device_id"),
            device_token=_required_string(data.get("device_token"), "device_token"),
            lease_content=_decode_bytes(data, "lease_content_base64"),
            lease_signature=_decode_bytes(data, "lease_signature_base64"),
            local_launch_key=_decode_bytes(
                data,
                "local_launch_key_base64",
                minimum_length=32,
            ),
            trusted_time=TrustedTimeState(
                last_server_time=_required_string(
                    trusted.get("last_server_time"),
                    "trusted_time.last_server_time",
                ),
                last_wall_clock=_required_string(
                    trusted.get("last_wall_clock"),
                    "trusted_time.last_wall_clock",
                ),
            ),
        )


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


class LicenseStateStorage:
    """Store the complete local license state under one authenticated envelope."""

    def __init__(self, path: str | Path, protector: DataProtector) -> None:
        self.path = Path(path)
        self.protector = protector

    def save(self, state: LocalLicenseState) -> None:
        if not isinstance(state, LocalLicenseState):
            raise TypeError("state must be a LocalLicenseState")
        plaintext = json.dumps(
            state.to_mapping(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        protected = self.protector.protect(plaintext, entropy=_ENTROPY)
        _atomic_write_bytes(self.path, _FILE_MAGIC + protected)

    def load(self) -> LocalLicenseState | None:
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_bytes()
            if not raw.startswith(_FILE_MAGIC) or len(raw) <= len(_FILE_MAGIC):
                raise ValueError("local license state has an invalid envelope")
            plaintext = self.protector.unprotect(
                raw[len(_FILE_MAGIC) :],
                entropy=_ENTROPY,
            )
            value = json.loads(plaintext.decode("utf-8"))
            return LocalLicenseState.from_mapping(value)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise UpdateError(
                ErrorCode.LOCAL_STATE_CORRUPT,
                "local license state is missing, damaged, or cannot be decrypted",
            ) from exc
