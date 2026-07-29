import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.core.ai_package import AiPackageResult
from wechat_cli.main import cli


class AiPackageCommandTests(unittest.TestCase):
    def setUp(self):
        self.fake_app = SimpleNamespace(
            msg_db_keys=[],
            cache=object(),
            decrypted_dir="decrypted",
            db_dir="db_storage",
            all_keys={},
            cfg={"db_dir": "db_storage"},
            config_path="config.json",
            display_name_fn=lambda username, names: names.get(username, username),
        )
        self.chat_ctx = {
            "display_name": "测试群",
            "username": "room@chatroom",
            "is_group": True,
            "db_path": "message.db",
            "message_tables": [],
        }
        self.items = [{
            "id": 1,
            "timestamp": 1785294352,
            "time": "2026-07-29 11:00",
            "type": "text",
            "text": "你好",
            "line": "你好",
        }]

    def invoke(self, args):
        result = AiPackageResult(
            path=str(Path(args[args.index("--output") + 1]).resolve()),
            chat="测试群",
            username="room@chatroom",
            message_count=1,
            assets=[],
            transcription_count=0,
            failures=[],
            messages=self.items,
            copy_text="请总结：你好",
            key_copy_text="你好",
        )
        patches = [
            patch("wechat_cli.main.AppContext", return_value=self.fake_app),
            patch(
                "wechat_cli.commands.ai_package.resolve_chat_context",
                return_value=self.chat_ctx,
            ),
            patch(
                "wechat_cli.commands.ai_package.get_contact_names",
                return_value={},
            ),
            patch(
                "wechat_cli.commands.ai_package.get_contact_avatars",
                return_value={},
            ),
            patch(
                "wechat_cli.commands.ai_package.decrypted_media_db_paths",
                return_value=[],
            ),
            patch(
                "wechat_cli.commands.ai_package.collect_chat_history_items",
                return_value=(self.items, []),
            ),
            patch(
                "wechat_cli.commands.ai_package.ensure_image_keys",
                return_value=("aes-key", 81),
            ),
            patch(
                "wechat_cli.commands.ai_package.build_ai_package",
                return_value=result,
            ),
        ]
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7]:
            return CliRunner().invoke(cli, args), patches[-1].target

    def test_command_is_registered(self):
        result = CliRunner().invoke(cli, ["ai-package", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--output", result.output)
        self.assertIn("--no-transcribe", result.output)

    def test_command_returns_json_and_optional_copy_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ai.zip"
            result, _ = self.invoke([
                "ai-package",
                "测试群",
                "--start-time",
                "2026-07-29",
                "--end-time",
                "2026-07-29",
                "--output",
                str(target),
                "--include-copy-data",
            ])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["chat"], "测试群")
        self.assertEqual(payload["copy_text"], "请总结：你好")
        self.assertEqual(payload["key_copy_text"], "你好")

    def test_command_passes_no_transcribe_to_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "ai.zip"
            with patch(
                "wechat_cli.main.AppContext", return_value=self.fake_app
            ), patch(
                "wechat_cli.commands.ai_package.resolve_chat_context",
                return_value=self.chat_ctx,
            ), patch(
                "wechat_cli.commands.ai_package.get_contact_names",
                return_value={},
            ), patch(
                "wechat_cli.commands.ai_package.get_contact_avatars",
                return_value={},
            ), patch(
                "wechat_cli.commands.ai_package.decrypted_media_db_paths",
                return_value=[],
            ), patch(
                "wechat_cli.commands.ai_package.collect_chat_history_items",
                return_value=(self.items, []),
            ), patch(
                "wechat_cli.commands.ai_package.ensure_image_keys",
                return_value=(None, None),
            ), patch(
                "wechat_cli.commands.ai_package.build_ai_package",
                return_value=AiPackageResult(
                    path=str(target),
                    chat="测试群",
                    username="room@chatroom",
                    message_count=1,
                    assets=[],
                    transcription_count=0,
                    failures=[],
                    messages=[],
                    copy_text="",
                    key_copy_text="",
                ),
            ) as builder:
                result = CliRunner().invoke(cli, [
                    "ai-package",
                    "测试群",
                    "--output",
                    str(target),
                    "--no-transcribe",
                ])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(builder.call_args.kwargs["transcribe_voice"])


if __name__ == "__main__":
    unittest.main()
