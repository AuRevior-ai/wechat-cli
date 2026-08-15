import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "services" / "license-update-worker" / "migrations"


class AutomationIdentityMigrationTests(unittest.TestCase):
    def test_migration_preserves_audits_and_adds_automation_actor(self):
        migration = MIGRATIONS / "0008_automation_identity.sql"
        self.assertTrue(migration.is_file(), "0008_automation_identity.sql must exist")

        connection = sqlite3.connect(":memory:")
        try:
            for path in sorted(MIGRATIONS.glob("000[1-7]_*.sql")):
                connection.executescript(path.read_text(encoding="utf-8"))
            connection.execute(
                """
                INSERT INTO audit_events (
                  id, actor_type, actor_id, action, target_type, target_id,
                  result, request_id, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "audit_existing",
                    "admin",
                    "admin_existing",
                    "existing.action",
                    "release",
                    "rel_existing",
                    "success",
                    "req_existing",
                    '{"safe":true}',
                    "2026-08-15T00:00:00.000Z",
                ),
            )
            connection.executescript(migration.read_text(encoding="utf-8"))

            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertIn("automation_principals", tables)
            self.assertEqual(
                connection.execute(
                    "SELECT actor_type, actor_id, action, metadata_json FROM audit_events WHERE id = ?",
                    ("audit_existing",),
                ).fetchone(),
                ("admin", "admin_existing", "existing.action", '{"safe":true}'),
            )
            connection.execute(
                """
                INSERT INTO audit_events (
                  id, actor_type, actor_id, action, result, request_id, created_at
                ) VALUES (?, 'automation', ?, ?, 'success', ?, ?)
                """,
                (
                    "audit_automation",
                    "automation_prod",
                    "release.register",
                    "req_automation",
                    "2026-08-15T00:01:00.000Z",
                ),
            )
            self.assertEqual(
                connection.execute(
                    "SELECT actor_type FROM audit_events WHERE id = ?",
                    ("audit_automation",),
                ).fetchone(),
                ("automation",),
            )
            indexes = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_events'"
                ).fetchall()
            }
            self.assertTrue(
                {"idx_audit_events_created", "idx_audit_events_target"}.issubset(indexes)
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
