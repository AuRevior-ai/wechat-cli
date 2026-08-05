"""Validated data models for the signed update manifest contract."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping

from ..version import UPDATE_SCHEMA_VERSION
from .errors import ErrorCode, ManifestValidationError
from .versioning import SemanticVersion

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_ALLOWED_CHANNELS = {"stable", "beta"}


def _invalid(message: str) -> ManifestValidationError:
    return ManifestValidationError(ErrorCode.UPDATE_MANIFEST_INVALID, message)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _invalid(f"{name} must be an object")
    return value


def _string(value: Any, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise _invalid(f"{name} must be a string")
    if not allow_empty and not value.strip():
        raise _invalid(f"{name} cannot be empty")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    if value is None:
        return None
    return _string(value, name)


def _integer(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _invalid(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise _invalid(f"{name} must be at least {minimum}")
    return value


def _boolean(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise _invalid(f"{name} must be a boolean")
    return value


def _version(value: Any, name: str) -> SemanticVersion:
    try:
        return SemanticVersion.parse(_string(value, name))
    except ValueError as exc:
        raise _invalid(f"{name} is not a valid semantic version") from exc


def _optional_version(value: Any, name: str) -> SemanticVersion | None:
    if value is None:
        return None
    return _version(value, name)


def _timestamp(value: Any, name: str) -> str:
    text = _string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _invalid(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise _invalid(f"{name} must include a timezone")
    return text


@dataclass(frozen=True)
class PackageInfo:
    filename: str
    size: int
    sha256: str
    format: str = "zip"

    @classmethod
    def from_mapping(cls, value: Any) -> "PackageInfo":
        data = _mapping(value, "package")
        filename = _string(data.get("filename"), "package.filename")
        if "/" in filename or "\\" in filename:
            raise _invalid("package.filename must be a base filename")
        size = _integer(data.get("size"), "package.size", minimum=1)
        sha256 = _string(data.get("sha256"), "package.sha256").lower()
        if _SHA256_RE.fullmatch(sha256) is None:
            raise _invalid("package.sha256 must contain 64 hexadecimal characters")
        package_format = _string(data.get("format", "zip"), "package.format").lower()
        if package_format != "zip":
            raise _invalid("package.format must be zip")
        return cls(filename=filename, size=size, sha256=sha256, format=package_format)


@dataclass(frozen=True)
class CompatibilityInfo:
    minimum_app_version: SemanticVersion
    minimum_launcher_version: SemanticVersion
    maximum_launcher_version: SemanticVersion | None = None

    @classmethod
    def from_mapping(cls, value: Any) -> "CompatibilityInfo":
        data = _mapping(value, "compatibility")
        minimum_app = _version(data.get("minimum_app_version"), "compatibility.minimum_app_version")
        minimum_launcher = _version(
            data.get("minimum_launcher_version"),
            "compatibility.minimum_launcher_version",
        )
        maximum_launcher = _optional_version(
            data.get("maximum_launcher_version"),
            "compatibility.maximum_launcher_version",
        )
        if maximum_launcher is not None and maximum_launcher < minimum_launcher:
            raise _invalid("maximum_launcher_version cannot be below minimum_launcher_version")
        return cls(minimum_app, minimum_launcher, maximum_launcher)


@dataclass(frozen=True)
class InstallInfo:
    entrypoint: str
    health_endpoint: str
    health_timeout_seconds: int = 30

    @classmethod
    def from_mapping(cls, value: Any) -> "InstallInfo":
        data = _mapping(value, "install")
        entrypoint = _string(data.get("entrypoint"), "install.entrypoint")
        if "/" in entrypoint or "\\" in entrypoint:
            raise _invalid("install.entrypoint must be a base filename")
        endpoint = _string(data.get("health_endpoint"), "install.health_endpoint")
        if not endpoint.startswith("/") or endpoint.startswith("//"):
            raise _invalid("install.health_endpoint must be an absolute local path")
        timeout = _integer(
            data.get("health_timeout_seconds", 30),
            "install.health_timeout_seconds",
            minimum=1,
        )
        if timeout > 300:
            raise _invalid("install.health_timeout_seconds cannot exceed 300")
        return cls(entrypoint, endpoint, timeout)


@dataclass(frozen=True)
class RolloutInfo:
    enabled: bool = True
    percentage: int = 100
    seed: str = ""
    paused: bool = False

    @classmethod
    def from_mapping(cls, value: Any | None) -> "RolloutInfo":
        if value is None:
            return cls()
        data = _mapping(value, "rollout")
        enabled = _boolean(data.get("enabled", True), "rollout.enabled")
        percentage = _integer(data.get("percentage", 100), "rollout.percentage", minimum=0)
        if percentage > 100:
            raise _invalid("rollout.percentage cannot exceed 100")
        seed = _string(data.get("seed", ""), "rollout.seed", allow_empty=True)
        paused = _boolean(data.get("paused", False), "rollout.paused")
        return cls(enabled, percentage, seed, paused)


@dataclass(frozen=True)
class UpdatePolicyInfo:
    forced: bool = False
    force_after: str | None = None
    minimum_allowed_version: SemanticVersion | None = None

    @classmethod
    def from_mapping(cls, value: Any | None) -> "UpdatePolicyInfo":
        if value is None:
            return cls()
        data = _mapping(value, "update_policy")
        forced = _boolean(data.get("forced", False), "update_policy.forced")
        force_after_value = data.get("force_after")
        force_after = None if force_after_value is None else _timestamp(
            force_after_value,
            "update_policy.force_after",
        )
        minimum_allowed = _optional_version(
            data.get("minimum_allowed_version"),
            "update_policy.minimum_allowed_version",
        )
        return cls(forced, force_after, minimum_allowed)


@dataclass(frozen=True)
class ReleaseNotes:
    summary: str = ""
    url: str | None = None

    @classmethod
    def from_mapping(cls, value: Any | None) -> "ReleaseNotes":
        if value is None:
            return cls()
        data = _mapping(value, "release_notes")
        summary = _string(data.get("summary", ""), "release_notes.summary", allow_empty=True)
        url = _optional_string(data.get("url"), "release_notes.url")
        return cls(summary, url)


@dataclass(frozen=True)
class SigningInfo:
    algorithm: str
    key_id: str

    @classmethod
    def from_mapping(cls, value: Any) -> "SigningInfo":
        data = _mapping(value, "signing")
        algorithm = _string(data.get("algorithm"), "signing.algorithm")
        if algorithm != "Ed25519":
            raise _invalid("signing.algorithm must be Ed25519")
        key_id = _string(data.get("key_id"), "signing.key_id")
        return cls(algorithm, key_id)


@dataclass(frozen=True)
class UpdateManifest:
    schema_version: int
    product: str
    release_id: str
    version: SemanticVersion
    channel: str
    published_at: str
    platform: str
    architecture: str
    package: PackageInfo
    compatibility: CompatibilityInfo
    install: InstallInfo
    rollout: RolloutInfo = field(default_factory=RolloutInfo)
    update_policy: UpdatePolicyInfo = field(default_factory=UpdatePolicyInfo)
    launcher_update: Mapping[str, Any] | None = None
    release_notes: ReleaseNotes = field(default_factory=ReleaseNotes)
    signing: SigningInfo | None = None

    @classmethod
    def from_json_bytes(cls, raw: bytes) -> "UpdateManifest":
        if not isinstance(raw, bytes):
            raise _invalid("manifest content must be bytes")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _invalid("manifest must be valid UTF-8 JSON") from exc
        return cls.from_mapping(value)

    @classmethod
    def from_mapping(cls, value: Any) -> "UpdateManifest":
        data = _mapping(value, "manifest")
        schema_version = _integer(data.get("schema_version"), "schema_version", minimum=1)
        if schema_version != UPDATE_SCHEMA_VERSION:
            raise ManifestValidationError(
                ErrorCode.UPDATE_SCHEMA_UNSUPPORTED,
                f"unsupported update schema version: {schema_version}",
            )
        product = _string(data.get("product"), "product")
        release_id = _string(data.get("release_id"), "release_id")
        version = _version(data.get("version"), "version")
        channel = _string(data.get("channel", "stable"), "channel")
        if channel not in _ALLOWED_CHANNELS:
            raise _invalid("channel must be stable or beta")
        published_at = _timestamp(data.get("published_at"), "published_at")
        platform = _string(data.get("platform"), "platform")
        architecture = _string(data.get("architecture"), "architecture")
        package = PackageInfo.from_mapping(data.get("package"))
        compatibility = CompatibilityInfo.from_mapping(data.get("compatibility"))
        install = InstallInfo.from_mapping(data.get("install"))
        rollout = RolloutInfo.from_mapping(data.get("rollout"))
        update_policy = UpdatePolicyInfo.from_mapping(data.get("update_policy"))
        launcher_value = data.get("launcher_update")
        launcher_update = None if launcher_value is None else dict(
            _mapping(launcher_value, "launcher_update")
        )
        release_notes = ReleaseNotes.from_mapping(data.get("release_notes"))
        signing = SigningInfo.from_mapping(data.get("signing"))
        return cls(
            schema_version=schema_version,
            product=product,
            release_id=release_id,
            version=version,
            channel=channel,
            published_at=published_at,
            platform=platform,
            architecture=architecture,
            package=package,
            compatibility=compatibility,
            install=install,
            rollout=rollout,
            update_policy=update_policy,
            launcher_update=launcher_update,
            release_notes=release_notes,
            signing=signing,
        )

    def validate_target(
        self,
        *,
        product: str,
        platform: str,
        architecture: str,
        current_app_version: str,
        launcher_version: str,
    ) -> None:
        if self.product != product:
            raise ManifestValidationError(
                ErrorCode.UPDATE_PRODUCT_MISMATCH,
                f"manifest product {self.product!r} does not match {product!r}",
            )
        if self.platform != platform:
            raise ManifestValidationError(
                ErrorCode.UPDATE_PLATFORM_MISMATCH,
                f"manifest platform {self.platform!r} does not match {platform!r}",
            )
        if self.architecture != architecture:
            raise ManifestValidationError(
                ErrorCode.UPDATE_ARCHITECTURE_MISMATCH,
                f"manifest architecture {self.architecture!r} does not match {architecture!r}",
            )
        try:
            current = SemanticVersion.parse(current_app_version)
            launcher = SemanticVersion.parse(launcher_version)
        except ValueError as exc:
            raise _invalid("local application or launcher version is invalid") from exc
        if current < self.compatibility.minimum_app_version:
            raise ManifestValidationError(
                ErrorCode.UPDATE_APP_TOO_OLD,
                "current application version is below the update compatibility floor",
            )
        if launcher < self.compatibility.minimum_launcher_version:
            raise ManifestValidationError(
                ErrorCode.LAUNCHER_TOO_OLD,
                "launcher version is below the manifest minimum",
            )
        maximum = self.compatibility.maximum_launcher_version
        if maximum is not None and launcher > maximum:
            raise ManifestValidationError(
                ErrorCode.UPDATE_LAUNCHER_TOO_NEW,
                "launcher version is above the manifest maximum",
            )
