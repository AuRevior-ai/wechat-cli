import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "services" / "license-update-worker" / "migrations"


class AdminSessionMigrationTests(unittest.TestCase):
    def test_admin_session_migration_adds_principal_code_and_session_tables(self):
        migration = MIGRATIONS / "0005_admin_sessions.sql"
        self.assertTrue(migration.is_file(), "0005_admin_sessions.sql must exist")

        connection = sqlite3.connect(":memory:")
        try:
            for path in sorted(MIGRATIONS.glob("000[1-5]_*.sql")):
                connection.executescript(path.read_text(encoding="utf-8"))
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            self.assertTrue(
                {"admin_principals", "admin_login_codes", "admin_sessions"}.issubset(tables)
            )
            session_columns = {
                row[1]
                for row in connection.execute("PRAGMA table_info(admin_sessions)").fetchall()
            }
            self.assertTrue(
                {
                    "token_id",
                    "token_digest",
                    "principal_id",
                    "scopes_json",
                    "authenticated_at",
                    "expires_at",
                    "status",
                }.issubset(session_columns)
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
