import base64
import json
import unittest

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from tests.test_update_models import make_manifest
from wechat_cli.update.client import UpdateApiClient
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.errors import ErrorCode, UpdateError


TEST_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes(range(32)))
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key().export_key(format="raw")


class FakeTransport:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __call__(self, method, path, headers, payload):
        self.calls.append((method, path, headers, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def signed_response():
    raw = json.dumps(make_manifest(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(raw)
    return {
        "update_available": True,
        "manifest": {
            "content_base64": base64.b64encode(raw).decode("ascii"),
            "signature_base64": base64.b64encode(signature).decode("ascii"),
        },
        "download_ticket": "dlt_ticket_secret",
        "download_ticket_expires_at": "2026-08-04T15:10:00Z",
    }


class UpdateApiClientTests(unittest.TestCase):
    def setUp(self):
        self.keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

    def test_check_sends_device_token_and_target_metadata(self):
        transport = FakeTransport((200, signed_response()))
        client = UpdateApiClient(transport, trusted_keys=self.keys)

        result = client.check(
            device_token="wcdt_token.secret",
            current_version="0.4.2",
            launcher_version="0.1.0",
            channel="stable",
            platform="windows",
            architecture="x86_64",
            product="wechat-cli-web",
            device_id="dev_01",
            failed_versions=["0.4.9"],
        )

        method, path, headers, payload = transport.calls[0]
        self.assertEqual(("POST", "/v1/updates/check"), (method, path))
        self.assertEqual("Bearer wcdt_token.secret", headers["Authorization"])
        self.assertNotIn("wcdt_token.secret", path)
        self.assertEqual("0.4.2", payload["current_version"])
        self.assertEqual("wechat-cli-web", payload["product"])
        self.assertEqual(["0.4.9"], payload["failed_versions"])
        self.assertTrue(result.update_available)
        self.assertEqual("0.5.0", str(result.manifest.version))
        self.assertEqual("dlt_ticket_secret", result.download_ticket)
        self.assertNotIn("dlt_ticket_secret", repr(result))

    def test_no_update_response_has_no_download_secret(self):
        transport = FakeTransport(
            (
                200,
                {
                    "update_available": False,
                    "current_version": "0.4.2",
                    "channel": "stable",
                    "checked_at": "2026-08-04T15:00:00Z",
                },
            )
        )

        result = UpdateApiClient(transport, trusted_keys=self.keys).check(
            device_token="token",
            current_version="0.4.2",
            launcher_version="0.1.0",
            channel="stable",
            platform="windows",
            architecture="x86_64",
            product="wechat-cli-web",
            device_id="dev_01",
            failed_versions=[],
        )

        self.assertFalse(result.update_available)
        self.assertIsNone(result.manifest)
        self.assertIsNone(result.download_ticket)

    def test_tampered_manifest_is_rejected_before_ticket_is_used(self):
        response = signed_response()
        raw = base64.b64decode(response["manifest"]["content_base64"])
        response["manifest"]["content_base64"] = base64.b64encode(raw + b" ").decode("ascii")
        transport = FakeTransport((200, response))

        with self.assertRaises(UpdateError) as caught:
            UpdateApiClient(transport, trusted_keys=self.keys).check(
                device_token="token",
                current_version="0.4.2",
                launcher_version="0.1.0",
                channel="stable",
                platform="windows",
                architecture="x86_64",
                product="wechat-cli-web",
                device_id="dev_01",
                failed_versions=[],
            )

        self.assertEqual(ErrorCode.UPDATE_SIGNATURE_INVALID, caught.exception.code)

    def test_manifest_target_mismatch_is_rejected(self):
        transport = FakeTransport((200, signed_response()))

        with self.assertRaises(UpdateError) as caught:
            UpdateApiClient(transport, trusted_keys=self.keys).check(
                device_token="token",
                current_version="0.4.2",
                launcher_version="0.1.0",
                channel="stable",
                platform="linux",
                architecture="x86_64",
                product="wechat-cli-web",
                device_id="dev_01",
                failed_versions=[],
            )

        self.assertEqual(ErrorCode.UPDATE_PLATFORM_MISMATCH, caught.exception.code)

    def test_server_error_is_stable_update_error(self):
        transport = FakeTransport(
            (
                403,
                {
                    "error": {
                        "code": "UPDATE_PAUSED",
                        "message": "发布已暂停",
                        "retryable": False,
                    }
                },
            )
        )

        with self.assertRaises(UpdateError) as caught:
            UpdateApiClient(transport, trusted_keys=self.keys).check(
                device_token="token",
                current_version="0.4.2",
                launcher_version="0.1.0",
                channel="stable",
                platform="windows",
                architecture="x86_64",
                product="wechat-cli-web",
                device_id="dev_01",
                failed_versions=[],
            )

        self.assertEqual(ErrorCode.UPDATE_PAUSED, caught.exception.code)
        self.assertFalse(caught.exception.retryable)


if __name__ == "__main__":
    unittest.main()
