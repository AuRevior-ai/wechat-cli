"""Preparation-only client for the production release automation surface."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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


class UrllibReleaseAutomationTransport:
    """HTTPS transport restricted to the privileged automation route surface."""

    def __init__(self, base_url: str, *, timeout_seconds: float = 60.0) -> None:
        parsed = urlparse(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
            or parsed.hostname.lower().endswith(".workers.dev")
        ):
            raise ValueError("automation base URL must be an exact HTTPS custom origin")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def __repr__(self) -> str:
        return f"UrllibReleaseAutomationTransport(base_url={self.base_url!r})"

    def _url(self, path: str) -> str:
        if not isinstance(path, str) or not path.startswith("/v1/automation/"):
            raise ValueError("automation transport path is outside /v1/automation/*")
        return f"{self.base_url}{path}"

    def _read_response(self, response: Any) -> tuple[int, Mapping[str, Any]]:
        with response:
            raw = response.read(4 * 1024 * 1024 + 1)
            status = int(response.status)
        if len(raw) > 4 * 1024 * 1024:
            raise AdminApiError(
                "AUTOMATION_RESPONSE_TOO_LARGE",
                "release automation response was too large",
                retryable=True,
                status=status,
            )
        if not raw:
            return status, {}
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdminApiError(
                "AUTOMATION_INVALID_RESPONSE",
                "release automation response was invalid",
                retryable=status >= 500,
                status=status,
            ) from exc
        if not isinstance(value, Mapping):
            raise AdminApiError(
                "AUTOMATION_INVALID_RESPONSE",
                "release automation response must be an object",
                retryable=status >= 500,
                status=status,
            )
        return status, dict(value)

    def _send(self, request: Request) -> tuple[int, Mapping[str, Any]]:
        try:
            response = urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            response = exc
        except (URLError, OSError, TimeoutError) as exc:
            raise AdminApiError(
                "AUTOMATION_SERVICE_UNAVAILABLE",
                "release automation service is unavailable",
                retryable=True,
            ) from exc
        return self._read_response(response)

    def json_request(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]:
        body = None if payload is None else json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request_headers = dict(headers)
        request_headers["Accept"] = "application/json"
        if body is not None:
            request_headers["Content-Type"] = "application/json"
        return self._send(
            Request(
                self._url(path),
                data=body,
                headers=request_headers,
                method=method,
            )
        )

    def upload(
        self,
        path: str,
        headers: Mapping[str, str],
        source: str | Path,
        metadata_headers: Mapping[str, str],
    ) -> Mapping[str, Any]:
        package = Path(source)
        if package.is_symlink() or not package.is_file():
            raise ValueError("release package must be a regular file")
        request_headers = dict(headers)
        request_headers.update(metadata_headers)
        request_headers["Accept"] = "application/json"
        request_headers["Content-Type"] = "application/zip"
        status, response = self._send(
            Request(
                self._url(path),
                data=package.read_bytes(),
                headers=request_headers,
                method="PUT",
            )
        )
        if 200 <= status < 300:
            return response
        error = response.get("error")
        if isinstance(error, Mapping):
            raise AdminApiError(
                str(error.get("code") or "AUTOMATION_REQUEST_FAILED"),
                str(error.get("message") or "release automation upload failed"),
                bool(error.get("retryable", False)),
                str(error.get("request_id")) if error.get("request_id") else None,
                status,
            )
        raise AdminApiError(
            "AUTOMATION_REQUEST_FAILED",
            "release automation upload failed",
            status=status,
        )


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
