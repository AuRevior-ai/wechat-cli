import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "services" / "license-update-worker" / "migrations"


class SecretVersionMigrationTests(unittest.TestCase):
    def test_migration_adds_version_metadata_with_legacy_version_one_defaults(self):
        migration = MIGRATIONS / "0007_secret_versions.sql"
        self.assertTrue(migration.is_file(), "0007_secret_versions.sql must exist")
        connection = sqlite3.connect(":memory:")
        try:
            for path in sorted(MIGRATIONS.glob("000[1-6]_*.sql")):
                connection.executescript(path.read_text(encoding="utf-8"))
            connection.executescript(migration.read_text(encoding="utf-8"))
            expected = {
                "licenses": "key_secret_version",
                "devices": "token_secret_version",
                "admin_sessions": "token_secret_version",
                "download_tickets": "secret_version",
                "license_contacts": "lookup_secret_version",
            }
            for table, column in expected.items():
                columns = {
                    row[1]: row[4]
                    for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
                }
                self.assertIn(column, columns)
                self.assertEqual("1", str(columns[column]))
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
