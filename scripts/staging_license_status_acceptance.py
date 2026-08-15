#!/usr/bin/env python3
"""Single-process staging suspend/reject/restore acceptance.

When explicitly confirmed, this script uses an existing staging test license and
Task 3 device identity to prove that an authoritative online suspension blocks
a device even while that process still holds a previously issued token/lease.
It then restores the license to active in a mandatory recovery path and verifies
that the same device token becomes valid again.

Permanent license keys, device tokens, administrator tokens, raw lease bytes,
signatures, and full device fingerprints are never printed or persisted.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol

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

from wechat_cli.admin.client import (
    AdminApiClient,
    AdminApiError,
    UrllibAdminJsonTransport,
)
from wechat_cli.admin.config import AdminConfigStorage, default_admin_config_path
from wechat_cli.license.client import (
    LicenseApiClient,
    LicenseRejected,
    LicenseServiceUnavailable,
    UrllibJsonTransport,
)
from wechat_cli.license.models import ActivationResult, ValidationResult
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.version import APP_VERSION, LAUNCHER_VERSION
from wechat_cli.windows.dpapi import WindowsDpapiProtector


class StatusAcceptanceError(RuntimeError):
    """The status-policy acceptance invariant was not satisfied."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class StatusRecoveryError(StatusAcceptanceError):
    """The license could not be confirmed restored after a suspend attempt."""

    def __init__(self) -> None:
        super().__init__(
            "RESTORE_FAILED",
            "staging license recovery to active failed or could not be confirmed",
        )


class AdminStatusClient(Protocol):
    def list_licenses(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Mapping[str, object]]: ...

    def set_license_status(
        self,
        license_id: str,
        status: str,
        operation_nonce: str,
    ) -> Mapping[str, object]: ...


class StatusLicenseClient(Protocol):
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


def _safe_id(value: str) -> str:
    if len(value) <= 16:
        return value
    return f"{value[:10]}…{value[-4:]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _nonce(prefix: str) -> str:
    return f"stgstatus_{prefix}_{uuid.uuid4().hex}"


def _exact_license_summary(
    admin_client: AdminStatusClient,
    expected_license_id: str,
) -> Mapping[str, object]:
    rows = admin_client.list_licenses(query=expected_license_id, limit=50)
    matches = [row for row in rows if row.get("license_id") == expected_license_id]
    if len(matches) != 1:
        raise StatusAcceptanceError(
            "LICENSE_PREFLIGHT_MISMATCH",
            "administrator preflight did not return exactly the expected staging license",
        )
    return matches[0]


def _assert_status_response(
    response: Mapping[str, object],
    *,
    expected_license_id: str,
    expected_status: str,
) -> None:
    if response.get("license_id") != expected_license_id:
        raise StatusAcceptanceError(
            "STATUS_RESPONSE_MISMATCH",
            "administrator status response returned an unexpected license id",
        )
    if response.get("status") != expected_status:
        raise StatusAcceptanceError(
            "STATUS_RESPONSE_MISMATCH",
            "administrator status response returned an unexpected status",
        )


def _assert_activation(
    activation: ActivationResult,
    *,
    expected_license_id: str,
    expected_device_id: str,
) -> None:
    if activation.license_id != expected_license_id:
        raise StatusAcceptanceError(
            "ACTIVATION_IDENTITY_MISMATCH",
            "activation returned an unexpected license id",
        )
    if activation.device_id != expected_device_id:
        raise StatusAcceptanceError(
            "ACTIVATION_IDENTITY_MISMATCH",
            "activation returned an unexpected device id",
        )
    if activation.maximum_devices != 3:
        raise StatusAcceptanceError(
            "ACTIVATION_POLICY_MISMATCH",
            "staging test license maximum_devices is not 3",
        )
    if not activation.device_token:
        raise StatusAcceptanceError(
            "ACTIVATION_TOKEN_MISSING",
            "activation did not return a device token",
        )
    if not activation.lease_content or not activation.lease_signature:
        raise StatusAcceptanceError(
            "ACTIVATION_LEASE_MISSING",
            "activation did not return a signed lease before suspension",
        )


def _assert_restored_validation(
    validation: ValidationResult,
    *,
    expected_license_id: str,
    expected_device_id: str,
) -> None:
    if validation.license_id != expected_license_id or validation.device_id != expected_device_id:
        raise StatusAcceptanceError(
            "RESTORED_VALIDATION_MISMATCH",
            "post-restore validation returned unexpected identity fields",
        )
    if not validation.lease_content or not validation.lease_signature:
        raise StatusAcceptanceError(
            "RESTORED_LEASE_MISSING",
            "post-restore validation did not return a signed lease",
        )


