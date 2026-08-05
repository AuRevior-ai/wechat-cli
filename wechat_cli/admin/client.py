"""Authenticated administrator HTTP client for the license/update Worker."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from ..version import APP_VERSION

_ADMIN_USER_AGENT = f"WeChatCliAdmin/{APP_VERSION}"


class AdminJsonTransport(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


class AdminDownloadTransport(Protocol):
    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
        destination: str | Path,
    ) -> Path: ...


@dataclass(frozen=True)
class AdminApiError(Exception):
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None
    status: int | None = None

    def __str__(self) -> str:
        suffix = f" (request_id={self.request_id})" if self.request_id else ""
        return f"{self.code}: {self.message}{suffix}"


class UrllibAdminJsonTransport:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
        allow_insecure_loopback: bool = False,
    ) -> None:
        parsed = urlparse(base_url)
        is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme != "https":
            if not (
                allow_insecure_loopback
                and parsed.scheme == "http"
                and is_loopback
            ):
                raise ValueError("administrator API URL must use HTTPS")
        if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("administrator API URL must contain only scheme and authority")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def __call__(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("administrator API path must stay under the configured origin")
        body = None
        request_headers = dict(headers)
        request_headers.setdefault("Accept", "application/json")
        request_headers.setdefault("User-Agent", _ADMIN_USER_AGENT)
        if payload is not None:
            body = json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = Request(
            self.base_url + path,
            data=body,
            headers=request_headers,
            method=method,
        )
        try:
            response = urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            response = exc
        except (URLError, OSError, TimeoutError) as exc:
            raise AdminApiError(
                "SERVICE_UNAVAILABLE",
                str(exc) or "administrator API unavailable",
                retryable=True,
            ) from exc
        with response:
            raw = response.read(4 * 1024 * 1024 + 1)
            status = int(response.status)
        if len(raw) > 4 * 1024 * 1024:
            raise AdminApiError(
                "RESPONSE_TOO_LARGE",
                "administrator API response is too large",
                retryable=True,
                status=status,
            )
        try:
            value = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdminApiError(
                "INVALID_RESPONSE",
                "administrator API returned invalid JSON",
                retryable=True,
                status=status,
            ) from exc
        if not isinstance(value, Mapping):
            raise AdminApiError(
                "INVALID_RESPONSE",
                "administrator API response must be an object",
                retryable=True,
                status=status,
            )
        return status, value


class UrllibAdminDownloadTransport:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 60.0,
        allow_insecure_loopback: bool = False,
    ) -> None:
        self._json_transport = UrllibAdminJsonTransport(
            base_url,
            timeout_seconds=timeout_seconds,
            allow_insecure_loopback=allow_insecure_loopback,
        )
        self.base_url = self._json_transport.base_url
        self.timeout_seconds = timeout_seconds

    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
        destination: str | Path,
    ) -> Path:
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("administrator download path must stay under the configured origin")
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError(target)
        request_headers = {**headers, "Accept": "application/zip"}
        request_headers.setdefault("User-Agent", _ADMIN_USER_AGENT)
        request = Request(
            self.base_url + path,
            headers=request_headers,
            method="GET",
        )
        temporary: Path | None = None
        try:
            try:
                response = urlopen(request, timeout=self.timeout_seconds)
            except HTTPError as exc:
                raw = exc.read(1024 * 1024 + 1)
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except Exception:
                    payload = {}
                error = payload.get("error") if isinstance(payload, Mapping) else None
                data = error if isinstance(error, Mapping) else {}
                raise AdminApiError(
                    str(data.get("code") or "DOWNLOAD_FAILED"),
                    str(data.get("message") or f"diagnostic download failed with HTTP {exc.code}"),
                    retryable=data.get("retryable") is True,
                    request_id=(
                        str(data.get("request_id"))
                        if data.get("request_id") is not None
                        else None
                    ),
                    status=exc.code,
                ) from exc
            with response:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix=f".{target.name}.",
                    suffix=".tmp",
                    dir=target.parent,
                    delete=False,
                ) as stream:
                    temporary = Path(stream.name)
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        stream.write(chunk)
                    stream.flush()
                    os.fsync(stream.fileno())
            os.replace(temporary, target)
            temporary = None
            return target
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass


@dataclass
class AdminApiClient:
    transport: AdminJsonTransport = field(repr=False)
    admin_token: str = field(repr=False)
    download_transport: AdminDownloadTransport | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.admin_token, str) or not self.admin_token.startswith(
            "wcadmin_"
        ):
            raise ValueError("administrator token format is invalid")

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Admin {self.admin_token}",
        }

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        try:
            status, response = self.transport(
                method,
                path,
                self._headers,
                payload,
            )
        except AdminApiError:
            raise
        except (OSError, TimeoutError) as exc:
            raise AdminApiError(
                "SERVICE_UNAVAILABLE",
                str(exc) or "administrator API unavailable",
                retryable=True,
            ) from exc
        if 200 <= status < 300:
            return response
        error = response.get("error")
        data = error if isinstance(error, Mapping) else {}
        raise AdminApiError(
            code=str(data.get("code") or "ADMIN_API_ERROR"),
            message=str(data.get("message") or f"administrator API returned HTTP {status}"),
            retryable=data.get("retryable") is True,
            request_id=(
                str(data.get("request_id"))
                if data.get("request_id") is not None
                else None
            ),
            status=status,
        )

    def create_license(
        self,
        *,
        maximum_devices: int = 3,
        release_channel: str = "stable",
        contacts: Mapping[str, str] | None = None,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "/v1/admin/licenses",
            {
                "maximum_devices": maximum_devices,
                "release_channel": release_channel,
                "contacts": dict(contacts or {}),
                "operation_nonce": operation_nonce,
            },
        )

    def batch_create_licenses(
        self,
        *,
        count: int,
        maximum_devices: int = 3,
        release_channel: str = "stable",
        operation_nonce: str,
    ) -> list[Mapping[str, Any]]:
        response = self._request(
            "POST",
            "/v1/admin/licenses/batch",
            {
                "count": count,
                "maximum_devices": maximum_devices,
                "release_channel": release_channel,
                "operation_nonce": operation_nonce,
            },
        )
        licenses = response.get("licenses")
        if not isinstance(licenses, list) or not all(
            isinstance(item, Mapping) for item in licenses
        ):
            raise AdminApiError(
                "INVALID_RESPONSE",
                "batch license response is invalid",
                retryable=True,
            )
        return list(licenses)

    def list_licenses(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Mapping[str, Any]]:
        parameters: dict[str, str] = {"limit": str(limit)}
        if query:
            parameters["query"] = query
        if status:
            parameters["status"] = status
        response = self._request(
            "GET",
            "/v1/admin/licenses?" + urlencode(parameters),
        )
        licenses = response.get("licenses")
        if not isinstance(licenses, list):
            raise AdminApiError("INVALID_RESPONSE", "license list response is invalid")
        return [item for item in licenses if isinstance(item, Mapping)]

    def set_license_status(
        self,
        license_id: str,
        status: str,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "PATCH",
            f"/v1/admin/licenses/{license_id}/status",
            {"status": status, "operation_nonce": operation_nonce},
        )

    def list_devices(self, license_id: str) -> list[Mapping[str, Any]]:
        response = self._request(
            "GET",
            f"/v1/admin/licenses/{license_id}/devices",
        )
        devices = response.get("devices")
        if not isinstance(devices, list):
            raise AdminApiError("INVALID_RESPONSE", "device list response is invalid")
        return [item for item in devices if isinstance(item, Mapping)]

    def set_device_status(
        self,
        device_id: str,
        status: str,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "PATCH",
            f"/v1/admin/devices/{device_id}/status",
            {"status": status, "operation_nonce": operation_nonce},
        )

    def unbind_device(
        self,
        device_id: str,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            f"/v1/admin/devices/{device_id}/unbind",
            {"operation_nonce": operation_nonce},
        )

    def list_releases(self) -> list[Mapping[str, Any]]:
        response = self._request("GET", "/v1/admin/releases")
        releases = response.get("releases")
        if not isinstance(releases, list):
            raise AdminApiError("INVALID_RESPONSE", "release list response is invalid")
        return [item for item in releases if isinstance(item, Mapping)]

    def register_release(
        self,
        payload: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        return self._request("POST", "/v1/admin/releases", payload)

    def update_release(
        self,
        release_id: str,
        *,
        enabled: bool | None = None,
        paused: bool | None = None,
        rollout_percentage: int | None = None,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"operation_nonce": operation_nonce}
        if enabled is not None:
            payload["enabled"] = enabled
        if paused is not None:
            payload["paused"] = paused
        if rollout_percentage is not None:
            payload["rollout_percentage"] = rollout_percentage
        return self._request(
            "PATCH",
            f"/v1/admin/releases/{release_id}",
            payload,
        )

    def list_diagnostics(self) -> list[Mapping[str, Any]]:
        response = self._request("GET", "/v1/admin/diagnostics")
        diagnostics = response.get("diagnostics")
        if not isinstance(diagnostics, list):
            raise AdminApiError(
                "INVALID_RESPONSE",
                "diagnostic list response is invalid",
            )
        return [item for item in diagnostics if isinstance(item, Mapping)]

    def download_diagnostic(
        self,
        submission_id: str,
        destination: str | Path,
    ) -> Path:
        if self.download_transport is None:
            raise RuntimeError("diagnostic download transport is not configured")
        return self.download_transport(
            f"/v1/admin/diagnostics/{submission_id}/content",
            self._headers,
            destination,
        )

    def delete_diagnostic(self, submission_id: str) -> Mapping[str, Any]:
        return self._request(
            "DELETE",
            f"/v1/admin/diagnostics/{submission_id}",
        )

    def contact_encryption_status(self) -> Mapping[str, Any]:
        return self._request("GET", "/v1/admin/contact-encryption/status")

    def rotate_contact_encryption(
        self,
        *,
        limit: int = 50,
        operation_nonce: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "POST",
            "/v1/admin/contact-encryption/rotate",
            {
                "limit": limit,
                "operation_nonce": operation_nonce,
            },
        )
