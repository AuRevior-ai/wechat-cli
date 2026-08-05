#!/usr/bin/env python3
"""Build and exercise a disposable local Worker/D1/R2 environment.

All credentials are generated in memory for one run. Worker dependencies,
Wrangler state, and the .dev.vars file live in a temporary directory outside
the repository and are removed when the run finishes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import urlopen

from Crypto.PublicKey import ECC

from local_e2e import run as run_api_checks


SERVICE_ROOT = Path(__file__).resolve().parents[1]
COPY_FILES = ("package.json", "tsconfig.json", "wrangler.jsonc")
COPY_DIRECTORIES = ("migrations", "src", "test", "scripts")


def _require_executable(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        raise RuntimeError(f"required executable is unavailable: {name}")
    return path


def _run(command: list[str], *, cwd: Path, quiet: bool = True) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.DEVNULL if quiet else None,
        stderr=subprocess.STDOUT if quiet else None,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed with exit code {completed.returncode}: {command[0]}")


def _copy_worker_source(destination: Path) -> None:
    for name in COPY_FILES:
        shutil.copy2(SERVICE_ROOT / name, destination / name)
    for name in COPY_DIRECTORIES:
        shutil.copytree(SERVICE_ROOT / name, destination / name)


def _random_secret() -> str:
    return secrets.token_urlsafe(32)


def _lease_private_key_base64() -> str:
    key = ECC.generate(curve="Ed25519")
    raw = key.export_key(format="DER", use_pkcs8=True)
    if not isinstance(raw, bytes):
        raise RuntimeError("Ed25519 private key export did not return bytes")
    return base64.b64encode(raw).decode("ascii")


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_dev_vars(path: Path, values: dict[str, str]) -> None:
    for name, value in values.items():
        if not name.replace("_", "").isalnum() or "\n" in value or "\r" in value:
            raise RuntimeError("unsafe disposable Worker variable")
    path.write_text(
        "".join(f"{name}={value}\n" for name, value in values.items()),
        encoding="utf-8",
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _stop_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _redacted_log_tail(path: Path, secrets_to_redact: Iterable[str]) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "<worker log unavailable>"
    for value in secrets_to_redact:
        if value:
            text = text.replace(value, "[REDACTED]")
    return "\n".join(text.splitlines()[-80:])


def _wait_for_health(
    base_url: str,
    process: subprocess.Popen[bytes],
    *,
    timeout_seconds: float,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Wrangler exited before health check: {process.returncode}")
        try:
            with urlopen(base_url + "/v1/health", timeout=3) as response:
                if int(response.status) == 200:
                    return
        except (OSError, URLError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"local Worker did not become healthy: {last_error}")


def main() -> None:
    npm = _require_executable("npm")
    node = _require_executable("node")

    with tempfile.TemporaryDirectory(prefix="wechat-cli-worker-e2e-") as raw_temp:
        root = Path(raw_temp)
        _copy_worker_source(root)
        _run(
            [npm, "install", "--no-audit", "--no-fund", "--ignore-scripts"],
            cwd=root,
        )
        _run([npm, "run", "typecheck"], cwd=root)
        _run([npm, "test"], cwd=root)
        wrangler = root / "node_modules" / "wrangler" / "bin" / "wrangler.js"
        if not wrangler.is_file():
            raise RuntimeError("Wrangler was not installed in the disposable environment")

        token_id = "adm_" + secrets.token_urlsafe(18)
        token_secret = secrets.token_urlsafe(32)
        admin_token = f"wcadmin_{token_id}.{token_secret}"
        admin_pepper = _random_secret()
        variables = {
            "LICENSE_KEY_PEPPER": _random_secret(),
            "DEVICE_TOKEN_PEPPER": _random_secret(),
            "ADMIN_TOKEN_PEPPER": admin_pepper,
            "CONTACT_LOOKUP_PEPPER": _random_secret(),
            "CONTACT_ENCRYPTION_KEY_V1": base64.b64encode(os.urandom(32)).decode("ascii"),
            "LEASE_SIGNING_PRIVATE_KEY": _lease_private_key_base64(),
            "DOWNLOAD_TICKET_SECRET": _random_secret(),
            "GITHUB_RELEASE_READ_TOKEN": "local-e2e-placeholder",
        }
        _write_dev_vars(root / ".dev.vars", variables)

        state = root / "state"
        state.mkdir()
        wrangler_command = [node, str(wrangler)]
        _run(
            wrangler_command
            + [
                "deploy",
                "--dry-run",
                '--env=',
                "--outdir",
                str(root / "worker-dist"),
            ],
            cwd=root,
        )
        _run(
            wrangler_command
            + [
                "d1",
                "migrations",
                "apply",
                "DB",
                "--local",
                "--persist-to",
                str(state),
                '--env=',
            ],
            cwd=root,
        )

        token_digest = hmac.new(
            admin_pepper.encode("utf-8"),
            token_secret.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        sql = (
            "INSERT INTO admin_tokens "
            "(id, token_id, token_digest, display_name, scopes_json, status, created_at) "
            "VALUES "
            f"('admin_local_e2e', '{token_id}', '{token_digest}', "
            f"'Local E2E', '[\"*\"]', 'active', '{created_at}');"
        )
        _run(
            wrangler_command
            + [
                "d1",
                "execute",
                "DB",
                "--local",
                "--persist-to",
                str(state),
                '--env=',
                "--command",
                sql,
            ],
            cwd=root,
        )

        port = _free_loopback_port()
        base_url = f"http://127.0.0.1:{port}"
        log_path = root / "worker.log"
        with log_path.open("wb") as log:
            process = subprocess.Popen(
                wrangler_command
                + [
                    "dev",
                    "--local",
                    "--ip",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--persist-to",
                    str(state),
                    '--env=',
                ],
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
                ),
            )
            try:
                _wait_for_health(base_url, process, timeout_seconds=90)
                result = run_api_checks(base_url, admin_token)
            except Exception as exc:
                tail = _redacted_log_tail(
                    log_path,
                    [admin_token, token_secret, *variables.values()],
                )
                raise RuntimeError(f"local Worker E2E failed: {exc}\n{tail}") from exc
            finally:
                _stop_process_tree(process)

        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        for secret_value in (admin_token, token_secret, *variables.values()):
            if secret_value and secret_value in log_text:
                raise RuntimeError("Wrangler log exposed disposable credential material")
        result["worker_log_secret_scan"] = "passed"
        print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
