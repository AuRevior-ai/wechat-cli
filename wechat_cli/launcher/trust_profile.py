"""Immutable trust-critical deployment profile for the Launcher."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse


_EMBEDDED_TRUST_PROFILE = Path("wechat_cli") / "launcher" / "deployment-trust-profile.json"


@dataclass(frozen=True)
class DeploymentTrustProfile:
    schema_version: int
    distribution_profile: str
    environment: str
    api_base_url: str
    expected_channel: str
    fingerprint_salt: str
    release_public_keys: Mapping[str, str]
    lease_public_keys: Mapping[str, str]
    windows_publisher_policy: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "DeploymentTrustProfile":
        if not isinstance(data, Mapping):
            raise ValueError("deployment trust profile root must be an object")
        schema_version = data.get("schema_version")
        if schema_version not in {1, 2}:
            raise ValueError("unsupported deployment trust profile schema")
        if schema_version == 1:
            distribution_profile = "legacy"
        else:
            distribution_profile = str(data.get("distribution_profile", "")).strip()
            if distribution_profile not in {"private_controlled", "public_formal"}:
                raise ValueError("deployment trust profile distribution profile is invalid")

        environment = str(data.get("environment", "")).strip()
        if environment not in {"local", "staging", "production"}:
            raise ValueError("deployment trust profile environment is invalid")
        api_base_url = str(data.get("api_base_url", "")).strip().rstrip("/")
        parsed = urlparse(api_base_url)
        if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("deployment trust profile API URL must contain only scheme and authority")
        expected_channel = str(data.get("expected_channel", "")).strip()
        if expected_channel not in {"stable", "beta"}:
            raise ValueError("deployment trust profile channel is invalid")
        fingerprint_salt = str(data.get("fingerprint_salt", "")).strip()
        if not fingerprint_salt:
            raise ValueError("deployment trust profile fingerprint salt is required")
        publisher_policy = str(data.get("windows_publisher_policy", "")).strip()

        release_public_keys = data.get("release_public_keys")
        lease_public_keys = data.get("lease_public_keys")
        if not isinstance(release_public_keys, Mapping) or not release_public_keys:
            raise ValueError("deployment trust profile release public keys are required")
        if not isinstance(lease_public_keys, Mapping) or not lease_public_keys:
            raise ValueError("deployment trust profile lease public keys are required")
        release_keys = {
            str(key).strip(): str(value).strip()
            for key, value in release_public_keys.items()
            if str(key).strip() and str(value).strip()
        }
        lease_keys = {
            str(key).strip(): str(value).strip()
            for key, value in lease_public_keys.items()
            if str(key).strip() and str(value).strip()
        }
        if len(release_keys) != len(release_public_keys) or len(lease_keys) != len(lease_public_keys):
            raise ValueError("deployment trust profile public key mapping is invalid")

        if environment == "production":
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https":
                raise ValueError("production deployment trust profile requires HTTPS")
            if host in {"127.0.0.1", "localhost", "::1"}:
                raise ValueError("production deployment trust profile rejects loopback API")
            if "staging" in host:
                raise ValueError("production deployment trust profile rejects staging API host")
            if expected_channel != "stable":
                raise ValueError("production deployment trust profile requires stable channel")
            if schema_version == 1 and not publisher_policy:
                raise ValueError("production deployment trust profile requires publisher policy")

        if schema_version == 2 and distribution_profile == "public_formal" and not publisher_policy:
            raise ValueError("public formal deployment trust profile requires publisher policy")

        return cls(
            schema_version=schema_version,
            distribution_profile=distribution_profile,
            environment=environment,
            api_base_url=api_base_url,
            expected_channel=expected_channel,
            fingerprint_salt=fingerprint_salt,
            release_public_keys=MappingProxyType(release_keys),
            lease_public_keys=MappingProxyType(lease_keys),
            windows_publisher_policy=publisher_policy,
        )

    @classmethod
    def load(cls, path: str | Path) -> "DeploymentTrustProfile":
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"deployment trust profile is unreadable: {source}") from exc
        return cls.from_mapping(data)


def load_embedded_trust_profile(
    base_dir: str | Path | None = None,
) -> DeploymentTrustProfile:
    if base_dir is not None:
        root = Path(base_dir)
    elif hasattr(sys, "_MEIPASS"):
        root = Path(getattr(sys, "_MEIPASS"))
    else:
        root = Path(__file__).resolve().parents[2]
    return DeploymentTrustProfile.load(root / _EMBEDDED_TRUST_PROFILE)
