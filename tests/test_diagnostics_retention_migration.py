import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "services" / "license-update-worker" / "migrations"


class DiagnosticsRetentionMigrationTests(unittest.TestCase):
    def test_migration_separates_upload_and_retention_expiry_without_extending_existing_rows(self):
        migration = MIGRATIONS / "0006_diagnostics_retention.sql"
        self.assertTrue(migration.is_file(), "0006_diagnostics_retention.sql must exist")
        connection = sqlite3.connect(":memory:")
        try:
            for path in sorted(MIGRATIONS.glob("000[1-5]_*.sql")):
                connection.executescript(path.read_text(encoding="utf-8"))
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute(
                """INSERT INTO diagnostic_submissions (
                    id, license_id, device_id, object_key, size, sha256,
                    client_version, launcher_version, status, expires_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'complete', ?, ?)""",
                (
                    "diag_existing",
                    "lic_existing",
                    "dev_existing",
                    "diagnostics/old.zip",
                    10,
                    "a" * 64,
                    "0.5.1",
                    "0.1.0",
                    "2026-08-13T00:15:00Z",
                    "2026-08-13T00:00:00Z",
                ),
            )
            connection.executescript(migration.read_text(encoding="utf-8"))
            row = connection.execute(
                """SELECT upload_expires_at, retention_expires_at, consent_version
                   FROM diagnostic_submissions WHERE id = 'diag_existing'"""
            ).fetchone()
            self.assertEqual(
                (
                    "2026-08-13T00:15:00Z",
                    "2026-08-13T00:15:00Z",
                    "legacy-v0",
                ),
                row,
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
