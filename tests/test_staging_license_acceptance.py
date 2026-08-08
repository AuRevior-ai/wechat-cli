import json
import unittest
from datetime import datetime, timezone

from scripts.staging_license_acceptance import (
    AcceptanceError,
    build_device_specs,
    run_acceptance,
)
from wechat_cli.license.client import LicenseRejected
from wechat_cli.license.models import ActivationResult, DeviceRecord, ValidationResult
from wechat_cli.update.errors import ErrorCode


class FakeAcceptanceClient:
    def __init__(self):
        self.license_id = "lic_test_01"
        self.maximum_devices = 3
        self.devices = {}
        self.tokens = {}
        self.calls = []

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
        active_count = sum(1 for item in self.devices.values() if item["status"] == "active")
        existing = self.devices.get(device_id)
        if existing is None and active_count >= self.maximum_devices:
            raise LicenseRejected(ErrorCode.DEVICE_LIMIT_REACHED, "limit reached")
        if existing is not None and existing["status"] == "unbound" and active_count >= self.maximum_devices:
            raise LicenseRejected(ErrorCode.DEVICE_LIMIT_REACHED, "limit reached")

        self.devices[device_id] = {
            "display_name": device_name,
            "status": "active",
            "app_version": app_version,
            "launcher_version": launcher_version,
        }
        token = f"wcdt_{device_id}.secret"
        self.tokens[token] = device_id
        count = sum(1 for item in self.devices.values() if item["status"] == "active")
        return ActivationResult(
            license_id=self.license_id,
            device_id=device_id,
            device_token=token,
            device_count=count,
            maximum_devices=self.maximum_devices,
            lease_content=b"lease",
            lease_signature=b"signature",
        )

    def validate(self, *, device_token, app_version, launcher_version):
        self.calls.append(("validate", device_token, app_version, launcher_version))
        device_id = self.tokens[device_token]
        return ValidationResult(
            license_id=self.license_id,
            device_id=device_id,
            server_time="2026-08-08T09:30:00Z",
            lease_content=b"lease",
            lease_signature=b"signature",
        )

    def list_devices(self, device_token):
        self.calls.append(("list_devices", device_token))
        current = self.tokens[device_token]
        return [
            DeviceRecord(
                device_id=device_id,
                display_name=item["display_name"],
                status=item["status"],
                is_current=device_id == current,
                last_validated_at="2026-08-08T09:30:00Z",
                last_app_version=item["app_version"],
                last_launcher_version=item["launcher_version"],
            )
            for device_id, item in sorted(self.devices.items())
        ]

    def rename_device(self, device_token, *, target_device_id, display_name, operation_nonce):
        self.calls.append(("rename", device_token, target_device_id, operation_nonce))
        self.devices[target_device_id]["display_name"] = display_name

    def unbind_device(self, device_token, *, target_device_id, operation_nonce):
        self.calls.append(("unbind", device_token, target_device_id, operation_nonce))
        self.devices[target_device_id]["status"] = "unbound"


class StagingLicenseAcceptanceTests(unittest.TestCase):
    def test_device_specs_are_stable_per_license_and_run_id(self):
        first = build_device_specs("lic_test_01", "board4-task3")
        again = build_device_specs("lic_test_01", "board4-task3")
        other = build_device_specs("lic_test_01", "another-run")

        self.assertEqual(first, again)
        self.assertNotEqual(first, other)
        self.assertEqual(4, len(first))
        self.assertTrue(all(spec.device_id.startswith("dev_stg_") for spec in first))
        self.assertTrue(all(len(spec.fingerprint) == 64 for spec in first))

    def test_run_acceptance_exercises_three_device_limit_without_leaking_secrets(self):
        client = FakeAcceptanceClient()
        report = run_acceptance(
            client,
            license_key="WCL-SECRET-STAGING-KEY",
            expected_license_id="lic_test_01",
            run_id="board4-task3",
            app_version="0.5.0",
            launcher_version="0.1.0",
            now=lambda: datetime(2026, 8, 8, 9, 30, tzinfo=timezone.utc),
        )

        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn("WCL-SECRET-STAGING-KEY", encoded)
        self.assertNotIn("wcdt_", encoded)
        self.assertEqual("DEVICE_LIMIT_REACHED", report["fourth_device_first_attempt"])
        self.assertTrue(report["validation_ok"])
        self.assertTrue(report["rename_ok"])
        self.assertTrue(report["unbind_rebind_ok"])
        self.assertEqual(3, report["final_active_device_count"])
        self.assertEqual("lic_test_01", report["license_id"])

        activate_calls = [call for call in client.calls if call[0] == "activate"]
        self.assertTrue(all(call[1] == "WCL-SECRET-STAGING-KEY" for call in activate_calls))
        non_activation_text = repr([call for call in client.calls if call[0] != "activate"])
        self.assertNotIn("WCL-SECRET-STAGING-KEY", non_activation_text)

    def test_run_acceptance_refuses_unknown_active_devices(self):
        client = FakeAcceptanceClient()
        client.devices["dev_unknown_12345678"] = {
            "display_name": "UNKNOWN",
            "status": "active",
            "app_version": "0.5.0",
            "launcher_version": "0.1.0",
        }

        with self.assertRaises(AcceptanceError) as caught:
            run_acceptance(
                client,
                license_key="WCL-SECRET-STAGING-KEY",
                expected_license_id="lic_test_01",
                run_id="board4-task3",
                app_version="0.5.0",
                launcher_version="0.1.0",
                now=lambda: datetime(2026, 8, 8, 9, 30, tzinfo=timezone.utc),
            )

        self.assertIn("unknown active device", str(caught.exception).lower())
        self.assertNotIn("WCL-SECRET-STAGING-KEY", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
