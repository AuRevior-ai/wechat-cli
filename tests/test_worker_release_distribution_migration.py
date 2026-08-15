import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class WorkerReleaseDistributionMigrationTests(unittest.TestCase):
    def test_migration_keeps_existing_releases_on_github_and_adds_optional_r2_key(self):
        migration = (
            ROOT
            / "services"
            / "license-update-worker"
            / "migrations"
            / "0004_release_distribution.sql"
        )
        self.assertTrue(migration.is_file())
        sql = migration.read_text(encoding="utf-8")
        self.assertIn("distribution_backend", sql)
        self.assertIn("DEFAULT 'github'", sql)
        self.assertIn("distribution_object_key", sql)
        self.assertNotIn("DROP TABLE releases", sql.upper())

    def test_migration_applies_and_existing_insert_shape_defaults_to_github(self):
        migrations = ROOT / "services" / "license-update-worker" / "migrations"
        connection = sqlite3.connect(":memory:")
        try:
            connection.executescript((migrations / "0001_initial.sql").read_text(encoding="utf-8"))
            connection.executescript(
                (migrations / "0004_release_distribution.sql").read_text(encoding="utf-8")
            )
            connection.execute(
                """
                INSERT INTO releases (
                  id, version, channel, manifest_content, manifest_signature,
                  manifest_sha256, package_sha256, package_size,
                  github_repository, github_release_id, github_asset_id,
                  github_asset_name, rollout_percentage, rollout_seed,
                  paused, enabled, published_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "rel_legacy",
                    "0.5.1",
                    "stable",
                    b"{}",
                    b"s" * 64,
                    "1" * 64,
                    "2" * 64,
                    3,
                    "org/repo",
                    "123",
                    "456",
                    "package.zip",
                    100,
                    "seed",
                    0,
                    1,
                    "2026-08-12T00:00:00Z",
                    "2026-08-12T00:00:00Z",
                ),
            )
            row = connection.execute(
                "SELECT distribution_backend, distribution_object_key FROM releases WHERE id = ?",
                ("rel_legacy",),
            ).fetchone()
            self.assertEqual(("github", None), row)
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
