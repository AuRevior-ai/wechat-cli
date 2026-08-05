import hashlib
import json
import os
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from tests.test_update_models import make_manifest
from wechat_cli.update.client import UpdateCheckResult
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.layout import CurrentVersion, InstallLayout
from wechat_cli.update.models import UpdateManifest
from wechat_cli.update.prepare import prepare_checked_update
from wechat_cli.update.state import load_pending_update


def create_package(path: Path, *, version="0.5.0", include_entrypoint=True):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "app-manifest.json",
            json.dumps(
                {
                    "product": "wechat-cli-web",
                    "version": version,
                    "platform": "windows",
                    "architecture": "x86_64",
                    "entrypoint": "wechat-cli.exe",
                    "build_id": "20260804.1",
                }
            ),
        )
        if include_entrypoint:
            archive.writestr("wechat-cli.exe", b"binary")


def check_result_for(package: Path, *, version="0.5.0"):
    raw = package.read_bytes()
    data = make_manifest(version=version)
    data["package"] = dict(
        data["package"],
        filename=package.name,
        size=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),
    )
    manifest_bytes = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return UpdateCheckResult(
        update_available=True,
        manifest=UpdateManifest.from_mapping(data),
        raw_manifest=manifest_bytes,
        manifest_signature=b"s" * 64,
        download_ticket="dlt_secret",
        download_ticket_expires_at="2026-08-04T15:10:00Z",
    )


class UpdatePreparationTests(unittest.TestCase):
    def make_layout(self, root: Path):
        layout = InstallLayout(root / "WeChatCliWeb")
        layout.ensure_directories()
        current = layout.version_path("0.4.2")
        current.mkdir()
        (current / "wechat-cli.exe").write_bytes(b"old")
        layout.save_current(
            CurrentVersion(
                current_version="0.4.2",
                previous_version=None,
                channel="stable",
                activated_at="2026-08-04T14:00:00Z",
                manifest_sha256="11" * 32,
            )
        )
        return layout

    def test_downloads_extracts_and_marks_update_for_next_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            create_package(source)
            result = check_result_for(source)
            layout = self.make_layout(root)
            requests = []

            def downloader(request, download_dir):
                requests.append(request)
                destination = Path(download_dir) / request.filename
                destination.write_bytes(source.read_bytes())
                return destination

            pending = prepare_checked_update(
                result,
                layout,
                download_url="https://api.example.test/v1/updates/download",
                downloader=downloader,
                prepared_at=datetime(2026, 8, 4, 15, 0, tzinfo=timezone.utc),
            )

            self.assertEqual("0.5.0", pending.version)
            self.assertTrue((layout.version_path("0.5.0") / "wechat-cli.exe").is_file())
            self.assertEqual(pending, load_pending_update(layout.pending_update_path))
            self.assertEqual("DownloadRequest", type(requests[0]).__name__)
            self.assertNotIn("dlt_secret", repr(requests[0]))
            self.assertEqual([], list(layout.staging_dir.iterdir()))

    def test_rejects_no_update_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            with self.assertRaises(ValueError):
                prepare_checked_update(
                    UpdateCheckResult(False),
                    layout,
                    download_url="https://api.example.test/v1/updates/download",
                    downloader=lambda *_args: None,
                )

    def test_rejects_non_newer_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            create_package(source, version="0.4.2")
            layout = self.make_layout(root)

            with self.assertRaises(UpdateError) as caught:
                prepare_checked_update(
                    check_result_for(source, version="0.4.2"),
                    layout,
                    download_url="https://api.example.test/v1/updates/download",
                    downloader=lambda request, directory: source,
                )

        self.assertEqual(ErrorCode.UPDATE_PACKAGE_INVALID, caught.exception.code)

    def test_invalid_package_leaves_current_and_pending_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            create_package(source, include_entrypoint=False)
            layout = self.make_layout(root)

            with self.assertRaises(UpdateError):
                prepare_checked_update(
                    check_result_for(source),
                    layout,
                    download_url="https://api.example.test/v1/updates/download",
                    downloader=lambda request, directory: source,
                )

            self.assertEqual("0.4.2", layout.load_current().current_version)
            self.assertFalse(layout.pending_update_path.exists())
            self.assertFalse(layout.version_path("0.5.0").exists())
            self.assertEqual([], list(layout.staging_dir.iterdir()))

    def test_existing_target_version_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.zip"
            create_package(source)
            layout = self.make_layout(root)
            target = layout.version_path("0.5.0")
            target.mkdir()
            marker = target / "marker.txt"
            marker.write_text("existing", encoding="utf-8")

            with self.assertRaises(UpdateError):
                prepare_checked_update(
                    check_result_for(source),
                    layout,
                    download_url="https://api.example.test/v1/updates/download",
                    downloader=lambda request, directory: source,
                )

            self.assertEqual("existing", marker.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
