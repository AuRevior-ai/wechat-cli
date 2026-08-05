import json
import unittest
from datetime import datetime, timedelta, timezone

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from wechat_cli.license.lease import (
    OfflineLease,
    TrustedTimeState,
    verify_signed_lease,
)
from wechat_cli.license.models import ClientLicenseState
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.errors import ErrorCode, UpdateError


TEST_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes(reversed(range(32))))
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key().export_key(format="raw")


def lease_bytes(**overrides):
    data = {
        "schema_version": 1,
        "license_id": "lic_01",
        "device_id": "dev_01",
        "status": "active",
        "license_revision": 4,
        "device_revision": 2,
        "issued_at": "2026-08-04T15:00:00Z",
        "offline_until": "2026-08-11T15:00:00Z",
        "nonce": "nonce_01",
        "key_id": "lease-key-test-01",
    }
    data.update(overrides)
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


class OfflineLeaseTests(unittest.TestCase):
    def setUp(self):
        self.keys = TrustedEd25519Keys({"lease-key-test-01": TEST_PUBLIC_KEY})

    def sign(self, raw):
        return eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(raw)

    def test_verifies_signed_seven_day_lease(self):
        raw = lease_bytes()

        lease = verify_signed_lease(
            raw,
            self.sign(raw),
            self.keys,
            expected_device_id="dev_01",
        )

        self.assertEqual("lic_01", lease.license_id)
        self.assertEqual(7 * 24 * 60 * 60, lease.duration_seconds)

    def test_rejects_tampered_lease(self):
        raw = lease_bytes()
        signature = self.sign(raw)

        with self.assertRaises(UpdateError) as caught:
            verify_signed_lease(
                raw.replace(b"dev_01", b"dev_02"),
                signature,
                self.keys,
                expected_device_id="dev_02",
            )

        self.assertEqual(ErrorCode.UPDATE_SIGNATURE_INVALID, caught.exception.code)

    def test_rejects_lease_longer_than_seven_days(self):
        raw = lease_bytes(offline_until="2026-08-11T15:00:01Z")

        with self.assertRaises(ValueError):
            OfflineLease.from_json_bytes(raw)

    def test_rejects_wrong_device_even_with_valid_signature(self):
        raw = lease_bytes(device_id="dev_other")

        with self.assertRaises(UpdateError) as caught:
            verify_signed_lease(
                raw,
                self.sign(raw),
                self.keys,
                expected_device_id="dev_01",
            )

        self.assertEqual(ErrorCode.OFFLINE_LEASE_DENIED, caught.exception.code)

    def test_offline_state_changes_at_warning_and_expiry_boundaries(self):
        lease = OfflineLease.from_json_bytes(lease_bytes())

        self.assertEqual(
            ClientLicenseState.OFFLINE_VALID,
            lease.client_state_at(datetime(2026, 8, 8, tzinfo=timezone.utc)),
        )
        self.assertEqual(
            ClientLicenseState.OFFLINE_EXPIRING,
            lease.client_state_at(datetime(2026, 8, 10, tzinfo=timezone.utc)),
        )
        self.assertEqual(
            ClientLicenseState.OFFLINE_EXPIRED,
            lease.client_state_at(datetime(2026, 8, 11, 15, 0, 1, tzinfo=timezone.utc)),
        )

    def test_suspended_or_revoked_lease_never_authorizes_offline(self):
        for status, expected in (
            ("suspended", ClientLicenseState.LICENSE_SUSPENDED),
            ("revoked", ClientLicenseState.LICENSE_REVOKED),
        ):
            with self.subTest(status=status):
                lease = OfflineLease.from_json_bytes(lease_bytes(status=status))
                self.assertEqual(
                    expected,
                    lease.client_state_at(datetime(2026, 8, 5, tzinfo=timezone.utc)),
                )


class TrustedTimeStateTests(unittest.TestCase):
    def test_allows_small_clock_correction(self):
        state = TrustedTimeState(
            last_server_time="2026-08-04T15:00:00Z",
            last_wall_clock="2026-08-04T15:00:00Z",
        )

        state.assert_not_rolled_back(
            datetime(2026, 8, 4, 14, 56, tzinfo=timezone.utc),
            tolerance=timedelta(minutes=5),
        )

    def test_rejects_significant_wall_clock_rollback(self):
        state = TrustedTimeState(
            last_server_time="2026-08-04T15:00:00Z",
            last_wall_clock="2026-08-04T15:00:00Z",
        )

        with self.assertRaises(UpdateError) as caught:
            state.assert_not_rolled_back(
                datetime(2026, 8, 4, 14, 40, tzinfo=timezone.utc),
                tolerance=timedelta(minutes=5),
            )

        self.assertEqual(ErrorCode.OFFLINE_LEASE_DENIED, caught.exception.code)

    def test_updates_trusted_server_and_wall_times(self):
        state = TrustedTimeState(
            last_server_time="2026-08-04T15:00:00Z",
            last_wall_clock="2026-08-04T15:00:00Z",
        )

        updated = state.updated(
            server_time=datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
            wall_clock=datetime(2026, 8, 5, 12, 0, 1, tzinfo=timezone.utc),
        )

        self.assertEqual("2026-08-05T12:00:00Z", updated.last_server_time)
        self.assertEqual("2026-08-05T12:00:01Z", updated.last_wall_clock)


if __name__ == "__main__":
    unittest.main()
