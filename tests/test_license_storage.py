import os
import tempfile
import unittest
from pathlib import Path

from wechat_cli.license.lease import TrustedTimeState
from wechat_cli.license.storage import LicenseStateStorage, LocalLicenseState
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.windows.dpapi import TestOnlyDataProtector, WindowsDpapiProtector


class LicenseStateStorageTests(unittest.TestCase):
    def make_state(self):
        return LocalLicenseState(
            license_id="lic_01",
            license_key="WCL-SECRET-KEY",
            device_id="dev_01",
            device_token="wcdt_token.secret",
            lease_content=b'{"lease":true}',
            lease_signature=b"signature",
            local_launch_key=b"L" * 32,
            trusted_time=TrustedTimeState(
                last_server_time="2026-08-04T15:00:00Z",
                last_wall_clock="2026-08-04T15:00:01Z",
            ),
        )

    def test_round_trips_encrypted_state_without_plaintext_on_disk(self):
        protector = TestOnlyDataProtector(
            b"storage-test-key",
            allow_insecure_test_use=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-state.dat"
            storage = LicenseStateStorage(path, protector)
            state = self.make_state()

            storage.save(state)
            raw = path.read_bytes()
            loaded = storage.load()

        self.assertEqual(state, loaded)
        self.assertNotIn(b"WCL-SECRET-KEY", raw)
        self.assertNotIn(b"wcdt_token.secret", raw)
        self.assertNotIn(b"dev_01", raw)

    def test_missing_state_returns_none(self):
        protector = TestOnlyDataProtector(b"test", allow_insecure_test_use=True)
        with tempfile.TemporaryDirectory() as tmp:
            storage = LicenseStateStorage(Path(tmp) / "missing.dat", protector)
            self.assertIsNone(storage.load())

    def test_wrong_protector_or_corrupt_file_reports_local_state_corrupt(self):
        first = TestOnlyDataProtector(b"first", allow_insecure_test_use=True)
        second = TestOnlyDataProtector(b"second", allow_insecure_test_use=True)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license-state.dat"
            LicenseStateStorage(path, first).save(self.make_state())

            with self.assertRaises(UpdateError) as caught:
                LicenseStateStorage(path, second).load()

        self.assertEqual(ErrorCode.LOCAL_STATE_CORRUPT, caught.exception.code)

    def test_repr_does_not_expose_secret_fields(self):
        text = repr(self.make_state())

        self.assertNotIn("WCL-SECRET-KEY", text)
        self.assertNotIn("wcdt_token.secret", text)
        self.assertNotIn("signature", text)
        self.assertNotIn("LLLL", text)

    def test_test_only_protector_requires_explicit_unsafe_opt_in(self):
        with self.assertRaises(RuntimeError):
            TestOnlyDataProtector(b"test")


@unittest.skipUnless(os.name == "nt", "Windows DPAPI is only available on Windows")
class WindowsDpapiTests(unittest.TestCase):
    def test_current_user_dpapi_round_trip(self):
        protector = WindowsDpapiProtector()
        entropy = b"wechat-cli-test-entropy"
        plaintext = b"sensitive local state"

        protected = protector.protect(plaintext, entropy=entropy)
        restored = protector.unprotect(protected, entropy=entropy)

        self.assertNotEqual(plaintext, protected)
        self.assertEqual(plaintext, restored)

    def test_wrong_entropy_cannot_decrypt(self):
        protector = WindowsDpapiProtector()
        protected = protector.protect(b"secret", entropy=b"correct")

        with self.assertRaises(OSError):
            protector.unprotect(protected, entropy=b"wrong")


if __name__ == "__main__":
    unittest.main()
