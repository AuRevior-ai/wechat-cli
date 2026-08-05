"""DPAPI-protected local release publication configuration."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..update.errors import ErrorCode, UpdateError
from ..windows.dpapi import DataProtector

_FILE_MAGIC = b"WCREL1\x00"
_ENTROPY = b"wechat-cli-release-config-v1"


@dataclass(frozen=True)
class ReleaseConfig:
    repository: str
    target_commitish: str
    github_token: str = field(repr=False)
    signing_key_path: str
    signing_key_id: str

    def __post_init__(self) -> None:
        parts = self.repository.split("/") if isinstance(self.repository, str) else []
        if len(parts) != 2 or any(
            not part
            or any(
                not (character.isalnum() or character in "_.-")
                for character in part
            )
            for part in parts
        ):
            raise ValueError("repository must use owner/name format")
        if (
            not isinstance(self.target_commitish, str)
            or not self.target_commitish.strip()
            or len(self.target_commitish) > 255
        ):
            raise ValueError("target_commitish is invalid")
        if (
            not isinstance(self.github_token, str)
            or len(self.github_token) < 8
            or len(self.github_token) > 1024
        ):
            raise ValueError("GitHub token is invalid")
        key_path = Path(self.signing_key_path)
        if not key_path.is_absolute():
            raise ValueError("signing_key_path must be absolute")
        if key_path.is_symlink() or not key_path.is_file():
            raise ValueError("signing_key_path must be an existing regular file")
        object.__setattr__(self, "signing_key_path", str(key_path.resolve()))
        if (
            not isinstance(self.signing_key_id, str)
            or not self.signing_key_id.strip()
            or len(self.signing_key_id) > 128
        ):
            raise ValueError("signing_key_id is invalid")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "repository": self.repository,
            "target_commitish": self.target_commitish,
            "github_token": self.github_token,
            "signing_key_path": self.signing_key_path,
            "signing_key_id": self.signing_key_id,
        }

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReleaseConfig":
        if not isinstance(value, Mapping) or value.get("schema_version") != 1:
            raise ValueError("unsupported release configuration schema")
        fields = {
            name: value.get(name)
            for name in (
                "repository",
                "target_commitish",
                "github_token",
                "signing_key_path",
                "signing_key_id",
            )
        }
        if not all(isinstance(item, str) for item in fields.values()):
            raise ValueError("release configuration is missing required fields")
        return cls(**fields)  # type: ignore[arg-type]


def default_release_config_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    local_appdata = values.get("LOCALAPPDATA")
    if not local_appdata:
        raise ValueError("LOCALAPPDATA is required for release configuration")
    return Path(local_appdata) / "WeChatCliAdmin" / "release-config.dat"


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


class ReleaseConfigStorage:
    def __init__(self, path: str | Path, protector: DataProtector) -> None:
        self.path = Path(path)
        self.protector = protector

    def save(self, config: ReleaseConfig) -> None:
        if not isinstance(config, ReleaseConfig):
            raise TypeError("config must be a ReleaseConfig")
        plaintext = json.dumps(
            config.to_mapping(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        protected = self.protector.protect(plaintext, entropy=_ENTROPY)
        _atomic_write_bytes(self.path, _FILE_MAGIC + protected)

    def load(self) -> ReleaseConfig | None:
        if not self.path.exists():
            return None
        try:
            raw = self.path.read_bytes()
            if not raw.startswith(_FILE_MAGIC) or len(raw) <= len(_FILE_MAGIC):
                raise ValueError("release configuration envelope is invalid")
            plaintext = self.protector.unprotect(
                raw[len(_FILE_MAGIC) :],
                entropy=_ENTROPY,
            )
            value = json.loads(plaintext.decode("utf-8"))
            if not isinstance(value, Mapping):
                raise ValueError("release configuration root must be an object")
            return ReleaseConfig.from_mapping(value)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            raise UpdateError(
                ErrorCode.LOCAL_STATE_CORRUPT,
                "release configuration is damaged or cannot be decrypted",
            ) from exc
