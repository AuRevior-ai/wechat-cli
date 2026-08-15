"""Short-lived administrator browser login and loopback callback flow."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import parse_qs, urlencode, urlparse

from .client import AdminApiError, AdminJsonTransport, UrllibAdminJsonTransport
from .config import AdminConfig, AdminConfigStorage


@dataclass(frozen=True)
class AdminLoginMaterial:
    verifier: str
    challenge: str
    state: str


def _urlsafe_token(byte_count: int) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(byte_count)).decode("ascii").rstrip("=")


def generate_login_material() -> AdminLoginMaterial:
    verifier = _urlsafe_token(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest())
        .decode("ascii")
        .rstrip("=")
    )
    return AdminLoginMaterial(
        verifier=verifier,
        challenge=challenge,
        state="state_" + _urlsafe_token(24),
    )


def _validate_api_origin(api_base_url: str) -> str:
    parsed = urlparse(api_base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("administrator login API URL must be an HTTPS origin")
    return api_base_url.rstrip("/")


def build_login_start_url(
    api_base_url: str,
    callback_url: str,
    material: AdminLoginMaterial,
) -> str:
    base = _validate_api_origin(api_base_url)
    callback = urlparse(callback_url)
    if (
        callback.scheme != "http"
        or callback.hostname != "127.0.0.1"
        or not callback.port
        or callback.path != "/callback"
        or callback.params
        or callback.query
        or callback.fragment
    ):
        raise ValueError("administrator login callback must be loopback http /callback")
    return (
        base
        + "/v1/admin/login/start?"
        + urlencode(
            {
                "challenge": material.challenge,
                "redirect_uri": callback_url,
                "state": material.state,
            }
        )
    )


class _CallbackHttpServer(HTTPServer):
    expected_state: str
    callback_code: str | None
    callback_error: str | None


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _CallbackHttpServer

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        parsed = urlparse(self.path)
        parameters = parse_qs(parsed.query, keep_blank_values=True)
        state = parameters.get("state", [""])[0]
        code = parameters.get("code", [""])[0]
        if (
            parsed.path != "/callback"
            or state != self.server.expected_state
            or not code.startswith("wcal_")
        ):
            self.server.callback_error = "administrator login callback validation failed"
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Login callback rejected.".encode("utf-8"))
            return
        self.server.callback_code = code
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write("Administrator login complete. You can close this window.".encode("utf-8"))


class LoopbackCallbackServer:
    def __init__(self, *, expected_state: str) -> None:
        if not isinstance(expected_state, str) or len(expected_state) < 20:
            raise ValueError("administrator login state is invalid")
        server = _CallbackHttpServer(("127.0.0.1", 0), _CallbackHandler)
        server.expected_state = expected_state
        server.callback_code = None
        server.callback_error = None
        server.timeout = 0.25
        self._server = server

    @property
    def callback_url(self) -> str:
        host, port = self._server.server_address[:2]
        if host != "127.0.0.1":
            raise RuntimeError("administrator callback server escaped IPv4 loopback")
        return f"http://127.0.0.1:{port}/callback"

    def wait_for_code(self, *, timeout_seconds: float = 120.0) -> str:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        import time

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            self._server.handle_request()
            if self._server.callback_code is not None:
                return self._server.callback_code
            if self._server.callback_error is not None:
                error = self._server.callback_error
                self._server.callback_error = None
                raise ValueError(error)
        raise TimeoutError("administrator browser login timed out")

    def close(self) -> None:
        self._server.server_close()


class BrowserOpener(Protocol):
    def __call__(self, url: str) -> bool: ...


def _login_response(
    transport: AdminJsonTransport,
    *,
    code: str,
    verifier: str,
) -> Mapping[str, Any]:
    try:
        status, response = transport(
            "POST",
            "/v1/admin/login/exchange",
            {"Accept": "application/json", "Content-Type": "application/json"},
            {"code": code, "verifier": verifier},
        )
    except AdminApiError:
        raise
    except (OSError, TimeoutError) as exc:
        raise AdminApiError(
            "SERVICE_UNAVAILABLE",
            str(exc) or "administrator login API unavailable",
            retryable=True,
        ) from exc
    if not 200 <= status < 300:
        error = response.get("error")
        data = error if isinstance(error, Mapping) else {}
        raise AdminApiError(
            str(data.get("code") or "ADMIN_LOGIN_FAILED"),
            str(data.get("message") or f"administrator login returned HTTP {status}"),
            retryable=data.get("retryable") is True,
            status=status,
        )
    return response


def exchange_and_store_session(
    *,
    api_base_url: str,
    environment: str,
    code: str,
    verifier: str,
    transport: AdminJsonTransport,
    storage: AdminConfigStorage,
) -> Mapping[str, Any]:
    response = _login_response(transport, code=code, verifier=verifier)
    token = response.get("session_token")
    expires_at = response.get("expires_at")
    principal_id = response.get("principal_id")
    if (
        not isinstance(token, str)
        or not token.startswith("wcas_adms_")
        or not isinstance(expires_at, str)
        or not expires_at
        or not isinstance(principal_id, str)
        or not principal_id
    ):
        raise AdminApiError(
            "INVALID_RESPONSE",
            "administrator login response is invalid",
            retryable=False,
        )
    config = AdminConfig(
        api_base_url=api_base_url,
        environment=environment,
        session_token=token,
        session_expires_at=expires_at,
    )
    storage.save(config)
    return response


def login_and_store_admin_session(
    *,
    api_base_url: str,
    environment: str,
    storage: AdminConfigStorage,
    transport: AdminJsonTransport | None = None,
    browser_open: BrowserOpener = webbrowser.open,
    timeout_seconds: float = 120.0,
) -> Mapping[str, Any]:
    if environment not in {"staging", "production"}:
        raise ValueError("browser administrator login is only for staging or production")
    base = _validate_api_origin(api_base_url)
    material = generate_login_material()
    callback = LoopbackCallbackServer(expected_state=material.state)
    try:
        login_url = build_login_start_url(base, callback.callback_url, material)
        if browser_open(login_url) is False:
            raise RuntimeError("default browser could not be opened")
        code = callback.wait_for_code(timeout_seconds=timeout_seconds)
    finally:
        callback.close()
    exchange_transport = transport or UrllibAdminJsonTransport(base)
    return exchange_and_store_session(
        api_base_url=base,
        environment=environment,
        code=code,
        verifier=material.verifier,
        transport=exchange_transport,
        storage=storage,
    )
