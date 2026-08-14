"""Validated non-secret Launcher configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from ..update.crypto import TrustedEd25519Keys
from .trust_profile import DeploymentTrustProfile


_TRUST_CRITICAL_EXTERNAL_FIELDS = frozenset(
    {
        "api_base_url",
        "channel",
        "fingerprint_salt",
        "release_public_keys",
        "lease_public_keys",
        "windows_publisher_policy",
        "distribution_profile",
        "environment",
    }
)


def _required_string(data: Mapping[str, Any], name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _key_mapping(data: Mapping[str, Any], name: str) -> Mapping[str, str]:
    value = data.get(name)
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must be a non-empty object")
    result: dict[str, str] = {}
    for key_id, encoded in value.items():
        if not isinstance(key_id, str) or not key_id.strip():
            raise ValueError(f"{name} contains an invalid key ID")
        if not isinstance(encoded, str) or not encoded:
            raise ValueError(f"{name} contains an invalid public key")
        result[key_id] = encoded
    return result


@dataclass(frozen=True)
class LauncherConfig:
    schema_version: int
    api_base_url: str
    port: int
    channel: str
    fingerprint_salt: str
    release_keys: TrustedEd25519Keys = field(repr=False)
    lease_keys: TrustedEd25519Keys = field(repr=False)
    environment: str
    distribution_profile: str
    windows_publisher_policy: str

    @property
    def update_download_url(self) -> str:
        return self.api_base_url.rstrip("/") + "/v1/updates/download"

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        allow_insecure_loopback: bool = False,
        trust_profile: DeploymentTrustProfile | None = None,
    ) -> "LauncherConfig":
        if not isinstance(data, Mapping):
            raise ValueError("launcher config root must be an object")
        if trust_profile is not None:
            forbidden = _TRUST_CRITICAL_EXTERNAL_FIELDS.intersection(data)
            if forbidden:
                names = ", ".join(sorted(forbidden))
                raise ValueError(f"external launcher config cannot contain trust-critical fields: {names}")
            if data.get("schema_version") != 2:
                raise ValueError("unsupported operational launcher config schema")
            port = data.get("port")
            if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
                raise ValueError("port must be between 1 and 65535")
            return cls(
                schema_version=2,
                api_base_url=trust_profile.api_base_url,
                port=port,
                channel=trust_profile.expected_channel,
                fingerprint_salt=trust_profile.fingerprint_salt,
                release_keys=TrustedEd25519Keys.from_base64(trust_profile.release_public_keys),
                lease_keys=TrustedEd25519Keys.from_base64(trust_profile.lease_public_keys),
                environment=trust_profile.environment,
                distribution_profile=trust_profile.distribution_profile,
                windows_publisher_policy=trust_profile.windows_publisher_policy,
            )
        schema = data.get("schema_version")
        if schema != 1:
            raise ValueError("unsupported launcher config schema")
        api_base_url = _required_string(data, "api_base_url").rstrip("/")
        parsed = urlparse(api_base_url)
        is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https":
            if not (
                allow_insecure_loopback
                and parsed.scheme == "http"
                and is_loopback
            ):
                raise ValueError("api_base_url must use HTTPS")
        if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("api_base_url must contain only scheme and authority")
        port = data.get("port")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        channel = _required_string(data, "channel")
        if channel not in {"stable", "beta"}:
            raise ValueError("channel must be stable or beta")
        fingerprint_salt = _required_string(data, "fingerprint_salt")
        release_keys = TrustedEd25519Keys.from_base64(
            _key_mapping(data, "release_public_keys")
        )
        lease_keys = TrustedEd25519Keys.from_base64(
            _key_mapping(data, "lease_public_keys")
        )
        return cls(
            schema_version=schema,
            api_base_url=api_base_url,
            port=port,
            channel=channel,
            fingerprint_salt=fingerprint_salt,
            release_keys=release_keys,
            lease_keys=lease_keys,
            environment="legacy",
            distribution_profile="legacy",
            windows_publisher_policy="",
        )

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        allow_insecure_loopback: bool = False,
        trust_profile: DeploymentTrustProfile | None = None,
    ) -> "LauncherConfig":
        source = Path(path)
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"launcher config is unreadable: {source}") from exc
        return cls.from_mapping(
            value,
            allow_insecure_loopback=allow_insecure_loopback,
            trust_profile=trust_profile,
        )
