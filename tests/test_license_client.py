import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from tests.test_license_lease import lease_bytes
from wechat_cli.license.client import (
    LicenseApiClient,
    LicenseRejected,
    LicenseServiceUnavailable,
    UrllibJsonTransport,
    authorize_startup,
)
from wechat_cli.license.lease import OfflineLease, TrustedTimeState
from wechat_cli.license.models import ClientLicenseState, ValidationResult
from wechat_cli.update.errors import ErrorCode


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, path, headers, payload):
        self.calls.append((method, path, headers, payload))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class LicenseApiClientTests(unittest.TestCase):
    @patch("wechat_cli.license.client.urlopen")
    def test_urllib_transport_sets_application_user_agent(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"ok":true}'
        response.__enter__.return_value = response
        mocked_urlopen.return_value = response

        transport = UrllibJsonTransport("https://example.com")
        status, payload = transport("GET", "/v1/health", {}, None)

        self.assertEqual(200, status)
        self.assertTrue(payload["ok"])
        request = mocked_urlopen.call_args.args[0]
        self.assertEqual("WeChatCliLicense/0.5.0", request.get_header("User-agent"))

    def test_activate_sends_permanent_key_only_in_json_body(self):
        transport = FakeTransport(
            [
                (
                    200,
                    {
                        "license_id": "lic_01",
                        "device_id": "dev_01",
                        "device_token": "wcdt_token.secret",
                        "device_count": 1,
                        "maximum_devices": 3,
                        "lease_content_base64": "e30=",
                        "lease_signature_base64": "c2ln",
                    },
                )
            ]
        )
        client = LicenseApiClient(transport)

        result = client.activate(
            license_key="WCL-TEST-KEY",
            device_id="dev_01",
            device_fingerprint="fingerprint",
            device_name="SURTR-PC",
            app_version="0.5.0",
            launcher_version="0.1.0",
        )

        method, path, headers, payload = transport.calls[0]
        self.assertEqual(("POST", "/v1/licenses/activate"), (method, path))
        self.assertEqual("WCL-TEST-KEY", payload["license_key"])
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("WCL-TEST-KEY", path)
        self.assertEqual("wcdt_token.secret", result.device_token)

    def test_validate_uses_device_token_and_never_resends_license_key(self):
        transport = FakeTransport(
            [
                (
                    200,
                    {
                        "license_id": "lic_01",
                        "device_id": "dev_01",
                        "server_time": "2026-08-04T15:00:00Z",
                        "lease_content_base64": "e30=",
                        "lease_signature_base64": "c2ln",
                    },
                )
            ]
        )
        client = LicenseApiClient(transport)

        result = client.validate(
            device_token="wcdt_token.secret",
            app_version="0.5.0",
            launcher_version="0.1.0",
        )

        method, path, headers, payload = transport.calls[0]
        self.assertEqual(("POST", "/v1/devices/validate"), (method, path))
        self.assertEqual("Bearer wcdt_token.secret", headers["Authorization"])
        self.assertNotIn("license_key", payload)
        self.assertEqual("lic_01", result.license_id)

    def test_device_list_and_unbind_use_current_device_token(self):
        transport = FakeTransport(
            [
                (
                    200,
                    {
                        "devices": [
                            {
                                "device_id": "dev_01",
                                "display_name": "SURTR-PC",
                                "status": "active",
                                "is_current": True,
                                "last_validated_at": "2026-08-04T15:00:00Z",
                                "last_app_version": "0.5.0",
                                "last_launcher_version": "0.1.0",
                            }
                        ]
                    },
                ),
                (200, {"ok": True, "unbound_device_id": "dev_02"}),
            ]
        )
        client = LicenseApiClient(transport)

        devices = client.list_devices("wcdt_token.secret")
        client.unbind_device(
            "wcdt_token.secret",
            target_device_id="dev_02",
            operation_nonce="nonce_01",
        )

        self.assertEqual("dev_01", devices[0].device_id)
        self.assertEqual("Bearer wcdt_token.secret", transport.calls[0][2]["Authorization"])
        self.assertEqual("dev_02", transport.calls[1][3]["target_device_id"])
        self.assertEqual("nonce_01", transport.calls[1][3]["operation_nonce"])

    def test_explicit_license_rejection_is_not_reported_as_network_failure(self):
        transport = FakeTransport(
            [
                (
                    403,
                    {
                        "error": {
                            "code": "LICENSE_REVOKED",
                            "message": "许可证已吊销",
                            "retryable": False,
                        }
                    },
                )
            ]
        )

        with self.assertRaises(LicenseRejected) as caught:
            LicenseApiClient(transport).validate(
                device_token="wcdt_token.secret",
                app_version="0.5.0",
                launcher_version="0.1.0",
            )

        self.assertEqual(ErrorCode.LICENSE_REVOKED, caught.exception.code)

    def test_transport_oserror_becomes_service_unavailable(self):
        transport = FakeTransport([OSError("network down")])

        with self.assertRaises(LicenseServiceUnavailable):
            LicenseApiClient(transport).validate(
                device_token="wcdt_token.secret",
                app_version="0.5.0",
                launcher_version="0.1.0",
            )


class StartupAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.lease = OfflineLease.from_json_bytes(lease_bytes())
        self.now = datetime(2026, 8, 5, tzinfo=timezone.utc)
        self.trusted_time = TrustedTimeState(
            last_server_time="2026-08-04T15:00:00Z",
            last_wall_clock="2026-08-04T15:00:00Z",
        )

    def test_online_validation_wins_and_returns_online_valid(self):
        result = ValidationResult.from_mapping(
            {
                "license_id": "lic_01",
                "device_id": "dev_01",
                "server_time": "2026-08-05T00:00:00Z",
                "lease_content_base64": "e30=",
                "lease_signature_base64": "c2ln",
            }
        )

        decision = authorize_startup(
            lambda: result,
            offline_lease=self.lease,
            now=self.now,
            trusted_time=self.trusted_time,
        )

        self.assertEqual(ClientLicenseState.ONLINE_VALID, decision.state)
        self.assertIs(result, decision.validation_result)

    def test_explicit_revocation_blocks_even_when_offline_lease_is_unexpired(self):
        def validate():
            raise LicenseRejected(
                ErrorCode.LICENSE_REVOKED,
                "revoked",
            )

        decision = authorize_startup(
            validate,
            offline_lease=self.lease,
            now=self.now,
            trusted_time=self.trusted_time,
        )

        self.assertEqual(ClientLicenseState.LICENSE_REVOKED, decision.state)
        self.assertFalse(decision.authorized)

    def test_network_failure_uses_unexpired_verified_offline_lease(self):
        def validate():
            raise LicenseServiceUnavailable("network down")

        decision = authorize_startup(
            validate,
            offline_lease=self.lease,
            now=self.now,
            trusted_time=self.trusted_time,
        )

        self.assertEqual(ClientLicenseState.OFFLINE_VALID, decision.state)
        self.assertTrue(decision.authorized)

    def test_network_failure_does_not_use_expired_lease(self):
        def validate():
            raise LicenseServiceUnavailable("network down")

        decision = authorize_startup(
            validate,
            offline_lease=self.lease,
            now=datetime(2026, 8, 12, tzinfo=timezone.utc),
            trusted_time=self.trusted_time,
        )

        self.assertEqual(ClientLicenseState.OFFLINE_EXPIRED, decision.state)
        self.assertFalse(decision.authorized)


if __name__ == "__main__":
    unittest.main()
