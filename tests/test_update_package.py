import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path

from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.package import PackageLimits, extract_update_zip


def app_manifest(**overrides):
    data = {
        "product": "wechat-cli-web",
        "version": "0.5.0",
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": "wechat-cli.exe",
        "build_id": "20260804.1",
    }
    data.update(overrides)
    return data


def write_zip(path: Path, entries, *, compression=zipfile.ZIP_DEFLATED):
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, content in entries:
            archive.writestr(name, content)


class UpdatePackageTests(unittest.TestCase):
    def test_extracts_valid_package_into_random_staging_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package.zip"
            write_zip(
                package,
                [
                    ("app-manifest.json", json.dumps(app_manifest())),
                    ("wechat-cli.exe", b"binary"),
                    ("web/static/app.js", b"console.log('ok')"),
                ],
            )

            prepared = extract_update_zip(
                package,
                root / "staging",
                expected_product="wechat-cli-web",
                expected_version="0.5.0",
                expected_platform="windows",
                expected_architecture="x86_64",
                expected_entrypoint="wechat-cli.exe",
            )

            self.assertEqual("binary", (prepared / "wechat-cli.exe").read_text())
            self.assertTrue((prepared / "web" / "static" / "app.js").is_file())
            self.assertNotEqual("0.5.0", prepared.name)

    def test_rejects_path_traversal_absolute_drive_and_unc_members(self):
        unsafe_names = (
            "../outside.txt",
            "folder/../../outside.txt",
            "/absolute.txt",
            "C:/drive.txt",
            "C:\\drive.txt",
            "\\\\server\\share\\file.txt",
            "..\\outside.txt",
        )
        for unsafe_name in unsafe_names:
            with self.subTest(name=unsafe_name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = root / "package.zip"
                write_zip(
                    package,
                    [
                        ("app-manifest.json", json.dumps(app_manifest())),
                        ("wechat-cli.exe", b"binary"),
                        (unsafe_name, b"bad"),
                    ],
                )

                with self.assertRaises(UpdateError) as caught:
                    extract_update_zip(
                        package,
                        root / "staging",
                        expected_product="wechat-cli-web",
                        expected_version="0.5.0",
                        expected_platform="windows",
                        expected_architecture="x86_64",
                        expected_entrypoint="wechat-cli.exe",
                    )

                self.assertEqual(ErrorCode.UPDATE_PACKAGE_UNSAFE, caught.exception.code)
                self.assertFalse((root / "outside.txt").exists())

    def test_rejects_symbolic_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package.zip"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr("app-manifest.json", json.dumps(app_manifest()))
                archive.writestr("wechat-cli.exe", b"binary")
                link = zipfile.ZipInfo("link")
                link.create_system = 3
                link.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(link, "wechat-cli.exe")

            with self.assertRaises(UpdateError) as caught:
                extract_update_zip(
                    package,
                    root / "staging",
                    expected_product="wechat-cli-web",
                    expected_version="0.5.0",
                    expected_platform="windows",
                    expected_architecture="x86_64",
                    expected_entrypoint="wechat-cli.exe",
                )

        self.assertEqual(ErrorCode.UPDATE_PACKAGE_UNSAFE, caught.exception.code)

    def test_rejects_case_insensitive_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package.zip"
            write_zip(
                package,
                [
                    ("app-manifest.json", json.dumps(app_manifest())),
                    ("wechat-cli.exe", b"binary"),
                    ("data/file.txt", b"one"),
                    ("DATA/FILE.TXT", b"two"),
                ],
            )

            with self.assertRaises(UpdateError) as caught:
                extract_update_zip(
                    package,
                    root / "staging",
                    expected_product="wechat-cli-web",
                    expected_version="0.5.0",
                    expected_platform="windows",
                    expected_architecture="x86_64",
                    expected_entrypoint="wechat-cli.exe",
                )

        self.assertEqual(ErrorCode.UPDATE_PACKAGE_UNSAFE, caught.exception.code)

    def test_rejects_excessive_compression_ratio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package.zip"
            write_zip(
                package,
                [
                    ("app-manifest.json", json.dumps(app_manifest())),
                    ("wechat-cli.exe", b"0" * 50_000),
                ],
            )

            with self.assertRaises(UpdateError) as caught:
                extract_update_zip(
                    package,
                    root / "staging",
                    expected_product="wechat-cli-web",
                    expected_version="0.5.0",
                    expected_platform="windows",
                    expected_architecture="x86_64",
                    expected_entrypoint="wechat-cli.exe",
                    limits=PackageLimits(max_compression_ratio=2),
                )

        self.assertEqual(ErrorCode.UPDATE_PACKAGE_UNSAFE, caught.exception.code)

    def test_rejects_mismatched_internal_metadata(self):
        mismatches = [
            ("product", "other"),
            ("version", "0.5.1"),
            ("platform", "linux"),
            ("architecture", "arm64"),
            ("entrypoint", "other.exe"),
        ]
        for field, value in mismatches:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = root / "package.zip"
                write_zip(
                    package,
                    [
                        ("app-manifest.json", json.dumps(app_manifest(**{field: value}))),
                        ("wechat-cli.exe", b"binary"),
                    ],
                )

                with self.assertRaises(UpdateError) as caught:
                    extract_update_zip(
                        package,
                        root / "staging",
                        expected_product="wechat-cli-web",
                        expected_version="0.5.0",
                        expected_platform="windows",
                        expected_architecture="x86_64",
                        expected_entrypoint="wechat-cli.exe",
                    )

                self.assertEqual(ErrorCode.UPDATE_PACKAGE_INVALID, caught.exception.code)

    def test_rejects_missing_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package.zip"
            write_zip(package, [("app-manifest.json", json.dumps(app_manifest()))])

            with self.assertRaises(UpdateError) as caught:
                extract_update_zip(
                    package,
                    root / "staging",
                    expected_product="wechat-cli-web",
                    expected_version="0.5.0",
                    expected_platform="windows",
                    expected_architecture="x86_64",
                    expected_entrypoint="wechat-cli.exe",
                )

        self.assertEqual(ErrorCode.UPDATE_PACKAGE_INVALID, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
