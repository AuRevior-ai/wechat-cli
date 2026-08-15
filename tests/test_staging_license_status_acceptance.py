import json
import unittest
from datetime import datetime, timezone

from wechat_cli.admin.client import AdminApiError
from wechat_cli.license.client import LicenseRejected
from wechat_cli.license.models import ActivationResult, ValidationResult
from wechat_cli.update.errors import ErrorCode

from scripts.staging_license_status_acceptance import (
    StatusAcceptanceError,
    StatusRecoveryError,
    run_status_acceptance,
)


class SharedState:
    def __init__(self):
        self.status = "active"


class FakeAdminClient:
    def __init__(self, state: SharedState, *, suspend_failure=None, restore_failure=None):
        self.state = state
        self.suspend_failure = suspend_failure
        self.restore_failure = restore_failure
        self.calls = []

    def list_licenses(self, *, query=None, status=None, limit=50):
        self.calls.append(("list", query, status, limit))
        return [
            {
                "license_id": "lic_test_01",
                "license_hint": "TEST",
                "status": self.state.status,
                "maximum_devices": 3,
                "active_devices": 3,
                "release_channel": "stable",
            }
        ]

    def set_license_status(self, license_id, status, operation_nonce):
        self.calls.append(("status", license_id, status, operation_nonce))
        if status == "suspended":
            self.state.status = "suspended"
            if self.suspend_failure is not None:
                raise self.suspend_failure
        elif status == "active":
            if self.restore_failure is not None:
                raise self.restore_failure
            self.state.status = "active"
        else:
            raise AssertionError(f"unexpected status {status}")
        return {"ok": True, "license_id": license_id, "status": status}


class FakeLicenseClient:
    def __init__(self, state: SharedState, *, ignore_suspension=False):
        self.state = state
        self.ignore_suspension = ignore_suspension
        self.calls = []
        self.token = "wcdt_hidden.secret"
        self.device_id = "dev_status_test_1234567890"

    def activate(
        self,
        *,
        license_key,
        device_id,
        device_fingerprint,
        device_name,
        app_version,
        launcher_version,
    ):
        self.calls.append(("activate", license_key, device_id, device_fingerprint))
        self.device_id = device_id
        return ActivationResult(
            license_id="lic_test_01",
            device_id=device_id,
            device_token=self.token,
            device_count=3,
            maximum_devices=3,
            lease_content=b"lease-before-suspend",
            lease_signature=b"signature-before-suspend",
        )

    def validate(self, *, device_token, app_version, launcher_version):
        self.calls.append(("validate", device_token, app_version, launcher_version))
        if self.state.status == "suspended" and not self.ignore_suspension:
            raise LicenseRejected(ErrorCode.LICENSE_SUSPENDED, "license suspended")
        return ValidationResult(
            license_id="lic_test_01",
            device_id=self.device_id,
            server_time="2026-08-08T10:00:00Z",
            lease_content=b"lease-after-restore",
            lease_signature=b"signature-after-restore",
        )


