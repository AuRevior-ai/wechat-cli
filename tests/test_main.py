import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.main import cli
from wechat_cli.main import _configure_utf8_stdio


class FakeStream:
    def __init__(self):
        self.calls = []

    def reconfigure(self, **kwargs):
        self.calls.append(kwargs)


class MainTests(unittest.TestCase):
    def test_release_version_is_0_5_0(self):
        result = CliRunner().invoke(cli, ["--version"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("0.5.0", result.output)

    def test_configure_utf8_stdio_reconfigures_stdout_and_stderr(self):
        stdout = FakeStream()
        stderr = FakeStream()

        _configure_utf8_stdio(stdout, stderr)

        self.assertEqual(stdout.calls, [{"encoding": "utf-8", "errors": "replace"}])
        self.assertEqual(stderr.calls, [{"encoding": "utf-8", "errors": "replace"}])

    def test_web_command_starts_without_loading_app_context(self):
        runner = CliRunner()
        with patch("wechat_cli.main.AppContext", side_effect=AssertionError("should not load AppContext")):
            with patch("wechat_cli.commands.web.serve") as serve:
                result = runner.invoke(cli, ["web", "--port", "9999"])

        self.assertEqual(result.exit_code, 0, result.output)
        serve.assert_called_once_with(port=9999, open_browser=False)

    def test_force_init_reuses_configured_database_directory(self):
        runner = CliRunner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            db_dir.mkdir()
            config_file = root / "config.json"
            config_file.write_text(
                json.dumps({"db_dir": str(db_dir)}), encoding="utf-8"
            )
            keys_file = root / "all_keys.json"
            keys_file.write_text("{}", encoding="utf-8")

            with patch(
                "wechat_cli.commands.init.CONFIG_FILE", str(config_file)
            ), patch(
                "wechat_cli.commands.init.KEYS_FILE", str(keys_file)
            ), patch(
                "wechat_cli.commands.init.STATE_DIR", str(root)
            ), patch(
                "wechat_cli.commands.init.auto_detect_db_dir",
                side_effect=AssertionError("should reuse configured db_dir"),
            ), patch(
                "wechat_cli.keys.extract_keys",
                return_value={"salt": "key"},
            ) as extract:
                result = runner.invoke(cli, ["init", "--force"])

        self.assertEqual(result.exit_code, 0, result.output)
        extract.assert_called_once_with(str(db_dir), str(keys_file))


if __name__ == "__main__":
    unittest.main()
