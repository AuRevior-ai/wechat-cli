import tempfile
import unittest
from pathlib import Path

from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.layout import CurrentVersion, InstallLayout


class InstallLayoutTests(unittest.TestCase):
    def test_builds_expected_directories_under_local_appdata(self):
        layout = InstallLayout.from_environment({"LOCALAPPDATA": r"C:\Users\Test\AppData\Local"})

        self.assertEqual(
            Path(r"C:\Users\Test\AppData\Local") / "WeChatCliWeb",
            layout.root,
        )
        self.assertEqual(layout.root / "versions", layout.versions_dir)
        self.assertEqual(layout.root / "state" / "current.json", layout.current_path)
        self.assertEqual(layout.root / "cache" / "staging", layout.staging_dir)

    def test_missing_localappdata_is_rejected(self):
        with self.assertRaises(ValueError):
            InstallLayout.from_environment({})

    def test_current_version_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            state = CurrentVersion(
                current_version="0.5.0",
                previous_version="0.4.2",
                channel="stable",
                activated_at="2026-08-04T15:00:00Z",
                manifest_sha256="ab" * 32,
            )

            layout.save_current(state)

            self.assertEqual(state, layout.load_current())

    def test_activate_version_updates_current_and_previous_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            layout.version_path("0.4.2").mkdir()
            layout.version_path("0.5.0").mkdir()
            layout.save_current(
                CurrentVersion(
                    current_version="0.4.2",
                    previous_version=None,
                    channel="stable",
                    activated_at="2026-08-04T14:00:00Z",
                    manifest_sha256="11" * 32,
                )
            )

            state = layout.activate_version(
                "0.5.0",
                manifest_sha256="22" * 32,
                activated_at="2026-08-04T15:00:00Z",
            )

            self.assertEqual("0.5.0", state.current_version)
            self.assertEqual("0.4.2", state.previous_version)
            self.assertEqual(state, layout.load_current())

    def test_activate_version_requires_prepared_version_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()

            with self.assertRaises(UpdateError) as caught:
                layout.activate_version(
                    "0.5.0",
                    manifest_sha256="22" * 32,
                    activated_at="2026-08-04T15:00:00Z",
                )

        self.assertEqual(ErrorCode.UPDATE_PACKAGE_INVALID, caught.exception.code)

    def test_prune_versions_keeps_only_current_and_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            for version in ("0.4.1", "0.4.2", "0.5.0"):
                directory = layout.version_path(version)
                directory.mkdir()
                (directory / "wechat-cli.exe").write_text(version, encoding="utf-8")
            state = CurrentVersion(
                current_version="0.5.0",
                previous_version="0.4.2",
                channel="stable",
                activated_at="2026-08-04T15:00:00Z",
                manifest_sha256="ab" * 32,
            )

            removed = layout.prune_versions(state)

            self.assertEqual(["0.4.1"], removed)
            self.assertFalse(layout.version_path("0.4.1").exists())
            self.assertTrue(layout.version_path("0.4.2").exists())
            self.assertTrue(layout.version_path("0.5.0").exists())


if __name__ == "__main__":
    unittest.main()
