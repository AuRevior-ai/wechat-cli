import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.core.invite_stats import (
    format_invite_stats_csv,
    format_invite_stats_text,
)
from wechat_cli.main import cli


SAMPLE = {
    "chat": "测试群",
    "username": "room@chatroom",
    "scope": {
        "first_visible_system_time": "2026-07-23 18:36",
        "last_visible_system_time": "2026-07-28 09:54",
    },
    "summary": {
        "system_message_count": 10,
        "invite_event_count": 3,
        "attributed_event_count": 3,
        "unique_invitee_count": 2,
        "unattributed_count": 0,
        "unresolved_identity_count": 0,
        "unparsed_count": 0,
    },
    "ranking": [{
        "rank": 1,
        "inviter_key": "user:wxid_a",
        "inviter_username": "wxid_a",
        "inviter_name": "甲",
        "historical_names": ["甲"],
        "identity_status": "resolved",
        "identity_source": "member_exact",
        "unique_invitee_count": 2,
        "event_count": 3,
        "direct_count": 2,
        "qr_count": 1,
        "first_invite_time": "2026-07-23 18:40",
        "last_invite_time": "2026-07-24 10:00",
        "invitees": [],
    }],
    "events": [{
        "event_id": "1:0",
        "server_id": 1,
        "rank": 1,
        "timestamp": 1,
        "time": "2026-07-23 18:40",
        "method": "direct",
        "inviter_name_raw": "甲",
        "inviter_username": "wxid_a",
        "inviter_key": "user:wxid_a",
        "inviter_identity_status": "resolved",
        "inviter_identity_source": "member_exact",
        "invitee_name_raw": "乙",
        "invitee_username": "wxid_b",
        "invitee_key": "user:wxid_b",
        "invitee_identity_status": "resolved",
        "invitee_identity_source": "member_exact",
        "raw_text": '"甲"邀请"乙"加入了群聊',
    }],
    "unattributed_events": [],
    "unparsed_messages": [],
    "failures": [],
}


class InviteFormatterTests(unittest.TestCase):
    def test_text_contains_rank_and_stable_identity(self):
        text = format_invite_stats_text(SAMPLE)

        self.assertIn("1. 甲 (wxid_a) — 2 人", text)
        self.assertIn("直接 2 / 二维码 1 / 事件 3", text)

    def test_csv_has_bom_and_relation_columns(self):
        text = format_invite_stats_csv(SAMPLE)

        self.assertTrue(text.startswith("\ufeff"))
        self.assertIn("邀请者排名,邀请者,邀请者账号,邀请者身份状态", text)
        self.assertIn("1,甲,wxid_a", text)


class InviteStatsCommandTests(unittest.TestCase):
    def setUp(self):
        self.fake_app = SimpleNamespace(
            msg_db_keys=[],
            cache=object(),
            decrypted_dir="decrypted",
        )
        self.chat_ctx = {
            "display_name": "测试群",
            "username": "room@chatroom",
            "is_group": True,
            "db_path": "message.db",
            "message_tables": [],
        }

    def invoke(self, args):
        with patch(
            "wechat_cli.main.AppContext", return_value=self.fake_app
        ), patch(
            "wechat_cli.commands.invite_stats.resolve_chat_context",
            return_value=self.chat_ctx,
        ), patch(
            "wechat_cli.commands.invite_stats.get_group_members",
            return_value={"members": [], "owner": ""},
        ), patch(
            "wechat_cli.commands.invite_stats.collect_group_invite_stats",
            return_value=SAMPLE,
        ):
            return CliRunner().invoke(cli, args)

    def test_command_is_registered(self):
        with patch("wechat_cli.main.AppContext", return_value=self.fake_app):
            result = CliRunner().invoke(cli, ["invite-stats", "--help"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--bind-identity", result.output)
        self.assertIn("--output", result.output)

    def test_command_outputs_authoritative_json(self):
        result = self.invoke(["invite-stats", "测试群"])

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('"ranking"', result.output)
        self.assertIn('"wxid_a"', result.output)

    def test_command_adds_local_username_to_chat_context(self):
        self.fake_app.db_dir = "db_storage"
        with patch(
            "wechat_cli.main.AppContext", return_value=self.fake_app
        ), patch(
            "wechat_cli.commands.invite_stats.resolve_chat_context",
            return_value=self.chat_ctx,
        ), patch(
            "wechat_cli.commands.invite_stats.get_group_members",
            return_value={"members": [], "owner": ""},
        ), patch(
            "wechat_cli.commands.invite_stats.get_self_username",
            create=True,
            return_value="wxid_me",
        ) as get_self, patch(
            "wechat_cli.commands.invite_stats.collect_group_invite_stats",
            return_value=SAMPLE,
        ) as collect:
            result = CliRunner().invoke(
                cli, ["invite-stats", "测试群"]
            )

        self.assertEqual(result.exit_code, 0, result.output)
        get_self.assert_called_once_with(
            "db_storage",
            self.fake_app.cache,
            self.fake_app.decrypted_dir,
        )
        self.assertEqual(
            collect.call_args.args[0]["self_username"],
            "wxid_me",
        )

    def test_command_writes_csv_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "invite.csv"
            result = self.invoke([
                "invite-stats", "测试群",
                "--format", "csv",
                "--output", str(target),
            ])
            raw = target.read_bytes()

        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_command_reports_unwritable_output_as_click_error(self):
        result = self.invoke([
            "invite-stats", "测试群",
            "--format", "csv",
            "--output", "missing/parent/invite.csv",
        ])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("无法写入输出文件", result.output)


if __name__ == "__main__":
    unittest.main()
