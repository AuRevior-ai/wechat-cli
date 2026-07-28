import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.main import cli


class MediaCommandTests(unittest.TestCase):
    def test_media_export_decodes_dat_image_to_output_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            db_dir.mkdir()
            source = root / "msg" / "attach" / "image.dat"
            source.parent.mkdir(parents=True)
            decoded = b"\xff\xd8\xff\xe0jpeg"
            key = 0x37
            source.write_bytes(bytes(byte ^ key for byte in decoded))
            output_dir = root / "out"

            fake_app = type("FakeApp", (), {"db_dir": str(db_dir)})()
            with patch("wechat_cli.main.AppContext", return_value=fake_app):
                result = CliRunner().invoke(cli, ["media", "export", str(source), "--output-dir", str(output_dir)])

            self.assertEqual(result.exit_code, 0, result.output)
            exported = output_dir / "image.jpg"
            self.assertTrue(exported.is_file())
            self.assertEqual(exported.read_bytes(), decoded)


if __name__ == "__main__":
    unittest.main()
