import hashlib
import tempfile
import unittest
from pathlib import Path

from wechat_cli.diagnostics_upload import (
    DiagnosticUploadClient,
    DiagnosticUploadError,
    DiagnosticUploadResult,
    InstalledDiagnosticSubmitter,
)
from wechat_cli.license.lease import TrustedTimeState
from wechat_cli.license.storage import LocalLicenseState
from wechat_cli.update.layout import CurrentVersion, InstallLayout


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
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, path, headers, source):
        source_path = Path(source)
        self.calls.append((path, dict(headers), source_path, source_path.read_bytes()))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeStorage:
    def __init__(self, state):
        self.state = state
        self.calls = 0

    def load(self):
        self.calls += 1
        return self.state


class FakeUploadClient:
    def __init__(self):
        self.calls = []

    def submit(self, path, **kwargs):
        self.calls.append((Path(path), kwargs))
        return DiagnosticUploadResult(
            submission_id="diag_01",
            status="complete",
            size_bytes=Path(path).stat().st_size,
            sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        )


class InstalledDiagnosticSubmitterTests(unittest.TestCase):
    def test_uses_dpapi_state_and_current_installed_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            layout = InstallLayout(root / "WeChatCliWeb")
            layout.ensure_directories()
            version_dir = layout.version_path("0.5.0")
            version_dir.mkdir()
            (version_dir / "wechat-cli.exe").write_bytes(b"binary")
            layout.save_current(
                CurrentVersion(
                    current_version="0.5.0",
                    previous_version="0.4.2",
                    channel="stable",
                    activated_at="2026-08-05T12:00:00Z",
                    manifest_sha256="11" * 32,
                )
            )
            state = LocalLicenseState(
                license_id="lic_01",
                license_key="WCL-SECRET-R4DN",
                device_id="dev_01",
                device_token="wcdt_token.secret",
                lease_content=b'{"lease":true}',
                lease_signature=b"signature",
                local_launch_key=b"K" * 32,
                trusted_time=TrustedTimeState(
                    last_server_time="2026-08-05T12:00:00Z",
                    last_wall_clock="2026-08-05T12:00:00Z",
                ),
            )
            storage = FakeStorage(state)
            client = FakeUploadClient()
            submitter = InstalledDiagnosticSubmitter(
                layout=layout,
                storage=storage,
                client=client,
                launcher_version="0.1.0",
            )
            bundle = root / "diagnostic.zip"
            bundle.write_bytes(b"diagnostic bundle")

            result = submitter.submit(bundle)

        self.assertEqual("diag_01", result.submission_id)
        self.assertEqual(1, storage.calls)
        path, kwargs = client.calls[0]
        self.assertEqual(bundle, path)
        self.assertEqual("wcdt_token.secret", kwargs["device_token"])
        self.assertEqual("0.5.0", kwargs["client_version"])
        self.assertEqual("0.1.0", kwargs["launcher_version"])

    def test_missing_local_license_state_blocks_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            submitter = InstalledDiagnosticSubmitter(
                layout=layout,
                storage=FakeStorage(None),
                client=FakeUploadClient(),
                launcher_version="0.1.0",
            )
            bundle = Path(tmp) / "diagnostic.zip"
            bundle.write_bytes(b"diagnostic")

            with self.assertRaises(DiagnosticUploadError) as caught:
                submitter.submit(bundle)

        self.assertEqual("DIAGNOSTIC_LICENSE_STATE_MISSING", caught.exception.code)


