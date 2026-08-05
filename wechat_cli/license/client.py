"""License service client and startup authorization fallback rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..update.errors import ErrorCode, UpdateError
from .lease import OfflineLease, TrustedTimeState
from .models import (
    ActivationResult,
    ClientLicenseState,
    DeviceRecord,
    ValidationResult,
)


class LicenseTransport(Protocol):
    def __call__(
        self,
        method: str,
        path: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any] | None,
    ) -> tuple[int, Mapping[str, Any]]: ...


class LicenseRejected(UpdateError):
    """The service explicitly rejected this license or device."""


class LicenseServiceUnavailable(UpdateError):
    """The service could not provide an authoritative license result."""

    def __init__(self, message: str) -> None:
        super().__init__(
            ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE,
            message,
            retryable=True,
        )


class UrllibJsonTransport:
    """Small HTTPS JSON transport with bounded response reads."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10.0,
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
                raise ValueError("license API base URL must use HTTPS")
        if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("license API base URL must contain only scheme and authority")
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
            raise ValueError("license API path must be absolute and local to the base URL")
        body = None
        request_headers = dict(headers)
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request_headers.setdefault("Accept", "application/json")
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
            raise OSError(str(exc)) from exc
        with response:
            raw = response.read(1024 * 1024 + 1)
            status = int(response.status)
        if len(raw) > 1024 * 1024:
            raise OSError("license service response is too large")
        try:
            value = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OSError("license service returned invalid JSON") from exc
        if not isinstance(value, Mapping):
            raise OSError("license service response must be an object")
        return status, value


_EXPLICIT_REJECTION_CODES = {
    ErrorCode.LICENSE_NOT_FOUND,
    ErrorCode.LICENSE_SUSPENDED,
    ErrorCode.LICENSE_REVOKED,
    ErrorCode.DEVICE_LIMIT_REACHED,
    ErrorCode.DEVICE_UNBOUND,
    ErrorCode.DEVICE_DISABLED,
    ErrorCode.INVALID_DEVICE_TOKEN,
    ErrorCode.OFFLINE_LEASE_DENIED,
}


