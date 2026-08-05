"""Application health payload validation and polling."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.request import Request, urlopen

from ..version import APP_VERSION, BUILD_ID, PRODUCT
from .errors import ErrorCode, UpdateError
from .versioning import SemanticVersion


def build_health_payload(
    *,
    config_loaded: bool,
    license_session_valid: bool,
    core_modules: Mapping[str, str],
    product: str = PRODUCT,
    version: str = APP_VERSION,
    build_id: str = BUILD_ID,
) -> dict[str, Any]:
    if not isinstance(config_loaded, bool) or not isinstance(license_session_valid, bool):
        raise TypeError("health flags must be booleans")
    if not isinstance(core_modules, Mapping) or not core_modules:
        raise ValueError("core_modules must be a non-empty mapping")
    normalized: dict[str, str] = {}
    for name, status in core_modules.items():
        if not isinstance(name, str) or not name:
            raise ValueError("core module names must be non-empty strings")
        if not isinstance(status, str) or not status:
            raise ValueError("core module statuses must be non-empty strings")
        normalized[name] = status
    SemanticVersion.parse(version)
    return {
        "status": "ok",
        "product": product,
        "version": version,
        "build_id": build_id,
        "config_loaded": config_loaded,
        "license_session_valid": license_session_valid,
        "core_modules": normalized,
    }


def _health_failure(message: str) -> UpdateError:
    return UpdateError(ErrorCode.UPDATE_HEALTH_FAILED, message, retryable=True)


def validate_health_payload(
    payload: Mapping[str, Any],
    *,
    expected_product: str,
    expected_version: str,
    expected_build_id: str | None = None,
) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise _health_failure("health response must be an object")
    if payload.get("status") != "ok":
        raise _health_failure(f"application health status is {payload.get('status')!r}")
    if payload.get("product") != expected_product:
        raise _health_failure("application health product does not match the update")
    if payload.get("version") != expected_version:
        raise _health_failure("application health version does not match the update")
    if expected_build_id is not None and payload.get("build_id") != expected_build_id:
        raise _health_failure("application health build ID does not match the update")
    if payload.get("config_loaded") is not True:
        raise _health_failure("application configuration subsystem is not ready")
    if payload.get("license_session_valid") is not True:
        raise _health_failure("application launch license session is not valid")
    modules = payload.get("core_modules")
    if not isinstance(modules, Mapping) or not modules:
        raise _health_failure("application core module health is missing")
    unhealthy = sorted(
        str(name) for name, status in modules.items() if status != "ok"
    )
    if unhealthy:
        raise _health_failure(
            "application core modules are unhealthy: " + ", ".join(unhealthy)
        )
    return payload


def fetch_health_json(url: str, *, timeout_seconds: float = 3.0) -> Mapping[str, Any]:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout_seconds) as response:
        raw = response.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("health response is too large")
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("health response must be an object")
    return value


def wait_for_health(
    fetch: Callable[[], Mapping[str, Any]],
    *,
    expected_product: str,
    expected_version: str,
    expected_build_id: str | None = None,
    timeout_seconds: float,
    interval_seconds: float = 0.5,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> Mapping[str, Any]:
    if timeout_seconds <= 0 or interval_seconds <= 0:
        raise ValueError("health timeout and interval must be positive")
    deadline = monotonic() + timeout_seconds
    last_error: Exception | None = None
    while True:
        try:
            payload = fetch()
            return validate_health_payload(
                payload,
                expected_product=expected_product,
                expected_version=expected_version,
                expected_build_id=expected_build_id,
            )
        except Exception as exc:  # polling intentionally tolerates startup failures
            last_error = exc
        now = monotonic()
        if now >= deadline:
            detail = str(last_error) if last_error is not None else "unknown failure"
            raise _health_failure(f"application health check timed out: {detail}") from last_error
        sleep(min(interval_seconds, max(0.0, deadline - now)))
