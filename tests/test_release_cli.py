import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from Crypto.PublicKey import ECC
from click.testing import CliRunner

from wechat_cli.release.builder import SignedRelease
from wechat_cli.release.cli import cli
from wechat_cli.release.config import ReleaseConfig
from wechat_cli.release.publisher import PublishedRelease


class FakeStorage:
    def __init__(self, config=None):
        self.config = config
        self.saved = []
        self.path = Path("release-config.dat")

    def save(self, config):
        self.saved.append(config)
        self.config = config

    def load(self):
        return self.config


class ReleaseCliTests(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def make_key(self, root: Path):
        key = ECC.generate(curve="Ed25519")
        path = root / "release-key.pem"
        path.write_text(key.export_key(format="PEM"), encoding="ascii")
        return path

    def make_package(self, root: Path, version="0.5.1"):
        package = root / f"wechat-cli-app-{version}-win-x64.zip"
        with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as archive:
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
            archive.writestr("wechat-cli.exe", b"binary")
        return package

    def config(self, key_path):
        return ReleaseConfig(
            repository="example/releases",
            target_commitish="main",
            github_token="github_pat_secret_value",
            signing_key_path=str(Path(key_path).resolve()),
            signing_key_id="release-key-demo-01",
        )

    def test_help_exposes_config_prepare_publish(self):
        result = self.runner.invoke(cli, ["--help"])

        self.assertEqual(0, result.exit_code, result.output)
        for command in ("config", "prepare", "publish"):
            self.assertIn(command, result.output)
        self.assertNotIn("--github-token", result.output)

    def test_config_set_prompts_hidden_github_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = self.make_key(Path(tmp))
            storage = FakeStorage()
            with patch("wechat_cli.release.cli._storage", return_value=storage):
                result = self.runner.invoke(
                    cli,
                    [
                        "config",
                        "set",
                        "--repository",
                        "example/releases",
                        "--target-commitish",
                        "main",
                        "--signing-key",
                        str(key),
                        "--signing-key-id",
                        "release-key-demo-01",
                    ],
                    input="github_pat_secret_value\n",
                )

        self.assertEqual(0, result.exit_code, result.output)
        self.assertEqual(1, len(storage.saved))
        self.assertEqual("example/releases", storage.saved[0].repository)
        self.assertNotIn("github_pat_secret_value", result.output)

    def test_prepare_writes_manifest_and_signature_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = self.make_key(root)
            package = self.make_package(root)
            output = root / "prepared"
            storage = FakeStorage(self.config(key))
            arguments = [
                "prepare",
                str(package),
                "--release-id",
                "rel_051",
                "--minimum-app-version",
                "0.5.0",
                "--minimum-launcher-version",
                "0.1.0",
                "--published-at",
                "2026-08-05T00:00:00Z",
                "--output-dir",
                str(output),
            ]
            with patch("wechat_cli.release.cli._storage", return_value=storage):
                first = self.runner.invoke(cli, arguments)
                second = self.runner.invoke(cli, arguments)

            self.assertEqual(0, first.exit_code, first.output)
            self.assertTrue((output / "wechat-cli-update-manifest-0.5.1.json").is_file())
            self.assertEqual(
                64,
                (output / "wechat-cli-update-manifest-0.5.1.sig").stat().st_size,
            )
            self.assertNotEqual(0, second.exit_code)
            self.assertIn("已存在", second.output)

    def test_publish_uses_configured_clients_and_keeps_enable_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = self.make_key(root)
            package = self.make_package(root)
            storage = FakeStorage(self.config(key))
            signed = SignedRelease(
                package_path=package,
                manifest_bytes=b"{}",
                signature=b"s" * 64,
                manifest_sha256="11" * 32,
                package_sha256="22" * 32,
                package_size=package.stat().st_size,
                version="0.5.1",
                release_id="rel_051",
                channel="stable",
                signing_key_id="release-key-demo-01",
            )
            published = PublishedRelease(
                release_id="rel_051",
                version="0.5.1",
                github_release_id=123,
                package_asset_id=401,
                manifest_asset_id=402,
                signature_asset_id=403,
                enabled=False,
                paused=True,
            )
            with (
                patch("wechat_cli.release.cli._storage", return_value=storage),
                patch("wechat_cli.release.cli.build_signed_release", return_value=signed),
                patch("wechat_cli.release.cli._github_client", return_value=object()),
                patch("wechat_cli.release.cli._admin_client", return_value=object()),
                patch(
                    "wechat_cli.release.cli.publish_signed_release",
                    return_value=published,
                ) as publish,
            ):
                result = self.runner.invoke(
                    cli,
                    [
                        "--json",
                        "publish",
                        str(package),
                        "--release-id",
                        "rel_051",
                        "--minimum-app-version",
                        "0.5.0",
                        "--minimum-launcher-version",
                        "0.1.0",
                        "--published-at",
                        "2026-08-05T00:00:00Z",
                    ],
                )

        self.assertEqual(0, result.exit_code, result.output)
        payload = json.loads(result.output)
        self.assertFalse(payload["enabled"])
        self.assertTrue(payload["paused"])
        self.assertNotIn("enable", publish.call_args.kwargs)
        self.assertNotIn("enable_operation_nonce", publish.call_args.kwargs)
        self.assertGreaterEqual(
            len(publish.call_args.kwargs["upload_operation_nonce"]),
            8,
        )


if __name__ == "__main__":
    unittest.main()