class LicenseApiClient:
    def __init__(self, transport: LicenseTransport) -> None:
        self.transport = transport

    def _request(
        self,
        method: str,
        path: str,
        *,
        device_token: str | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if device_token is not None:
            if not device_token:
                raise ValueError("device token cannot be empty")
            headers["Authorization"] = f"Bearer {device_token}"
        try:
            status, response = self.transport(method, path, headers, payload)
        except (OSError, TimeoutError) as exc:
            raise LicenseServiceUnavailable(str(exc) or "license service unavailable") from exc
        if not isinstance(response, Mapping):
            raise LicenseServiceUnavailable("license service returned a non-object response")
        if 200 <= status < 300:
            return response

        error = response.get("error")
        error_data = error if isinstance(error, Mapping) else {}
        raw_code = error_data.get("code")
        message = error_data.get("message")
        retryable = error_data.get("retryable") is True
        try:
            code = ErrorCode(raw_code) if isinstance(raw_code, str) else ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE
        except ValueError:
            code = ErrorCode.SERVICE_TEMPORARILY_UNAVAILABLE
        text = message if isinstance(message, str) and message else f"license service returned HTTP {status}"
        if code in _EXPLICIT_REJECTION_CODES or (400 <= status < 500 and not retryable):
            raise LicenseRejected(code, text, retryable=False)
        raise LicenseServiceUnavailable(text)

    def activate(
        self,
        *,
        license_key: str,
        device_id: str,
        device_fingerprint: str,
        device_name: str,
        app_version: str,
        launcher_version: str,
    ) -> ActivationResult:
        response = self._request(
            "POST",
            "/v1/licenses/activate",
            payload={
                "license_key": license_key,
                "device_id": device_id,
                "device_fingerprint": device_fingerprint,
                "device_name": device_name,
                "app_version": app_version,
                "launcher_version": launcher_version,
            },
        )
        return ActivationResult.from_mapping(response)

    def validate(
        self,
        *,
        device_token: str,
        app_version: str,
        launcher_version: str,
    ) -> ValidationResult:
        response = self._request(
            "POST",
            "/v1/devices/validate",
            device_token=device_token,
            payload={
                "app_version": app_version,
                "launcher_version": launcher_version,
            },
        )
        return ValidationResult.from_mapping(response)

    def list_devices(self, device_token: str) -> list[DeviceRecord]:
        response = self._request(
            "GET",
            "/v1/devices",
            device_token=device_token,
        )
        devices = response.get("devices")
        if not isinstance(devices, list):
            raise LicenseServiceUnavailable("device list response is invalid")
        try:
            return [DeviceRecord.from_mapping(item) for item in devices]
        except ValueError as exc:
            raise LicenseServiceUnavailable("device list contains invalid records") from exc

    def rename_device(
        self,
        device_token: str,
        *,
        target_device_id: str,
        display_name: str,
        operation_nonce: str,
    ) -> None:
        self._request(
            "PATCH",
            f"/v1/devices/{target_device_id}",
            device_token=device_token,
            payload={
                "display_name": display_name,
                "operation_nonce": operation_nonce,
            },
        )

    def unbind_device(
        self,
        device_token: str,
        *,
        target_device_id: str,
        operation_nonce: str,
    ) -> None:
        self._request(
            "POST",
            f"/v1/devices/{target_device_id}/unbind",
            device_token=device_token,
            payload={
                "target_device_id": target_device_id,
                "operation_nonce": operation_nonce,
            },
        )


@dataclass(frozen=True)
class AuthorizationDecision:
    state: ClientLicenseState
    validation_result: ValidationResult | None = None
    reason: str | None = None

    @property
    def authorized(self) -> bool:
        return self.state in {
            ClientLicenseState.ONLINE_VALID,
            ClientLicenseState.OFFLINE_VALID,
            ClientLicenseState.OFFLINE_EXPIRING,
        }


_REJECTION_STATE = {
    ErrorCode.LICENSE_REVOKED: ClientLicenseState.LICENSE_REVOKED,
    ErrorCode.LICENSE_SUSPENDED: ClientLicenseState.LICENSE_SUSPENDED,
    ErrorCode.DEVICE_UNBOUND: ClientLicenseState.DEVICE_UNBOUND,
    ErrorCode.DEVICE_DISABLED: ClientLicenseState.DEVICE_DISABLED,
    ErrorCode.INVALID_DEVICE_TOKEN: ClientLicenseState.UNACTIVATED,
    ErrorCode.LICENSE_NOT_FOUND: ClientLicenseState.UNACTIVATED,
}


def authorize_startup(
    online_validation: Callable[[], ValidationResult],
    *,
    offline_lease: OfflineLease | None,
    now: datetime,
    trusted_time: TrustedTimeState | None,
) -> AuthorizationDecision:
    """Apply the explicit-rejection-before-offline-fallback rule."""

    try:
        result = online_validation()
    except LicenseRejected as exc:
        return AuthorizationDecision(
            state=_REJECTION_STATE.get(exc.code, ClientLicenseState.UNACTIVATED),
            reason=exc.message,
        )
    except LicenseServiceUnavailable as exc:
        if offline_lease is None:
            return AuthorizationDecision(
                state=ClientLicenseState.OFFLINE_EXPIRED,
                reason=exc.message,
            )
        if trusted_time is not None:
            try:
                trusted_time.assert_not_rolled_back(now)
            except UpdateError as clock_error:
                return AuthorizationDecision(
                    state=ClientLicenseState.OFFLINE_EXPIRED,
                    reason=clock_error.message,
                )
        state = offline_lease.client_state_at(now)
        return AuthorizationDecision(state=state, reason=exc.message)
    return AuthorizationDecision(
        state=ClientLicenseState.ONLINE_VALID,
        validation_result=result,
    )
