import inspect
import tempfile
import unittest
from pathlib import Path

from wechat_cli.admin.config import AdminConfig, AdminConfigStorage
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.windows.dpapi import TestOnlyDataProtector


class AdminConfigTests(unittest.TestCase):
    def setUp(self):
        self.protector = TestOnlyDataProtector(
            b"admin-config-tests",
            allow_insecure_test_use=True,
        )

    def test_v2_config_contract_supports_short_lived_session_without_promoting_legacy(self):
        parameters = inspect.signature(AdminConfig).parameters
        for name in (
            "environment",
            "session_token",
            "session_expires_at",
            "legacy_admin_token",
        ):
            self.assertIn(name, parameters)

        session = AdminConfig(
            api_base_url="https://api.example.test",
            environment="production",
            session_token="wcas_adms_identifier123456.secret_value_abcdefghijklmnopqrstuvwxyz123456",
            session_expires_at="2099-01-01T00:30:00Z",
        )
        self.assertTrue(session.api_credential().startswith("wcas_"))
        self.assertNotIn("secret_value", repr(session))
        mapping = session.to_mapping()
        self.assertEqual(2, mapping["schema_version"])
        self.assertNotIn("admin_token", mapping)

        legacy = AdminConfig.from_mapping(
            {
                "schema_version": 1,
                "api_base_url": "https://api.example.test",
                "admin_token": "wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
                "allow_insecure_loopback": False,
            }
        )
        self.assertIsNone(legacy.session_token)
        self.assertTrue(legacy.legacy_admin_token.startswith("wcadmin_"))
        with self.assertRaises(ValueError):
            legacy.api_credential()

    def test_validates_https_and_admin_token_format(self):
        config = AdminConfig(
            api_base_url="https://api.example.test",
            admin_token="wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
        )

        self.assertEqual("https://api.example.test", config.api_base_url)
        self.assertNotIn("secret_value", repr(config))

    def test_rejects_http_except_explicit_loopback_development(self):
        with self.assertRaises(ValueError):
            AdminConfig(
                api_base_url="http://api.example.test",
                admin_token="wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
            )

        config = AdminConfig(
            api_base_url="http://127.0.0.1:8788",
            admin_token="wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
            allow_insecure_loopback=True,
        )
        self.assertEqual("http://127.0.0.1:8788", config.api_base_url)

    def test_encrypted_storage_round_trip_contains_no_plaintext(self):
        config = AdminConfig(
            api_base_url="https://api.example.test",
            admin_token="wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admin-config.dat"
            storage = AdminConfigStorage(path, self.protector)

            storage.save(config)
            raw = path.read_bytes()
            loaded = storage.load()

        self.assertEqual(config, loaded)
        self.assertNotIn(b"api.example.test", raw)
        self.assertNotIn(b"secret_value", raw)

    def test_missing_config_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AdminConfigStorage(
                Path(tmp) / "missing.dat",
                self.protector,
            )
            self.assertIsNone(storage.load())

    def test_wrong_protector_reports_corrupt_state(self):
        other = TestOnlyDataProtector(
            b"other-admin-config-tests",
            allow_insecure_test_use=True,
        )
        config = AdminConfig(
            api_base_url="https://api.example.test",
            admin_token="wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "admin-config.dat"
            AdminConfigStorage(path, self.protector).save(config)

            with self.assertRaises(UpdateError) as caught:
                AdminConfigStorage(path, other).load()

        self.assertEqual(ErrorCode.LOCAL_STATE_CORRUPT, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
