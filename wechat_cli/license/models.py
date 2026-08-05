"""Validated license and device API response models."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


class ClientLicenseState(str, Enum):
    UNACTIVATED = "unactivated"
    ONLINE_VALID = "online_valid"
    OFFLINE_VALID = "offline_valid"
    OFFLINE_EXPIRING = "offline_expiring"
    OFFLINE_EXPIRED = "offline_expired"
    DEVICE_UNBOUND = "device_unbound"
    DEVICE_DISABLED = "device_disabled"
    LICENSE_SUSPENDED = "license_suspended"
    LICENSE_REVOKED = "license_revoked"
    LOCAL_STATE_CORRUPT = "local_state_corrupt"


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _required_int(data: Mapping[str, Any], name: str, *, minimum: int = 0) -> int:
    value = data.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _decode_base64(data: Mapping[str, Any], name: str) -> bytes:
    encoded = _required_string(data, name)
    try:
        return base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{name} must be valid base64") from exc


def _timestamp(data: Mapping[str, Any], name: str) -> str:
    value = _required_string(data, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return value


@dataclass(frozen=True)
class ActivationResult:
    license_id: str
    device_id: str
    device_token: str = field(repr=False)
    device_count: int = 0
    maximum_devices: int = 3
    lease_content: bytes = field(default=b"", repr=False)
    lease_signature: bytes = field(default=b"", repr=False)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ActivationResult":
        if not isinstance(data, Mapping):
            raise ValueError("activation response must be an object")
        device_count = _required_int(data, "device_count")
        maximum_devices = _required_int(data, "maximum_devices", minimum=1)
        if device_count > maximum_devices:
            raise ValueError("device_count cannot exceed maximum_devices")
        return cls(
            license_id=_required_string(data, "license_id"),
            device_id=_required_string(data, "device_id"),
            device_token=_required_string(data, "device_token"),
            device_count=device_count,
            maximum_devices=maximum_devices,
            lease_content=_decode_base64(data, "lease_content_base64"),
            lease_signature=_decode_base64(data, "lease_signature_base64"),
        )


@dataclass(frozen=True)
class ValidationResult:
    license_id: str
    device_id: str
    server_time: str
    lease_content: bytes = field(repr=False)
    lease_signature: bytes = field(repr=False)

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ValidationResult":
        if not isinstance(data, Mapping):
            raise ValueError("validation response must be an object")
        return cls(
            license_id=_required_string(data, "license_id"),
            device_id=_required_string(data, "device_id"),
            server_time=_timestamp(data, "server_time"),
            lease_content=_decode_base64(data, "lease_content_base64"),
            lease_signature=_decode_base64(data, "lease_signature_base64"),
        )


@dataclass(frozen=True)
class DeviceRecord:
    device_id: str
    display_name: str
    status: str
    is_current: bool
    last_validated_at: str | None
    last_app_version: str | None
    last_launcher_version: str | None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DeviceRecord":
        if not isinstance(data, Mapping):
            raise ValueError("device record must be an object")
        status = _required_string(data, "status")
        if status not in {"active", "disabled", "unbound"}:
            raise ValueError("device status is invalid")
        is_current = data.get("is_current")
        if not isinstance(is_current, bool):
            raise ValueError("is_current must be a boolean")

        def optional_string(name: str) -> str | None:
            value = data.get(name)
            if value is None:
                return None
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be null or a non-empty string")
            return value

        last_validated = optional_string("last_validated_at")
        if last_validated is not None:
            _timestamp({"value": last_validated}, "value")
        return cls(
            device_id=_required_string(data, "device_id"),
            display_name=_required_string(data, "display_name"),
            status=status,
            is_current=is_current,
            last_validated_at=last_validated,
            last_app_version=optional_string("last_app_version"),
            last_launcher_version=optional_string("last_launcher_version"),
        )
