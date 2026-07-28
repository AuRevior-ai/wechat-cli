import json
import tempfile
import unittest
from pathlib import Path

from wechat_cli.keys.common import save_results


class KeyResultPersistenceTests(unittest.TestCase):
    def test_preserves_existing_database_keys_when_refresh_adds_new_shard(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "all_keys.json"
            output_path.write_text(
                json.dumps(
                    {
                        "message/message_0.db": {
                            "enc_key": "old-key",
                            "salt": "00" * 16,
                        }
                    }
                ),
                encoding="utf-8",
            )
            salt_hex = "11" * 16
            db_files = [
                (
                    "message/message_1.db",
                    "unused",
                    4096,
                    salt_hex,
                    b"\x11" * 4096,
                )
            ]

            save_results(
                db_files,
                {salt_hex: ["message/message_1.db"]},
                {salt_hex: "new-key"},
                str(output_path),
                lambda message: None,
            )
            saved = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(
            set(saved),
            {"message/message_0.db", "message/message_1.db"},
        )
        self.assertEqual(
            saved["message/message_1.db"]["enc_key"], "new-key"
        )


if __name__ == "__main__":
    unittest.main()
