"""Preparation-only client for the production release automation surface."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

from ..admin.client import AdminApiError


class AutomationJsonTransport(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


class AutomationUploadTransport(Protocol):
    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
        source: str | Path,
        metadata_headers: Mapping[str, str],
    ) -> Mapping[str, Any]: ...


HeaderProvider = Callable[[], Mapping[str, str]]


class ReleaseAutomationClient:
    """Upload/read/register only; release-state mutation is intentionally absent."""

    def __init__(
        self,
        *,
        json_transport: AutomationJsonTransport,
        upload_transport: AutomationUploadTransport,
        header_provider: HeaderProvider,
    ) -> None:
        self._json_transport = json_transport
        self._upload_transport = upload_transport
        self._header_provider = header_provider

    def _headers(self) -> dict[str, str]:
        raw = self._header_provider()
        headers: dict[str, str] = {}
        for key, value in raw.items():
            if not isinstance(key, str) or not key or not isinstance(value, str) or not value:
                raise ValueError("automation credential headers are invalid")
            headers[key] = value
        if not headers:
            raise ValueError("automation credential headers are missing")
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        status, response = self._json_transport(
            method,
            path,
            self._headers(),
            payload,
        )
        if 200 <= int(status) < 300:
            return response
        error = response.get("error")
        if isinstance(error, Mapping):
            raise AdminApiError(
                str(error.get("code") or "AUTOMATION_REQUEST_FAILED"),
                str(error.get("message") or "release automation request failed"),
                bool(error.get("retryable", False)),
                str(error.get("request_id")) if error.get("request_id") else None,
                int(status),
            )
        raise AdminApiError(
            "AUTOMATION_REQUEST_FAILED",
            "release automation request failed",
            status=int(status),
        )

    def list_releases(self) -> list[Mapping[str, Any]]:
        response = self._request("GET", "/v1/automation/releases")
        releases = response.get("releases")
        if not isinstance(releases, list):
            raise AdminApiError("INVALID_RESPONSE", "release list response is invalid")
        return [item for item in releases if isinstance(item, Mapping)]

    def upload_release_package(
        self,
        release_id: str,
        *,
        channel: str,
        package_path: str | Path,
        package_sha256: str,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        if channel not in {"stable", "beta"}:
            raise ValueError("channel must be stable or beta")
        if not release_id or len(release_id) > 128:
            raise ValueError("release_id is invalid")
        digest = package_sha256.lower()
        if len(digest) != 64:
            raise ValueError("package_sha256 must contain 64 hexadecimal characters")
        int(digest, 16)
        if not operation_nonce or len(operation_nonce) < 8:
            raise ValueError("operation_nonce is invalid")
        package = Path(package_path)
        if package.is_symlink() or not package.is_file():
            raise ValueError("release package must be a regular file")
        if hashlib.sha256(package.read_bytes()).hexdigest() != digest:
            raise ValueError("release package bytes no longer match package_sha256")
        return self._upload_transport(
            f"/v1/automation/releases/{release_id}/package",
            self._headers(),
            package,
            {
                "X-Release-Channel": channel,
                "X-Package-Sha256": digest,
                "X-Operation-Nonce": operation_nonce,
                "Content-Length": str(package.stat().st_size),
            },
        )

    def register_release(self, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return self._request("POST", "/v1/automation/releases", payload)
