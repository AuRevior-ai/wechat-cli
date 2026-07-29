import unittest
import hashlib
import os
import tempfile
from datetime import datetime
from pathlib import Path
from unittest import mock

from wechat_cli.core.messages import (
    _build_history_item,
    find_unkeyed_msg_db_paths,
    save_message_item_media,
    validate_search_scope,
)
from wechat_cli.core.voice import VoiceRecord


class MessageShardDiscoveryTests(unittest.TestCase):
    def test_finds_new_message_shards_missing_from_key_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            message_dir = Path(tmp) / "message"
            message_dir.mkdir()
            (message_dir / "message_0.db").write_bytes(b"old")
            (message_dir / "message_1.db").write_bytes(b"new")
            (message_dir / "media_1.db").write_bytes(b"media")
            all_keys = {
                "message\\message_0.db": {
                    "enc_key": "unused",
                    "salt": "unused",
                }
            }

            missing = find_unkeyed_msg_db_paths(all_keys, tmp)

        self.assertEqual(
            [path.replace("\\", "/") for path in missing],
            ["message/message_1.db"],
        )

    def test_ignores_path_separator_and_case_differences(self):
        with tempfile.TemporaryDirectory() as tmp:
            message_dir = Path(tmp) / "message"
            message_dir.mkdir()
            (message_dir / "message_0.db").write_bytes(b"old")
            all_keys = {
                "MESSAGE/message_0.db": {
                    "enc_key": "unused",
                    "salt": "unused",
                }
            }

            missing = find_unkeyed_msg_db_paths(all_keys, tmp)

        self.assertEqual(missing, [])


class SearchScopeValidationTests(unittest.TestCase):
    def test_allows_keyword_without_time_range(self):
        validate_search_scope("合同", "", "")

    def test_allows_empty_keyword_with_complete_time_range(self):
        validate_search_scope("", "2026-05-01", "2026-05-13")

    def test_rejects_empty_keyword_without_complete_time_range(self):
        with self.assertRaisesRegex(ValueError, "关键词为空"):
            validate_search_scope("", "2026-05-01", "")