class DiagnosticUploadClientTests(unittest.TestCase):
    def make_bundle(self, root: Path):
        path = root / "wechat-cli-diagnostics.zip"
        path.write_bytes(b"diagnostic bundle bytes")
        return path

    def test_creates_session_then_uploads_exact_bundle_with_separate_token(self):
        json_transport = FakeJsonTransport(
            [
                (
                    201,
                    {
                        "submission_id": "diag_01",
                        "upload_url": "/v1/diagnostics/diag_01/content",
                        "upload_token": "diag_9999999999.nonce.signature",
                        "expires_at": "2026-08-05T12:15:00Z",
                        "upload_expires_at": "2026-08-05T12:15:00Z",
                        "retention_expires_at": "2026-08-12T12:00:00Z",
                        "retention_days": 7,
                        "consent_version": "diagnostics-consent-v1",
                        "maximum_bytes": 20 * 1024 * 1024,
                    },
                )
            ]
        )
        upload_transport = FakeUploadTransport(
            [
                (
                    200,
                    {
                        "ok": True,
                        "submission_id": "diag_01",
                        "status": "complete",
                        "size_bytes": len(b"diagnostic bundle bytes"),
                        "sha256": hashlib.sha256(
                            b"diagnostic bundle bytes"
                        ).hexdigest(),
                    },
                )
            ]
        )
        client = DiagnosticUploadClient(json_transport, upload_transport)
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.make_bundle(Path(tmp))
            bundle_size = bundle.stat().st_size

            result = client.submit(
                bundle,
                device_token="wcdt_token.secret",
                client_version="0.5.0",
                launcher_version="0.1.0",
            )

        method, path, headers, payload = json_transport.calls[0]
        self.assertEqual(("POST", "/v1/diagnostics/sessions"), (method, path))
        self.assertEqual("Bearer wcdt_token.secret", headers["Authorization"])
        self.assertEqual(bundle_size, payload["size_bytes"])
        self.assertEqual("diagnostics-consent-v1", payload.get("consent_version"))
        self.assertEqual(
            hashlib.sha256(b"diagnostic bundle bytes").hexdigest(),
            payload["sha256"],
        )
        upload_path, upload_headers, _source, uploaded = upload_transport.calls[0]
        self.assertEqual("/v1/diagnostics/diag_01/content", upload_path)
        self.assertEqual(
            "Diagnostic diag_9999999999.nonce.signature",
            upload_headers["Authorization"],
        )
        self.assertNotIn("wcdt_token.secret", upload_headers["Authorization"])
        self.assertEqual(b"diagnostic bundle bytes", uploaded)
        self.assertEqual("complete", result.status)
        self.assertEqual("diag_01", result.submission_id)
        self.assertNotIn("upload_token", repr(result))

    def test_rejects_server_retention_policy_drift(self):
        client = DiagnosticUploadClient(
            FakeJsonTransport(
                [
                    (
                        201,
                        {
                            "submission_id": "diag_01",
                            "upload_url": "/v1/diagnostics/diag_01/content",
                            "upload_token": "diag_token",
                            "expires_at": "2026-08-05T12:15:00Z",
                            "upload_expires_at": "2026-08-05T12:15:00Z",
                            "retention_expires_at": "2026-09-05T12:00:00Z",
                            "retention_days": 30,
                            "consent_version": "diagnostics-consent-v1",
                            "maximum_bytes": 1000,
                        },
                    )
                ]
            ),
            FakeUploadTransport(
                [
                    (
                        200,
                        {
                            "ok": True,
                            "submission_id": "diag_01",
                            "status": "complete",
                            "size_bytes": len(b"diagnostic bundle bytes"),
                            "sha256": hashlib.sha256(
                                b"diagnostic bundle bytes"
                            ).hexdigest(),
                        },
                    )
                ]
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.make_bundle(Path(tmp))
            with self.assertRaises(DiagnosticUploadError) as caught:
                client.submit(
                    bundle,
                    device_token="token",
                    client_version="0.5.0",
                    launcher_version="0.1.0",
                )

        self.assertEqual("DIAGNOSTIC_SESSION_INVALID", caught.exception.code)

    def test_rejects_absolute_or_cross_origin_upload_url(self):
        client = DiagnosticUploadClient(
            FakeJsonTransport(
                [
                    (
                        201,
                        {
                            "submission_id": "diag_01",
                            "upload_url": "https://malicious.example/upload",
                            "upload_token": "diag_token",
                            "expires_at": "2026-08-05T12:15:00Z",
                            "upload_expires_at": "2026-08-05T12:15:00Z",
                            "retention_expires_at": "2026-08-12T12:00:00Z",
                            "retention_days": 7,
                            "consent_version": "diagnostics-consent-v1",
                            "maximum_bytes": 1000,
                        },
                    )
                ]
            ),
            FakeUploadTransport([]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.make_bundle(Path(tmp))
            with self.assertRaises(DiagnosticUploadError) as caught:
                client.submit(
                    bundle,
                    device_token="token",
                    client_version="0.5.0",
                    launcher_version="0.1.0",
                )

        self.assertEqual("DIAGNOSTIC_SESSION_INVALID", caught.exception.code)

    def test_rejects_bundle_larger_than_server_limit_before_upload(self):
        upload = FakeUploadTransport([])
        client = DiagnosticUploadClient(
            FakeJsonTransport(
                [
                    (
                        201,
                        {
                            "submission_id": "diag_01",
                            "upload_url": "/v1/diagnostics/diag_01/content",
                            "upload_token": "diag_token",
                            "expires_at": "2026-08-05T12:15:00Z",
                            "upload_expires_at": "2026-08-05T12:15:00Z",
                            "retention_expires_at": "2026-08-12T12:00:00Z",
                            "retention_days": 7,
                            "consent_version": "diagnostics-consent-v1",
                            "maximum_bytes": 1,
                        },
                    )
                ]
            ),
            upload,
        )
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.make_bundle(Path(tmp))
            with self.assertRaises(DiagnosticUploadError) as caught:
                client.submit(
                    bundle,
                    device_token="token",
                    client_version="0.5.0",
                    launcher_version="0.1.0",
                )

        self.assertEqual("DIAGNOSTIC_TOO_LARGE", caught.exception.code)
        self.assertEqual([], upload.calls)

    def test_service_error_preserves_stable_code_and_retryability(self):
        client = DiagnosticUploadClient(
            FakeJsonTransport(
                [
                    (
                        429,
                        {
                            "error": {
                                "code": "RATE_LIMITED",
                                "message": "请求过于频繁",
                                "retryable": True,
                                "request_id": "req_12345678",
                            }
                        },
                    )
                ]
            ),
            FakeUploadTransport([]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            bundle = self.make_bundle(Path(tmp))
            with self.assertRaises(DiagnosticUploadError) as caught:
                client.submit(
                    bundle,
                    device_token="token",
                    client_version="0.5.0",
                    launcher_version="0.1.0",
                )

        self.assertEqual("RATE_LIMITED", caught.exception.code)
        self.assertTrue(caught.exception.retryable)
        self.assertEqual("req_12345678", caught.exception.request_id)


if __name__ == "__main__":
    unittest.main()
