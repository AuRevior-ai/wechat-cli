"""Signed offline lease validation and trusted wall-clock checks."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from ..update.crypto import TrustedEd25519Keys
from ..update.errors import ErrorCode, UpdateError
from .models import ClientLicenseState

_MAX_OFFLINE_DURATION = timedelta(days=7)
_DEFAULT_EXPIRING_WINDOW = timedelta(days=2)


def _parse_timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_revision(data: Mapping[str, Any], name: str) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an integer >= 1")
    return value


@dataclass(frozen=True)
class OfflineLease:
    schema_version: int
    license_id: str
    device_id: str
    status: str
    license_revision: int
    device_revision: int
    issued_at: str
    offline_until: str
    nonce: str
    key_id: str

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported offline lease schema")
        if self.status not in {"active", "suspended", "revoked"}:
            raise ValueError("offline lease status is invalid")
        for name in ("license_id", "device_id", "nonce", "key_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.license_revision < 1 or self.device_revision < 1:
            raise ValueError("lease revisions must be positive")
        issued = self.issued_datetime
        expires = self.offline_until_datetime
        duration = expires - issued
        if duration <= timedelta(0):
            raise ValueError("offline lease must expire after it is issued")
        if duration > _MAX_OFFLINE_DURATION:
            raise ValueError("offline lease cannot exceed seven days")

    @property
    def issued_datetime(self) -> datetime:
        return _parse_timestamp(self.issued_at, "issued_at")

    @property
    def offline_until_datetime(self) -> datetime:
        return _parse_timestamp(self.offline_until, "offline_until")

    @property
    def duration_seconds(self) -> int:
        return int((self.offline_until_datetime - self.issued_datetime).total_seconds())

    @classmethod
    def from_json_bytes(cls, raw: bytes) -> "OfflineLease":
        if not isinstance(raw, bytes):
            raise ValueError("offline lease content must be bytes")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("offline lease must be valid UTF-8 JSON") from exc
        if not isinstance(value, Mapping):
            raise ValueError("offline lease root must be an object")
        schema = value.get("schema_version")
        if isinstance(schema, bool) or not isinstance(schema, int):
            raise ValueError("schema_version must be an integer")
        return cls(
            schema_version=schema,
            license_id=_required_string(value, "license_id"),
            device_id=_required_string(value, "device_id"),
            status=_required_string(value, "status"),
            license_revision=_required_revision(value, "license_revision"),
            device_revision=_required_revision(value, "device_revision"),
            issued_at=_required_string(value, "issued_at"),
            offline_until=_required_string(value, "offline_until"),
            nonce=_required_string(value, "nonce"),
            key_id=_required_string(value, "key_id"),
        )

    def client_state_at(
        self,
        now: datetime,
        *,
        expiring_window: timedelta = _DEFAULT_EXPIRING_WINDOW,
    ) -> ClientLicenseState:
        if now.tzinfo is None:
            raise ValueError("now must include a timezone")
        if expiring_window < timedelta(0):
            raise ValueError("expiring_window cannot be negative")
        if self.status == "suspended":
            return ClientLicenseState.LICENSE_SUSPENDED
        if self.status == "revoked":
            return ClientLicenseState.LICENSE_REVOKED
        remaining = self.offline_until_datetime - now.astimezone(timezone.utc)
        if remaining < timedelta(0):
            return ClientLicenseState.OFFLINE_EXPIRED
        if remaining <= expiring_window:
            return ClientLicenseState.OFFLINE_EXPIRING
        return ClientLicenseState.OFFLINE_VALID


def _decode_signature(signature: bytes | str) -> bytes:
    if isinstance(signature, bytes):
        return signature
    if isinstance(signature, str):
        try:
            return base64.b64decode(signature, validate=True)
        except (ValueError, TypeError) as exc:
            raise UpdateError(
                ErrorCode.UPDATE_SIGNATURE_INVALID,
                "offline lease signature is not valid base64",
            ) from exc
    raise UpdateError(
        ErrorCode.UPDATE_SIGNATURE_INVALID,
        "offline lease signature must be bytes or base64 text",
    )


def verify_signed_lease(
    raw_lease: bytes,
    signature: bytes | str,
    trusted_keys: TrustedEd25519Keys,
    *,
    expected_device_id: str,
    expected_license_id: str | None = None,
) -> OfflineLease:
    lease = OfflineLease.from_json_bytes(raw_lease)
    trusted_keys.verify(lease.key_id, raw_lease, _decode_signature(signature))
    if lease.device_id != expected_device_id:
        raise UpdateError(
            ErrorCode.OFFLINE_LEASE_DENIED,
            "offline lease is bound to a different device",
        )
    if expected_license_id is not None and lease.license_id != expected_license_id:
        raise UpdateError(
            ErrorCode.OFFLINE_LEASE_DENIED,
            "offline lease is bound to a different license",
        )
    return lease


@dataclass(frozen=True)
class TrustedTimeState:
    last_server_time: str
    last_wall_clock: str

    def __post_init__(self) -> None:
        _parse_timestamp(self.last_server_time, "last_server_time")
        _parse_timestamp(self.last_wall_clock, "last_wall_clock")

    @property
    def latest_trusted_datetime(self) -> datetime:
        return max(
            _parse_timestamp(self.last_server_time, "last_server_time"),
            _parse_timestamp(self.last_wall_clock, "last_wall_clock"),
        )

    def assert_not_rolled_back(
        self,
        now: datetime,
        *,
        tolerance: timedelta = timedelta(minutes=5),
    ) -> None:
        if now.tzinfo is None:
            raise ValueError("now must include a timezone")
        if tolerance < timedelta(0):
            raise ValueError("tolerance cannot be negative")
        if now.astimezone(timezone.utc) + tolerance < self.latest_trusted_datetime:
            raise UpdateError(
                ErrorCode.OFFLINE_LEASE_DENIED,
                "system clock moved significantly behind the last trusted time",
            )

    def updated(
        self,
        *,
        server_time: datetime,
        wall_clock: datetime,
    ) -> "TrustedTimeState":
        if server_time.tzinfo is None or wall_clock.tzinfo is None:
            raise ValueError("trusted time updates must include timezones")
        return TrustedTimeState(
            last_server_time=_format_timestamp(server_time),
            last_wall_clock=_format_timestamp(wall_clock),
        )