class HistoryItemTests(unittest.TestCase):
    def test_preserves_group_invitation_system_notice_verbatim(self):
        ts = int(datetime(2026, 7, 16, 20, 11).timestamp())
        notice = '"集阳"邀请"姝均"加入了群聊'
        item = _build_history_item(
            (8350, 10000, ts, 0, notice, None),
            {
                "username": "room@chatroom",
                "display_name": "畅所欲言",
                "is_group": True,
            },
            {"room@chatroom": "畅所欲言"},
            {},
            lambda username, all_names: all_names.get(username, username),
            {},
        )

        self.assertEqual(item["type"], "system")
        self.assertEqual(item["text"], f"[系统] {notice}")

    def test_builds_structured_group_message_with_sender_avatar(self):
        ts = int(datetime(2026, 5, 18, 9, 30).timestamp())
        ctx = {
            "username": "room@chatroom",
            "display_name": "项目群",
            "is_group": True,
        }
        names = {
            "room@chatroom": "项目群",
            "wxid_sender": "小张",
        }
        row = (123, 1, ts, 7, "wxid_sender:\n早上好", None)

        item = _build_history_item(
            row,
            ctx,
            names,
            {7: "wxid_sender"},
            lambda username, all_names: all_names.get(username, username),
            {"wxid_sender": "https://example.com/avatar.jpg"},
        )

        self.assertEqual(item["id"], 123)
        self.assertEqual(item["sender"], "小张")
        self.assertEqual(item["sender_username"], "wxid_sender")
        self.assertEqual(item["sender_avatar_url"], "https://example.com/avatar.jpg")
        self.assertEqual(item["text"], "早上好")
        self.assertEqual(item["type"], "text")
        self.assertFalse(item["is_self"])

    def test_builds_structured_image_message_with_media_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            image_dir = root / "msg" / "attach" / hashlib.md5("wxid_friend".encode()).hexdigest() / "2026-05" / "Img"
            image_dir.mkdir(parents=True)
            image_path = image_dir / "sample.dat"
            image_path.write_bytes(b"\xff\xd8\xff\xe0jpeg")
            db_dir.mkdir()

            ts = int(datetime(2026, 5, 18, 9, 30).timestamp())
            ctx = {
                "username": "wxid_friend",
                "display_name": "朋友",
                "is_group": False,
            }
            row = (124, 3, ts, 7, "image payload", None)

            item = _build_history_item(
                row,
                ctx,
                {"wxid_friend": "朋友"},
                {7: "wxid_friend"},
                lambda username, all_names: all_names.get(username, username),
                {"wxid_friend": "https://example.com/friend.jpg"},
                db_dir=str(db_dir),
                resolve_media=True,
            )

        self.assertEqual(item["type"], "image")
        self.assertEqual(item["media"]["kind"], "image")
        self.assertEqual(item["media"]["path"], str(image_path))
        self.assertTrue(item["media"]["exists"])

    def test_builds_structured_group_image_with_media_path_closest_to_message_time(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            image_dir = root / "msg" / "attach" / hashlib.md5("room@chatroom".encode()).hexdigest() / "2026-05" / "Img"
            image_dir.mkdir(parents=True)
            db_dir.mkdir()
            older = image_dir / "000-old.dat"
            target_thumb = image_dir / "999-target_t.dat"
            target_full = image_dir / "999-target.dat"
            older.write_bytes(b"\xff\xd8\xff\xe0old")
            target_thumb.write_bytes(b"\xff\xd8\xff\xe0thumb")
            target_full.write_bytes(b"\xff\xd8\xff\xe0full")

            ts = int(datetime(2026, 5, 18, 9, 30).timestamp())
            os.utime(older, (ts - 86400, ts - 86400))
            os.utime(target_thumb, (ts + 2, ts + 2))
            os.utime(target_full, (ts + 30, ts + 30))

            ctx = {
                "username": "room@chatroom",
                "display_name": "项目群",
                "is_group": True,
            }
            row = (126, 3, ts, 7, "wxid_sender:\nimage payload", None)

            item = _build_history_item(
                row,
                ctx,
                {"room@chatroom": "项目群", "wxid_sender": "小张"},
                {7: "wxid_sender"},
                lambda username, all_names: all_names.get(username, username),
                {},
                db_dir=str(db_dir),
                resolve_media=True,
            )

        self.assertEqual(item["media"]["path"], str(target_full))

    def test_builds_structured_sticker_message_with_remote_url(self):
        ts = int(datetime(2026, 5, 18, 9, 30).timestamp())
        ctx = {
            "username": "wxid_friend",
            "display_name": "朋友",
            "is_group": False,
        }
        content = '<msg><emoji md5="abc123" cdnurl="https://example.com/sticker.gif" /></msg>'
        row = (125, 47, ts, 7, content, None)

        item = _build_history_item(
            row,
            ctx,
            {"wxid_friend": "朋友"},
            {7: "wxid_friend"},
            lambda username, all_names: all_names.get(username, username),
            {},
        )

        self.assertEqual(item["type"], "sticker")
        self.assertEqual(item["text"], "[表情] abc123")
        self.assertEqual(item["media"]["kind"], "sticker")
        self.assertEqual(item["media"]["url"], "https://example.com/sticker.gif")
        self.assertEqual(item["media"]["md5"], "abc123")

    def test_builds_clean_voice_message_from_media_database(self):
        ts = int(datetime(2026, 7, 29, 11, 5, 52).timestamp())
        content = '<msg><voicemsg voicelength="7460" voiceformat="4" /></msg>'
        record = VoiceRecord(
            data=b"#!SILK_V3voice",
            local_id=116,
            create_time=ts,
            svr_id=999,
            media_db="media_1.db",
        )

        with mock.patch(
            "wechat_cli.core.messages.find_voice_record",
            return_value=record,
        ):
            item = _build_history_item(
                (116, 34, ts, 7, content, None),
                {"username": "wxid_friend", "display_name": "佳佳姐", "is_group": False},
                {"wxid_friend": "佳佳姐"},
                {7: "wxid_friend"},
                lambda username, all_names: all_names.get(username, username),
                {},
                resolve_media=True,
                db_dir="unused",
                media_db_paths=["decrypted-media-1.db"],
            )

        self.assertEqual(item["text"], "[语音 7.5秒]")
        self.assertNotIn("<voicemsg", item["line"])
        self.assertEqual(item["voice"]["source"], "media_database")
        self.assertEqual(item["voice"]["media_db"], "media_1.db")
        self.assertEqual(item["voice"]["bytes"], len(record.data))

    def test_saves_message_item_media_to_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "msg" / "file" / "2026-05" / "方案.pdf"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"%PDF-1.4")
            output_dir = root / "exported"
            item = {
                "id": 88,
                "time": "2026-05-18 09:30",
                "type": "file",
                "media": {
                    "kind": "file",
                    "path": str(source),
                    "exists": True,
                    "filename": "方案.pdf",
                },
            }

            saved = save_message_item_media(item, str(output_dir))

            self.assertEqual(saved["kind"], "file")
            self.assertEqual(saved["original_path"], str(source))
            self.assertTrue(Path(saved["path"]).is_file())
            self.assertEqual(Path(saved["path"]).read_bytes(), b"%PDF-1.4")
            self.assertEqual(item["media"]["saved_path"], saved["path"])


if __name__ == "__main__":
    unittest.main()
