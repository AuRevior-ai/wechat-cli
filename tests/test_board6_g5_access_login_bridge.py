import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class FakeCallback:
    def __init__(self, *, expected_state: str) -> None:
        self.expected_state = expected_state
        self.callback_url = "http://127.0.0.1:54321/callback"
        self.closed = False

    def wait_for_code(self, *, timeout_seconds: float) -> str:
        if timeout_seconds <= 0:
            raise AssertionError("timeout must be positive")
        return "wcal_test_code"

    def close(self) -> None:
        self.closed = True


class Board6G5AccessLoginBridgeTests(unittest.TestCase):
    def test_manual_bridge_writes_only_transient_url_and_safe_result(self):
        from scripts import board6_g5_access_login_bridge as module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "admin-config.dat"
            url_path = root / "login-url.txt"
            result_path = root / "result.json"
            observed = {}

            def exchange(**kwargs):
                observed.update(kwargs)
                self.assertTrue(url_path.exists())
                url_text = url_path.read_text(encoding="utf-8")
                self.assertIn("challenge=", url_text)
                self.assertIn("redirect_uri=", url_text)
                self.assertNotIn(kwargs["verifier"], url_text)
                return {
                    "session_token": "wcas_adms_test.secret-not-persisted-here",
                    "principal_id": "admin_board6_g5_primary",
                    "expires_at": "2026-08-14T09:00:00Z",
                }

            with mock.patch.object(module, "assert_outside_repository", side_effect=lambda p, **_: Path(p)), mock.patch.object(
                module,
                "generate_login_material",
                return_value=module.AdminLoginMaterial(
                    verifier="verifier-secret-material",
                    challenge="challenge-public-material",
                    state="state_123456789012345678901234",
                ),
            ):
                safe = module.run_manual_login(
                    api_base_url="https://staging-admin.example.test",
                    config_path=config_path,
                    url_file=url_path,
                    result_file=result_path,
                    timeout_seconds=30,
                    callback_factory=FakeCallback,
                    transport_factory=lambda _base: object(),
                    storage_factory=lambda _path: object(),
                    exchange=exchange,
                )

            self.assertEqual(
                {
                    "ok": True,
                    "principal_id": "admin_board6_g5_primary",
                    "expires_at": "2026-08-14T09:00:00Z",
                },
                safe,
            )
            persisted = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(safe, persisted)
            serialized = result_path.read_text(encoding="utf-8")
            self.assertNotIn("session_token", serialized)
            self.assertNotIn("verifier-secret-material", serialized)
            self.assertNotIn("wcal_test_code", serialized)
            self.assertFalse(url_path.exists())
            self.assertEqual("wcal_test_code", observed["code"])
            self.assertEqual("verifier-secret-material", observed["verifier"])


if __name__ == "__main__":
    unittest.main()
