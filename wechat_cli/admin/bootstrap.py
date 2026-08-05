"""Generate disposable Demo Worker secrets and the first administrator token."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from Crypto.PublicKey import ECC


def _urlsafe_token(size: int) -> str:
    if size < 16:
        raise ValueError("token size must be at least 16 bytes")
    return base64.urlsafe_b64encode(secrets.token_bytes(size)).decode("ascii").rstrip("=")


def _sql_text(value: str) -> str:
    return value.replace("'", "''")


@dataclass(frozen=True)
class DemoBootstrapArtifacts:
    worker_secrets: Mapping[str, str] = field(repr=False)
    admin_token: str = field(repr=False)
    admin_token_digest: str
    admin_sql: str = field(repr=False)
    admin_scopes: tuple[str, ...]
    lease_signing_key_id: str
    lease_public_key_base64: str
    release_signing_key_id: str
    release_private_key_pem: str = field(repr=False)
    release_public_key_base64: str


def generate_demo_bootstrap(
    *,
    lease_signing_key_id: str = "lease-key-demo-01",
    release_signing_key_id: str = "release-key-demo-01",
    admin_display_name: str = "Demo Administrator",
    admin_scopes: tuple[str, ...] = ("*",),
) -> DemoBootstrapArtifacts:
    """Generate independent high-entropy Demo values without writing them."""

    if (
        not isinstance(lease_signing_key_id, str)
        or not lease_signing_key_id.strip()
        or len(lease_signing_key_id) > 128
    ):
        raise ValueError("lease_signing_key_id is invalid")
    if (
        not isinstance(release_signing_key_id, str)
        or not release_signing_key_id.strip()
        or len(release_signing_key_id) > 128
    ):
        raise ValueError("release_signing_key_id is invalid")
    if (
        not isinstance(admin_display_name, str)
        or not admin_display_name.strip()
        or len(admin_display_name) > 256
    ):
        raise ValueError("admin_display_name is invalid")
    if not admin_scopes or not all(
        isinstance(scope, str) and scope.strip() and len(scope) <= 128
        for scope in admin_scopes
    ):
        raise ValueError("admin_scopes are invalid")

    lease_key = ECC.generate(curve="Ed25519")
    private_pkcs8 = lease_key.export_key(format="DER", use_pkcs8=True)
    public_raw = lease_key.public_key().export_key(format="raw")
    release_key = ECC.generate(curve="Ed25519")
    release_private_key_pem = release_key.export_key(format="PEM")
    release_public_raw = release_key.public_key().export_key(format="raw")
    worker_secrets = {
        "LICENSE_KEY_PEPPER": _urlsafe_token(32),
        "DEVICE_TOKEN_PEPPER": _urlsafe_token(32),
        "ADMIN_TOKEN_PEPPER": _urlsafe_token(32),
        "CONTACT_LOOKUP_PEPPER": _urlsafe_token(32),
        "CONTACT_ENCRYPTION_KEY_V1": base64.b64encode(
            secrets.token_bytes(32)
        ).decode("ascii"),
        "LEASE_SIGNING_PRIVATE_KEY": base64.b64encode(private_pkcs8).decode(
            "ascii"
        ),
        "DOWNLOAD_TICKET_SECRET": _urlsafe_token(32),
    }

    token_id = "adm_" + _urlsafe_token(16)
    token_secret = _urlsafe_token(32)
    admin_token = f"wcadmin_{token_id}.{token_secret}"
    token_digest = hmac.new(
        worker_secrets["ADMIN_TOKEN_PEPPER"].encode("utf-8"),
        token_secret.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    admin_id = "admin_" + _urlsafe_token(16)
    scopes_json = json.dumps(
        list(admin_scopes),
        ensure_ascii=False,
        separators=(",", ":"),
    )
    admin_sql = (
        "INSERT INTO admin_tokens (\n"
        "  id, token_id, token_digest, display_name, scopes_json,\n"
        "  status, created_at\n"
        ") VALUES (\n"
        f"  '{_sql_text(admin_id)}',\n"
        f"  '{_sql_text(token_id)}',\n"
        f"  '{token_digest}',\n"
        f"  '{_sql_text(admin_display_name.strip())}',\n"
        f"  '{_sql_text(scopes_json)}',\n"
        "  'active',\n"
        "  strftime('%Y-%m-%dT%H:%M:%fZ', 'now')\n"
        ");\n"
    )
    return DemoBootstrapArtifacts(
        worker_secrets=worker_secrets,
        admin_token=admin_token,
        admin_token_digest=token_digest,
        admin_sql=admin_sql,
        admin_scopes=tuple(admin_scopes),
        lease_signing_key_id=lease_signing_key_id,
        lease_public_key_base64=base64.b64encode(public_raw).decode("ascii"),
        release_signing_key_id=release_signing_key_id,
        release_private_key_pem=release_private_key_pem,
        release_public_key_base64=base64.b64encode(release_public_raw).decode(
            "ascii"
        ),
    )


def _write_new(path: Path, content: bytes, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        mode,
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def write_demo_bootstrap(
    output_dir: str | Path,
    artifacts: DemoBootstrapArtifacts,
) -> dict[str, Path]:
    """Write all bootstrap artifacts once; never overwrite or partially replace."""

    if not isinstance(artifacts, DemoBootstrapArtifacts):
        raise TypeError("artifacts must be DemoBootstrapArtifacts")
    root = Path(output_dir)
    paths = {
        "worker_secrets": root / ".dev.vars",
        "admin_sql": root / "bootstrap-admin.sql",
        "admin_token": root / "admin-token.txt",
        "public_keys": root / "launcher-public-keys.json",
        "release_private_key": root / "release-signing-key.pem",
        "launcher_config_template": root / "launcher-config.template.json",
        "instructions": root / "README.txt",
    }
    existing = [path for path in paths.values() if path.exists()]
    if existing:
        raise FileExistsError(existing[0])
    root.mkdir(parents=True, exist_ok=True)

    worker_lines = [
        "# Generated Demo values. Do not commit or reuse in production.",
        *(f"{name}={value}" for name, value in artifacts.worker_secrets.items()),
        "GITHUB_RELEASE_READ_TOKEN=REPLACE_WITH_PRIVATE_GITHUB_RELEASE_READ_TOKEN",
        "",
    ]
    public_keys = {
        "release_public_keys": {
            artifacts.release_signing_key_id: artifacts.release_public_key_base64
        },
        "lease_public_keys": {
            artifacts.lease_signing_key_id: artifacts.lease_public_key_base64
        },
    }
    launcher_config_template = {
        "schema_version": 1,
        "api_base_url": "https://REPLACE_WITH_WORKER_HOSTNAME",
        "port": 8787,
        "channel": "stable",
        "fingerprint_salt": _urlsafe_token(32),
        **public_keys,
    }
    instructions = (
        "WeChat CLI Demo bootstrap artifacts\n"
        "===================================\n\n"
        "1. Keep .dev.vars and admin-token.txt outside source control.\n"
        "2. Apply D1 migrations, then execute bootstrap-admin.sql once.\n"
        "3. Import admin-token.txt with `wechat-cli-admin config set`.\n"
        "4. Copy launcher-config.template.json, replace the API hostname, and use it for packaging.\n"
        "5. Keep release-signing-key.pem outside source control and configure it with wechat-cli-release.\n"
        "6. Replace the GitHub token placeholder before running Wrangler.\n"
        "7. Delete admin-token.txt after it is protected by Windows DPAPI.\n"
        "8. Generate completely new values for production.\n"
    )

    created: list[Path] = []
    try:
        contents = {
            paths["worker_secrets"]: "\n".join(worker_lines).encode("utf-8"),
            paths["admin_sql"]: artifacts.admin_sql.encode("utf-8"),
            paths["admin_token"]: (artifacts.admin_token + "\n").encode("utf-8"),
            paths["public_keys"]: (
                json.dumps(
                    public_keys,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
            paths["release_private_key"]: artifacts.release_private_key_pem.encode(
                "ascii"
            ),
            paths["launcher_config_template"]: (
                json.dumps(
                    launcher_config_template,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                )
                + "\n"
            ).encode("utf-8"),
            paths["instructions"]: instructions.encode("utf-8"),
        }
        for path, content in contents.items():
            _write_new(
                path,
                content,
                mode=(
                    0o644
                    if path
                    in {
                        paths["instructions"],
                        paths["public_keys"],
                        paths["launcher_config_template"],
                    }
                    else 0o600
                ),
            )
            created.append(path)
    except Exception:
        for path in reversed(created):
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise
    return paths
