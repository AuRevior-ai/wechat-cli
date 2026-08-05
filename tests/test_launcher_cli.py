import unittest
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.launcher.cli import cli


class LauncherCliTests(unittest.TestCase):
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
