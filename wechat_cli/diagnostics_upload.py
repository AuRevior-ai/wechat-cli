"""Explicit opt-in upload of already-redacted diagnostic ZIP bundles."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .license.storage import LicenseStateStorage
from .update.layout import InstallLayout
from .version import APP_VERSION, LAUNCHER_VERSION


class DiagnosticJsonTransport(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


class DiagnosticBinaryTransport(Protocol):
    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
        source: str | Path,
    ) -> tuple[int, Mapping[str, Any]]: ...


@dataclass(frozen=True)
class DiagnosticUploadError(Exception):
    code: str
    message: str
    retryable: bool = False
    request_id: str | None = None
    status: int | None = None

    def __str__(self) -> str:
        request = f" (request_id={self.request_id})" if self.request_id else ""
        return f"{self.code}: {self.message}{request}"


@dataclass(frozen=True)
class DiagnosticUploadResult:
    submission_id: str
    status: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not self.submission_id or self.status != "complete":
            raise ValueError("diagnostic upload result is invalid")
        if self.size_bytes <= 0:
            raise ValueError("diagnostic upload size must be positive")
        if len(self.sha256) != 64:
            raise ValueError("diagnostic upload SHA-256 is invalid")
        int(self.sha256, 16)


class UrllibDiagnosticJsonTransport:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 15.0,
        allow_insecure_loopback: bool = False,
    ) -> None:
        _validate_base_url(base_url, allow_insecure_loopback)
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
        _validate_relative_api_path(path)
        request_headers = dict(headers)
        request_headers.setdefault("Accept", "application/json")
        request_headers.setdefault("User-Agent", f"WeChatCliDiagnostics/{APP_VERSION}")
        body = None
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
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SERVICE_UNAVAILABLE",
                str(exc) or "diagnostic service unavailable",
                retryable=True,
            ) from exc
        with response:
            raw = response.read(1024 * 1024 + 1)
            status = int(response.status)
        if len(raw) > 1024 * 1024:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_RESPONSE_TOO_LARGE",
                "diagnostic service response is too large",
                retryable=True,
                status=status,
            )
        try:
            value = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_INVALID_RESPONSE",
                "diagnostic service returned invalid JSON",
                retryable=True,
                status=status,
            ) from exc
        if not isinstance(value, Mapping):
            raise DiagnosticUploadError(
                "DIAGNOSTIC_INVALID_RESPONSE",
                "diagnostic service response must be an object",
                retryable=True,
                status=status,
            )
        return status, value


class UrllibDiagnosticBinaryTransport:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 120.0,
        allow_insecure_loopback: bool = False,
    ) -> None:
        _validate_base_url(base_url, allow_insecure_loopback)
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def __call__(
        self,
        path: str,
        headers: Mapping[str, str],
        source: str | Path,
    ) -> tuple[int, Mapping[str, Any]]:
        _validate_relative_api_path(path)
        file_path = Path(source)
        if file_path.is_symlink() or not file_path.is_file():
            raise ValueError("diagnostic bundle must be a regular file")
        body = file_path.read_bytes()
        request = Request(
            self.base_url + path,
            data=body,
            headers={
                **headers,
                "Accept": "application/json",
                "Content-Type": "application/zip",
                "Content-Length": str(len(body)),
                "User-Agent": f"WeChatCliDiagnostics/{APP_VERSION}",
            },
            method="PUT",
        )
        try:
            response = urlopen(request, timeout=self.timeout_seconds)
        except HTTPError as exc:
            response = exc
        except (URLError, OSError, TimeoutError) as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SERVICE_UNAVAILABLE",
                str(exc) or "diagnostic upload unavailable",
                retryable=True,
            ) from exc
        with response:
            raw = response.read(1024 * 1024 + 1)
            status = int(response.status)
        if len(raw) > 1024 * 1024:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_RESPONSE_TOO_LARGE",
                "diagnostic upload response is too large",
                retryable=True,
                status=status,
            )
        try:
            value = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_INVALID_RESPONSE",
                "diagnostic upload returned invalid JSON",
                retryable=True,
                status=status,
            ) from exc
        if not isinstance(value, Mapping):
            raise DiagnosticUploadError(
                "DIAGNOSTIC_INVALID_RESPONSE",
                "diagnostic upload response must be an object",
                retryable=True,
                status=status,
            )
        return status, value


def _validate_base_url(base_url: str, allow_insecure_loopback: bool) -> None:
    parsed = urlparse(base_url)
    is_loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https":
        if not (
            allow_insecure_loopback
            and parsed.scheme == "http"
            and is_loopback
        ):
            raise ValueError("diagnostic API base URL must use HTTPS")
    if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("diagnostic API base URL must contain only scheme and authority")


def _validate_relative_api_path(path: str) -> None:
    if (
        not isinstance(path, str)
        or not path.startswith("/v1/")
        or path.startswith("//")
        or "?" in path
        or "#" in path
    ):
        raise ValueError("diagnostic API path must be a relative /v1 path")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _service_error(status: int, response: Mapping[str, Any]) -> DiagnosticUploadError:
    error = response.get("error")
    data = error if isinstance(error, Mapping) else {}
    return DiagnosticUploadError(
        code=str(data.get("code") or "DIAGNOSTIC_UPLOAD_FAILED"),
        message=str(data.get("message") or f"diagnostic service returned HTTP {status}"),
        retryable=data.get("retryable") is True,
        request_id=(
            str(data.get("request_id"))
            if data.get("request_id") is not None
            else None
        ),
        status=status,
    )


class InstalledDiagnosticSubmitter:
    """Upload a generated bundle using the installed device authorization."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        storage: LicenseStateStorage,
        client: "DiagnosticUploadClient",
        launcher_version: str = LAUNCHER_VERSION,
    ) -> None:
        if not isinstance(layout, InstallLayout):
            raise TypeError("layout must be an InstallLayout")
        if not isinstance(launcher_version, str) or not launcher_version:
            raise ValueError("launcher_version is required")
        self.layout = layout
        self.storage = storage
        self.client = client
        self.launcher_version = launcher_version

    def submit(self, bundle_path: str | Path) -> DiagnosticUploadResult:
        state = self.storage.load()
        if state is None:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_LICENSE_STATE_MISSING",
                "local license state is missing; diagnostic upload is unavailable",
                retryable=False,
            )
        try:
            current = self.layout.load_current()
        except Exception as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_VERSION_STATE_INVALID",
                "installed version state cannot be read",
                retryable=False,
            ) from exc
        return self.client.submit(
            bundle_path,
            device_token=state.device_token,
            client_version=current.current_version,
            launcher_version=self.launcher_version,
        )


