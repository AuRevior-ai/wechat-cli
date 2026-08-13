"""DPAPI-protected administrator API configuration."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from ..update.errors import ErrorCode, UpdateError
from ..windows.dpapi import DataProtector

_FILE_MAGIC = b"WCADM1\x00"
_ENTROPY = b"wechat-cli-admin-config-v1"
_LEGACY_ADMIN_TOKEN_PREFIX = "wcadmin_adm_"
_SESSION_TOKEN_PREFIX = "wcas_adms_"
_ENVIRONMENTS = {"local", "staging", "production", "legacy"}


def _validate_token(value: str, *, session: bool) -> None:
    prefix = _SESSION_TOKEN_PREFIX if session else _LEGACY_ADMIN_TOKEN_PREFIX
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError("administrator token format is invalid")
    raw_prefix = "wcas_" if session else "wcadmin_"
    parts = value.removeprefix(raw_prefix).split(".", 1)
    if (
        len(parts) != 2
        or not 12 <= len(parts[0]) <= 80
        or not 32 <= len(parts[1]) <= 256
        or not all(
            character.isalnum() or character in "_-"
            for component in parts
            for character in component
        )
    ):
        raise ValueError("administrator token format is invalid")


def _parse_timestamp(value: str, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class AdminConfig:
    api_base_url: str
    environment: str = "local"
    session_token: str | None = field(default=None, repr=False)
    session_expires_at: str | None = None
    legacy_admin_token: str | None = field(default=None, repr=False)
    allow_insecure_loopback: bool = False
    admin_token: str | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        parsed = urlparse(self.api_base_url)
        is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https":
            if not (
                self.allow_insecure_loopback
                and parsed.scheme == "http"
                and is_loopback
            ):
                raise ValueError("administrator API URL must use HTTPS")
        if (
            not parsed.netloc
            or parsed.path not in {"", "/"}
            or parsed.params
            or parsed.query
            or parsed.fragment
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise ValueError("administrator API URL must contain only scheme and authority")
        object.__setattr__(self, "api_base_url", self.api_base_url.rstrip("/"))

        if self.environment not in _ENVIRONMENTS:
            raise ValueError("administrator environment is invalid")
        if self.environment == "production" and self.allow_insecure_loopback:
            raise ValueError("production administrator API cannot allow insecure loopback")

        legacy = self.legacy_admin_token
        if self.admin_token is not None:
            if legacy is not None and legacy != self.admin_token:
                raise ValueError("conflicting legacy administrator tokens")
            legacy = self.admin_token
        object.__setattr__(self, "admin_token", None)
        object.__setattr__(self, "legacy_admin_token", legacy)

        if self.session_token is None:
            if self.session_expires_at is not None:
                raise ValueError("session expiry requires a session token")
        else:
            _validate_token(self.session_token, session=True)
            if self.session_expires_at is None:
                raise ValueError("session token requires an expiry")
            _parse_timestamp(self.session_expires_at, "session_expires_at")

        if legacy is not None:
            _validate_token(legacy, session=False)

        if self.session_token is None and legacy is None:
            raise ValueError("administrator configuration requires a credential")

    def api_credential(self, *, now: datetime | None = None) -> str:
        if self.session_token is not None and self.session_expires_at is not None:
            current = now or datetime.now(timezone.utc)
            if current.tzinfo is None:
                raise ValueError("credential check time must include a timezone")
            expires = _parse_timestamp(self.session_expires_at, "session_expires_at")
            if current.astimezone(timezone.utc) < expires:
                return self.session_token
            raise ValueError("administrator session has expired; run login again")
        if self.environment == "local" and self.legacy_admin_token is not None:
            return self.legacy_admin_token
        raise ValueError("short-lived administrator session is required for this environment")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "api_base_url": self.api_base_url,
            "environment": self.environment,
            "session_token": self.session_token,
            "session_expires_at": self.session_expires_at,
            "legacy_admin_token": self.legacy_admin_token,
            "allow_insecure_loopback": self.allow_insecure_loopback,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AdminConfig":
        if not isinstance(value, Mapping):
            raise ValueError("administrator config root must be an object")
        schema = value.get("schema_version")
        if schema == 1:
            api_base_url = value.get("api_base_url")
            admin_token = value.get("admin_token")
            allow_insecure = value.get("allow_insecure_loopback", False)
            if not isinstance(api_base_url, str) or not isinstance(admin_token, str):
                raise ValueError("administrator config is missing required fields")
            if not isinstance(allow_insecure, bool):
                raise ValueError("allow_insecure_loopback must be a boolean")
            return cls(
                api_base_url=api_base_url,
                environment="legacy",
                legacy_admin_token=admin_token,
                allow_insecure_loopback=allow_insecure,
            )
        if schema != 2:
            raise ValueError("unsupported administrator config schema")
        api_base_url = value.get("api_base_url")
        environment = value.get("environment")
        session_token = value.get("session_token")
        session_expires_at = value.get("session_expires_at")
        legacy_token = value.get("legacy_admin_token")
        allow_insecure = value.get("allow_insecure_loopback", False)
        if not isinstance(api_base_url, str) or not isinstance(environment, str):
            raise ValueError("administrator config is missing required fields")
        if session_token is not None and not isinstance(session_token, str):
            raise ValueError("session_token must be text or null")
        if session_expires_at is not None and not isinstance(session_expires_at, str):
            raise ValueError("session_expires_at must be text or null")
        if legacy_token is not None and not isinstance(legacy_token, str):
            raise ValueError("legacy_admin_token must be text or null")
        if not isinstance(allow_insecure, bool):
            raise ValueError("allow_insecure_loopback must be a boolean")
        return cls(
            api_base_url=api_base_url,
            environment=environment,
            session_token=session_token,
            session_expires_at=session_expires_at,
            legacy_admin_token=legacy_token,
            allow_insecure_loopback=allow_insecure,
        )


def default_admin_config_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    local_appdata = values.get("LOCALAPPDATA")
    if not local_appdata:
        raise ValueError("LOCALAPPDATA is required for administrator configuration")
    return Path(local_appdata) / "WeChatCliAdmin" / "admin-config.dat"


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


class AdminConfigStorage:
    def __init__(self, path: str | Path, protector: DataProtector) -> None:
        self.path = Path(path)
        self.protector = protector

    def save(self, config: AdminConfig) -> None:
        if not isinstance(config, AdminConfig):
            raise TypeError("config must be an AdminConfig")
        plaintext = json.dumps(
            config.to_mapping(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        protected = self.protector.protect(plaintext, entropy=_ENTROPY)
        _atomic_write_bytes(self.path, _FILE_MAGIC + protected)

    def load(self) -> AdminConfig | None:
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_bytes()
            if not raw.startswith(_FILE_MAGIC) or len(raw) <= len(_FILE_MAGIC):
                raise ValueError("administrator config envelope is invalid")
            plaintext = self.protector.unprotect(
                raw[len(_FILE_MAGIC) :],
                entropy=_ENTROPY,
            )
            value = json.loads(plaintext.decode("utf-8"))
            if not isinstance(value, Mapping):
                raise ValueError("administrator config root must be an object")
            return AdminConfig.from_mapping(value)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise UpdateError(
                ErrorCode.LOCAL_STATE_CORRUPT,
                "administrator configuration is damaged or cannot be decrypted",
            ) from exc
