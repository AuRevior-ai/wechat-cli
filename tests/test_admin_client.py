import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from wechat_cli.admin.client import (
    AdminApiClient,
    AdminApiError,
    UrllibAdminDownloadTransport,
    UrllibAdminJsonTransport,
)


class FakeJsonTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, path, headers, payload):
        self.calls.append((method, path, dict(headers), payload))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeUploadTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, path, headers, source, metadata_headers):
        source = Path(source)
        self.calls.append((path, dict(headers), source, dict(metadata_headers)))
        return {
            "release_id": source.stem,
            "distribution_backend": "r2",
            "distribution_object_key": "releases/stable/rel_01/object.zip",
            "ready": True,
        }


class FakeDownloadTransport:
    def __init__(self, content=b"diagnostic zip"):
        self.content = content
        self.calls = []

    def __call__(self, path, headers, destination):
        self.calls.append((path, dict(headers), Path(destination)))
        Path(destination).write_bytes(self.content)
        return Path(destination)


class AdminApiClientTests(unittest.TestCase):
    def test_short_lived_session_token_uses_existing_admin_authorization_scheme(self):
        transport = FakeJsonTransport([(200, {"releases": []})])
        token = "wcas_adms_identifier123456.secret_value_abcdefghijklmnopqrstuvwxyz123456"
        try:
            client = AdminApiClient(transport, admin_token=token)
        except ValueError as exc:
            self.fail(f"short-lived admin session token should be accepted: {exc}")

        self.assertEqual([], client.list_releases())
        self.assertEqual(f"Admin {token}", transport.calls[0][2]["Authorization"])
        self.assertNotIn("secret_value", repr(client))

    @patch("wechat_cli.admin.client.urlopen")
    def test_json_transport_sets_application_user_agent(self, mocked_urlopen):
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"releases":[]}'
        response.__enter__.return_value = response
        mocked_urlopen.return_value = response

        transport = UrllibAdminJsonTransport("https://example.com")
        transport(
            "GET",
            "/v1/admin/releases",
            {"Authorization": "Admin wcadmin_adm_id.secret"},
            None,
        )

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual("WeChatCliAdmin/0.6.0", request.get_header("User-agent"))

    @patch("wechat_cli.admin.client.urlopen")
    def test_download_transport_sets_application_user_agent(self, mocked_urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b""
        mocked_urlopen.return_value = response

        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / "diagnostic.zip"
            transport = UrllibAdminDownloadTransport("https://example.com")
            transport(
                "/v1/admin/diagnostics/diag_01/content",
                {"Authorization": "Admin wcadmin_adm_id.secret"},
                destination,
            )

        request = mocked_urlopen.call_args.args[0]
        self.assertEqual("WeChatCliAdmin/0.6.0", request.get_header("User-agent"))

    def test_create_license_uses_admin_header_and_operation_nonce(self):
        transport = FakeJsonTransport(
            [
                (
                    201,
                    {
                        "license_id": "lic_01",
                        "license_key": "WCL-AAAA-BBBB-CCCC-DDDD",
                        "license_hint": "DDDD",
                        "status": "active",
                        "maximum_devices": 3,
                        "release_channel": "stable",
                        "created_at": "2026-08-05T00:00:00Z",
                    },
                )
            ]
        )
        client = AdminApiClient(transport, admin_token="wcadmin_adm_id.secret")

        result = client.create_license(
            maximum_devices=3,
            release_channel="stable",
            contacts={"email": "user@example.com"},
            operation_nonce="nonce_create_01",
        )

        method, path, headers, payload = transport.calls[0]
        self.assertEqual(("POST", "/v1/admin/licenses"), (method, path))
        self.assertEqual("Admin wcadmin_adm_id.secret", headers["Authorization"])
        self.assertEqual("nonce_create_01", payload["operation_nonce"])
        self.assertEqual("user@example.com", payload["contacts"]["email"])
        self.assertEqual("WCL-AAAA-BBBB-CCCC-DDDD", result["license_key"])
        self.assertNotIn("wcadmin_adm_id.secret", repr(client))

    def test_list_licenses_encodes_query_without_token_in_url(self):
        transport = FakeJsonTransport([(200, {"licenses": []})])
        client = AdminApiClient(transport, admin_token="wcadmin_adm_id.secret")

        result = client.list_licenses(query="user+test@example.com", status="active")

        self.assertEqual([], result)
        _, path, headers, _ = transport.calls[0]
        self.assertIn("query=user%2Btest%40example.com", path)
        self.assertIn("status=active", path)
        self.assertNotIn("wcadmin", path)
        self.assertEqual("Admin wcadmin_adm_id.secret", headers["Authorization"])

    def test_license_status_and_device_operations_have_stable_paths(self):
        transport = FakeJsonTransport(
            [
                (200, {"ok": True, "license_id": "lic_01", "status": "suspended"}),
                (200, {"devices": []}),
                (200, {"ok": True, "device_id": "dev_01", "status": "disabled"}),
                (200, {"ok": True, "unbound_device_id": "dev_02"}),
            ]
        )
        client = AdminApiClient(transport, admin_token="wcadmin_adm_id.secret")

        client.set_license_status("lic_01", "suspended", "nonce_status_01")
        client.list_devices("lic_01")
        client.set_device_status("dev_01", "disabled", "nonce_device_01")
        client.unbind_device("dev_02", "nonce_unbind_01")

        self.assertEqual(
            [
                ("PATCH", "/v1/admin/licenses/lic_01/status"),
                ("GET", "/v1/admin/licenses/lic_01/devices"),
                ("PATCH", "/v1/admin/devices/dev_01/status"),
                ("POST", "/v1/admin/devices/dev_02/unbind"),
            ],
            [(method, path) for method, path, _headers, _payload in transport.calls],
        )

    def test_release_package_upload_uses_binary_transport_and_exact_metadata(self):
        transport = FakeJsonTransport([])
        upload = FakeUploadTransport()
        client = AdminApiClient(
            transport,
            admin_token="wcadmin_adm_id.secret",
            upload_transport=upload,
        )
        with TemporaryDirectory() as tmp:
            package = Path(tmp) / "rel_01.zip"
            package.write_bytes(b"signed package bytes")
            digest = hashlib.sha256(package.read_bytes()).hexdigest()
            result = client.upload_release_package(
                "rel_01",
                channel="stable",
                package_path=package,
                package_sha256=digest,
                operation_nonce="nonce_upload_01",
            )

        path, headers, source, metadata = upload.calls[0]
        self.assertEqual("/v1/admin/releases/rel_01/package", path)
        self.assertEqual("Admin wcadmin_adm_id.secret", headers["Authorization"])
        self.assertEqual(package, source)
        self.assertEqual("stable", metadata["X-Release-Channel"])
        self.assertEqual(digest, metadata["X-Package-Sha256"])
        self.assertEqual("nonce_upload_01", metadata["X-Operation-Nonce"])
        self.assertEqual(str(len(b"signed package bytes")), metadata["Content-Length"])
        self.assertTrue(result["ready"])

    def test_release_and_diagnostic_operations(self):
        transport = FakeJsonTransport(
            [
                (200, {"releases": []}),
                (200, {"ok": True, "release_id": "rel_01", "enabled": True}),
                (200, {"diagnostics": [{"submission_id": "diag_01"}]}),
                (200, {"ok": True, "submission_id": "diag_01", "status": "deleted"}),
                (200, {"current_key_version": 1, "records_by_version": []}),
                (
                    200,
                    {
                        "ok": True,
                        "current_key_version": 2,
                        "rotated_count": 10,
                        "remaining_count": 0,
                    },
                ),
            ]
        )
        download = FakeDownloadTransport()
        client = AdminApiClient(
            transport,
            admin_token="wcadmin_adm_id.secret",
            download_transport=download,
        )

        self.assertEqual([], client.list_releases())
        client.update_release(
            "rel_01",
            enabled=True,
            operation_nonce="nonce_release_01",
        )
        self.assertEqual("diag_01", client.list_diagnostics()[0]["submission_id"])
        with TemporaryDirectory() as tmp:
            destination = Path(tmp) / "diag.zip"
            result = client.download_diagnostic("diag_01", destination)
            self.assertEqual(b"diagnostic zip", result.read_bytes())
        client.delete_diagnostic("diag_01")
        status = client.contact_encryption_status()
        self.assertEqual(1, status["current_key_version"])
        rotation = client.rotate_contact_encryption(
            limit=10,
            operation_nonce="nonce_rotate_01",
        )
        self.assertEqual(10, rotation["rotated_count"])
        self.assertEqual(
            "/v1/admin/contact-encryption/rotate",
            transport.calls[-1][1],
        )
        self.assertEqual(10, transport.calls[-1][3]["limit"])
        self.assertEqual(
            "/v1/admin/diagnostics/diag_01/content",
            download.calls[0][0],
        )

    def test_server_error_becomes_admin_api_error(self):
        transport = FakeJsonTransport(
            [
                (
                    403,
                    {
                        "error": {
                            "code": "ADMIN_SCOPE_DENIED",
                            "message": "权限不足",
                            "retryable": False,
                            "request_id": "req_12345678",
                        }
                    },
                )
            ]
        )

        with self.assertRaises(AdminApiError) as caught:
            AdminApiClient(
                transport,
                admin_token="wcadmin_adm_id.secret",
            ).list_licenses()

        self.assertEqual("ADMIN_SCOPE_DENIED", caught.exception.code)
        self.assertEqual("req_12345678", caught.exception.request_id)
        self.assertFalse(caught.exception.retryable)


if __name__ == "__main__":
    unittest.main()
