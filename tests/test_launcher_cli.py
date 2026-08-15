import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import wechat_cli.launcher.cli as launcher_cli_module

from click.testing import CliRunner

from wechat_cli.launcher.cli import cli


class LauncherCliTests(unittest.TestCase):
    def test_launcher_runtime_exposes_embedded_trust_profile_loader(self):
        self.assertTrue(hasattr(launcher_cli_module, "load_embedded_trust_profile"))

    @patch("wechat_cli.launcher.cli.LauncherService")
    @patch("wechat_cli.launcher.cli.LocalApplicationRuntime")
    @patch("wechat_cli.launcher.cli.LicenseApiClient")
    @patch("wechat_cli.launcher.cli.LicenseStateStorage")
    @patch("wechat_cli.launcher.cli.WindowsDpapiProtector")
    @patch("wechat_cli.launcher.cli._transport")
    def test_build_service_applies_embedded_windows_publisher_policy(
        self,
        _transport,
        _protector,
        _storage,
        _license_client,
        runtime_type,
        _service_type,
    ):
        layout = MagicMock()
        layout.state_dir = Path("C:/fake/state")
        config = MagicMock()
        config.port = 8787
        config.lease_keys = object()
        config.windows_publisher_policy = "CN=Expected Publisher"

        launcher_cli_module._build_service(layout, config)

        policy = runtime_type.call_args.kwargs.get("authenticode_policy")
        self.assertIsNotNone(policy)
        self.assertTrue(policy.required)
        self.assertEqual("CN=Expected Publisher", policy.expected_subject)

    @patch("wechat_cli.launcher.cli.LauncherService")
    @patch("wechat_cli.launcher.cli.LocalApplicationRuntime")
    @patch("wechat_cli.launcher.cli.LicenseApiClient")
    @patch("wechat_cli.launcher.cli.LicenseStateStorage")
    @patch("wechat_cli.launcher.cli.WindowsDpapiProtector")
    @patch("wechat_cli.launcher.cli._transport")
    def test_build_service_private_profile_disables_authenticode_requirement(
        self,
        _transport,
        _protector,
        _storage,
        _license_client,
        runtime_type,
        _service_type,
    ):
        layout = MagicMock()
        layout.state_dir = Path("C:/fake/state")
        config = MagicMock()
        config.port = 8787
        config.lease_keys = object()
        config.windows_publisher_policy = ""

        launcher_cli_module._build_service(layout, config)

        policy = runtime_type.call_args.kwargs.get("authenticode_policy")
        self.assertIsNotNone(policy)
        self.assertFalse(policy.required)
        self.assertIsNone(policy.expected_subject)

    @patch("wechat_cli.launcher.cli._repair", return_value=0)
    @patch("wechat_cli.launcher.cli.read_current_user_sid", return_value="S-1-5-21-test")
    @patch("wechat_cli.launcher.cli.LauncherInstanceLock")
    @patch("wechat_cli.launcher.cli.LauncherConfig.load")
    @patch("wechat_cli.launcher.cli.load_embedded_trust_profile")
    @patch("wechat_cli.launcher.cli.InstallLayout.from_environment")
    def test_run_mode_loads_embedded_trust_profile_before_external_config(
        self,
        layout_from_environment,
        load_profile,
        load_config,
        lock_type,
        _read_sid,
        _repair,
    ):
        layout = MagicMock()
        layout.launcher_dir = Path("C:/fake/launcher")
        layout_from_environment.return_value = layout
        profile = object()
        load_profile.return_value = profile
        lock = MagicMock()
        lock.__enter__.return_value = lock
        lock.__exit__.return_value = False
        lock_type.return_value = lock

        result = launcher_cli_module.run_launcher_mode(
            "repair",
            config_path="C:/fake/launcher/launcher-config.json",
        )

        self.assertEqual(0, result)
        load_profile.assert_called_once_with()
        load_config.assert_called_once_with(
            Path("C:/fake/launcher/launcher-config.json"),
            allow_insecure_loopback=False,
            trust_profile=profile,
        )

    def setUp(self):
        self.runner = CliRunner()

    def test_help_exposes_modes_but_no_license_key_option(self):
        result = self.runner.invoke(cli, ["--help"])

        self.assertEqual(0, result.exit_code, result.output)
        self.assertIn("--activate", result.output)
        self.assertIn("--download-update", result.output)
        self.assertIn("--apply-update", result.output)
        self.assertIn("--repair", result.output)
        self.assertNotIn("--license-key", result.output)

    def test_modes_are_mutually_exclusive(self):
        result = self.runner.invoke(cli, ["--repair", "--download-update"])

        self.assertNotEqual(0, result.exit_code)
        self.assertIn("only one launcher mode", result.output.lower())

    @patch("wechat_cli.launcher.cli.run_launcher_mode", return_value=0)
    def test_default_mode_runs_start(self, run_mode):
        result = self.runner.invoke(cli, [])

        self.assertEqual(0, result.exit_code, result.output)
        run_mode.assert_called_once_with("start", config_path=None)

    @patch("wechat_cli.launcher.cli.run_launcher_mode", return_value=0)
    def test_activate_opens_local_ui_without_console_key_input(self, run_mode):
        result = self.runner.invoke(cli, ["--activate"])

        self.assertEqual(0, result.exit_code, result.output)
        run_mode.assert_called_once_with("activate", config_path=None)
        self.assertNotIn("许可证密钥:", result.output)

    @patch("wechat_cli.launcher.cli.run_launcher_mode", return_value=3)
    def test_nonzero_mode_result_becomes_cli_exit_code(self, run_mode):
        result = self.runner.invoke(cli, ["--repair"])

        self.assertEqual(3, result.exit_code)
        run_mode.assert_called_once_with("repair", config_path=None)


if __name__ == "__main__":
    unittest.main()