def run_status_acceptance(
    *,
    admin_client: AdminStatusClient,
    license_client: StatusLicenseClient,
    license_key: str,
    expected_license_id: str,
    run_id: str,
    app_version: str,
    launcher_version: str,
    now: Callable[[], datetime] = _utc_now,
    nonce_factory: Callable[[str], str] = _nonce,
) -> dict[str, object]:
    summary = _exact_license_summary(admin_client, expected_license_id)
    if summary.get("status") != "active":
        raise StatusAcceptanceError(
            "LICENSE_NOT_ACTIVE_AT_PREFLIGHT",
            "staging test license is not active at status-acceptance preflight",
        )

    spec = build_device_specs(expected_license_id, run_id)[0]
    activation = license_client.activate(
        license_key=license_key,
        device_id=spec.device_id,
        device_fingerprint=spec.fingerprint,
        device_name=spec.display_name,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    _assert_activation(
        activation,
        expected_license_id=expected_license_id,
        expected_device_id=spec.device_id,
    )
    device_token = activation.device_token

    restore_required = False
    restore_succeeded = False
    suspended_rejection_code: str | None = None
    primary_error: Exception | None = None

    try:
        # From this point onward the suspend request may have reached the server,
        # even if the client later sees a timeout or a lost response. Recovery is
        # therefore mandatory after *any* suspend attempt.
        restore_required = True
        try:
            suspended = admin_client.set_license_status(
                expected_license_id,
                "suspended",
                nonce_factory("suspend"),
            )
            _assert_status_response(
                suspended,
                expected_license_id=expected_license_id,
                expected_status="suspended",
            )
        except Exception as exc:  # recovery still mandatory after uncertain mutation
            raise StatusAcceptanceError(
                "SUSPEND_FAILED_OR_UNCERTAIN",
                "suspend request failed or its server-side outcome is uncertain",
            ) from exc

        try:
            license_client.validate(
                device_token=device_token,
                app_version=app_version,
                launcher_version=launcher_version,
            )
        except LicenseRejected as exc:
            if exc.code != ErrorCode.LICENSE_SUSPENDED:
                raise StatusAcceptanceError(
                    "UNEXPECTED_SUSPEND_REJECTION",
                    "online validation was rejected with an unexpected code while suspended",
                ) from exc
            suspended_rejection_code = exc.code.value
        else:
            raise StatusAcceptanceError(
                "SUSPENSION_NOT_ENFORCED",
                "online validation unexpectedly succeeded while the license was suspended",
            )
    except Exception as exc:
        primary_error = exc
    finally:
        if restore_required:
            try:
                restored = admin_client.set_license_status(
                    expected_license_id,
                    "active",
                    nonce_factory("restore"),
                )
                _assert_status_response(
                    restored,
                    expected_license_id=expected_license_id,
                    expected_status="active",
                )
                restore_succeeded = True
            except Exception as exc:
                # Recovery failure outranks every other acceptance failure.
                raise StatusRecoveryError() from exc

    if primary_error is not None:
        if isinstance(primary_error, StatusAcceptanceError):
            raise primary_error
        raise StatusAcceptanceError(
            "STATUS_ACCEPTANCE_FAILED",
            "staging status acceptance failed after recovery",
        ) from primary_error

    restored_validation = license_client.validate(
        device_token=device_token,
        app_version=app_version,
        launcher_version=launcher_version,
    )
    _assert_restored_validation(
        restored_validation,
        expected_license_id=expected_license_id,
        expected_device_id=spec.device_id,
    )

    timestamp = now()
    if timestamp.tzinfo is None:
        raise ValueError("now() must return a timezone-aware datetime")

    return {
        "ok": True,
        "license_id": expected_license_id,
        "license_hint": str(summary.get("license_hint") or ""),
        "device_hint": _safe_id(spec.device_id),
        "run_id": run_id,
        "checked_at": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "app_version": app_version,
        "launcher_version": launcher_version,
        "suspended_rejection_code": suspended_rejection_code,
        "restore_succeeded": restore_succeeded,
        "restored_validation_ok": True,
    }


def _load_admin_client(config_path: Path | None, *, expected_base_url: str) -> AdminApiClient:
    path = config_path if config_path is not None else default_admin_config_path()
    config = AdminConfigStorage(path, WindowsDpapiProtector()).load()
    if config is None:
        raise StatusAcceptanceError(
            "ADMIN_CONFIG_MISSING",
            "administrator configuration is not available",
        )
    normalized_expected = expected_base_url.rstrip("/")
    if config.api_base_url != normalized_expected:
        raise StatusAcceptanceError(
            "ADMIN_BASE_URL_MISMATCH",
            "administrator configuration does not target the requested staging origin",
        )
    return AdminApiClient(
        UrllibAdminJsonTransport(
            config.api_base_url,
            allow_insecure_loopback=config.allow_insecure_loopback,
        ),
        admin_token=config.admin_token,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify staging suspend rejection and mandatory restore in one process."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--license-file", required=True, type=Path)
    parser.add_argument("--metadata-file", required=True, type=Path)
    parser.add_argument("--admin-config-path", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--app-version", default=APP_VERSION)
    parser.add_argument("--launcher-version", default=LAUNCHER_VERSION)
    parser.add_argument(
        "--confirm-cloud-mutation",
        action="store_true",
        help="Required: confirms one repeat activation, suspend, suspended validation, restore, and post-restore validation against staging.",
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
        admin_client = _load_admin_client(
            args.admin_config_path,
            expected_base_url=args.base_url,
        )
        license_client = LicenseApiClient(UrllibJsonTransport(args.base_url))
        report = run_status_acceptance(
            admin_client=admin_client,
            license_client=license_client,
            license_key=license_key,
            expected_license_id=str(metadata["license_id"]),
            run_id=args.run_id,
            app_version=args.app_version,
            launcher_version=args.launcher_version,
        )
        if not report.get("license_hint"):
            report["license_hint"] = str(metadata["license_hint"])
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except StatusRecoveryError as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": exc.code,
                    "restore_succeeded": False,
                    "manual_status_check_required": True,
                },
                sort_keys=True,
            )
        )
        return 3
    except StatusAcceptanceError as exc:
        print(json.dumps({"ok": False, "error": exc.code}, sort_keys=True))
        return 2
    except AdminApiError as exc:
        print(json.dumps({"ok": False, "error": exc.code}, sort_keys=True))
        return 2
    except LicenseRejected as exc:
        print(json.dumps({"ok": False, "error": exc.code.value}, sort_keys=True))
        return 2
    except (LicenseServiceUnavailable, UpdateError, AcceptanceError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": type(exc).__name__}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
