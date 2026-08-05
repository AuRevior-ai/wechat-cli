"""Atomic JSON state files used by the launcher and updater."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PureWindowsPath
from typing import Any, Mapping

from .errors import ErrorCode, UpdateError
from .versioning import SemanticVersion

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _state_error(message: str, *, cause: Exception | None = None) -> UpdateError:
    error = UpdateError(ErrorCode.LOCAL_STATE_CORRUPT, message)
    if cause is not None:
        error.__cause__ = cause
    return error


def atomic_write_json(path: str | Path, value: Mapping[str, Any]) -> None:
    if not isinstance(value, Mapping):
        raise TypeError("atomic JSON state must be an object")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, target)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass


def read_json_object(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        raw = source.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _state_error(f"state file is unreadable or invalid: {source}", cause=exc)
    if not isinstance(value, dict):
        raise _state_error(f"state file root must be an object: {source}")
    return value


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _validate_timestamp(value: str, name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return value


def _validate_relative_windows_path(value: str, name: str) -> str:
    path = PureWindowsPath(value)
    if path.is_absolute() or path.drive or not path.parts or ".." in path.parts:
        raise ValueError(f"{name} must be a safe relative Windows path")
    return str(path)


@dataclass(frozen=True)
class PendingUpdate:
    release_id: str
    version: str
    prepared_path: str
    manifest_sha256: str
    prepared_at: str
    install_on_next_start: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.release_id, str) or not self.release_id.strip():
            raise ValueError("release_id must be a non-empty string")
        SemanticVersion.parse(self.version)
        _validate_relative_windows_path(self.prepared_path, "prepared_path")
        if _SHA256_RE.fullmatch(self.manifest_sha256) is None:
            raise ValueError("manifest_sha256 must contain 64 hexadecimal characters")
        _validate_timestamp(self.prepared_at, "prepared_at")
        if not isinstance(self.install_on_next_start, bool):
            raise ValueError("install_on_next_start must be a boolean")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "version": self.version,
            "prepared_path": self.prepared_path,
            "manifest_sha256": self.manifest_sha256.lower(),
            "prepared_at": self.prepared_at,
            "install_on_next_start": self.install_on_next_start,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "PendingUpdate":
        try:
            install = data.get("install_on_next_start")
            if not isinstance(install, bool):
                raise ValueError("install_on_next_start must be a boolean")
            return cls(
                release_id=_required_string(data, "release_id"),
                version=_required_string(data, "version"),
                prepared_path=_required_string(data, "prepared_path"),
                manifest_sha256=_required_string(data, "manifest_sha256"),
                prepared_at=_required_string(data, "prepared_at"),
                install_on_next_start=install,
            )
        except (TypeError, ValueError) as exc:
            raise _state_error("pending update state is invalid", cause=exc)


def save_pending_update(path: str | Path, pending: PendingUpdate) -> None:
    atomic_write_json(path, pending.to_mapping())


def load_pending_update(path: str | Path) -> PendingUpdate | None:
    source = Path(path)
    if not source.exists():
        return None
    return PendingUpdate.from_mapping(read_json_object(source))
