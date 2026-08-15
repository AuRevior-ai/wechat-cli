import hashlib
import tempfile
import unittest
from pathlib import Path

from wechat_cli.release.automation_client import ReleaseAutomationClient


class ReleaseAutomationClientTests(unittest.TestCase):
    def test_client_exposes_prepare_read_register_only(self):
        client = ReleaseAutomationClient(
            json_transport=lambda method, path, headers, payload: (200, {"releases": []}),
            upload_transport=lambda path, headers, source, metadata: {"ready": True},
            header_provider=lambda: {"Cf-Access-Client-Id": "safe-client-id"},
        )
        self.assertTrue(callable(client.list_releases))
        self.assertTrue(callable(client.upload_release_package))
        self.assertTrue(callable(client.register_release))
        self.assertFalse(hasattr(client, "update_release"))

    def test_paths_use_only_automation_surface_and_headers_are_injected(self):
        calls = []

        def json_transport(method, path, headers, payload):
            calls.append(("json", method, path, dict(headers), payload))
            if method == "GET":
                return 200, {"releases": []}
            return 201, {"release_id": payload["release_id"], "enabled": False, "paused": True}

        def upload_transport(path, headers, source, metadata):
            calls.append(("upload", path, dict(headers), Path(source), dict(metadata)))
            return {"release_id": "rel_060", "ready": True}

        client = ReleaseAutomationClient(
            json_transport=json_transport,
            upload_transport=upload_transport,
            header_provider=lambda: {
                "Cf-Access-Client-Id": "safe-client-id",
                "Cf-Access-Client-Secret": "test-only-secret",
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package.zip"
            package.write_bytes(b"abc")
            digest = hashlib.sha256(b"abc").hexdigest()
            client.upload_release_package(
                "rel_060",
                channel="stable",
                package_path=package,
                package_sha256=digest,
                operation_nonce="nonce_upload_01",
            )
        client.register_release({"release_id": "rel_060"})
        self.assertEqual([], client.list_releases())

        self.assertEqual("/v1/automation/releases/rel_060/package", calls[0][1])
        self.assertEqual("/v1/automation/releases", calls[1][2])
        self.assertEqual("/v1/automation/releases", calls[2][2])
        self.assertEqual("safe-client-id", calls[0][2]["Cf-Access-Client-Id"])


if __name__ == "__main__":
    unittest.main()
