"""Short-lived one-time authorization between Launcher and the app process."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from ..update.state import atomic_write_json
from ..update.versioning import SemanticVersion


class LaunchSessionError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("session times must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise LaunchSessionError("invalid", f"{name} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LaunchSessionError("invalid", f"{name} is invalid") from exc
    if parsed.tzinfo is None:
        raise LaunchSessionError("invalid", f"{name} has no timezone")
    return parsed.astimezone(timezone.utc)


def _canonical_unsigned(payload: Mapping[str, Any]) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _signature(local_launch_key: bytes, payload: Mapping[str, Any]) -> str:
    if not isinstance(local_launch_key, bytes) or len(local_launch_key) < 32:
        raise ValueError("local launch key must contain at least 32 bytes")
    return hmac.new(
        local_launch_key,
        _canonical_unsigned(payload),
        hashlib.sha256,
    ).hexdigest()


@dataclass(frozen=True)
class LaunchSession:
    session_id: str
    app_version: str
    device_id: str
    lease_hash: str
    issued_at: str
    expires_at: str
    nonce: str
    signature: str

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "LaunchSession":
        if not isinstance(value, Mapping):
            raise LaunchSessionError("invalid", "launch session root must be an object")

        def text(name: str) -> str:
            item = value.get(name)
            if not isinstance(item, str) or not item:
                raise LaunchSessionError("invalid", f"launch session field {name} is invalid")
            return item

        session = cls(
            session_id=text("session_id"),
            app_version=text("app_version"),
            device_id=text("device_id"),
            lease_hash=text("lease_hash"),
            issued_at=text("issued_at"),
            expires_at=text("expires_at"),
            nonce=text("nonce"),
            signature=text("signature"),
        )
        try:
            SemanticVersion.parse(session.app_version)
            if len(session.lease_hash) != 64 or len(session.signature) != 64:
                raise ValueError
            int(session.lease_hash, 16)
            int(session.signature, 16)
        except ValueError as exc:
            raise LaunchSessionError("invalid", "launch session contains invalid signed fields") from exc
        _parse_time(session.issued_at, "issued_at")
        _parse_time(session.expires_at, "expires_at")
        return session

    def to_mapping(self) -> dict[str, str]:
        return {
            "session_id": self.session_id,
            "app_version": self.app_version,
            "device_id": self.device_id,
            "lease_hash": self.lease_hash,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "signature": self.signature,
        }


def create_launch_session(
    *,
    runtime_dir: str | Path,
    local_launch_key: bytes,
    app_version: str,
    device_id: str,
    lease_content: bytes,
    now: datetime,
    ttl: timedelta = timedelta(minutes=2),
) -> Path:
    SemanticVersion.parse(app_version)
    if not isinstance(device_id, str) or not device_id:
        raise ValueError("device_id is required")
    if not isinstance(lease_content, bytes) or not lease_content:
        raise ValueError("lease_content is required")
    if ttl <= timedelta(0) or ttl > timedelta(minutes=5):
        raise ValueError("launch session TTL must be positive and at most five minutes")
    issued = now.astimezone(timezone.utc) if now.tzinfo is not None else None
    if issued is None:
        raise ValueError("now must include a timezone")
    payload: dict[str, Any] = {
        "session_id": "ls_" + secrets.token_urlsafe(24),
        "app_version": app_version,
        "device_id": device_id,
        "lease_hash": hashlib.sha256(lease_content).hexdigest(),
        "issued_at": _format_time(issued),
        "expires_at": _format_time(issued + ttl),
        "nonce": secrets.token_urlsafe(24),
    }
    payload["signature"] = _signature(local_launch_key, payload)
    directory = Path(runtime_dir)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"launch-session-{payload['session_id']}.json"
    atomic_write_json(path, payload)
    return path


def _claim_session(path: Path) -> Path:
    claimed = path.with_name(path.name + ".claimed-" + secrets.token_hex(8))
    try:
        os.replace(path, claimed)
    except FileNotFoundError as exc:
        raise LaunchSessionError("missing_or_consumed", "launch session is missing or already consumed") from exc
    except OSError as exc:
        raise LaunchSessionError("claim_failed", "launch session could not be claimed") from exc
    return claimed


def consume_launch_session(
    path: str | Path,
    *,
    local_launch_key: bytes,
    expected_app_version: str,
    expected_device_id: str,
    now: datetime,
    expected_lease_content: bytes | None = None,
    clock_tolerance: timedelta = timedelta(seconds=30),
) -> LaunchSession:
    source = Path(path)
    claimed = _claim_session(source)
    try:
        try:
            value = json.loads(claimed.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LaunchSessionError("invalid", "launch session is unreadable") from exc
        session = LaunchSession.from_mapping(value)
        expected_signature = _signature(local_launch_key, session.to_mapping())
        if not hmac.compare_digest(session.signature.lower(), expected_signature):
            raise LaunchSessionError("signature_invalid", "launch session signature is invalid")
        if session.app_version != expected_app_version:
            raise LaunchSessionError("version_mismatch", "launch session targets another app version")
        if session.device_id != expected_device_id:
            raise LaunchSessionError("device_mismatch", "launch session targets another device")
        if expected_lease_content is not None:
            if not isinstance(expected_lease_content, bytes) or not expected_lease_content:
                raise ValueError("expected_lease_content must be non-empty bytes")
            expected_lease_hash = hashlib.sha256(expected_lease_content).hexdigest()
            if not hmac.compare_digest(session.lease_hash, expected_lease_hash):
                raise LaunchSessionError("lease_mismatch", "launch session targets another lease")
        if now.tzinfo is None:
            raise ValueError("now must include a timezone")
        current = now.astimezone(timezone.utc)
        issued = _parse_time(session.issued_at, "issued_at")
        expires = _parse_time(session.expires_at, "expires_at")
        if expires <= issued or expires - issued > timedelta(minutes=5):
            raise LaunchSessionError("invalid", "launch session lifetime is invalid")
        if issued - current > clock_tolerance:
            raise LaunchSessionError("not_yet_valid", "launch session was issued in the future")
        if current > expires:
            raise LaunchSessionError("expired", "launch session has expired")
        return session
    finally:
        try:
            claimed.unlink()
        except FileNotFoundError:
            pass
