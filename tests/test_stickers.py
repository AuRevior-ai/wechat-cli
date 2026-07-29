import sqlite3
import tempfile
import unittest
from pathlib import Path

from wechat_cli.core.stickers import enrich_sticker_media, load_sticker_metadata


class _Cache:
    def __init__(self, path):
        self.path = path

    def get(self, _key):
        return self.path


class StickerMetadataTests(unittest.TestCase):
    def test_loads_and_enriches_top_level_and_forwarded_stickers(self):
        md5 = "0123456789abcdef0123456789abcdef"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "emoticon.db"
            connection = sqlite3.connect(path)
            connection.execute(
                "CREATE TABLE kNonStoreEmoticonTable("
                "md5 TEXT, aes_key TEXT, cdn_url TEXT, "
                "encrypt_url TEXT, thumb_url TEXT)"
            )
            connection.execute(
                "INSERT INTO kNonStoreEmoticonTable VALUES (?, ?, ?, '', '')",
                (md5, "fedcba9876543210fedcba9876543210", "https://wx.qlogo.cn/e.gif"),
            )
            connection.commit()
            connection.close()
            metadata = load_sticker_metadata(_Cache(str(path)))
            items = [
                {"media": {"kind": "sticker", "md5": md5}},
                {
                    "forwarded": {
                        "items": [{
                            "kind": "sticker",
                            "media": {"kind": "sticker", "md5": md5},
                            "children": [],
                        }],
                    },
                },
            ]

            enrich_sticker_media(items, metadata)

        self.assertEqual(
            items[0]["media"]["aes_key"],
            "fedcba9876543210fedcba9876543210",
        )
        self.assertEqual(
            items[1]["forwarded"]["items"][0]["media"]["url"],
            "https://wx.qlogo.cn/e.gif",
        )
