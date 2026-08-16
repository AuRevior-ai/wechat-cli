import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.release.automation_client import (
    ReleaseAutomationClient,
    UrllibReleaseAutomationTransport,
)
from wechat_cli.version import APP_VERSION


class ReleaseAutomationClientTests(unittest.TestCase):
    def test_urllib_transport_sets_product_user_agent_for_json_and_upload_requests(self):
        requests = []

        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, _limit):
                return b'{"releases":[],"ready":true}'

        def fake_urlopen(request, timeout):
            requests.append(request)
            return FakeResponse()

        transport = UrllibReleaseAutomationTransport("https://admin.example.test")
        with patch("wechat_cli.release.automation_client.urlopen", side_effect=fake_urlopen):
            transport.json_request("GET", "/v1/automation/releases", {}, None)
            with tempfile.TemporaryDirectory() as tmp:
                package = Path(tmp) / "package.zip"
                package.write_bytes(b"abc")
                transport.upload(
                    "/v1/automation/releases/rel_060/package",
                    {},
                    package,
                    {
                        "X-Release-Channel": "stable",
                        "X-Package-Sha256": hashlib.sha256(b"abc").hexdigest(),
                        "X-Operation-Nonce": "nonce_upload_01",
                        "Content-Length": "3",
                    },
                )

        expected = f"WeChatCliReleaseAutomation/{APP_VERSION}"
        self.assertEqual(2, len(requests))
        for request in requests:
            with self.subTest(method=request.method):
                self.assertEqual(expected, request.get_header("User-agent"))

    def test_https_transport_is_restricted_to_custom_automation_origin_and_paths(self):
        for invalid in (
            "http://admin.example.test",
            "https://worker.workers.dev",
            "https://admin.example.test/path",
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                UrllibReleaseAutomationTransport(invalid)
        transport = UrllibReleaseAutomationTransport("https://admin.example.test")
        self.assertIn("admin.example.test", repr(transport))
        with self.assertRaisesRegex(ValueError, "/v1/automation"):
            transport.json_request("GET", "/v1/admin/releases", {}, None)

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
        client.register_release(
            {
                "release_id": "rel_060",
                "rollout_percentage": 100,
                "rollout_seed": "caller-controlled-seed",
            }
        )
        self.assertEqual([], client.list_releases())

        self.assertEqual("/v1/automation/releases/rel_060/package", calls[0][1])
        self.assertEqual("/v1/automation/releases", calls[1][2])
        self.assertEqual("/v1/automation/releases", calls[2][2])
        self.assertEqual("safe-client-id", calls[0][2]["Cf-Access-Client-Id"])
        registration_payload = calls[1][4]
        self.assertNotIn("rollout_percentage", registration_payload)
        self.assertNotIn("rollout_seed", registration_payload)


if __name__ == "__main__":
    unittest.main()
