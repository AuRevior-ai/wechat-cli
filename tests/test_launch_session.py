import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wechat_cli.license.session import (
    LaunchSessionError,
    consume_launch_session,
    create_launch_session,
)


class LaunchSessionTests(unittest.TestCase):
    def setUp(self):
        self.key = b"K" * 32
        self.now = datetime(2026, 8, 4, 15, 0, tzinfo=timezone.utc)

    def create(self, root: Path, **overrides):
        values = {
            "runtime_dir": root,
            "local_launch_key": self.key,
            "app_version": "0.5.0",
            "device_id": "dev_01",
            "lease_content": b'{"lease":true}',
            "now": self.now,
            "ttl": timedelta(minutes=2),
        }
        values.update(overrides)
        return create_launch_session(**values)

    def test_creates_and_consumes_one_time_version_bound_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.create(Path(tmp))

            session = consume_launch_session(
                path,
                local_launch_key=self.key,
                expected_app_version="0.5.0",
                expected_device_id="dev_01",
                now=self.now + timedelta(seconds=30),
            )

            self.assertEqual("0.5.0", session.app_version)
            self.assertEqual("dev_01", session.device_id)
            self.assertFalse(path.exists())

    def test_consumption_is_one_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.create(Path(tmp))
            consume_launch_session(
                path,
                local_launch_key=self.key,
                expected_app_version="0.5.0",
                expected_device_id="dev_01",
                now=self.now,
            )

            with self.assertRaises(LaunchSessionError):
                consume_launch_session(
                    path,
                    local_launch_key=self.key,
                    expected_app_version="0.5.0",
                    expected_device_id="dev_01",
                    now=self.now,
                )

    def test_rejects_wrong_key_and_deletes_claimed_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.create(Path(tmp))

            with self.assertRaises(LaunchSessionError) as caught:
                consume_launch_session(
                    path,
                    local_launch_key=b"X" * 32,
                    expected_app_version="0.5.0",
                    expected_device_id="dev_01",
                    now=self.now,
                )

            self.assertEqual("signature_invalid", caught.exception.reason)
            self.assertFalse(path.exists())

    def test_rejects_expired_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.create(Path(tmp))

            with self.assertRaises(LaunchSessionError) as caught:
                consume_launch_session(
                    path,
                    local_launch_key=self.key,
                    expected_app_version="0.5.0",
                    expected_device_id="dev_01",
                    now=self.now + timedelta(minutes=3),
                )

            self.assertEqual("expired", caught.exception.reason)

    def test_rejects_future_session_beyond_clock_tolerance(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.create(Path(tmp), now=self.now + timedelta(minutes=10))

            with self.assertRaises(LaunchSessionError) as caught:
                consume_launch_session(
                    path,
                    local_launch_key=self.key,
                    expected_app_version="0.5.0",
                    expected_device_id="dev_01",
                    now=self.now,
                )

            self.assertEqual("not_yet_valid", caught.exception.reason)

    def test_rejects_version_or_device_mismatch(self):
        for expected_version, expected_device, reason in (
            ("0.5.1", "dev_01", "version_mismatch"),
            ("0.5.0", "dev_other", "device_mismatch"),
        ):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp:
                path = self.create(Path(tmp))
                with self.assertRaises(LaunchSessionError) as caught:
                    consume_launch_session(
                        path,
                        local_launch_key=self.key,
                        expected_app_version=expected_version,
                        expected_device_id=expected_device,
                        now=self.now,
                    )
                self.assertEqual(reason, caught.exception.reason)

    def test_tampering_any_signed_field_is_rejected(self):
        import json

        with tempfile.TemporaryDirectory() as tmp:
            path = self.create(Path(tmp))
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["app_version"] = "9.9.9"
            path.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaises(LaunchSessionError) as caught:
                consume_launch_session(
                    path,
                    local_launch_key=self.key,
                    expected_app_version="9.9.9",
                    expected_device_id="dev_01",
                    now=self.now,
                )

            self.assertEqual("signature_invalid", caught.exception.reason)


if __name__ == "__main__":
    unittest.main()
