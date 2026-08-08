#!/usr/bin/env python3
"""Minimal real-staging signed-lease acceptance.

When explicitly confirmed, this script performs exactly two license-service
mutations against an already-active staging device: one repeat activation to
obtain a fresh device token, followed by one online validation. Permanent
license keys, device tokens, raw lease bytes, signatures, and lease nonces are
never printed or persisted.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

if __package__:
    from .staging_license_acceptance import (
        AcceptanceError,
        _read_license_key,
        _read_metadata,
        build_device_specs,
    )
else:
    from staging_license_acceptance import (
        AcceptanceError,
        _read_license_key,
        _read_metadata,
        build_device_specs,
    )
from wechat_cli.license.client import (
    LicenseApiClient,
    LicenseRejected,
    LicenseServiceUnavailable,
    UrllibJsonTransport,
)
from wechat_cli.license.lease import TrustedTimeState, verify_signed_lease
from wechat_cli.license.models import ActivationResult, ClientLicenseState, ValidationResult
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.version import APP_VERSION, LAUNCHER_VERSION


class LeaseAcceptanceClient(Protocol):
    def activate(
        self,
        *,
        license_key: str,
        device_id: str,
        device_fingerprint: str,
        device_name: str,
        app_version: str,
        launcher_version: str,
    ) -> ActivationResult: ...

    def validate(
        self,
        *,
        device_token: str,
        app_version: str,
        launcher_version: str,
    ) -> ValidationResult: ...


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AcceptanceError("staging service returned an invalid timestamp") from exc
    if parsed.tzinfo is None:
        raise AcceptanceError("staging service timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _safe_id(value: str) -> str:
    if len(value) <= 16:
        return value
    return f"{value[:10]}…{value[-4:]}"


def load_lease_public_keys(path: Path) -> TrustedEd25519Keys:
    if path.is_symlink() or not path.is_file():
        raise AcceptanceError("public-key file must be a regular file")
    if path.stat().st_size > 64 * 1024:
        raise AcceptanceError("public-key file is unexpectedly large")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError("public-key file is invalid") from exc
    if not isinstance(payload, dict):
        raise AcceptanceError("public-key file root must be an object")
    keys = payload.get("lease_public_keys")
    if not isinstance(keys, dict) or not keys:
        raise AcceptanceError("public-key file does not contain lease_public_keys")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in keys.items()):
        raise AcceptanceError("lease_public_keys must map string key IDs to base64 keys")
    try:
        return TrustedEd25519Keys.from_base64(keys)
    except ValueError as exc:
        raise AcceptanceError("lease public-key registry is invalid") from exc


def run_lease_acceptance(
    client: LeaseAcceptanceClient,
    *,
    trusted_keys: TrustedEd25519Keys,
    license_key: str,
    expected_license_id: str,
    run_id: str,
    expected_key_id: str,
    app_version: str,
    launcher_version: str,
) -> dict[str, object]:
    spec = build_device_specs(expected_license_id, run_id)[0]

    activation = client.activate(
        license_key=license_key,
        device_id=spec.device_id,
        device_fingerprint=spec.fingerprint,
        device_name=spec.display_name,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    if activation.license_id != expected_license_id:
        raise AcceptanceError("repeat activation returned an unexpected license id")
    if activation.device_id != spec.device_id:
        raise AcceptanceError("repeat activation returned an unexpected device id")
    if activation.maximum_devices != 3:
        raise AcceptanceError("staging license maximum_devices is not 3")
    if not activation.device_token:
        raise AcceptanceError("repeat activation did not return a device token")

    validation = client.validate(
        device_token=activation.device_token,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    if validation.license_id != expected_license_id or validation.device_id != spec.device_id:
        raise AcceptanceError("online validation returned unexpected identity fields")

    lease = verify_signed_lease(
        validation.lease_content,
        validation.lease_signature,
        trusted_keys,
        expected_device_id=spec.device_id,
        expected_license_id=expected_license_id,
    )
    if lease.key_id != expected_key_id:
        raise AcceptanceError("offline lease used an unexpected signing key")
    if lease.status != "active":
        raise AcceptanceError("offline lease status is not active")
    if lease.duration_seconds != 7 * 24 * 60 * 60:
        raise AcceptanceError("offline lease duration is not exactly seven days")

    server_time = _parse_timestamp(validation.server_time)
    if server_time != lease.issued_datetime:
        raise AcceptanceError("validation server_time does not match lease issued_at")

    valid_at = lease.issued_datetime + timedelta(days=1)
    expiring_at = lease.offline_until_datetime - timedelta(days=1)
    expired_at = lease.offline_until_datetime + timedelta(seconds=1)

    valid_state = lease.client_state_at(valid_at)
    expiring_state = lease.client_state_at(expiring_at)
    expired_state = lease.client_state_at(expired_at)
    if valid_state != ClientLicenseState.OFFLINE_VALID:
        raise AcceptanceError("lease did not enter offline_valid state")
    if expiring_state != ClientLicenseState.OFFLINE_EXPIRING:
        raise AcceptanceError("lease did not enter offline_expiring state")
    if expired_state != ClientLicenseState.OFFLINE_EXPIRED:
        raise AcceptanceError("lease did not enter offline_expired state")

    trusted_time = TrustedTimeState(
        last_server_time=validation.server_time,
        last_wall_clock=validation.server_time,
    )
    trusted_time.assert_not_rolled_back(server_time - timedelta(minutes=4))

    rollback_code: str | None = None
    try:
        trusted_time.assert_not_rolled_back(server_time - timedelta(minutes=10))
    except UpdateError as exc:
        if exc.code != ErrorCode.OFFLINE_LEASE_DENIED:
            raise AcceptanceError("clock rollback returned an unexpected error code") from exc
        rollback_code = exc.code.value
    else:
        raise AcceptanceError("significant clock rollback was not rejected")

    return {
        "ok": True,
        "license_id": expected_license_id,
        "device_hint": _safe_id(spec.device_id),
        "run_id": run_id,
        "app_version": app_version,
        "launcher_version": launcher_version,
        "signature_verified": True,
        "key_id": lease.key_id,
        "issued_at": lease.issued_at,
        "offline_until": lease.offline_until,
        "duration_seconds": lease.duration_seconds,
        "valid_state": valid_state.value,
        "expiring_state": expiring_state.value,
        "expired_state": expired_state.value,
        "small_clock_correction_allowed": True,
        "rollback_rejection_code": rollback_code,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify a fresh real-staging offline lease for an existing acceptance device."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--license-file", required=True, type=Path)
    parser.add_argument("--metadata-file", required=True, type=Path)
    parser.add_argument("--public-keys-file", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-key-id", default="lease-key-staging-01")
    parser.add_argument("--app-version", default=APP_VERSION)
    parser.add_argument("--launcher-version", default=LAUNCHER_VERSION)
    parser.add_argument(
        "--confirm-cloud-mutation",
        action="store_true",
        help="Required: confirms one repeat activation and one online validation against staging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.confirm_cloud_mutation:
        print(json.dumps({"ok": False, "error": "CLOUD_MUTATION_NOT_CONFIRMED"}, sort_keys=True))
        return 2
    try:
        metadata = _read_metadata(args.metadata_file)
        license_key = _read_license_key(args.license_file)
        trusted_keys = load_lease_public_keys(args.public_keys_file)
        client = LicenseApiClient(UrllibJsonTransport(args.base_url))
        report = run_lease_acceptance(
            client,
            trusted_keys=trusted_keys,
            license_key=license_key,
            expected_license_id=str(metadata["license_id"]),
            run_id=args.run_id,
            expected_key_id=args.expected_key_id,
            app_version=args.app_version,
            launcher_version=args.launcher_version,
        )
        report["license_hint"] = str(metadata["license_hint"])
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (AcceptanceError, LicenseRejected, LicenseServiceUnavailable, OSError, UpdateError) as exc:
        if isinstance(exc, LicenseRejected):
            code = exc.code.value
        elif isinstance(exc, UpdateError):
            code = exc.code.value
        else:
            code = type(exc).__name__
        print(json.dumps({"ok": False, "error": code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
