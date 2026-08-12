"""Authenticated update-check client with mandatory manifest verification."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol

from .crypto import TrustedEd25519Keys
from .errors import ErrorCode, UpdateError
from .manifest import verify_signed_manifest
from .models import FailedReleaseIdentity, UpdateManifest
from .versioning import SemanticVersion


class UpdateTransport(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


def _decode_base64(value: Any, name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise UpdateError(
            ErrorCode.UPDATE_MANIFEST_INVALID,
            f"{name} must be non-empty base64 text",
        )
    try:
        return base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise UpdateError(
            ErrorCode.UPDATE_MANIFEST_INVALID,
            f"{name} is not valid base64",
        ) from exc


def _timestamp(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise UpdateError(ErrorCode.UPDATE_MANIFEST_INVALID, f"{name} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UpdateError(
            ErrorCode.UPDATE_MANIFEST_INVALID,
            f"{name} must be an ISO-8601 timestamp",
        ) from exc
    if parsed.tzinfo is None:
        raise UpdateError(
            ErrorCode.UPDATE_MANIFEST_INVALID,
            f"{name} must include a timezone",
        )
    return value


@dataclass(frozen=True)
class UpdateCheckResult:
    update_available: bool
    manifest: UpdateManifest | None = None
    raw_manifest: bytes | None = field(default=None, repr=False)
    manifest_signature: bytes | None = field(default=None, repr=False)
    download_ticket: str | None = field(default=None, repr=False)
    download_ticket_expires_at: str | None = None
    checked_at: str | None = None


class UpdateApiClient:
    def __init__(
        self,
        transport: UpdateTransport,
        *,
        trusted_keys: TrustedEd25519Keys,
    ) -> None:
        self.transport = transport
        self.trusted_keys = trusted_keys

    def _request(
        self,
        *,
        device_token: str,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        if not device_token:
            raise ValueError("device token is required")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {device_token}",
        }
        try:
            status, response = self.transport(
                "POST",
                "/v1/updates/check",
                headers,
                payload,
            )
        except (OSError, TimeoutError) as exc:
            raise UpdateError(
                ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE,
                str(exc) or "update service unavailable",
                retryable=True,
            ) from exc
        if not isinstance(response, Mapping):
            raise UpdateError(
                ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE,
                "update service returned a non-object response",
                retryable=True,
            )
        if 200 <= status < 300:
            return response
        error = response.get("error")
        data = error if isinstance(error, Mapping) else {}
        raw_code = data.get("code")
        try:
            code = ErrorCode(raw_code) if isinstance(raw_code, str) else ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE
        except ValueError:
            code = ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE
        message = data.get("message")
        retryable = data.get("retryable") is True
        raise UpdateError(
            code,
            message if isinstance(message, str) and message else f"update service returned HTTP {status}",
            retryable=retryable,
        )

    def check(
        self,
        *,
        device_token: str,
        current_version: str,
        launcher_version: str,
        channel: str,
        platform: str,
        architecture: str,
        product: str,
        device_id: str,
        failed_versions: list[str] | None = None,
        failed_releases: list[FailedReleaseIdentity | Mapping[str, Any]] | None = None,
    ) -> UpdateCheckResult:
        SemanticVersion.parse(current_version)
        SemanticVersion.parse(launcher_version)
        if channel not in {"stable", "beta"}:
            raise ValueError("channel must be stable or beta")
        if not device_id:
            raise ValueError("device_id is required")
        legacy_failed_versions = list(failed_versions or [])
        for failed in legacy_failed_versions:
            SemanticVersion.parse(failed)
        exact_failed_releases: list[FailedReleaseIdentity] = []
        for failed in failed_releases or []:
            if isinstance(failed, FailedReleaseIdentity):
                exact_failed_releases.append(failed)
            elif isinstance(failed, Mapping):
                exact_failed_releases.append(FailedReleaseIdentity.from_mapping(failed))
            else:
                raise ValueError("failed release identity must be a mapping")
        response = self._request(
            device_token=device_token,
            payload={
                "current_version": current_version,
                "launcher_version": launcher_version,
                "channel": channel,
                "platform": platform,
                "architecture": architecture,
                "product": product,
                "device_id": device_id,
                "failed_versions": legacy_failed_versions,
                "failed_releases": [item.to_mapping() for item in exact_failed_releases],
            },
        )
        available = response.get("update_available")
        if not isinstance(available, bool):
            raise UpdateError(
                ErrorCode.UPDATE_MANIFEST_INVALID,
                "update_available must be a boolean",
            )
        if not available:
            checked_value = response.get("checked_at")
            checked_at = None if checked_value is None else _timestamp(checked_value, "checked_at")
            return UpdateCheckResult(False, checked_at=checked_at)

        manifest_envelope = response.get("manifest")
        if not isinstance(manifest_envelope, Mapping):
            raise UpdateError(
                ErrorCode.UPDATE_MANIFEST_INVALID,
                "update response is missing its manifest envelope",
            )
        raw_manifest = _decode_base64(
            manifest_envelope.get("content_base64"),
            "manifest.content_base64",
        )
        signature = _decode_base64(
            manifest_envelope.get("signature_base64"),
            "manifest.signature_base64",
        )
        manifest = verify_signed_manifest(raw_manifest, signature, self.trusted_keys)
        manifest.validate_target(
            product=product,
            platform=platform,
            architecture=architecture,
            current_app_version=current_version,
            launcher_version=launcher_version,
        )
        ticket = response.get("download_ticket")
        if not isinstance(ticket, str) or not ticket:
            raise UpdateError(
                ErrorCode.DOWNLOAD_NOT_AUTHORIZED,
                "update response is missing a download ticket",
            )
        expires = _timestamp(
            response.get("download_ticket_expires_at"),
            "download_ticket_expires_at",
        )
        return UpdateCheckResult(
            update_available=True,
            manifest=manifest,
            raw_manifest=raw_manifest,
            manifest_signature=signature,
            download_ticket=ticket,
            download_ticket_expires_at=expires,
        )
