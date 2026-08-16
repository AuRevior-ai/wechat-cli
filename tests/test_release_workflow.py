import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from Crypto.PublicKey import ECC

from scripts import production_release
from wechat_cli.admin.client import AdminApiError
from wechat_cli.release.builder import ReleaseBuildOptions
from wechat_cli.release.workflow import (
    load_prepared_release,
    sign_release_for_workflow,
)


class ReleaseWorkflowTests(unittest.TestCase):
    def test_production_release_entrypoint_is_directly_executable(self):
        root = Path(__file__).resolve().parents[1]
        for arguments in (
            ["--help"],
            ["sign", "--help"],
            ["probe", "--help"],
            ["publish", "--help"],
        ):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [sys.executable, str(root / "scripts" / "production_release.py"), *arguments],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(0, result.returncode, result.stderr)

    def test_production_probe_uses_same_python_transport_without_mutation(self):
        class FakeTransport:
            def __init__(self):
                self.json_calls = []
                self.upload_calls = []

            def json_request(self, method, path, headers, payload):
                self.json_calls.append((method, path, dict(headers), payload))
                return 200, {"releases": []}

            def upload(self, path, headers, source, metadata_headers):
                source_path = Path(source)
                self.upload_calls.append(
                    (
                        path,
                        dict(headers),
                        source_path.stat().st_size,
                        dict(metadata_headers),
                    )
                )
                raise AdminApiError(
                    "INVALID_REQUEST",
                    "发布包摘要无效。",
                    status=400,
                )

        fake = FakeTransport()
        with patch.object(
            production_release,
            "UrllibReleaseAutomationTransport",
            return_value=fake,
        ), patch.dict(
            os.environ,
            {
                "WECHAT_CLI_ACCESS_CLIENT_ID": "client-id.access",
                "WECHAT_CLI_ACCESS_CLIENT_SECRET": "client-secret",
            },
            clear=False,
        ):
            result = production_release.probe_command(
                SimpleNamespace(admin_origin="https://admin.example.test")
            )

        self.assertEqual(
            {
                "ok": True,
                "release_count": 0,
                "put_probe_status": 400,
                "put_probe_code": "INVALID_REQUEST",
            },
            result,
        )
        self.assertEqual("GET", fake.json_calls[0][0])
        self.assertEqual("/v1/automation/releases", fake.json_calls[0][1])
        self.assertEqual(1, len(fake.upload_calls))
        upload_path, _, source_size, metadata = fake.upload_calls[0]
        self.assertEqual(
            "/v1/automation/releases/rel_transport_probe/package",
            upload_path,
        )
        self.assertEqual(1, source_size)
        self.assertEqual("invalid", metadata["X-Package-Sha256"])
        self.assertEqual("1", metadata["Content-Length"])

    def test_production_sign_cli_does_not_expose_rollout_control(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(
            [sys.executable, str(root / "scripts" / "production_release.py"), "sign", "--help"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertNotIn("--rollout-percentage", result.stdout)

    def make_package(self, root: Path) -> Path:
        package = root / "wechat-cli-app-0.6.0-win-x64.zip"
        with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "app-manifest.json",
                json.dumps(
                    {
                        "product": "wechat-cli-web",
                        "version": "0.6.0",
                        "platform": "windows",
                        "architecture": "x86_64",
                        "entrypoint": "wechat-cli.exe",
                        "build_id": "prod-060-aaaaaaaaaaaa",
                    }
                ),
            )
            archive.writestr("wechat-cli.exe", b"binary")
        return package

    def make_key_and_profile(self, root: Path):
        key = ECC.generate(curve="Ed25519")
        key_path = root / "release-key.pem"
        key_path.write_text(key.export_key(format="PEM"), encoding="ascii")
        raw_public = key.public_key().export_key(format="raw")
        self.assertIsInstance(raw_public, bytes)
        profile = root / "deployment-trust-profile.json"
        profile.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "distribution_profile": "private_controlled",
                    "environment": "production",
                    "api_base_url": "https://api.prod.example.test",
                    "expected_channel": "stable",
                    "fingerprint_salt": "fresh-production-fingerprint-salt",
                    "release_public_keys": {
                        "release-key-production-01": base64.b64encode(raw_public).decode("ascii")
                    },
                    "lease_public_keys": {
                        "lease-key-production-01": base64.b64encode(bytes(range(32))).decode("ascii")
                    },
                    "windows_publisher_policy": "",
                }
            ),
            encoding="utf-8",
        )
        return key_path, profile

    def test_sign_step_outputs_safe_prepared_assets_and_publish_step_reloads_without_private_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            key_path, profile = self.make_key_and_profile(root)
            output = root / "prepared"
            result = sign_release_for_workflow(
                package_path=package,
                signing_key_path=key_path,
                output_dir=output,
                options=ReleaseBuildOptions(
                    release_id="rel_prod_060",
                    channel="stable",
                    published_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
                    minimum_app_version="0.6.0",
                    minimum_launcher_version="0.2.0",
                    signing_key_id="release-key-production-01",
                    release_summary="Production baseline",
                ),
            )

            self.assertEqual(
                {"manifest", "signature", "metadata", "manifest_sha256", "package_sha256", "package_size"},
                set(result),
            )
            self.assertNotIn("PRIVATE", json.dumps(result))
            loaded = load_prepared_release(
                package_path=package,
                manifest_path=Path(result["manifest"]),
                signature_path=Path(result["signature"]),
                metadata_path=Path(result["metadata"]),
                trust_profile_path=profile,
                expected_api_origin="https://api.prod.example.test",
            )

        self.assertEqual("0.6.0", loaded.version)
        self.assertEqual("rel_prod_060", loaded.release_id)
        self.assertEqual("stable", loaded.channel)
        self.assertEqual("release-key-production-01", loaded.signing_key_id)

    def test_prepared_release_rejects_package_or_signature_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = self.make_package(root)
            key_path, profile = self.make_key_and_profile(root)
            output = root / "prepared"
            result = sign_release_for_workflow(
                package_path=package,
                signing_key_path=key_path,
                output_dir=output,
                options=ReleaseBuildOptions(
                    release_id="rel_prod_060",
                    channel="stable",
                    published_at=datetime(2026, 8, 15, tzinfo=timezone.utc),
                    minimum_app_version="0.6.0",
                    minimum_launcher_version="0.2.0",
                    signing_key_id="release-key-production-01",
                ),
            )
            signature = Path(result["signature"])
            signature.write_bytes(b"x" * 64)
            with self.assertRaises(Exception):
                load_prepared_release(
                    package_path=package,
                    manifest_path=Path(result["manifest"]),
                    signature_path=signature,
                    metadata_path=Path(result["metadata"]),
                    trust_profile_path=profile,
                    expected_api_origin="https://api.prod.example.test",
                )


if __name__ == "__main__":
    unittest.main()
