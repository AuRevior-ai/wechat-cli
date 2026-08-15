from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch


class Board6G5BehaviorAcceptanceTests(unittest.TestCase):
    def _module(self):
        try:
            from scripts import board6_g5_behavior_acceptance as module
        except ImportError:
            module = SimpleNamespace()
        self.assertTrue(hasattr(module, "run_acceptance"))
        self.assertTrue(hasattr(module, "read_single_license_csv"))
        return module

    def test_single_license_csv_keeps_full_key_internal(self):
        module = self._module()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "license.csv"
            path.write_text(
                "license_id,license_key,license_hint,maximum_devices,release_channel,created_at\n"
                "lic_test,wclic_secret_value,HINT,1,beta,2026-08-14T00:00:00Z\n",
                encoding="utf-8",
            )
            record = module.read_single_license_csv(path)
            self.assertEqual("lic_test", record.license_id)
            self.assertEqual("HINT", record.license_hint)
            self.assertEqual("beta", record.release_channel)
            self.assertEqual("wclic_secret_value", record.license_key)
            self.assertNotIn("wclic_secret_value", repr(record))

    def test_range_probe_uses_real_updater_user_agent_and_range(self):
        module = self._module()

        class Response:
            status = 206
            headers = {"Content-Range": "bytes 0-0/10"}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _size=-1):
                return b"x"

        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

        with patch.object(module, "urlopen", side_effect=opener):
            result = module._default_range_probe(
                api_url="https://api.example.test",
                ticket="download-secret",
                expected_size=10,
            )

        self.assertEqual(206, result["status"])
        request = captured["request"]
        self.assertEqual("bytes=0-0", request.get_header("Range"))
        self.assertTrue(request.get_header("User-agent").startswith("WeChatCliUpdate/"))
        self.assertNotIn("download-secret", request.full_url)

    def test_run_acceptance_reports_only_safe_summary(self):
        module = self._module()

        stable = SimpleNamespace(
            license_id="lic_stable",
            license_key="stable-secret",
            license_hint="STBL",
            release_channel="stable",
        )
        beta = SimpleNamespace(
            license_id="lic_beta",
            license_key="beta-secret",
            license_hint="BETA",
            release_channel="beta",
        )
        stable_activation = SimpleNamespace(
            license_id="lic_stable",
            device_id="dev_stable",
            device_token="device-token-stable",
        )
        beta_activation = SimpleNamespace(
            license_id="lic_beta",
            device_id="dev_beta",
            device_token="device-token-beta",
        )

        license_client = Mock()
        license_client.activate.side_effect = [stable_activation, beta_activation]

        candidate_manifest = SimpleNamespace(
            release_id="rel_board6_g5_052_01",
            version="0.5.2-board6g5.1",
            package=SimpleNamespace(
                filename="wechat-cli-app-0.5.2-board6g5.1-win-x64.zip",
                size=14268937,
                sha256="a" * 64,
            ),
        )
        candidate = SimpleNamespace(
            update_available=True,
            manifest=candidate_manifest,
            raw_manifest=b"manifest",
            download_ticket="download-secret-1",
        )
        no_update = SimpleNamespace(update_available=False, manifest=None, download_ticket=None)

        class MismatchError(Exception):
            def __init__(self):
                self.code = SimpleNamespace(value="UPDATE_CHANNEL_MISMATCH")
                self.retryable = False

        update_client = Mock()
        update_client.check.side_effect = [
            no_update,
            MismatchError(),
            MismatchError(),
            candidate,
            candidate,
            no_update,
            candidate,
        ]

        range_probe = Mock(return_value={"status": 206, "content_range": "bytes 0-0/14268937"})
        full_download = Mock(return_value={"size": 14268937, "sha256": "a" * 64})

        summary = module.run_acceptance(
            stable_license=stable,
            beta_license=beta,
            license_client=license_client,
            update_client=update_client,
            expected_release_id="rel_board6_g5_052_01",
            expected_version="0.5.2-board6g5.1",
            expected_manifest_sha256=__import__("hashlib").sha256(b"manifest").hexdigest(),
            expected_package_sha256="a" * 64,
            expected_package_size=14268937,
            range_probe=range_probe,
            full_download=full_download,
        )

        serialized = json.dumps(summary, sort_keys=True)
        for secret in (
            "stable-secret",
            "beta-secret",
            "device-token-stable",
            "device-token-beta",
            "download-secret-1",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual("UPDATE_CHANNEL_MISMATCH", summary["stable_mismatch_code"])
        self.assertEqual("UPDATE_CHANNEL_MISMATCH", summary["beta_mismatch_code"])
        self.assertTrue(summary["wrong_manifest_hash_remains_selectable"])
        self.assertTrue(summary["exact_failed_release_suppressed"])
        self.assertEqual(206, summary["r2_range_status"])


if __name__ == "__main__":
    unittest.main()
