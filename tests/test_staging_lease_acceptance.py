import json
import unittest
from datetime import datetime, timezone

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from scripts.staging_license_acceptance import build_device_specs
from scripts.staging_lease_acceptance import run_lease_acceptance
from wechat_cli.license.models import ActivationResult, ValidationResult
from wechat_cli.update.crypto import TrustedEd25519Keys


TEST_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes(range(32)))
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key().export_key(format="raw")


class FakeLeaseClient:
    def __init__(self, *, license_id: str, device_id: str) -> None:
        self.license_id = license_id
        self.device_id = device_id
        self.device_token = "wcdt_realistic.secret-value"
        self.calls = []
        self.raw_lease = json.dumps(
            {
                "schema_version": 1,
                "license_id": license_id,
                "device_id": device_id,
                "status": "active",
                "license_revision": 1,
                "device_revision": 4,
                "issued_at": "2026-08-08T10:00:00Z",
                "offline_until": "2026-08-15T10:00:00Z",
                "nonce": "lease_private_nonce",
                "key_id": "lease-key-staging-01",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        self.signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(self.raw_lease)

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
        self.calls.append(
            (
                "activate",
                license_key,
                device_id,
                device_fingerprint,
                device_name,
                app_version,
                launcher_version,
            )
        )
        return ActivationResult(
            license_id=self.license_id,
            device_id=device_id,
            device_token=self.device_token,
            device_count=3,
            maximum_devices=3,
            lease_content=self.raw_lease,
            lease_signature=self.signature,
        )

    def validate(self, *, device_token, app_version, launcher_version):
        self.calls.append(("validate", device_token, app_version, launcher_version))
        return ValidationResult(
            license_id=self.license_id,
            device_id=self.device_id,
            server_time="2026-08-08T10:00:00Z",
            lease_content=self.raw_lease,
            lease_signature=self.signature,
        )


class StagingLeaseAcceptanceTests(unittest.TestCase):
    def test_verifies_realistic_lease_and_clock_states_without_leaking_secrets(self):
        license_id = "lic_test_01"
        run_id = "board4-task3"
        device_id = build_device_specs(license_id, run_id)[0].device_id
        client = FakeLeaseClient(license_id=license_id, device_id=device_id)
        keys = TrustedEd25519Keys({"lease-key-staging-01": TEST_PUBLIC_KEY})

        report = run_lease_acceptance(
            client,
            trusted_keys=keys,
            license_key="WCL-SECRET-STAGING-KEY",
            expected_license_id=license_id,
            run_id=run_id,
            expected_key_id="lease-key-staging-01",
            app_version="0.5.0",
            launcher_version="0.1.0",
        )

        self.assertTrue(report["ok"])
        self.assertTrue(report["signature_verified"])
        self.assertEqual(604800, report["duration_seconds"])
        self.assertEqual("offline_valid", report["valid_state"])
        self.assertEqual("offline_expiring", report["expiring_state"])
        self.assertEqual("offline_expired", report["expired_state"])
        self.assertTrue(report["small_clock_correction_allowed"])
        self.assertEqual("OFFLINE_LEASE_DENIED", report["rollback_rejection_code"])
        self.assertEqual("lease-key-staging-01", report["key_id"])
        self.assertEqual("2026-08-08T10:00:00Z", report["issued_at"])
        self.assertEqual("2026-08-15T10:00:00Z", report["offline_until"])

        encoded = json.dumps(report, sort_keys=True)
        self.assertNotIn("WCL-SECRET-STAGING-KEY", encoded)
        self.assertNotIn("wcdt_realistic", encoded)
        self.assertNotIn("lease_private_nonce", encoded)
        self.assertNotIn(self.raw_text(client.raw_lease), encoded)

        self.assertEqual("activate", client.calls[0][0])
        self.assertEqual("validate", client.calls[1][0])
        self.assertEqual(client.device_token, client.calls[1][1])
        self.assertEqual(2, len(client.calls))

    def test_rejects_unexpected_signing_key_id(self):
        license_id = "lic_test_01"
        run_id = "board4-task3"
        device_id = build_device_specs(license_id, run_id)[0].device_id
        client = FakeLeaseClient(license_id=license_id, device_id=device_id)
        keys = TrustedEd25519Keys({"lease-key-staging-01": TEST_PUBLIC_KEY})

        with self.assertRaises(RuntimeError) as caught:
            run_lease_acceptance(
                client,
                trusted_keys=keys,
                license_key="WCL-SECRET-STAGING-KEY",
                expected_license_id=license_id,
                run_id=run_id,
                expected_key_id="lease-key-staging-02",
                app_version="0.5.0",
                launcher_version="0.1.0",
            )

        self.assertIn("signing key", str(caught.exception).lower())
        self.assertNotIn("WCL-SECRET-STAGING-KEY", str(caught.exception))

    @staticmethod
    def raw_text(raw: bytes) -> str:
        return raw.decode("utf-8")


if __name__ == "__main__":
    unittest.main()
