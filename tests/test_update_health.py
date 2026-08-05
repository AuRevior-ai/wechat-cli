import unittest

from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.health import (
    build_health_payload,
    validate_health_payload,
    wait_for_health,
)


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.value += seconds


class HealthPayloadTests(unittest.TestCase):
    def test_build_health_payload_contains_required_contract(self):
        payload = build_health_payload(
            config_loaded=True,
            license_session_valid=True,
            core_modules={"server": "ok", "storage": "ok", "routes": "ok"},
        )

        self.assertEqual("ok", payload["status"])
        self.assertEqual("wechat-cli-web", payload["product"])
        self.assertIn("version", payload)
        self.assertIn("build_id", payload)
        self.assertTrue(payload["config_loaded"])
        self.assertTrue(payload["license_session_valid"])

    def test_validate_health_payload_accepts_expected_application(self):
        payload = {
            "status": "ok",
            "product": "wechat-cli-web",
            "version": "0.5.0",
            "build_id": "20260804.1",
            "config_loaded": True,
            "license_session_valid": True,
            "core_modules": {"server": "ok", "storage": "ok", "routes": "ok"},
        }

        result = validate_health_payload(
            payload,
            expected_product="wechat-cli-web",
            expected_version="0.5.0",
            expected_build_id="20260804.1",
        )

        self.assertEqual(payload, result)

    def test_validate_health_payload_rejects_wrong_version_and_bad_module(self):
        cases = [
            ({"version": "0.5.1"}, "wrong version"),
            ({"core_modules": {"server": "ok", "storage": "error", "routes": "ok"}}, "bad module"),
            ({"license_session_valid": False}, "invalid license session"),
        ]
        base = {
            "status": "ok",
            "product": "wechat-cli-web",
            "version": "0.5.0",
            "build_id": "20260804.1",
            "config_loaded": True,
            "license_session_valid": True,
            "core_modules": {"server": "ok", "storage": "ok", "routes": "ok"},
        }
        for override, label in cases:
            with self.subTest(label=label):
                payload = dict(base)
                payload.update(override)
                with self.assertRaises(UpdateError) as caught:
                    validate_health_payload(
                        payload,
                        expected_product="wechat-cli-web",
                        expected_version="0.5.0",
                        expected_build_id="20260804.1",
                    )
                self.assertEqual(ErrorCode.UPDATE_HEALTH_FAILED, caught.exception.code)


class WaitForHealthTests(unittest.TestCase):
    def test_retries_transient_failures_until_valid_payload(self):
        clock = FakeClock()
        responses = [OSError("not listening"), {"status": "starting"}, {
            "status": "ok",
            "product": "wechat-cli-web",
            "version": "0.5.0",
            "build_id": "20260804.1",
            "config_loaded": True,
            "license_session_valid": True,
            "core_modules": {"server": "ok", "storage": "ok", "routes": "ok"},
        }]

        def fetch():
            value = responses.pop(0)
            if isinstance(value, Exception):
                raise value
            return value

        payload = wait_for_health(
            fetch,
            expected_product="wechat-cli-web",
            expected_version="0.5.0",
            expected_build_id="20260804.1",
            timeout_seconds=5,
            interval_seconds=1,
            monotonic=clock.monotonic,
            sleep=clock.sleep,
        )

        self.assertEqual("ok", payload["status"])
        self.assertEqual(2.0, clock.value)

    def test_timeout_reports_last_failure(self):
        clock = FakeClock()

        with self.assertRaises(UpdateError) as caught:
            wait_for_health(
                lambda: (_ for _ in ()).throw(OSError("connection refused")),
                expected_product="wechat-cli-web",
                expected_version="0.5.0",
                timeout_seconds=2,
                interval_seconds=1,
                monotonic=clock.monotonic,
                sleep=clock.sleep,
            )

        self.assertEqual(ErrorCode.UPDATE_HEALTH_FAILED, caught.exception.code)
        self.assertIn("connection refused", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
