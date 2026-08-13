import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.admin.cli import cli


class FakeClient:
    def __init__(self):
        self.calls = []

    def create_license(self, **kwargs):
        self.calls.append(("create_license", kwargs))
        return {
            "license_id": "lic_01",
            "license_key": "WCL-AAAA-BBBB-CCCC-DDDD",
            "license_hint": "DDDD",
            "status": "active",
            "maximum_devices": kwargs["maximum_devices"],
            "release_channel": kwargs["release_channel"],
            "created_at": "2026-08-05T00:00:00Z",
        }

    def batch_create_licenses(self, **kwargs):
        self.calls.append(("batch_create_licenses", kwargs))
        return [
            {
                "license_id": "lic_01",
                "license_key": "WCL-AAAA-BBBB-CCCC-DDDD",
                "license_hint": "DDDD",
                "maximum_devices": kwargs["maximum_devices"],
                "release_channel": kwargs["release_channel"],
                "created_at": "2026-08-05T00:00:00Z",
            }
        ]

    def list_licenses(self, **kwargs):
        self.calls.append(("list_licenses", kwargs))
        return [
            {
                "license_id": "lic_01",
                "license_hint": "DDDD",
                "status": "active",
                "maximum_devices": 3,
                "active_devices": 1,
                "release_channel": "stable",
            }
        ]

    def set_license_status(self, license_id, status, operation_nonce):
        self.calls.append(
            (
                "set_license_status",
                {
                    "license_id": license_id,
                    "status": status,
                    "operation_nonce": operation_nonce,
                },
            )
        )
        return {"ok": True, "license_id": license_id, "status": status}

    def list_releases(self):
        self.calls.append(("list_releases", {}))
        return []

    def list_diagnostics(self):
        self.calls.append(("list_diagnostics", {}))
        return []

    def contact_encryption_status(self):
        self.calls.append(("contact_encryption_status", {}))
        return {"current_key_version": 1, "records_by_version": []}

    def rotate_contact_encryption(self, **kwargs):
        self.calls.append(("rotate_contact_encryption", kwargs))
        return {
            "ok": True,
            "current_key_version": 2,
            "rotated_count": kwargs["limit"],
            "remaining_count": 0,
        }


class AdminCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.client = FakeClient()
        self.client_patch = patch(
            "wechat_cli.admin.cli._load_client",
            return_value=self.client,
        )
        self.client_patch.start()
        self.addCleanup(self.client_patch.stop)

    def test_help_lists_administrator_workflows(self):
        result = self.runner.invoke(cli, ["--help"])

        self.assertEqual(0, result.exit_code, result.output)
        for command in (
            "bootstrap",
            "config",
            "login",
            "licenses",
            "devices",
            "releases",
            "diagnostics",
            "contacts",
        ):
            self.assertIn(command, result.output)

    @patch("wechat_cli.admin.cli.login_and_store_admin_session", create=True)
    def test_login_uses_browser_session_flow_without_echoing_session_token(self, login):
        login.return_value = {
            "principal_id": "prn_admin_1",
            "expires_at": "2099-01-01T00:30:00Z",
            "session_token": "wcas_adms_identifier123456.secret_value_abcdefghijklmnopqrstuvwxyz123456",
        }
        result = self.runner.invoke(
            cli,
            [
                "--json",
                "login",
                "--api-url",
                "https://admin.example.test",
                "--environment",
                "production",
            ],
        )

        self.assertEqual(0, result.exit_code, result.output)
        payload = json.loads(result.output)
        self.assertEqual("prn_admin_1", payload["principal_id"])
        self.assertEqual("2099-01-01T00:30:00Z", payload["expires_at"])
        self.assertNotIn("session_token", payload)
        self.assertNotIn("secret_value", result.output)
        login.assert_called_once()

    @patch("wechat_cli.admin.cli.write_demo_bootstrap")
    @patch("wechat_cli.admin.cli.generate_demo_bootstrap")
    def test_bootstrap_demo_writes_artifacts_without_echoing_token(
        self,
        generate,
        write,
    ):
        artifacts = type(
            "Artifacts",
            (),
            {"admin_token": "wcadmin_adm_secret.identifier"},
        )()
        generate.return_value = artifacts
        write.return_value = {
            "worker_secrets": Path("out/.dev.vars"),
            "admin_sql": Path("out/bootstrap-admin.sql"),
            "admin_token": Path("out/admin-token.txt"),
            "public_keys": Path("out/launcher-public-keys.json"),
            "instructions": Path("out/README.txt"),
        }

        result = self.runner.invoke(
            cli,
            ["--json", "bootstrap", "demo", "--output-dir", "out"],
        )

        self.assertEqual(0, result.exit_code, result.output)
        payload = json.loads(result.output)
        self.assertEqual("out/admin-token.txt", payload["admin_token"])
        self.assertNotIn("wcadmin_adm_secret.identifier", result.output)
        generate.assert_called_once()
        write.assert_called_once_with(Path("out"), artifacts)

    def test_create_license_never_echoes_admin_token_and_supports_json(self):
        result = self.runner.invoke(
            cli,
            [
                "--json",
                "licenses",
                "create",
                "--maximum-devices",
                "3",
                "--email",
                "user@example.com",
            ],
        )

        self.assertEqual(0, result.exit_code, result.output)
        payload = json.loads(result.output)
        self.assertEqual("WCL-AAAA-BBBB-CCCC-DDDD", payload["license_key"])
        self.assertNotIn("wcadmin", result.output)
        call = self.client.calls[0]
        self.assertEqual("create_license", call[0])
        self.assertEqual("user@example.com", call[1]["contacts"]["email"])
        self.assertGreaterEqual(len(call[1]["operation_nonce"]), 8)

    def test_batch_create_exports_non_overwriting_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "licenses.csv"
            result = self.runner.invoke(
                cli,
                [
                    "licenses",
                    "batch-create",
                    "--count",
                    "1",
                    "--output",
                    str(output),
                ],
            )

            self.assertEqual(0, result.exit_code, result.output)
            self.assertTrue(output.is_file())
            self.assertIn("已写入", result.output)
            second = self.runner.invoke(
                cli,
                [
                    "licenses",
                    "batch-create",
                    "--count",
                    "1",
                    "--output",
                    str(output),
                ],
            )
            self.assertNotEqual(0, second.exit_code)
            self.assertIn("已存在", second.output)

    def test_license_status_uses_separate_suspend_resume_revoke_values(self):
        for status in ("suspended", "active", "revoked"):
            with self.subTest(status=status):
                result = self.runner.invoke(
                    cli,
                    ["licenses", "status", "lic_01", status],
                )
                self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(
            ["suspended", "active", "revoked"],
            [
                call[1]["status"]
                for call in self.client.calls
                if call[0] == "set_license_status"
            ],
        )

    def test_contact_rotation_uses_bounded_batch_and_nonce(self):
        result = self.runner.invoke(
            cli,
            ["--json", "contacts", "rotate", "--limit", "25"],
        )

        self.assertEqual(0, result.exit_code, result.output)
        payload = json.loads(result.output)
        self.assertEqual(25, payload["rotated_count"])
        call = self.client.calls[0]
        self.assertEqual("rotate_contact_encryption", call[0])
        self.assertEqual(25, call[1]["limit"])
        self.assertGreaterEqual(len(call[1]["operation_nonce"]), 8)

    def test_json_lists_are_machine_readable(self):
        result = self.runner.invoke(
            cli,
            ["--json", "licenses", "list", "--status", "active"],
        )

        self.assertEqual(0, result.exit_code, result.output)
        payload = json.loads(result.output)
        self.assertEqual("lic_01", payload[0]["license_id"])
        self.assertEqual("active", self.client.calls[0][1]["status"])


if __name__ == "__main__":
    unittest.main()
