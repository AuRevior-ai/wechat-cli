"""Windows installation layout and atomic current-version pointer."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .errors import ErrorCode, UpdateError
from .state import atomic_write_json, read_json_object
from .versioning import SemanticVersion

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _validate_timestamp(value: str, name: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")
    return value


@dataclass(frozen=True)
class CurrentVersion:
    current_version: str
    previous_version: str | None
    channel: str
    activated_at: str
    manifest_sha256: str

    def __post_init__(self) -> None:
        SemanticVersion.parse(self.current_version)
        if self.previous_version is not None:
            SemanticVersion.parse(self.previous_version)
        if self.channel not in {"stable", "beta"}:
            raise ValueError("channel must be stable or beta")
        _validate_timestamp(self.activated_at, "activated_at")
        if _SHA256_RE.fullmatch(self.manifest_sha256) is None:
            raise ValueError("manifest_sha256 must contain 64 hexadecimal characters")

    def to_mapping(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "previous_version": self.previous_version,
            "channel": self.channel,
            "activated_at": self.activated_at,
            "manifest_sha256": self.manifest_sha256.lower(),
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "CurrentVersion":
        try:
            current = data.get("current_version")
            previous = data.get("previous_version")
            channel = data.get("channel")
            activated_at = data.get("activated_at")
            digest = data.get("manifest_sha256")
            if not isinstance(current, str):
                raise ValueError("current_version must be a string")
            if previous is not None and not isinstance(previous, str):
                raise ValueError("previous_version must be null or a string")
            if not isinstance(channel, str):
                raise ValueError("channel must be a string")
            if not isinstance(activated_at, str):
                raise ValueError("activated_at must be a string")
            if not isinstance(digest, str):
                raise ValueError("manifest_sha256 must be a string")
            return cls(current, previous, channel, activated_at, digest)
        except (TypeError, ValueError) as exc:
            raise UpdateError(
                ErrorCode.LOCAL_STATE_CORRUPT,
                "current version state is invalid",
            ) from exc


@dataclass(frozen=True)
class InstallLayout:
    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @classmethod
    def from_environment(cls, environment: Mapping[str, str] | None = None) -> "InstallLayout":
        values = os.environ if environment is None else environment
        local_appdata = values.get("LOCALAPPDATA")
        if not local_appdata:
            raise ValueError("LOCALAPPDATA is required to locate WeChatCliWeb")
        return cls(Path(local_appdata) / "WeChatCliWeb")

    @property
    def launcher_dir(self) -> Path:
        return self.root / "launcher"

    @property
    def versions_dir(self) -> Path:
        return self.root / "versions"

    @property
    def state_dir(self) -> Path:
        return self.root / "state"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def locks_dir(self) -> Path:
        return self.runtime_dir / "locks"

    @property
    def cache_dir(self) -> Path:
        return self.root / "cache"

    @property
    def downloads_dir(self) -> Path:
        return self.cache_dir / "downloads"

    @property
    def staging_dir(self) -> Path:
        return self.cache_dir / "staging"

    @property
    def logs_dir(self) -> Path:
        return self.root / "logs"

    @property
    def current_path(self) -> Path:
        return self.state_dir / "current.json"

    @property
    def pending_update_path(self) -> Path:
        return self.state_dir / "pending-update.json"

    @property
    def update_status_path(self) -> Path:
        return self.state_dir / "update-status.json"

    @property
    def transaction_path(self) -> Path:
        return self.state_dir / "update-transaction.json"

    @property
    def failed_versions_path(self) -> Path:
        return self.state_dir / "failed-versions.json"

    def ensure_directories(self) -> None:
        for path in (
            self.launcher_dir,
            self.versions_dir,
            self.state_dir,
            self.locks_dir,
            self.downloads_dir,
            self.staging_dir,
            self.logs_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def version_path(self, version: str) -> Path:
        parsed = SemanticVersion.parse(version)
        if str(parsed) != version:
            raise ValueError("version path must use normalized semantic version text")
        return self.versions_dir / version

    def load_current(self) -> CurrentVersion:
        return CurrentVersion.from_mapping(read_json_object(self.current_path))

    def save_current(self, state: CurrentVersion) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.current_path, state.to_mapping())

    def activate_version(
        self,
        version: str,
        *,
        manifest_sha256: str,
        activated_at: str,
    ) -> CurrentVersion:
        target = self.version_path(version)
        if not target.is_dir():
            raise UpdateError(
                ErrorCode.UPDATE_PACKAGE_INVALID,
                f"prepared version directory does not exist: {target}",
            )
        current = self.load_current() if self.current_path.exists() else None
        previous = None
        channel = "stable"
        if current is not None:
            channel = current.channel
            previous = (
                current.previous_version
                if current.current_version == version
                else current.current_version
            )
        state = CurrentVersion(
            current_version=version,
            previous_version=previous,
            channel=channel,
            activated_at=activated_at,
            manifest_sha256=manifest_sha256,
        )
        self.save_current(state)
        return state

    def restore_version(
        self,
        version: str,
        *,
        previous_version: str | None,
        manifest_sha256: str,
        activated_at: str,
    ) -> CurrentVersion:
        target = self.version_path(version)
        if not target.is_dir():
            raise UpdateError(
                ErrorCode.UPDATE_PACKAGE_INVALID,
                f"rollback version directory does not exist: {target}",
            )
        state = CurrentVersion(
            current_version=version,
            previous_version=previous_version,
            channel=self.load_current().channel if self.current_path.exists() else "stable",
            activated_at=activated_at,
            manifest_sha256=manifest_sha256,
        )
        self.save_current(state)
        return state

    def prune_versions(self, state: CurrentVersion) -> list[str]:
        keep = {state.current_version}
        if state.previous_version:
            keep.add(state.previous_version)
        removed: list[str] = []
        if not self.versions_dir.exists():
            return removed
        for child in self.versions_dir.iterdir():
            if not child.is_dir() or child.name in keep:
                continue
            try:
                SemanticVersion.parse(child.name)
            except ValueError:
                continue
            shutil.rmtree(child)
            removed.append(child.name)
        return sorted(removed)
