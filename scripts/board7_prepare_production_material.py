#!/usr/bin/env python3
"""Prepare Board 7 production key/Secret material outside source control.

This helper intentionally performs no Cloudflare, GitHub, D1, or Worker write.
It generates only the exact B7-G4 local credential material and safe public
metadata needed by later gates. Sensitive values are never printed.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import json
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from Crypto.PublicKey import ECC

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.packaging_paths import assert_outside_repository

LEASE_KEY_ID = "lease-key-production-01"
RELEASE_KEY_ID = "release-key-production-01"
API_ORIGIN = "https://wechat-cli-api.aurevior-devspace.com"
HUMAN_PRINCIPAL_ID = "production-primary-admin"
AUTOMATION_PRINCIPAL_ID = "release-automation-production"

WORKER_SECRET_NAMES = (
    "ADMIN_SESSION_PEPPER_V1",
    "CONTACT_ENCRYPTION_KEY_V1",
    "CONTACT_LOOKUP_PEPPER_V1",
    "DEVICE_TOKEN_PEPPER_V1",
    "DIAGNOSTIC_UPLOAD_SECRET_V1",
    "DOWNLOAD_TICKET_SECRET_V1",
    "LEASE_SIGNING_PRIVATE_KEY",
    "LICENSE_KEY_PEPPER_V1",
    "RATE_LIMIT_PEPPER_V1",
)

HUMAN_SCOPES = (
    "licenses:read",
    "licenses:write",
    "devices:read",
    "devices:write",
    "releases:upload",
    "releases:read",
    "releases:register",
    "releases:state",
    "diagnostics:read",
    "diagnostics:delete",
    "contacts:rotate",
)


def _urlsafe_token(size: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(size)).decode("ascii").rstrip("=")


def _sql_text(value: str) -> str:
    return value.replace("'", "''")


def _normalize_email(value: str) -> str:
    text = str(value or "").strip().lower()
    if (
        not text
        or text.count("@") != 1
        or any(ch.isspace() for ch in text)
        or text.startswith("@")
        or text.endswith("@")
        or "." not in text.split("@", 1)[1]
    ):
        raise ValueError("human identity must be one valid email address")
    return text


@dataclass(frozen=True)
class ProductionMaterial:
    worker_secrets: Mapping[str, str] = field(repr=False)
    human_identity: str = field(repr=False)
    human_scopes: tuple[str, ...]
    human_principal_sql: str = field(repr=False)
    lease_public_key_base64: str
    release_private_key_pem: str = field(repr=False)
    release_public_key_base64: str
    trust_profile: Mapping[str, Any] = field(repr=False)

    def safe_metadata(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "worker_secret_names": sorted(self.worker_secrets),
            "lease_signing_key_id": LEASE_KEY_ID,
            "lease_public_key_base64": self.lease_public_key_base64,
            "release_signing_key_id": RELEASE_KEY_ID,
            "release_public_key_base64": self.release_public_key_base64,
            "human_principal_id": HUMAN_PRINCIPAL_ID,
            "human_scopes": list(self.human_scopes),
            "automation_principal_id": AUTOMATION_PRINCIPAL_ID,
            "automation_identity_state": "pending_exact_g4_service_token_client_id",
            "distribution_profile": "private_controlled",
            "environment": "production",
            "api_origin": API_ORIGIN,
        }


def generate_material(*, human_identity: str) -> ProductionMaterial:
    identity = _normalize_email(human_identity)

    lease_key = ECC.generate(curve="Ed25519")
    lease_private_pkcs8 = lease_key.export_key(format="DER", use_pkcs8=True)
    lease_public_raw = lease_key.public_key().export_key(format="raw")

    release_key = ECC.generate(curve="Ed25519")
    release_private_pem = release_key.export_key(format="PEM")
    release_public_raw = release_key.public_key().export_key(format="raw")

    worker_secrets = {
        "ADMIN_SESSION_PEPPER_V1": _urlsafe_token(),
        "CONTACT_ENCRYPTION_KEY_V1": base64.b64encode(secrets.token_bytes(32)).decode("ascii"),
        "CONTACT_LOOKUP_PEPPER_V1": _urlsafe_token(),
        "DEVICE_TOKEN_PEPPER_V1": _urlsafe_token(),
        "DIAGNOSTIC_UPLOAD_SECRET_V1": _urlsafe_token(),
        "DOWNLOAD_TICKET_SECRET_V1": _urlsafe_token(),
        "LEASE_SIGNING_PRIVATE_KEY": base64.b64encode(lease_private_pkcs8).decode("ascii"),
        "LICENSE_KEY_PEPPER_V1": _urlsafe_token(),
        "RATE_LIMIT_PEPPER_V1": _urlsafe_token(),
    }
    if tuple(sorted(worker_secrets)) != tuple(sorted(WORKER_SECRET_NAMES)):
        raise AssertionError("production Worker Secret inventory drifted")

    lease_public_b64 = base64.b64encode(lease_public_raw).decode("ascii")
    release_public_b64 = base64.b64encode(release_public_raw).decode("ascii")
    fingerprint_salt = _urlsafe_token()
    trust_profile = {
        "schema_version": 2,
        "distribution_profile": "private_controlled",
        "environment": "production",
        "api_base_url": API_ORIGIN,
        "expected_channel": "stable",
        "fingerprint_salt": fingerprint_salt,
        "release_public_keys": {RELEASE_KEY_ID: release_public_b64},
        "lease_public_keys": {LEASE_KEY_ID: lease_public_b64},
        "windows_publisher_policy": "",
    }

    scopes_json = json.dumps(list(HUMAN_SCOPES), separators=(",", ":"))
    human_sql = (
        "INSERT INTO admin_principals (\n"
        "  id, identity, display_name, scopes_json, status, created_at, revoked_at\n"
        ") VALUES (\n"
        f"  '{HUMAN_PRINCIPAL_ID}',\n"
        f"  '{_sql_text(identity)}',\n"
        "  'Production Primary Administrator',\n"
        f"  '{_sql_text(scopes_json)}',\n"
        "  'active',\n"
        "  strftime('%Y-%m-%dT%H:%M:%fZ', 'now'),\n"
        "  NULL\n"
        ");\n"
    )

    return ProductionMaterial(
        worker_secrets=worker_secrets,
        human_identity=identity,
        human_scopes=HUMAN_SCOPES,
        human_principal_sql=human_sql,
        lease_public_key_base64=lease_public_b64,
        release_private_key_pem=release_private_pem,
        release_public_key_base64=release_public_b64,
        trust_profile=trust_profile,
    )


def restrict_windows_acl(
    root: Path,
    *,
    current_identity: str,
    runner=subprocess.run,
) -> None:
    identity = str(current_identity or "").strip()
    if not identity:
        raise ValueError("current Windows identity is required")
    command = [
        "icacls",
        str(root),
        "/inheritance:r",
        "/grant:r",
        f"{identity}:(OI)(CI)F",
        "*S-1-5-18:(OI)(CI)F",
        "*S-1-5-32-544:(OI)(CI)F",
        "/T",
        "/C",
    ]
    runner(command, check=True, capture_output=True, text=True)


def _windows_identity() -> str:
    result = subprocess.run(
        ["whoami"],
        check=True,
        capture_output=True,
        text=True,
    )
    identity = result.stdout.strip()
    if not identity:
        raise RuntimeError("could not resolve current Windows identity")
    return identity


def _write_new(path: Path, data: bytes, *, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def write_material(
    output_dir: str | Path,
    artifacts: ProductionMaterial,
    *,
    apply_acl: bool = True,
) -> dict[str, Path]:
    if not isinstance(artifacts, ProductionMaterial):
        raise TypeError("artifacts must be ProductionMaterial")
    root = assert_outside_repository(Path(output_dir), repository_root=ROOT)
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True, exist_ok=False)
    if os.name != "nt":
        os.chmod(root, 0o700)
    elif apply_acl:
        restrict_windows_acl(root, current_identity=_windows_identity())

    paths = {
        "worker_secrets": root / "worker-secrets.production.json",
        "release_private_key": root / "release-key-production-01.pem",
        "public_keys": root / "production-public-keys.json",
        "trust_profile": root / "production-trust-profile.json",
        "human_principal_sql": root / "production-human-principal.sql",
        "safe_metadata": root / "production-safe-metadata.json",
        "instructions": root / "README.txt",
    }
    public_keys = {
        "release_public_keys": {RELEASE_KEY_ID: artifacts.release_public_key_base64},
        "lease_public_keys": {LEASE_KEY_ID: artifacts.lease_public_key_base64},
    }
    instructions = (
        "Board 7 production material\n"
        "===========================\n\n"
        "- Never commit this directory or copy private values into chat/logs.\n"
        "- worker-secrets.production.json is reserved for the B7-G5 atomic production deploy.\n"
        "- release-key-production-01.pem belongs only to the approved publisher/signing domain.\n"
        "- production-trust-profile.json is the repo-external real private_controlled trust profile.\n"
        "- production-human-principal.sql contains only the approved human identity/scopes and no credential.\n"
        "- The automation principal is finalized only after the exact B7-G4 Access Service Token client ID exists.\n"
    )
    contents: dict[Path, tuple[bytes, int]] = {
        paths["worker_secrets"]: (
            (json.dumps(dict(artifacts.worker_secrets), sort_keys=True, indent=2) + "\n").encode("utf-8"),
            0o600,
        ),
        paths["release_private_key"]: (
            artifacts.release_private_key_pem.encode("ascii"),
            0o600,
        ),
        paths["public_keys"]: (
            (json.dumps(public_keys, sort_keys=True, indent=2) + "\n").encode("utf-8"),
            0o644,
        ),
        paths["trust_profile"]: (
            (json.dumps(dict(artifacts.trust_profile), sort_keys=True, indent=2) + "\n").encode("utf-8"),
            0o600,
        ),
        paths["human_principal_sql"]: (artifacts.human_principal_sql.encode("utf-8"), 0o600),
        paths["safe_metadata"]: (
            (json.dumps(artifacts.safe_metadata(), sort_keys=True, indent=2) + "\n").encode("utf-8"),
            0o644,
        ),
        paths["instructions"]: (instructions.encode("utf-8"), 0o644),
    }
    for path, (data, mode) in contents.items():
        _write_new(path, data, mode=mode)
    return paths


def _safe_cli_result(paths: Mapping[str, Path], artifacts: ProductionMaterial) -> dict[str, object]:
    return {
        **artifacts.safe_metadata(),
        "output_dir": str(next(iter(paths.values())).parent),
        "files": sorted(path.name for path in paths.values()),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate fresh Board 7 production credential material outside the repository."
    )
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    human_identity = input("Accepted production human Access email: ").strip()
    artifacts = generate_material(human_identity=human_identity)
    paths = write_material(args.output_dir, artifacts)
    print(json.dumps(_safe_cli_result(paths, artifacts), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
