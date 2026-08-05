import base64
import json
import tempfile
import unittest
from pathlib import Path

from wechat_cli.launcher.config import LauncherConfig


PUBLIC_KEY = bytes(range(32))
PUBLIC_KEY_B64 = base64.b64encode(PUBLIC_KEY).decode("ascii")


class LauncherConfigTests(unittest.TestCase):
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
