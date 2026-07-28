import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.core import config


class DbDirDetectionTests(unittest.TestCase):
    def test_windows_detection_returns_all_db_storage_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            appdata = root / "appdata"
            config_dir = appdata / "Tencent" / "xwechat" / "config"
            data_root = root / "weixin_download"
            config_dir.mkdir(parents=True)
            (config_dir / "storage.ini").write_text(str(data_root), encoding="utf-8")

            first = data_root / "xwechat_files" / "wxid_one" / "db_storage"
            second = data_root / "xwechat_files" / "wxid_two" / "db_storage"
            first.mkdir(parents=True)
            second.mkdir(parents=True)

            with patch.object(config, "_SYSTEM", "windows"), patch.dict(os.environ, {"APPDATA": str(appdata)}):
                candidates = config.detect_db_dir_candidates()

        self.assertEqual(candidates, [str(first), str(second)])


if __name__ == "__main__":
    unittest.main()
