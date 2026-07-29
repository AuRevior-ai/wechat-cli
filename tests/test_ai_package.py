import json
import tempfile
import unittest
import wave
from pathlib import Path
from zipfile import ZipFile

from wechat_cli.core.ai_package import (
    _validate_remote_image_url,
    build_ai_package,
    download_remote_image,
)
from wechat_cli.core.voice import VoiceRecord, write_pcm_wav


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"png-data"
GIF_BYTES = b"GIF89a" + b"gif-data"


def _chat():
    return {
        "display_name": "测试群",
        "username": "room@chatroom",
        "is_group": True,
    }


def _base_item(message_id, kind, text):
    return {
        "id": message_id,
        "timestamp": 1785294352 + message_id,
        "time": f"2026-07-29 11:{message_id:02d}",
        "chat": "测试群",
        "chat_username": "room@chatroom",
        "is_group": True,
        "sender": "小陶",
        "sender_username": "wxid_sender",
        "is_self": False,
        "type": kind,
        "type_label": kind,
        "text": text,
        "line": text,
    }


class AiPackageTests(unittest.TestCase):
    def test_builds_zip_with_relative_assets_transcript_and_forward_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "source.dat"
            image.write_bytes(PNG_BYTES)
            items = [
                {
                    **_base_item(4, "image", r"[图片] C:\private\source.dat"),
                    "media": {
                        "kind": "image",
                        "path": str(image),
                        "exists": True,
                        "filename": "source.dat",
                    },
                },
                {
                    **_base_item(5, "sticker", "[表情] abc"),
                    "media": {
                        "kind": "sticker",
                        "url": "http://wxapp.tc.qq.com/sticker.gif",
                        "md5": "abc",
                    },
                },
                {
                    **_base_item(6, "voice", "[语音 1.0秒]"),
                    "voice": {"source": "media_database"},
                },
                {
                    **_base_item(7, "forwarded", "[合并转发] 内层记录"),
                    "forwarded": {
                        "title": "内层记录",
                        "truncated": False,
                        "items": [{
                            "kind": "text",
                            "datatype": 1,
                            "sender": "陈子明",
                            "time": "2026-07-29 10:00",
                            "text": "转发内文字",
                            "title": "",
                            "children": [],
                        }],
                    },
                },
            ]
            output = root / "测试 AI 资料包.zip"

            def voice_finder(_paths, _chat, local_id, _timestamp):
                self.assertEqual(local_id, 6)
                return VoiceRecord(
                    data=b"#!SILK_V3voice",
                    local_id=6,
                    create_time=1785294358,
                    svr_id=999,
                    media_db="media_1.db",
                )

            def voice_decoder(_data, target):
                return write_pcm_wav(target, b"\x00\x00" * 16000)

            result = build_ai_package(
                _chat(),
                items,
                output,
                db_dir=str(root / "db_storage"),
                media_db_paths=["media.db"],
                start_time="2026-07-29",
                end_time="2026-07-29",
                remote_image_loader=lambda _url: (GIF_BYTES, "image/gif"),
                voice_finder=voice_finder,
                voice_decoder=voice_decoder,
                transcriber=lambda _path: "今天完成",
            )

            with ZipFile(result.path) as archive:
                names = archive.namelist()
                transcript = archive.read("聊天记录.txt").decode("utf-8")
                manifest = json.loads(archive.read("清单.json"))

        self.assertIn("聊天记录.txt", names)
        self.assertIn("清单.json", names)
        self.assertEqual(len([name for name in names if name.startswith("素材/")]), 3)
        self.assertNotIn(r"C:\private", transcript)
        self.assertNotIn("http://", transcript)
        self.assertIn("素材/", transcript)
        self.assertIn("语音转文字（机器识别）：今天完成", transcript)
        self.assertIn("转发内文字", transcript)
        self.assertEqual(manifest["package_version"], 1)
        self.assertEqual(manifest["message_count"], 4)
        self.assertEqual(manifest["asset_count"], 3)
        self.assertEqual(manifest["transcription_count"], 1)
        self.assertEqual(result.transcription_count, 1)
        self.assertIn("请总结下面这段微信聊天记录", result.copy_text)
        self.assertNotIn("请总结下面这段微信聊天记录", result.key_copy_text)

    def test_deduplicates_identical_stickers(self):
        items = []
        for message_id in (5, 6):
            items.append({
                **_base_item(message_id, "sticker", "[表情] same"),
                "media": {
                    "kind": "sticker",
                    "url": "https://wxapp.tc.qq.com/same.gif",
                    "md5": "same",
                },
            })

        with tempfile.TemporaryDirectory() as tmp:
            result = build_ai_package(
                _chat(),
                items,
                Path(tmp) / "result.zip",
                remote_image_loader=lambda _url: (GIF_BYTES, "image/gif"),
                transcribe_voice=False,
            )
            with ZipFile(result.path) as archive:
                assets = [name for name in archive.namelist() if name.startswith("素材/")]

        self.assertEqual(len(assets), 1)
        self.assertEqual(result.asset_count, 1)
        self.assertEqual(
            result.messages[0]["asset_path"],
            result.messages[1]["asset_path"],
        )

    def test_keeps_package_when_one_asset_fails(self):
        item = {
            **_base_item(9, "sticker", "[表情] unavailable"),
            "media": {
                "kind": "sticker",
                "url": "https://wxapp.tc.qq.com/missing.gif",
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            result = build_ai_package(
                _chat(),
                [item],
                Path(tmp) / "partial.zip",
                remote_image_loader=lambda _url: (_ for _ in ()).throw(
                    RuntimeError("下载失败")
                ),
                transcribe_voice=False,
            )
            with ZipFile(result.path) as archive:
                manifest = json.loads(archive.read("清单.json"))
            package_exists = Path(result.path).is_file()

        self.assertTrue(package_exists)
        self.assertEqual(result.asset_count, 0)
        self.assertEqual(result.failures[0]["message_id"], 9)
        self.assertIn("下载失败", result.failures[0]["error"])
        self.assertEqual(manifest["failures"], result.failures)

    def test_rejects_non_wechat_sticker_host_before_network(self):
        with self.assertRaisesRegex(PermissionError, "微信官方"):
            download_remote_image("https://example.com/sticker.gif")

    def test_keeps_official_legacy_http_sticker_url(self):
        url = "http://wxapp.tc.qq.com/path/sticker.gif"

        self.assertEqual(_validate_remote_image_url(url), url)

    def test_uses_jpeg_thumbnail_when_standard_image_is_wxgf(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            standard = root / "abc.dat"
            thumbnail = root / "abc_t.dat"
            standard.write_bytes(b"wxgf" + b"hevc-data")
            thumbnail.write_bytes(PNG_BYTES)
            item = {
                **_base_item(12, "image", "[图片]"),
                "media": {
                    "kind": "image",
                    "path": str(standard),
                    "exists": True,
                    "filename": standard.name,
                },
            }

            result = build_ai_package(
                _chat(),
                [item],
                root / "fallback.zip",
                db_dir=str(root / "db_storage"),
                transcribe_voice=False,
            )
            with ZipFile(result.path) as archive:
                asset_name = next(
                    name for name in archive.namelist() if name.startswith("素材/")
                )
                asset_body = archive.read(asset_name)

        self.assertTrue(asset_name.endswith(".png"))
        self.assertEqual(asset_body, PNG_BYTES)

    def test_does_not_package_placeholder_when_v2_image_key_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            encrypted = root / "missing-key.dat"
            encrypted.write_bytes(b"\x07\x08V2" + b"\x00" * 100)
            item = {
                **_base_item(13, "image", "[图片]"),
                "media": {
                    "kind": "image",
                    "path": str(encrypted),
                    "exists": True,
                    "filename": encrypted.name,
                },
            }

            result = build_ai_package(
                _chat(),
                [item],
                root / "missing-key.zip",
                db_dir=str(root / "db_storage"),
                transcribe_voice=False,
            )

        self.assertEqual(result.asset_count, 0)
        self.assertEqual(result.failures[0]["phase"], "local_media")
        self.assertIn("密钥", result.failures[0]["error"])


if __name__ == "__main__":
    unittest.main()
