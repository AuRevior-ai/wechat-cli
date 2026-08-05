import json
import unittest

from wechat_cli.update.errors import ErrorCode, ManifestValidationError
from wechat_cli.update.models import UpdateManifest


def make_manifest(**overrides):
    data = {
        "schema_version": 1,
        "product": "wechat-cli-web",
        "release_id": "rel_test_050",
        "version": "0.5.0",
        "channel": "stable",
        "published_at": "2026-08-04T15:00:00Z",
        "platform": "windows",
        "architecture": "x86_64",
        "package": {
            "filename": "wechat-cli-app-0.5.0-win-x64.zip",
            "size": 84213760,
            "sha256": "ab" * 32,
            "format": "zip",
        },
        "compatibility": {
            "minimum_app_version": "0.4.2",
            "minimum_launcher_version": "0.1.0",
            "maximum_launcher_version": None,
        },
        "install": {
            "entrypoint": "wechat-cli.exe",
            "health_endpoint": "/api/health",
            "health_timeout_seconds": 30,
        },
        "rollout": {
            "enabled": True,
            "percentage": 100,
            "seed": "stable-0.5.0",
            "paused": False,
        },
        "update_policy": {
            "forced": False,
            "force_after": None,
            "minimum_allowed_version": None,
        },
        "launcher_update": None,
        "release_notes": {
            "summary": "测试更新",
            "url": None,
        },
        "signing": {
            "algorithm": "Ed25519",
            "key_id": "release-key-test-01",
        },
    }
    data.update(overrides)
    return data


class UpdateManifestTests(unittest.TestCase):
    def test_parses_complete_manifest(self):
        raw = json.dumps(make_manifest(), ensure_ascii=False).encode("utf-8")

        manifest = UpdateManifest.from_json_bytes(raw)

        self.assertEqual("0.5.0", str(manifest.version))
        self.assertEqual("wechat-cli-app-0.5.0-win-x64.zip", manifest.package.filename)
        self.assertEqual(100, manifest.rollout.percentage)
        self.assertFalse(manifest.update_policy.forced)
        self.assertEqual("release-key-test-01", manifest.signing.key_id)

    def test_optional_demo_sections_use_safe_defaults(self):
        data = make_manifest()
        data.pop("rollout")
        data.pop("update_policy")
        data.pop("release_notes")
        data.pop("launcher_update")

        manifest = UpdateManifest.from_mapping(data)

        self.assertTrue(manifest.rollout.enabled)
        self.assertEqual(100, manifest.rollout.percentage)
        self.assertFalse(manifest.rollout.paused)
        self.assertFalse(manifest.update_policy.forced)
        self.assertIsNone(manifest.launcher_update)
        self.assertEqual("", manifest.release_notes.summary)

    def test_rejects_unknown_schema_version(self):
        with self.assertRaises(ManifestValidationError) as caught:
            UpdateManifest.from_mapping(make_manifest(schema_version=2))

        self.assertEqual(ErrorCode.UPDATE_SCHEMA_UNSUPPORTED, caught.exception.code)

    def test_rejects_invalid_package_hash(self):
        data = make_manifest()
        data["package"] = dict(data["package"], sha256="not-a-sha256")

        with self.assertRaises(ManifestValidationError) as caught:
            UpdateManifest.from_mapping(data)

        self.assertEqual(ErrorCode.UPDATE_MANIFEST_INVALID, caught.exception.code)

    def test_rejects_rollout_percentage_outside_range(self):
        data = make_manifest()
        data["rollout"] = dict(data["rollout"], percentage=101)

        with self.assertRaises(ManifestValidationError) as caught:
            UpdateManifest.from_mapping(data)

        self.assertEqual(ErrorCode.UPDATE_MANIFEST_INVALID, caught.exception.code)

    def test_validates_product_platform_and_architecture(self):
        manifest = UpdateManifest.from_mapping(make_manifest())

        manifest.validate_target(
            product="wechat-cli-web",
            platform="windows",
            architecture="x86_64",
            current_app_version="0.4.2",
            launcher_version="0.1.0",
        )

        cases = [
            ({"product": "other", "platform": "windows", "architecture": "x86_64"}, ErrorCode.UPDATE_PRODUCT_MISMATCH),
            ({"product": "wechat-cli-web", "platform": "linux", "architecture": "x86_64"}, ErrorCode.UPDATE_PLATFORM_MISMATCH),
            ({"product": "wechat-cli-web", "platform": "windows", "architecture": "arm64"}, ErrorCode.UPDATE_ARCHITECTURE_MISMATCH),
        ]
        for target, expected_code in cases:
            with self.subTest(target=target):
                with self.assertRaises(ManifestValidationError) as caught:
                    manifest.validate_target(
                        current_app_version="0.4.2",
                        launcher_version="0.1.0",
                        **target,
                    )
                self.assertEqual(expected_code, caught.exception.code)

    def test_rejects_launcher_older_than_minimum(self):
        manifest = UpdateManifest.from_mapping(make_manifest())

        with self.assertRaises(ManifestValidationError) as caught:
            manifest.validate_target(
                product="wechat-cli-web",
                platform="windows",
                architecture="x86_64",
                current_app_version="0.4.2",
                launcher_version="0.0.9",
            )

        self.assertEqual(ErrorCode.LAUNCHER_TOO_OLD, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
