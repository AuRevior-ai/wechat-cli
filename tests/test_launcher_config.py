import base64
import importlib.util
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from wechat_cli.launcher.config import LauncherConfig


PUBLIC_KEY = bytes(range(32))
PUBLIC_KEY_B64 = base64.b64encode(PUBLIC_KEY).decode("ascii")


class DeploymentTrustProfileTests(unittest.TestCase):
    def profile_mapping(self, **overrides):
        data = {
            "schema_version": 1,
            "environment": "staging",
            "api_base_url": "https://staging-api.example.test",
            "expected_channel": "beta",
            "fingerprint_salt": "staging-fingerprint-salt-v1",
            "release_public_keys": {"release-key-test-01": PUBLIC_KEY_B64},
            "lease_public_keys": {"lease-key-test-01": PUBLIC_KEY_B64},
            "windows_publisher_policy": "test-publisher",
        }
        data.update(overrides)
        return data

    def test_trust_profile_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("wechat_cli.launcher.trust_profile"))

    def test_trust_profile_exports_immutable_mapping_contract(self):
        from wechat_cli.launcher import trust_profile

        profile_type = getattr(trust_profile, "DeploymentTrustProfile", None)
        self.assertIsNotNone(profile_type)
        from_mapping = getattr(profile_type, "from_mapping", None)
        self.assertTrue(callable(from_mapping))

    def test_trust_profile_public_key_mappings_are_immutable(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        profile = DeploymentTrustProfile.from_mapping(self.profile_mapping())
        with self.assertRaises(TypeError):
            profile.release_public_keys["replacement"] = PUBLIC_KEY_B64
        with self.assertRaises(TypeError):
            profile.lease_public_keys["replacement"] = PUBLIC_KEY_B64

    def test_trust_profile_supports_strict_file_load(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        loader = getattr(DeploymentTrustProfile, "load", None)
        self.assertTrue(callable(loader))

    def test_trust_profile_file_load_validates_json_through_profile_model(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deployment-trust-profile.json"
            path.write_text(json.dumps(self.profile_mapping()), encoding="utf-8")
            try:
                profile = DeploymentTrustProfile.load(path)
            except Exception as exc:
                self.fail(f"valid deployment trust profile file was rejected: {exc}")

        self.assertEqual("staging", profile.environment)
        self.assertEqual("https://staging-api.example.test", profile.api_base_url)

    def test_embedded_trust_profile_loader_contract_exists(self):
        from wechat_cli.launcher import trust_profile

        loader = getattr(trust_profile, "load_embedded_trust_profile", None)
        self.assertTrue(callable(loader))

    def test_embedded_loader_reads_only_fixed_pyinstaller_resource_path(self):
        from wechat_cli.launcher.trust_profile import load_embedded_trust_profile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            resource = root / "wechat_cli" / "launcher" / "deployment-trust-profile.json"
            resource.parent.mkdir(parents=True)
            resource.write_text(json.dumps(self.profile_mapping()), encoding="utf-8")
            try:
                profile = load_embedded_trust_profile(root)
            except Exception as exc:
                self.fail(f"fixed embedded deployment trust profile was rejected: {exc}")

        self.assertEqual("staging", profile.environment)
        self.assertEqual("beta", profile.expected_channel)

    def test_production_profile_rejects_beta_loopback_staging_host_and_missing_publisher(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        cases = [
            {"expected_channel": "beta"},
            {"api_base_url": "http://127.0.0.1:8788"},
            {"api_base_url": "https://staging-api.example.test"},
            {"windows_publisher_policy": ""},
        ]
        for override in cases:
            with self.subTest(override=override):
                data = self.profile_mapping(
                    environment="production",
                    api_base_url="https://api.example.test",
                    expected_channel="stable",
                    windows_publisher_policy="CN=Example Publisher",
                )
                data.update(override)
                with self.assertRaises(ValueError):
                    DeploymentTrustProfile.from_mapping(data)

    def test_schema1_profile_preserves_legacy_distribution_mode(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        profile = DeploymentTrustProfile.from_mapping(self.profile_mapping())

        self.assertEqual("legacy", profile.distribution_profile)

    def test_schema2_private_controlled_production_allows_empty_publisher(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        profile = DeploymentTrustProfile.from_mapping(
            self.profile_mapping(
                schema_version=2,
                distribution_profile="private_controlled",
                environment="production",
                api_base_url="https://api.example.test",
                expected_channel="stable",
                windows_publisher_policy="",
            )
        )

        self.assertEqual(2, profile.schema_version)
        self.assertEqual("private_controlled", profile.distribution_profile)
        self.assertEqual("", profile.windows_publisher_policy)

    def test_schema2_public_formal_requires_publisher(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        with self.assertRaisesRegex(ValueError, "public.*publisher|publisher.*public"):
            DeploymentTrustProfile.from_mapping(
                self.profile_mapping(
                    schema_version=2,
                    distribution_profile="public_formal",
                    environment="production",
                    api_base_url="https://api.example.test",
                    expected_channel="stable",
                    windows_publisher_policy="",
                )
            )

    def test_schema2_requires_explicit_distribution_profile(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        with self.assertRaisesRegex(ValueError, "distribution profile"):
            DeploymentTrustProfile.from_mapping(
                self.profile_mapping(
                    schema_version=2,
                    environment="production",
                    api_base_url="https://api.example.test",
                    expected_channel="stable",
                    windows_publisher_policy="",
                )
            )

    def test_schema2_private_production_preserves_environment_guards(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        cases = [
            {"expected_channel": "beta"},
            {"api_base_url": "http://127.0.0.1:8788"},
            {"api_base_url": "https://staging-api.example.test"},
        ]
        for override in cases:
            with self.subTest(override=override):
                data = self.profile_mapping(
                    schema_version=2,
                    distribution_profile="private_controlled",
                    environment="production",
                    api_base_url="https://api.example.test",
                    expected_channel="stable",
                    windows_publisher_policy="",
                )
                data.update(override)
                with self.assertRaises(ValueError):
                    DeploymentTrustProfile.from_mapping(data)


class LauncherConfigTests(unittest.TestCase):
    def deployment_profile(self):
        from wechat_cli.launcher.trust_profile import DeploymentTrustProfile

        return DeploymentTrustProfile.from_mapping(
            {
                "schema_version": 1,
                "environment": "staging",
                "api_base_url": "https://staging-api.example.test",
                "expected_channel": "beta",
                "fingerprint_salt": "embedded-fingerprint-salt",
                "release_public_keys": {"release-key-test-01": PUBLIC_KEY_B64},
                "lease_public_keys": {"lease-key-test-01": PUBLIC_KEY_B64},
                "windows_publisher_policy": "CN=Board6 Test Publisher",
            }
        )

    def test_launcher_config_accepts_explicit_trust_profile(self):
        self.assertIn("trust_profile", inspect.signature(LauncherConfig.from_mapping).parameters)

    def test_external_config_cannot_redeclare_trust_critical_fields(self):
        with self.assertRaises(ValueError):
            LauncherConfig.from_mapping(
                self.config_mapping(),
                trust_profile=self.deployment_profile(),
            )

        with self.assertRaisesRegex(ValueError, "distribution_profile"):
            LauncherConfig.from_mapping(
                {
                    "schema_version": 2,
                    "port": 8787,
                    "distribution_profile": "public_formal",
                },
                trust_profile=self.deployment_profile(),
            )

    def test_operational_config_derives_all_trust_fields_from_profile(self):
        profile = self.deployment_profile()
        try:
            config = LauncherConfig.from_mapping(
                {"schema_version": 2, "port": 8787},
                trust_profile=profile,
            )
        except Exception as exc:
            self.fail(f"operational config with embedded trust profile was rejected: {exc}")

        self.assertEqual("https://staging-api.example.test", config.api_base_url)
        self.assertEqual("beta", config.channel)
        self.assertEqual("embedded-fingerprint-salt", config.fingerprint_salt)
        self.assertEqual("staging", config.environment)
        self.assertEqual("legacy", config.distribution_profile)
        self.assertEqual("CN=Board6 Test Publisher", config.windows_publisher_policy)
        config.release_keys.verify
        config.lease_keys.verify

    def config_mapping(self, **overrides):
        data = {
            "schema_version": 1,
            "api_base_url": "https://api.example.test",
            "port": 8787,
            "channel": "stable",
            "fingerprint_salt": "fingerprint-salt-v1",
            "release_public_keys": {"release-key-test-01": PUBLIC_KEY_B64},
            "lease_public_keys": {"lease-key-test-01": PUBLIC_KEY_B64},
        }
        data.update(overrides)
        return data

    def test_loads_valid_config_and_derives_endpoints(self):
        config = LauncherConfig.from_mapping(self.config_mapping())

        self.assertEqual("https://api.example.test", config.api_base_url)
        self.assertEqual(
            "https://api.example.test/v1/updates/download",
            config.update_download_url,
        )
        self.assertEqual(8787, config.port)
        self.assertEqual("stable", config.channel)
        config.release_keys.verify  # trusted key registry exists
        config.lease_keys.verify

    def test_loads_utf8_json_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "launcher-config.json"
            path.write_text(
                json.dumps(self.config_mapping(), ensure_ascii=False),
                encoding="utf-8",
            )

            config = LauncherConfig.load(path)

        self.assertEqual("fingerprint-salt-v1", config.fingerprint_salt)

    def test_rejects_http_non_local_api(self):
        with self.assertRaises(ValueError):
            LauncherConfig.from_mapping(
                self.config_mapping(api_base_url="http://api.example.test")
            )

    def test_allows_http_loopback_only_in_explicit_development_mode(self):
        data = self.config_mapping(api_base_url="http://127.0.0.1:8788")
        with self.assertRaises(ValueError):
            LauncherConfig.from_mapping(data)

        config = LauncherConfig.from_mapping(data, allow_insecure_loopback=True)
        self.assertEqual("http://127.0.0.1:8788", config.api_base_url)

    def test_rejects_invalid_port_channel_and_public_key(self):
        cases = [
            {"port": 0},
            {"port": 70000},
            {"channel": "nightly"},
            {"release_public_keys": {"key": "bad-base64"}},
            {"lease_public_keys": {}},
        ]
        for override in cases:
            with self.subTest(override=override):
                with self.assertRaises(ValueError):
                    LauncherConfig.from_mapping(self.config_mapping(**override))


if __name__ == "__main__":
    unittest.main()
