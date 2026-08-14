#!/usr/bin/env python3
"""Manual browser bridge for the Board 6 G5 staging Access login acceptance."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.packaging_paths import assert_outside_repository
except ModuleNotFoundError:  # Direct execution fallback.
    from packaging_paths import assert_outside_repository

from wechat_cli.admin.client import UrllibAdminJsonTransport
from wechat_cli.admin.config import AdminConfigStorage
from wechat_cli.admin.session import (
    AdminLoginMaterial,
    LoopbackCallbackServer,
    build_login_start_url,
    exchange_and_store_session,
    generate_login_material,
)
from wechat_cli.windows.dpapi import WindowsDpapiProtector


def _storage(path: Path) -> AdminConfigStorage:
    return AdminConfigStorage(path, WindowsDpapiProtector())


def _write_new(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", closefd=True) as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def run_manual_login(
    *,
    api_base_url: str,
    config_path: str | Path,
    url_file: str | Path,
    result_file: str | Path,
    timeout_seconds: float = 600.0,
    callback_factory: Callable[..., object] = LoopbackCallbackServer,
    transport_factory: Callable[[str], object] = UrllibAdminJsonTransport,
    storage_factory: Callable[[Path], object] = _storage,
    exchange: Callable[..., object] = exchange_and_store_session,
) -> dict[str, object]:
    if timeout_seconds <= 0 or timeout_seconds > 1800:
        raise ValueError("manual Access login timeout must be between 1 and 1800 seconds")

    config = assert_outside_repository(Path(config_path), repository_root=ROOT)
    url_path = assert_outside_repository(Path(url_file), repository_root=ROOT)
    result_path = assert_outside_repository(Path(result_file), repository_root=ROOT)
    if url_path.exists() or result_path.exists():
        raise FileExistsError("manual Access login bridge output already exists")

    material = generate_login_material()
    callback = callback_factory(expected_state=material.state)
    try:
        login_url = build_login_start_url(api_base_url, callback.callback_url, material)
        _write_new(url_path, login_url)
        code = callback.wait_for_code(timeout_seconds=timeout_seconds)
        response = exchange(
            api_base_url=api_base_url.rstrip("/"),
            environment="staging",
            code=code,
            verifier=material.verifier,
            transport=transport_factory(api_base_url.rstrip("/")),
            storage=storage_factory(config),
        )
    finally:
        callback.close()

    if not isinstance(response, dict):
        response = dict(response)
    principal_id = response.get("principal_id")
    expires_at = response.get("expires_at")
    if not isinstance(principal_id, str) or not principal_id:
        raise ValueError("administrator login result is missing principal_id")
    if not isinstance(expires_at, str) or not expires_at:
        raise ValueError("administrator login result is missing expires_at")

    safe: dict[str, object] = {
        "ok": True,
        "principal_id": principal_id,
        "expires_at": expires_at,
    }
    _write_new(result_path, json.dumps(safe, sort_keys=True))
    try:
        url_path.unlink()
    except FileNotFoundError:
        pass
    return safe


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Wait for one manual Board 6 G5 Access login callback.")
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--config-path", type=Path, required=True)
    parser.add_argument("--url-file", type=Path, required=True)
    parser.add_argument("--result-file", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result_path = Path(args.result_file)
    try:
        run_manual_login(
            api_base_url=args.api_url,
            config_path=args.config_path,
            url_file=args.url_file,
            result_file=result_path,
            timeout_seconds=args.timeout_seconds,
        )
    except Exception as exc:
        try:
            if not result_path.exists():
                safe_error = {"ok": False, "error": type(exc).__name__}
                _write_new(result_path, json.dumps(safe_error, sort_keys=True))
        except OSError:
            pass
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
