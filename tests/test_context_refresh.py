import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.core import context


class AppContextShardRefreshTests(unittest.TestCase):
    def test_refreshes_keys_automatically_when_new_message_shard_appears(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            message_dir = db_dir / "message"
            message_dir.mkdir(parents=True)
            (message_dir / "message_0.db").write_bytes(b"old")
            (message_dir / "message_1.db").write_bytes(b"new")
            keys_file = root / "all_keys.json"
            keys_file.write_text(
                json.dumps(
                    {
                        "message/message_0.db": {
                            "enc_key": "old-key",
                            "salt": "old-salt",
                        }
                    }
                ),
                encoding="utf-8",
            )
            cfg = {
                "db_dir": str(db_dir),
                "decrypted_dir": str(root / "decrypted"),
                "keys_file": str(keys_file),
            }

            def fake_extract(selected_db_dir, output_path, **kwargs):
                Path(output_path).write_text(
                    json.dumps(
                        {
                            "message/message_0.db": {
                                "enc_key": "old-key",
                                "salt": "old-salt",
                            },
                            "message/message_1.db": {
                                "enc_key": "new-key",
                                "salt": "new-salt",
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return {"new-salt": "new-key"}

            with patch.object(context, "load_config", return_value=cfg), \
                    patch("wechat_cli.keys.extract_keys", side_effect=fake_extract) as extract, \
                    patch.object(context, "DBCache"), \
                    patch.object(context.atexit, "register"):
                app = context.AppContext()

        extract.assert_called_once()
        self.assertIn("message/message_1.db", app.msg_db_keys)


if __name__ == "__main__":
    unittest.main()
