import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from wechat_cli.license.app_management import AppManagementService
from wechat_cli.license.lease import TrustedTimeState
from wechat_cli.license.models import DeviceRecord, ValidationResult
from wechat_cli.license.storage import LicenseStateStorage, LocalLicenseState
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.layout import CurrentVersion, InstallLayout
from wechat_cli.update.state import PendingUpdate, atomic_write_json, save_pending_update
from wechat_cli.windows.dpapi import TestOnlyDataProtector


LEASE_KEY = ECC.construct(curve="Ed25519", seed=bytes([9]) * 32)
LEASE_PUBLIC = LEASE_KEY.public_key().export_key(format="raw")


def lease_bytes(*, issued="2026-08-04T15:00:00Z", expires="2026-08-11T15:00:00Z"):
    raw = json.dumps(
        {
            "schema_version": 1,
            "license_id": "lic_01",
            "device_id": "dev_01",
            "status": "active",
            "license_revision": 1,
            "device_revision": 1,
            "issued_at": issued,
            "offline_until": expires,
            "nonce": "lease",
            "key_id": "lease-key-test-01",
        },
        separators=(",", ":"),
    ).encode("utf-8")
    return raw, eddsa.new(LEASE_KEY, "rfc8032").sign(raw)


class FakeClient:
    def __init__(self):
        self.validate_calls = []
        self.list_calls = []
        self.unbind_calls = []
        self.rename_calls = []
        self.devices = [
            DeviceRecord(
                device_id="dev_01",
                display_name="SURTR-PC",
                status="active",
                is_current=True,
                last_validated_at="2026-08-05T12:00:00Z",
                last_app_version="0.5.0",
                last_launcher_version="0.1.0",
            ),
            DeviceRecord(
                device_id="dev_02",
                display_name="LAPTOP",
                status="active",
                is_current=False,
                last_validated_at="2026-08-04T12:00:00Z",
                last_app_version="0.4.2",
                last_launcher_version="0.1.0",
            ),
        ]

    def validate(self, **kwargs):
        self.validate_calls.append(kwargs)
        raw, signature = lease_bytes(
            issued="2026-08-05T12:00:00Z",
            expires="2026-08-12T12:00:00Z",
        )
        import base64

        return ValidationResult.from_mapping(
            {
                "license_id": "lic_01",
                "device_id": "dev_01",
                "server_time": "2026-08-05T12:00:00Z",
                "lease_content_base64": base64.b64encode(raw).decode("ascii"),
                "lease_signature_base64": base64.b64encode(signature).decode("ascii"),
            }
        )

    def list_devices(self, token):
        self.list_calls.append(token)
        return list(self.devices)

    def unbind_device(self, token, **kwargs):
        self.unbind_calls.append((token, kwargs))

    def rename_device(self, token, **kwargs):
        self.rename_calls.append((token, kwargs))


class AppManagementServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        self.protector = TestOnlyDataProtector(
            b"app-management",
            allow_insecure_test_use=True,
        )
        self.keys = TrustedEd25519Keys({"lease-key-test-01": LEASE_PUBLIC})

    def make_service(self, root):
        layout = InstallLayout(Path(root) / "WeChatCliWeb")
        layout.ensure_directories()
        for version in ("0.4.2", "0.5.0"):
            version_path = layout.version_path(version)
            version_path.mkdir()
            (version_path / "wechat-cli.exe").write_bytes(version.encode())
        layout.save_current(
            CurrentVersion(
                current_version="0.5.0",
                previous_version="0.4.2",
                channel="stable",
                activated_at="2026-08-05T11:00:00Z",
                manifest_sha256="22" * 32,
            )
        )
        raw, signature = lease_bytes()
        storage = LicenseStateStorage(
            layout.state_dir / "license-state.dat",
            self.protector,
        )
        storage.save(
            LocalLicenseState(
                license_id="lic_01",
                license_key="WCL-SECRET-R4DN",
                device_id="dev_01",
                device_token="wcdt_token.secret",
                lease_content=raw,
                lease_signature=signature,
                local_launch_key=b"K" * 32,
                trusted_time=TrustedTimeState(
                    last_server_time="2026-08-04T15:00:00Z",
                    last_wall_clock="2026-08-04T15:00:00Z",
                ),
            )
        )
        client = FakeClient()
        service = AppManagementService(
            layout=layout,
            storage=storage,
            client=client,
            lease_keys=self.keys,
            now=lambda: self.now,
            update_trigger=lambda: True,
        )
        return service, layout, storage, client

    def test_license_status_masks_secrets_and_reports_offline_deadline(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _layout, _storage, _client = self.make_service(tmp)

            status = service.license_status()

        self.assertEqual("R4DN", status["license_hint"])
        self.assertEqual("offline_valid", status["state"])
        self.assertEqual("2026-08-11T15:00:00Z", status["offline_until"])
        self.assertEqual("0.5.0", status["current_version"])
        self.assertEqual("stable", status["channel"])
        serialized = json.dumps(status)
        self.assertNotIn("WCL-SECRET", serialized)
        self.assertNotIn("wcdt_token", serialized)

    def test_device_list_returns_management_fields_without_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _layout, _storage, client = self.make_service(tmp)

            devices = service.list_devices()

        self.assertEqual(2, len(devices))
        self.assertTrue(devices[0]["is_current"])
        self.assertEqual("LAPTOP", devices[1]["display_name"])
        self.assertNotIn("device_token", json.dumps(devices))
        self.assertEqual(["wcdt_token.secret"], client.list_calls)

    def test_unbind_requires_recent_online_validation_and_rejects_current_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _layout, _storage, client = self.make_service(tmp)

            with self.assertRaises(ValueError):
                service.unbind_device("dev_01", "nonce_current")

            result = service.unbind_device("dev_02", "nonce_other")

        self.assertEqual({"ok": True, "unbound_device_id": "dev_02"}, result)
        self.assertEqual(1, len(client.validate_calls))
        self.assertEqual(
            ("wcdt_token.secret", {"target_device_id": "dev_02", "operation_nonce": "nonce_other"}),
            client.unbind_calls[0],
        )

    def test_rename_validates_name_and_current_online_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _layout, _storage, client = self.make_service(tmp)

            with self.assertRaises(ValueError):
                service.rename_device("dev_02", "", "nonce")
            result = service.rename_device("dev_02", "WORK LAPTOP", "nonce_01")

        self.assertEqual({"ok": True, "device_id": "dev_02"}, result)
        self.assertEqual("WORK LAPTOP", client.rename_calls[0][1]["display_name"])

    def test_update_status_reports_pending_and_local_progress_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, layout, _storage, _client = self.make_service(tmp)
            save_pending_update(
                layout.pending_update_path,
                PendingUpdate(
                    release_id="rel_051",
                    version="0.5.1",
                    prepared_path="versions\\0.5.1",
                    manifest_sha256="33" * 32,
                    prepared_at="2026-08-05T12:00:00Z",
                    install_on_next_start=True,
                ),
            )
            atomic_write_json(
                layout.update_status_path,
                {
                    "status": "downloading",
                    "target_version": "0.5.1",
                    "downloaded_bytes": 25,
                    "expected_size": 100,
                },
            )

            status = service.update_status()

        self.assertEqual("0.5.1", status["pending_version"])
        self.assertEqual(25, status["downloaded_bytes"])
        self.assertEqual(100, status["expected_size"])
        self.assertEqual(25, status["progress_percent"])
        self.assertNotIn("manifest_sha256", status)

    def test_trigger_update_check_delegates_without_returning_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            service, _layout, _storage, _client = self.make_service(tmp)

            result = service.trigger_update_check()

        self.assertEqual({"ok": True, "started": True}, result)


if __name__ == "__main__":
    unittest.main()
