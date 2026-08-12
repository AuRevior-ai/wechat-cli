import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from wechat_cli.launcher.service import LauncherService, LauncherStatus
from wechat_cli.license.client import LicenseRejected, LicenseServiceUnavailable
from wechat_cli.license.lease import TrustedTimeState
from wechat_cli.license.models import ValidationResult
from wechat_cli.license.storage import LicenseStateStorage, LocalLicenseState
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.layout import CurrentVersion, InstallLayout
from wechat_cli.update.state import PendingUpdate, save_pending_update
from wechat_cli.update.transaction import UpdateTransactionEngine
from wechat_cli.windows.dpapi import TestOnlyDataProtector


LEASE_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes(reversed(range(32))))
LEASE_PUBLIC_KEY = LEASE_PRIVATE_KEY.public_key().export_key(format="raw")


def signed_lease(*, issued="2026-08-04T15:00:00Z", expires="2026-08-11T15:00:00Z"):
    payload = json.dumps(
        {
            "schema_version": 1,
            "license_id": "lic_01",
            "device_id": "dev_01",
            "status": "active",
            "license_revision": 1,
            "device_revision": 1,
            "issued_at": issued,
            "offline_until": expires,
            "nonce": "lease_nonce",
            "key_id": "lease-key-test-01",
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature = eddsa.new(LEASE_PRIVATE_KEY, "rfc8032").sign(payload)
    return payload, signature


class FakeLicenseClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def validate(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeRuntime:
    def __init__(self, unhealthy_versions=(), stop_error=None):
        self.unhealthy_versions = set(unhealthy_versions)
        self.stop_error = stop_error
        self.starts = []
        self.stops = []
        self.health_checks = []

    def start(self, version, session_path):
        process = {"version": version, "session_path": str(session_path)}
        self.starts.append(process)
        return process

    def wait_healthy(self, version):
        self.health_checks.append(version)
        if version in self.unhealthy_versions:
            raise UpdateError(ErrorCode.UPDATE_HEALTH_FAILED, f"{version} unhealthy")
        return {"status": "ok", "version": version}

    def stop(self, process):
        self.stops.append(process)
        if self.stop_error is not None:
            raise self.stop_error


class LauncherServiceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)
        self.protector = TestOnlyDataProtector(
            b"launcher-service-test",
            allow_insecure_test_use=True,
        )
        self.lease_keys = TrustedEd25519Keys(
            {"lease-key-test-01": LEASE_PUBLIC_KEY}
        )

    def make_layout(self, root: Path):
        layout = InstallLayout(root / "WeChatCliWeb")
        layout.ensure_directories()
        current = layout.version_path("0.4.2")
        current.mkdir()
        (current / "wechat-cli.exe").write_bytes(b"old")
        layout.save_current(
            CurrentVersion(
                current_version="0.4.2",
                previous_version=None,
                channel="stable",
                activated_at="2026-08-04T14:00:00Z",
                manifest_sha256="11" * 32,
            )
        )
        return layout

    def make_storage(self, layout):
        return LicenseStateStorage(
            layout.state_dir / "license-state.dat",
            self.protector,
        )

    def save_state(self, storage):
        lease, signature = signed_lease()
        state = LocalLicenseState(
            license_id="lic_01",
            license_key="WCL-SECRET",
            device_id="dev_01",
            device_token="wcdt_token.secret",
            lease_content=lease,
            lease_signature=signature,
            local_launch_key=b"K" * 32,
            trusted_time=TrustedTimeState(
                last_server_time="2026-08-04T15:00:00Z",
                last_wall_clock="2026-08-04T15:00:00Z",
            ),
        )
        storage.save(state)
        return state

    def online_result(self):
        lease, signature = signed_lease(
            issued="2026-08-05T12:00:00Z",
            expires="2026-08-12T12:00:00Z",
        )
        import base64

        return ValidationResult.from_mapping(
            {
                "license_id": "lic_01",
                "device_id": "dev_01",
                "server_time": "2026-08-05T12:00:00Z",
                "lease_content_base64": base64.b64encode(lease).decode("ascii"),
                "lease_signature_base64": base64.b64encode(signature).decode("ascii"),
            }
        )

    def make_service(self, layout, storage, client, runtime):
        return LauncherService(
            layout=layout,
            state_storage=storage,
            license_client=client,
            lease_keys=self.lease_keys,
            runtime=runtime,
            now=lambda: self.now,
        )

    def test_missing_local_state_requires_activation_without_starting_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            runtime = FakeRuntime()
            service = self.make_service(
                layout,
                self.make_storage(layout),
                FakeLicenseClient(self.online_result()),
                runtime,
            )

            result = service.start()

            self.assertEqual(LauncherStatus.ACTIVATION_REQUIRED, result.status)
            self.assertEqual([], runtime.starts)

    def test_online_validation_refreshes_lease_and_starts_current_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            storage = self.make_storage(layout)
            old_state = self.save_state(storage)
            runtime = FakeRuntime()
            client = FakeLicenseClient(self.online_result())

            result = self.make_service(layout, storage, client, runtime).start()

            self.assertEqual(LauncherStatus.STARTED, result.status)
            self.assertEqual("0.4.2", result.version)
            self.assertEqual(["0.4.2"], [item["version"] for item in runtime.starts])
            self.assertEqual("wcdt_token.secret", client.calls[0]["device_token"])
            refreshed = storage.load()
            self.assertNotEqual(old_state.lease_content, refreshed.lease_content)
            self.assertEqual("2026-08-05T12:00:00Z", refreshed.trusted_time.last_server_time)

    def test_explicit_revocation_blocks_unexpired_offline_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            storage = self.make_storage(layout)
            self.save_state(storage)
            runtime = FakeRuntime()
            rejected = LicenseRejected(ErrorCode.LICENSE_REVOKED, "revoked")

            result = self.make_service(
                layout,
                storage,
                FakeLicenseClient(rejected),
                runtime,
            ).start()

            self.assertEqual(LauncherStatus.BLOCKED, result.status)
            self.assertEqual("license_revoked", result.license_state.value)
            self.assertEqual([], runtime.starts)

    def test_network_failure_uses_verified_unexpired_offline_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            storage = self.make_storage(layout)
            self.save_state(storage)
            runtime = FakeRuntime()

            result = self.make_service(
                layout,
                storage,
                FakeLicenseClient(LicenseServiceUnavailable("offline")),
                runtime,
            ).start()

            self.assertEqual(LauncherStatus.STARTED, result.status)
            self.assertEqual("offline_valid", result.license_state.value)
            self.assertEqual(["0.4.2"], [item["version"] for item in runtime.starts])

    def add_pending_update(self, layout):
        target = layout.version_path("0.5.0")
        target.mkdir()
        (target / "wechat-cli.exe").write_bytes(b"new")
        save_pending_update(
            layout.pending_update_path,
            PendingUpdate(
                release_id="rel_050",
                version="0.5.0",
                prepared_path="versions\\0.5.0",
                manifest_sha256="22" * 32,
                prepared_at="2026-08-05T11:30:00Z",
                install_on_next_start=True,
            ),
        )

    def test_pending_update_commits_after_new_version_health_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            self.add_pending_update(layout)
            storage = self.make_storage(layout)
            self.save_state(storage)
            runtime = FakeRuntime()

            result = self.make_service(
                layout,
                storage,
                FakeLicenseClient(self.online_result()),
                runtime,
            ).start()

            self.assertEqual(LauncherStatus.UPDATED, result.status)
            self.assertEqual("0.5.0", layout.load_current().current_version)
            self.assertFalse(layout.pending_update_path.exists())

    def test_unhealthy_pending_update_rolls_back_and_starts_previous_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            self.add_pending_update(layout)
            storage = self.make_storage(layout)
            self.save_state(storage)
            runtime = FakeRuntime(unhealthy_versions={"0.5.0"})

            result = self.make_service(
                layout,
                storage,
                FakeLicenseClient(self.online_result()),
                runtime,
            ).start()

            self.assertEqual(LauncherStatus.ROLLED_BACK, result.status)
            self.assertEqual("0.4.2", layout.load_current().current_version)
            self.assertEqual(
                ["0.5.0", "0.4.2"],
                [item["version"] for item in runtime.starts],
            )
            self.assertEqual(1, len(runtime.stops))
            self.assertTrue(
                UpdateTransactionEngine(layout).failed_versions.is_failed(
                    "0.5.0", "22" * 32
                )
            )

    def test_candidate_stop_failure_rolls_pointer_back_but_does_not_start_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            self.add_pending_update(layout)
            storage = self.make_storage(layout)
            self.save_state(storage)
            runtime = FakeRuntime(
                unhealthy_versions={"0.5.0"},
                stop_error=OSError("candidate port still occupied"),
            )

            result = self.make_service(
                layout,
                storage,
                FakeLicenseClient(self.online_result()),
                runtime,
            ).start()

            self.assertEqual(LauncherStatus.FAILED, result.status)
            self.assertEqual("0.4.2", layout.load_current().current_version)
            self.assertEqual(
                ["0.5.0"],
                [item["version"] for item in runtime.starts],
            )
            self.assertEqual(1, len(runtime.stops))
            self.assertTrue(
                UpdateTransactionEngine(layout).failed_versions.is_failed(
                    "0.5.0", "22" * 32
                )
            )
            self.assertIn("candidate port still occupied", result.reason or "")


if __name__ == "__main__":
    unittest.main()
