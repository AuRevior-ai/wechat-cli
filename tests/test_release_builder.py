import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from wechat_cli.release.builder import (
    ReleaseBuildOptions,
    build_signed_release,
    load_ed25519_private_key,
)
from wechat_cli.update.models import UpdateManifest


class ReleaseBuilderTests(unittest.TestCase):
    def make_package(self, root: Path, *, version="0.5.1", entrypoint=True):
        package = root / f"wechat-cli-app-{version}-win-x64.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "app-manifest.json",
                json.dumps(
                    {
                        "product": "wechat-cli-web",
                        "version": version,
                        "platform": "windows",
                        "architecture": "x86_64",
                        "entrypoint": "wechat-cli.exe",
                        "build_id": "20260805.1",
                    }
                ),
            )
            if entrypoint:
                archive.writestr("wechat-cli.exe", b"binary")
        return package

    def make_key(self, root: Path):
        key = ECC.generate(curve="Ed25519")
        path = root / "release-signing-key.pem"
        path.write_text(key.export_key(format="PEM"), encoding="ascii")
        return key, path

    def test_builds_valid_signed_manifest_from_package_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            key, key_path = self.make_key(root)

            package_size = package.stat().st_size
            result = build_signed_release(
                package,
                key_path,
                ReleaseBuildOptions(
                    release_id="rel_051",
                    channel="stable",
                    published_at=datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc),
                    minimum_app_version="0.5.0",
                    minimum_launcher_version="0.1.0",
                    signing_key_id="release-key-demo-01",
                    release_summary="Demo update",
                ),
            )

        manifest = UpdateManifest.from_json_bytes(result.manifest_bytes)
        self.assertEqual("0.5.1", str(manifest.version))
        self.assertEqual("rel_051", manifest.release_id)
        self.assertEqual("release-key-demo-01", manifest.signing.key_id)
        self.assertEqual(package.name, manifest.package.filename)
        self.assertEqual(package_size, manifest.package.size)
        eddsa.new(key.public_key(), "rfc8032").verify(
            result.manifest_bytes,
            result.signature,
        )
        self.assertEqual(64, len(result.signature))
        self.assertEqual(64, len(result.manifest_sha256))
        self.assertEqual(64, len(result.package_sha256))
        self.assertNotIn("PRIVATE", repr(result))

    def test_manifest_bytes_are_deterministic_for_fixed_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            _key, key_path = self.make_key(root)
            options = ReleaseBuildOptions(
                release_id="rel_051",
                channel="stable",
                published_at=datetime(2026, 8, 5, 0, 0, tzinfo=timezone.utc),
                minimum_app_version="0.5.0",
                minimum_launcher_version="0.1.0",
                signing_key_id="release-key-demo-01",
            )

            first = build_signed_release(package, key_path, options)
            second = build_signed_release(package, key_path, options)

        self.assertEqual(first.manifest_bytes, second.manifest_bytes)
        self.assertEqual(first.signature, second.signature)

    def test_rejects_package_missing_declared_entrypoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root, entrypoint=False)
            _key, key_path = self.make_key(root)

            with self.assertRaises(Exception):
                build_signed_release(
                    package,
                    key_path,
                    ReleaseBuildOptions(
                        release_id="rel_051",
                        channel="stable",
                        published_at=datetime.now(timezone.utc),
                        minimum_app_version="0.5.0",
                        minimum_launcher_version="0.1.0",
                        signing_key_id="release-key-demo-01",
                    ),
                )

    def test_rejects_non_ed25519_or_public_only_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            p256 = ECC.generate(curve="P-256")
            wrong = root / "wrong.pem"
            wrong.write_text(p256.export_key(format="PEM"), encoding="ascii")
            public = root / "public.pem"
            public.write_text(
                ECC.generate(curve="Ed25519").public_key().export_key(format="PEM"),
                encoding="ascii",
            )

            with self.assertRaises(ValueError):
                load_ed25519_private_key(wrong)
            with self.assertRaises(ValueError):
                load_ed25519_private_key(public)

    def test_private_key_path_must_be_a_regular_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_ed25519_private_key(Path(tmp))


if __name__ == "__main__":
    unittest.main()
