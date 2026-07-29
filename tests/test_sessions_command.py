import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from wechat_cli.main import cli


class SessionsCommandTests(unittest.TestCase):
    def test_json_sessions_include_chat_avatar_url(self):
        fake_cache = MagicMock()
        fake_cache.get.return_value = "session.db"
        fake_app = SimpleNamespace(cache=fake_cache, decrypted_dir="decrypted")
        fake_connection = MagicMock()
        fake_connection.execute.return_value.fetchall.return_value = [
            (
                "room@chatroom",
                2,
                "最新消息",
                1785294000,
                1,
                "wxid_sender",
                "发送者",
            )
        ]

        with patch(
            "wechat_cli.main.AppContext", return_value=fake_app
        ), patch(
            "wechat_cli.commands.sessions.sqlite3.connect",
            return_value=fake_connection,
        ), patch(
            "wechat_cli.commands.sessions.get_contact_names",
            return_value={"room@chatroom": "项目群"},
        ), patch(
            "wechat_cli.commands.sessions.get_contact_avatars",
            return_value={"room@chatroom": "https://wx.qlogo.cn/group/132"},
        ):
            result = CliRunner().invoke(cli, ["sessions", "--limit", "1"])

        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(
            payload[0]["avatar_url"],
            "https://wx.qlogo.cn/group/132",
        )


if __name__ == "__main__":
    unittest.main()
