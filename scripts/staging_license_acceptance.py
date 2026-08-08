#!/usr/bin/env python3
"""Minimal real-staging license/device acceptance without Windows installation.

The script intentionally exercises only the existing license/device client API.
It never prints or persists the permanent license key or device tokens.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Protocol

from wechat_cli.license.client import (
    LicenseApiClient,
    LicenseRejected,
    LicenseServiceUnavailable,
    UrllibJsonTransport,
)
from wechat_cli.license.models import ActivationResult, DeviceRecord, ValidationResult
from wechat_cli.update.errors import ErrorCode
from wechat_cli.version import APP_VERSION, LAUNCHER_VERSION


class AcceptanceError(RuntimeError):
    """A staging acceptance invariant was not satisfied."""


class AcceptanceClient(Protocol):
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

    def list_devices(self, device_token: str) -> list[DeviceRecord]: ...

    def rename_device(
        self,
        device_token: str,
        *,
        target_device_id: str,
        display_name: str,
        operation_nonce: str,
    ) -> None: ...

    def unbind_device(
        self,
        device_token: str,
        *,
        target_device_id: str,
        operation_nonce: str,
    ) -> None: ...


@dataclass(frozen=True)
class DeviceSpec:
    device_id: str
    fingerprint: str
    display_name: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _operation_nonce() -> str:
    return "stgacc_" + uuid.uuid4().hex


def _safe_id(value: str) -> str:
    if len(value) <= 16:
        return value
    return f"{value[:10]}…{value[-4:]}"


def build_device_specs(license_id: str, run_id: str) -> tuple[DeviceSpec, ...]:
    if not isinstance(license_id, str) or not license_id.strip():
        raise ValueError("license_id is required")
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{4,64}", run_id):
        raise ValueError("run_id must contain 4-64 safe characters")

    result: list[DeviceSpec] = []
    for index in range(1, 5):
        seed = f"wechat-cli-staging-acceptance-v1\0{license_id}\0{run_id}\0{index}".encode(
            "utf-8"
        )
        identity_digest = hashlib.sha256(seed).hexdigest()
        fingerprint = hashlib.sha256(b"fingerprint\0" + seed).hexdigest()
        result.append(
            DeviceSpec(
                device_id=f"dev_stg_{identity_digest[:32]}",
                fingerprint=fingerprint,
                display_name=f"STAGING-ACCEPTANCE-{index:02d}",
            )
        )
    return tuple(result)


def _active_ids(records: list[DeviceRecord]) -> set[str]:
    return {record.device_id for record in records if record.status == "active"}


def _assert_activation(
    result: ActivationResult,
    *,
    expected_license_id: str,
    expected_device_id: str,
) -> None:
    if result.license_id != expected_license_id:
        raise AcceptanceError("activation returned an unexpected license id")
    if result.device_id != expected_device_id:
        raise AcceptanceError("activation returned an unexpected device id")
    if result.maximum_devices != 3:
        raise AcceptanceError("staging license maximum_devices is not 3")
    if not result.device_token:
        raise AcceptanceError("activation did not return a device token")
    if not result.lease_content or not result.lease_signature:
        raise AcceptanceError("activation did not return a signed offline lease")


def _activate(
    client: AcceptanceClient,
    *,
    license_key: str,
    spec: DeviceSpec,
    expected_license_id: str,
    app_version: str,
    launcher_version: str,
) -> ActivationResult:
    result = client.activate(
        license_key=license_key,
        device_id=spec.device_id,
        device_fingerprint=spec.fingerprint,
        device_name=spec.display_name,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    _assert_activation(
        result,
        expected_license_id=expected_license_id,
        expected_device_id=spec.device_id,
    )
    return result


def run_acceptance(
    client: AcceptanceClient,
    *,
    license_key: str,
    expected_license_id: str,
    run_id: str,
    app_version: str,
    launcher_version: str,
    now: Callable[[], datetime] = _utc_now,
) -> dict[str, object]:
    specs = build_device_specs(expected_license_id, run_id)
    expected_ids = {spec.device_id for spec in specs}

    first = _activate(
        client,
        license_key=license_key,
        spec=specs[0],
        expected_license_id=expected_license_id,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    primary_token = first.device_token

    initial_records = client.list_devices(primary_token)
    unknown_active = _active_ids(initial_records) - expected_ids
    if unknown_active:
        raise AcceptanceError("unknown active device exists on the staging test license")

    if specs[3].device_id in _active_ids(initial_records):
        client.unbind_device(
            primary_token,
            target_device_id=specs[3].device_id,
            operation_nonce=_operation_nonce(),
        )

    second = _activate(
        client,
        license_key=license_key,
        spec=specs[1],
        expected_license_id=expected_license_id,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    third = _activate(
        client,
        license_key=license_key,
        spec=specs[2],
        expected_license_id=expected_license_id,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    del second, third

    before_limit = client.list_devices(primary_token)
    if _active_ids(before_limit) != {specs[0].device_id, specs[1].device_id, specs[2].device_id}:
        raise AcceptanceError("expected staging devices 1-3 are not the only active devices")

    fourth_code: str | None = None
    try:
        unexpected = _activate(
            client,
            license_key=license_key,
            spec=specs[3],
            expected_license_id=expected_license_id,
            app_version=app_version,
            launcher_version=launcher_version,
        )
    except LicenseRejected as exc:
        if exc.code != ErrorCode.DEVICE_LIMIT_REACHED:
            raise AcceptanceError("fourth device was rejected with an unexpected error code") from exc
        fourth_code = exc.code.value
    else:
        try:
            client.unbind_device(
                primary_token,
                target_device_id=unexpected.device_id,
                operation_nonce=_operation_nonce(),
            )
        finally:
            raise AcceptanceError("fourth device activation unexpectedly succeeded")

    validation = client.validate(
        device_token=primary_token,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    if validation.license_id != expected_license_id or validation.device_id != specs[0].device_id:
        raise AcceptanceError("online validation returned unexpected identity fields")
    if not validation.lease_content or not validation.lease_signature:
        raise AcceptanceError("online validation did not return a signed offline lease")

    client.rename_device(
        primary_token,
        target_device_id=specs[1].device_id,
        display_name="STAGING-ACCEPTANCE-RENAMED",
        operation_nonce=_operation_nonce(),
    )
    renamed_records = client.list_devices(primary_token)
    renamed = next(
        (record for record in renamed_records if record.device_id == specs[1].device_id),
        None,
    )
    if renamed is None or renamed.display_name != "STAGING-ACCEPTANCE-RENAMED":
        raise AcceptanceError("device rename was not reflected by the service")

    client.unbind_device(
        primary_token,
        target_device_id=specs[2].device_id,
        operation_nonce=_operation_nonce(),
    )
    after_unbind = client.list_devices(primary_token)
    if specs[2].device_id in _active_ids(after_unbind):
        raise AcceptanceError("unbound device remained active")

    fourth = _activate(
        client,
        license_key=license_key,
        spec=specs[3],
        expected_license_id=expected_license_id,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    del fourth

    final_records = client.list_devices(primary_token)
    final_active = _active_ids(final_records)
    expected_final = {specs[0].device_id, specs[1].device_id, specs[3].device_id}
    if final_active != expected_final:
        raise AcceptanceError("final active device set does not match the expected staging state")

    timestamp = now()
    if timestamp.tzinfo is None:
        raise ValueError("now() must return a timezone-aware datetime")

    return {
        "ok": True,
        "license_id": expected_license_id,
        "run_id": run_id,
        "checked_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "app_version": app_version,
        "launcher_version": launcher_version,
        "device_hints": [_safe_id(spec.device_id) for spec in specs],
        "initial_three_devices_active": True,
        "fourth_device_first_attempt": fourth_code,
        "validation_ok": True,
        "offline_lease_issued": True,
        "rename_ok": True,
        "unbind_rebind_ok": True,
        "final_active_device_count": len(final_active),
    }


def _read_license_key(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise AcceptanceError("license file must be a regular file")
    if path.stat().st_size > 1024:
        raise AcceptanceError("license file is unexpectedly large")
    value = path.read_text(encoding="utf-8").strip()
    compact = re.sub(r"[^A-Za-z0-9]", "", value).upper()
    if not compact.startswith("WCL") or not 19 <= len(compact) <= 80:
        raise AcceptanceError("license file does not contain a valid WeChat CLI license")
    return value


def _read_metadata(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise AcceptanceError("metadata file must be a regular file")
    if path.stat().st_size > 64 * 1024:
        raise AcceptanceError("metadata file is unexpectedly large")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError("metadata file is invalid") from exc
    if not isinstance(value, dict):
        raise AcceptanceError("metadata file root must be an object")
    required = {
        "license_id": str,
        "license_hint": str,
        "status": str,
        "maximum_devices": int,
        "release_channel": str,
        "created_at": str,
    }
    for name, expected_type in required.items():
        item = value.get(name)
        if isinstance(item, bool) or not isinstance(item, expected_type):
            raise AcceptanceError(f"metadata field {name} is invalid")
    if value["status"] != "active":
        raise AcceptanceError("staging test license is not active")
    if value["maximum_devices"] != 3:
        raise AcceptanceError("staging test license maximum_devices is not 3")
    if value["release_channel"] != "stable":
        raise AcceptanceError("staging test license channel is not stable")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run minimal license/device acceptance against an explicitly selected staging Worker."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--license-file", required=True, type=Path)
    parser.add_argument("--metadata-file", required=True, type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--app-version", default=APP_VERSION)
    parser.add_argument("--launcher-version", default=LAUNCHER_VERSION)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        metadata = _read_metadata(args.metadata_file)
        license_key = _read_license_key(args.license_file)
        client = LicenseApiClient(UrllibJsonTransport(args.base_url))
        report = run_acceptance(
            client,
            license_key=license_key,
            expected_license_id=str(metadata["license_id"]),
            run_id=args.run_id,
            app_version=args.app_version,
            launcher_version=args.launcher_version,
        )
        report["license_hint"] = str(metadata["license_hint"])
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (AcceptanceError, LicenseRejected, LicenseServiceUnavailable, OSError) as exc:
        code = exc.code.value if isinstance(exc, LicenseRejected) else type(exc).__name__
        print(json.dumps({"ok": False, "error": code}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
