import csv
import os
import tempfile
import unittest
from pathlib import Path

from wechat_cli.admin.csv_export import export_license_csv


class AdminCsvExportTests(unittest.TestCase):
    def sample(self):
        return [
            {
                "license_id": "lic_01",
                "license_key": "WCL-AAAA-BBBB-CCCC-DDDD",
                "license_hint": "DDDD",
                "maximum_devices": 3,
                "release_channel": "stable",
                "created_at": "2026-08-05T00:00:00Z",
            },
            {
                "license_id": "lic_02",
                "license_key": "WCL-EEEE-FFFF-GGGG-HHHH",
                "license_hint": "HHHH",
                "maximum_devices": 3,
                "release_channel": "stable",
                "created_at": "2026-08-05T00:00:01Z",
            },
        ]

    def test_writes_sensitive_csv_once_with_expected_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "licenses.csv"

            result = export_license_csv(path, self.sample())

            self.assertEqual(path, result)
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(2, len(rows))
            self.assertEqual("WCL-AAAA-BBBB-CCCC-DDDD", rows[0]["license_key"])
            self.assertEqual(
                [
                    "license_id",
                    "license_key",
                    "license_hint",
                    "maximum_devices",
                    "release_channel",
                    "created_at",
                ],
                list(rows[0].keys()),
            )

    def test_refuses_to_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "licenses.csv"
            path.write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                export_license_csv(path, self.sample())

            self.assertEqual("existing", path.read_text(encoding="utf-8"))

    def test_rejects_rows_missing_plaintext_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "licenses.csv"
            with self.assertRaises(ValueError):
                export_license_csv(
                    path,
                    [{"license_id": "lic_01", "license_hint": "DDDD"}],
                )
            self.assertFalse(path.exists())

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not authoritative on Windows")
    def test_posix_file_is_owner_read_write_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "licenses.csv"
            export_license_csv(path, self.sample())
            self.assertEqual(0o600, path.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
