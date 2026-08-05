"""DPAPI-protected administrator API configuration."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from ..update.errors import ErrorCode, UpdateError
from ..windows.dpapi import DataProtector

_FILE_MAGIC = b"WCADM1\x00"
_ENTROPY = b"wechat-cli-admin-config-v1"
_ADMIN_TOKEN_PREFIX = "wcadmin_adm_"


@dataclass(frozen=True)
class AdminConfig:
    api_base_url: str
    admin_token: str = field(repr=False)
    allow_insecure_loopback: bool = False

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
        ):
            raise ValueError("administrator API URL must contain only scheme and authority")
        normalized_url = self.api_base_url.rstrip("/")
        object.__setattr__(self, "api_base_url", normalized_url)
        if not isinstance(self.admin_token, str) or not self.admin_token.startswith(
            _ADMIN_TOKEN_PREFIX
        ):
            raise ValueError("administrator token format is invalid")
        parts = self.admin_token.removeprefix("wcadmin_").split(".", 1)
        if (
            len(parts) != 2
            or not 12 <= len(parts[0]) <= 68
            or not 16 <= len(parts[1]) <= 256
            or not all(
                character.isalnum() or character in "_-"
                for component in parts
                for character in component
            )
        ):
            raise ValueError("administrator token format is invalid")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "api_base_url": self.api_base_url,
            "admin_token": self.admin_token,
            "allow_insecure_loopback": self.allow_insecure_loopback,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AdminConfig":
        if not isinstance(value, Mapping) or value.get("schema_version") != 1:
            raise ValueError("unsupported administrator config schema")
        api_base_url = value.get("api_base_url")
        admin_token = value.get("admin_token")
        allow_insecure = value.get("allow_insecure_loopback", False)
        if not isinstance(api_base_url, str) or not isinstance(admin_token, str):
            raise ValueError("administrator config is missing required fields")
        if not isinstance(allow_insecure, bool):
            raise ValueError("allow_insecure_loopback must be a boolean")
        return cls(
            api_base_url=api_base_url,
            admin_token=admin_token,
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
