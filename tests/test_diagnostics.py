import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from wechat_cli.diagnostics import (
    DiagnosticBundleBuilder,
    Redactor,
    scan_for_sensitive_content,
)
from wechat_cli.update.layout import CurrentVersion, InstallLayout


class RedactorTests(unittest.TestCase):
    def setUp(self):
        self.redactor = Redactor(windows_user_name="SURTR")

    def test_redacts_known_secret_formats_headers_contacts_and_user_paths(self):
        source = "\n".join(
            [
                "license=WCL-7K3M-9Q2P-H6TX-R4DN",
                "device=wcdt_token01.supersecretvalue",
                "admin=wcadmin_admin01.adminsecret",
                "github=github_pat_11AA_secretsecretsecret",
                "Authorization: Bearer secret-bearer-token",
                "Cookie: session=secret-cookie",
                "url=https://example.test/?ticket=dlt_secret&key=WCL-AAAA-BBBB-CCCC-DDDD",
                r"path=C:\Users\SURTR\AppData\Local\WeChatCliWeb",
                "email=user@example.com wechat=wx-secret",
            ]
        )

        redacted = self.redactor.redact(source)

        for secret in (
            "7K3M-9Q2P-H6TX",
            "supersecretvalue",
            "adminsecret",
            "github_pat_11AA",
            "secret-bearer-token",
            "secret-cookie",
            "dlt_secret",
            "user@example.com",
            "wx-secret",
            "SURTR",
        ):
            self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED]", redacted)
        self.assertIn("path=C:", redacted)
        self.assertIn("[USER]", redacted)
        # replaced fragile backslash literal: self.assertIn("C:\\\\Users\\\\[USER]\\\\", redacted)
        # invalid raw-string form replaced below: self.assertIn(r"C:\Users\[USER]\", redacted)

    def test_preserves_non_sensitive_error_context(self):
        source = "2026-08-05 health_check_timeout HTTP 503 retryable=true"

        self.assertEqual(source, self.redactor.redact(source))

    def test_sensitive_scanner_finds_unredacted_values(self):
        findings = scan_for_sensitive_content(
            "Authorization: Bearer secret\nWCL-AAAA-BBBB-CCCC-DDDD"
        )

        self.assertIn("authorization_header", findings)
        self.assertIn("license_key", findings)
        self.assertEqual([], scan_for_sensitive_content("Authorization: [REDACTED]"))


class DiagnosticBundleBuilderTests(unittest.TestCase):
    def make_layout(self, root: Path) -> InstallLayout:
        layout = InstallLayout(root / "WeChatCliWeb")
        layout.ensure_directories()
        version = layout.version_path("0.5.0")
        version.mkdir()
        (version / "wechat-cli.exe").write_bytes(b"binary")
        layout.save_current(
            CurrentVersion(
                current_version="0.5.0",
                previous_version="0.4.2",
                channel="stable",
                activated_at="2026-08-05T12:00:00Z",
                manifest_sha256="ab" * 32,
            )
        )
        return layout

    def test_builds_redacted_local_zip_with_user_readable_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = self.make_layout(root)
            (layout.logs_dir / "launcher.log").write_text(
                "Authorization: Bearer secret-token\n"
                "license WCL-AAAA-BBBB-CCCC-DDDD\n"
                r"path C:\Users\SURTR\AppData\Local" "\n"
                "health_check_timeout\n",
                encoding="utf-8",
            )
            (layout.logs_dir / "updater.log").write_text(
                "device=wcdt_id.supersecret\nHTTP 503\n",
                encoding="utf-8",
            )
            user_data = root / ".wechat-cli"
            user_data.mkdir()
            (user_data / "chat.db").write_bytes(b"PRIVATE CHAT DATA")
            builder = DiagnosticBundleBuilder(
                layout=layout,
                windows_user_name="SURTR",
                now=lambda: datetime(2026, 8, 5, 12, 34, 56, tzinfo=timezone.utc),
                webview2_version_provider=lambda: "127.0.1000.2",
                system_info_provider=lambda: {
                    "platform": "Windows-11",
                    "python": "3.12.0",
                },
            )

            result = builder.build_local()

            self.assertTrue(result.path.is_file())
            self.assertEqual(
                "wechat-cli-diagnostics-20260805-123456.zip",
                result.path.name,
            )
            with zipfile.ZipFile(result.path) as archive:
                names = set(archive.namelist())
                self.assertIn("contents.txt", names)
                self.assertIn("metadata.json", names)
                self.assertIn("logs/launcher.log", names)
                self.assertIn("logs/updater.log", names)
                self.assertNotIn("chat.db", " ".join(names))
                launcher = archive.read("logs/launcher.log").decode("utf-8")
                metadata = json.loads(archive.read("metadata.json"))
                contents = archive.read("contents.txt").decode("utf-8")

            self.assertIn("health_check_timeout", launcher)
            self.assertNotIn("secret-token", launcher)
            self.assertNotIn("WCL-AAAA", launcher)
            self.assertNotIn("SURTR", launcher)
            self.assertEqual("0.5.0", metadata["current_version"])
            self.assertEqual("127.0.1000.2", metadata["webview2_runtime"])
            self.assertIn("不会包含微信聊天记录", contents)
            self.assertIn("launcher.log", contents)
            self.assertEqual((), result.sensitive_findings)
            self.assertFalse(result.submitted)

    def test_truncates_large_logs_and_limits_total_bundle_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = self.make_layout(root)
            (layout.logs_dir / "launcher.log").write_text(
                "start\n" + ("x" * 10000) + "\nend",
                encoding="utf-8",
            )
            builder = DiagnosticBundleBuilder(
                layout=layout,
                max_log_bytes=1024,
                max_total_log_bytes=2048,
                windows_user_name="SURTR",
            )

            result = builder.build_local()

            with zipfile.ZipFile(result.path) as archive:
                text = archive.read("logs/launcher.log").decode("utf-8")
            self.assertLessEqual(len(text.encode("utf-8")), 1200)
            self.assertIn("[TRUNCATED", text)

    def test_rejects_bundle_when_second_sensitive_scan_finds_secret(self):
        class BrokenRedactor:
            def redact(self, text):
                return text

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = self.make_layout(root)
            (layout.logs_dir / "launcher.log").write_text(
                "Authorization: Bearer still-secret",
                encoding="utf-8",
            )
            builder = DiagnosticBundleBuilder(
                layout=layout,
                redactor=BrokenRedactor(),
            )

            with self.assertRaises(RuntimeError) as caught:
                builder.build_local()

            self.assertIn("敏感字段", str(caught.exception))
            diagnostics_dir = layout.logs_dir / "diagnostics"
            self.assertEqual([], list(diagnostics_dir.glob("*.zip")))

    def test_ignores_non_log_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = self.make_layout(root)
            (layout.logs_dir / "launcher.log").write_text("safe", encoding="utf-8")
            (layout.logs_dir / "database.db").write_bytes(b"PRIVATE")
            outside = root / "outside.log"
            outside.write_text("outside secret", encoding="utf-8")
            link = layout.logs_dir / "linked.log"
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError):
                link = None

            result = DiagnosticBundleBuilder(layout=layout).build_local()

            with zipfile.ZipFile(result.path) as archive:
                names = set(archive.namelist())
            self.assertIn("logs/launcher.log", names)
            self.assertNotIn("logs/database.db", names)
            self.assertNotIn("logs/linked.log", names)


if __name__ == "__main__":
    unittest.main()