class DiagnosticUploadClient:
    def __init__(
        self,
        json_transport: DiagnosticJsonTransport,
        upload_transport: DiagnosticBinaryTransport,
    ) -> None:
        self.json_transport = json_transport
        self.upload_transport = upload_transport

    def submit(
        self,
        bundle_path: str | Path,
        *,
        device_token: str,
        client_version: str,
        launcher_version: str,
    ) -> DiagnosticUploadResult:
        bundle = Path(bundle_path)
        if bundle.is_symlink() or not bundle.is_file():
            raise ValueError("diagnostic bundle must be a regular file")
        size = bundle.stat().st_size
        if size <= 0:
            raise ValueError("diagnostic bundle cannot be empty")
        digest = _sha256_file(bundle)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {device_token}",
        }
        try:
            status, session = self.json_transport(
                "POST",
                "/v1/diagnostics/sessions",
                headers,
                {
                    "client_version": client_version,
                    "launcher_version": launcher_version,
                    "size_bytes": size,
                    "sha256": digest,
                    "consent_version": "diagnostics-consent-v1",
                },
            )
        except DiagnosticUploadError:
            raise
        except (OSError, TimeoutError) as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SERVICE_UNAVAILABLE",
                str(exc) or "diagnostic service unavailable",
                retryable=True,
            ) from exc
        if not 200 <= status < 300:
            raise _service_error(status, session)
        submission_id = session.get("submission_id")
        upload_url = session.get("upload_url")
        upload_token = session.get("upload_token")
        maximum_bytes = session.get("maximum_bytes")
        upload_expires_at = session.get("upload_expires_at")
        retention_expires_at = session.get("retention_expires_at")
        retention_days = session.get("retention_days")
        consent_version = session.get("consent_version")
        if (
            not isinstance(submission_id, str)
            or not submission_id
            or not isinstance(upload_url, str)
            or not isinstance(upload_token, str)
            or not upload_token
            or isinstance(maximum_bytes, bool)
            or not isinstance(maximum_bytes, int)
            or maximum_bytes <= 0
            or not isinstance(upload_expires_at, str)
            or not upload_expires_at
            or not isinstance(retention_expires_at, str)
            or not retention_expires_at
            or retention_days != 7
            or consent_version != "diagnostics-consent-v1"
        ):
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SESSION_INVALID",
                "diagnostic service returned an invalid upload session",
                status=status,
            )
        try:
            _validate_relative_api_path(upload_url)
        except ValueError as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SESSION_INVALID",
                "diagnostic upload URL is not a trusted relative path",
                status=status,
            ) from exc
        expected_path = f"/v1/diagnostics/{submission_id}/content"
        if upload_url != expected_path:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SESSION_INVALID",
                "diagnostic upload URL does not match its submission",
                status=status,
            )
        if size > maximum_bytes:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_TOO_LARGE",
                "diagnostic bundle exceeds the server limit",
                status=413,
            )
        try:
            upload_status, response = self.upload_transport(
                upload_url,
                {
                    "Authorization": f"Diagnostic {upload_token}",
                    "Content-Type": "application/zip",
                },
                bundle,
            )
        except DiagnosticUploadError:
            raise
        except (OSError, TimeoutError) as exc:
            raise DiagnosticUploadError(
                "DIAGNOSTIC_SERVICE_UNAVAILABLE",
                str(exc) or "diagnostic upload unavailable",
                retryable=True,
            ) from exc
        if not 200 <= upload_status < 300:
            raise _service_error(upload_status, response)
        response_submission = response.get("submission_id")
        response_status = response.get("status")
        response_size = response.get("size_bytes")
        response_digest = response.get("sha256")
        if (
            response_submission != submission_id
            or response_status != "complete"
            or response_size != size
            or response_digest != digest
        ):
            raise DiagnosticUploadError(
                "DIAGNOSTIC_UPLOAD_INVALID_RESPONSE",
                "diagnostic upload completion response does not match the bundle",
                status=upload_status,
            )
        return DiagnosticUploadResult(
            submission_id=submission_id,
            status="complete",
            size_bytes=size,
            sha256=digest,
        )