class StagingLicenseStatusAcceptanceTests(unittest.TestCase):
    def test_happy_path_suspends_rejects_restores_and_revalidates_without_leaks(self):
        state = SharedState()
        admin = FakeAdminClient(state)
        license_client = FakeLicenseClient(state)

        report = run_status_acceptance(
            admin_client=admin,
            license_client=license_client,
            license_key="WCL-SECRET-STAGING-KEY",
            expected_license_id="lic_test_01",
            run_id="board4-task3",
            app_version="0.5.0",
            launcher_version="0.1.0",
            now=lambda: datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc),
            nonce_factory=lambda prefix: f"{prefix}_nonce",
        )

        self.assertEqual("active", state.status)
        self.assertTrue(report["ok"])
        self.assertEqual("LICENSE_SUSPENDED", report["suspended_rejection_code"])
        self.assertTrue(report["restore_succeeded"])
        self.assertTrue(report["restored_validation_ok"])
        self.assertEqual(
            ["suspended", "active"],
            [call[2] for call in admin.calls if call[0] == "status"],
        )
        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn("WCL-SECRET-STAGING-KEY", encoded)
        self.assertNotIn("wcdt_hidden", encoded)
        self.assertNotIn("lease-before-suspend", encoded)
        self.assertNotIn("signature-before-suspend", encoded)

    def test_unexpected_validation_success_still_restores_license(self):
        state = SharedState()
        admin = FakeAdminClient(state)
        license_client = FakeLicenseClient(state, ignore_suspension=True)

        with self.assertRaises(StatusAcceptanceError):
            run_status_acceptance(
                admin_client=admin,
                license_client=license_client,
                license_key="WCL-SECRET-STAGING-KEY",
                expected_license_id="lic_test_01",
                run_id="board4-task3",
                app_version="0.5.0",
                launcher_version="0.1.0",
                nonce_factory=lambda prefix: f"{prefix}_nonce",
            )

        self.assertEqual("active", state.status)
        self.assertEqual(
            ["suspended", "active"],
            [call[2] for call in admin.calls if call[0] == "status"],
        )

    def test_suspend_response_failure_still_attempts_restore(self):
        state = SharedState()
        admin = FakeAdminClient(
            state,
            suspend_failure=AdminApiError(
                "SERVICE_UNAVAILABLE",
                "response lost after write",
                retryable=True,
            ),
        )
        license_client = FakeLicenseClient(state)

        with self.assertRaises(StatusAcceptanceError):
            run_status_acceptance(
                admin_client=admin,
                license_client=license_client,
                license_key="WCL-SECRET-STAGING-KEY",
                expected_license_id="lic_test_01",
                run_id="board4-task3",
                app_version="0.5.0",
                launcher_version="0.1.0",
                nonce_factory=lambda prefix: f"{prefix}_nonce",
            )

        self.assertEqual("active", state.status)
        self.assertEqual(
            ["suspended", "active"],
            [call[2] for call in admin.calls if call[0] == "status"],
        )

    def test_restore_failure_has_priority_and_does_not_leak_secrets(self):
        state = SharedState()
        admin = FakeAdminClient(
            state,
            restore_failure=AdminApiError(
                "SERVICE_UNAVAILABLE",
                "restore response unavailable",
                retryable=True,
            ),
        )
        license_client = FakeLicenseClient(state)

        with self.assertRaises(StatusRecoveryError) as caught:
            run_status_acceptance(
                admin_client=admin,
                license_client=license_client,
                license_key="WCL-SECRET-STAGING-KEY",
                expected_license_id="lic_test_01",
                run_id="board4-task3",
                app_version="0.5.0",
                launcher_version="0.1.0",
                nonce_factory=lambda prefix: f"{prefix}_nonce",
            )

        self.assertEqual("RESTORE_FAILED", caught.exception.code)
        self.assertNotIn("WCL-SECRET-STAGING-KEY", str(caught.exception))
        self.assertNotIn("wcdt_hidden", str(caught.exception))

    def test_refuses_non_active_preflight_without_mutation(self):
        state = SharedState()
        state.status = "suspended"
        admin = FakeAdminClient(state)
        license_client = FakeLicenseClient(state)

        with self.assertRaises(StatusAcceptanceError):
            run_status_acceptance(
                admin_client=admin,
                license_client=license_client,
                license_key="WCL-SECRET-STAGING-KEY",
                expected_license_id="lic_test_01",
                run_id="board4-task3",
                app_version="0.5.0",
                launcher_version="0.1.0",
                nonce_factory=lambda prefix: f"{prefix}_nonce",
            )

        self.assertEqual([], [call for call in admin.calls if call[0] == "status"])
        self.assertEqual([], license_client.calls)


if __name__ == "__main__":
    unittest.main()
