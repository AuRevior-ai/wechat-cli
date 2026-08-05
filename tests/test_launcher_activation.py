import base64
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from wechat_cli.launcher.service import LauncherService
from wechat_cli.license.device_identity import DeviceIdentity
from wechat_cli.license.models import ActivationResult
from wechat_cli.license.storage import LicenseStateStorage
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.layout import CurrentVersion, InstallLayout
from wechat_cli.windows.dpapi import TestOnlyDataProtector


LEASE_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes([7]) * 32)
LEASE_PUBLIC_KEY = LEASE_PRIVATE_KEY.public_key().export_key(format="raw")


def activation_result(*, tamper_signature=False):
    lease = json.dumps(
        {
            "schema_version": 1,
            "license_id": "lic_01",
            "device_id": "dev_01",
            "status": "active",
            "license_revision": 1,
            "device_revision": 1,
            "issued_at": "2026-08-05T12:00:00Z",
            "offline_until": "2026-08-12T12:00:00Z",
            "nonce": "activation-lease",
            "key_id": "lease-key-test-01",
        },
        separators=(",", ":"),
    ).encode("utf-8")
    signature = eddsa.new(LEASE_PRIVATE_KEY, "rfc8032").sign(lease)
    if tamper_signature:
        signature = bytes([signature[0] ^ 1]) + signature[1:]
    return ActivationResult.from_mapping(
        {
            "license_id": "lic_01",
            "device_id": "dev_01",
            "device_token": "wcdt_token.secret",
            "device_count": 1,
            "maximum_devices": 3,
            "lease_content_base64": base64.b64encode(lease).decode("ascii"),
            "lease_signature_base64": base64.b64encode(signature).decode("ascii"),
        }
    )


class FakeActivationClient:
    def __init__(self, result):
        self.result = result
        self.activation_calls = []

    def activate(self, **kwargs):
        self.activation_calls.append(kwargs)
        return self.result

    def validate(self, **_kwargs):
        raise AssertionError("validate should not be called during activation")


class NoopRuntime:
    def start(self, *_args):
        raise AssertionError("app should not start during activation")

    def wait_healthy(self, *_args):
        raise AssertionError("health should not run during activation")

    def stop(self, *_args):
        pass


class LauncherActivationTests(unittest.TestCase):
    def make_service(self, root, client):
        layout = InstallLayout(Path(root) / "WeChatCliWeb")
        layout.ensure_directories()
        version = layout.version_path("0.4.2")
        version.mkdir()
        (version / "wechat-cli.exe").write_bytes(b"app")
        layout.save_current(
            CurrentVersion(
                current_version="0.4.2",
                previous_version=None,
                channel="stable",
                activated_at="2026-08-04T15:00:00Z",
                manifest_sha256="11" * 32,
            )
        )
        storage = LicenseStateStorage(
            layout.state_dir / "license-state.dat",
            TestOnlyDataProtector(
                b"activation-storage",
                allow_insecure_test_use=True,
            ),
        )
        service = LauncherService(
            layout=layout,
            state_storage=storage,
            license_client=client,
            lease_keys=TrustedEd25519Keys(
                {"lease-key-test-01": LEASE_PUBLIC_KEY}
            ),
            runtime=NoopRuntime(),
            now=lambda: datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc),
        )
        return service, storage

    def test_activation_verifies_lease_and_stores_device_credentials(self):
        client = FakeActivationClient(activation_result())
        with tempfile.TemporaryDirectory() as tmp:
            service, storage = self.make_service(tmp, client)

            state = service.activate(
                license_key="WCL-PERMANENT-SECRET",
                identity=DeviceIdentity(
                    device_id="dev_01",
                    fingerprint="ab" * 32,
                    display_name="SURTR-PC",
                ),
            )
            loaded = storage.load()

        self.assertEqual(state, loaded)
        self.assertEqual("WCL-PERMANENT-SECRET", loaded.license_key)
        self.assertEqual("wcdt_token.secret", loaded.device_token)
        self.assertEqual(32, len(loaded.local_launch_key))
        self.assertEqual("WCL-PERMANENT-SECRET", client.activation_calls[0]["license_key"])
        self.assertEqual("ab" * 32, client.activation_calls[0]["device_fingerprint"])

    def test_invalid_server_lease_signature_is_not_saved(self):
        client = FakeActivationClient(activation_result(tamper_signature=True))
        with tempfile.TemporaryDirectory() as tmp:
            service, storage = self.make_service(tmp, client)

            with self.assertRaises(UpdateError) as caught:
                service.activate(
                    license_key="WCL-PERMANENT-SECRET",
                    identity=DeviceIdentity(
                        device_id="dev_01",
                        fingerprint="ab" * 32,
                        display_name="SURTR-PC",
                    ),
                )

            self.assertIsNone(storage.load())

        self.assertEqual(ErrorCode.UPDATE_SIGNATURE_INVALID, caught.exception.code)

    def test_activation_rejects_service_returning_another_device(self):
        result = activation_result()
        mismatched = ActivationResult(
            license_id=result.license_id,
            device_id="dev_other",
            device_token=result.device_token,
            device_count=result.device_count,
            maximum_devices=result.maximum_devices,
            lease_content=result.lease_content,
            lease_signature=result.lease_signature,
        )
        with tempfile.TemporaryDirectory() as tmp:
            service, storage = self.make_service(tmp, FakeActivationClient(mismatched))

            with self.assertRaises(UpdateError) as caught:
                service.activate(
                    license_key="WCL-PERMANENT-SECRET",
                    identity=DeviceIdentity(
                        device_id="dev_01",
                        fingerprint="ab" * 32,
                        display_name="SURTR-PC",
                    ),
                )

        self.assertEqual(ErrorCode.OFFLINE_LEASE_DENIED, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
