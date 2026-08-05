import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from wechat_cli.diagnostics import DiagnosticBundleResult
from wechat_cli.diagnostics_upload import DiagnosticUploadResult
from wechat_cli.web.server import WeChatWebHandler


class FakeDiagnostics:
    def __init__(self, path):
        self.path = path
        self.calls = 0

    def build_local(self):
        self.calls += 1
        self.path.write_bytes(b"zip")
        return DiagnosticBundleResult(
            path=self.path,
            sensitive_findings=(),
            submitted=False,
        )


class FakeSubmitter:
    def __init__(self):
        self.calls = []

    def submit(self, path):
        source = Path(path)
        self.calls.append(source)
        return DiagnosticUploadResult(
            submission_id="diag_01",
            status="complete",
            size_bytes=source.stat().st_size,
            sha256="11" * 32,
        )


class WebDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "wechat-cli-diagnostics-20260805-120000.zip"
        self.diagnostics = FakeDiagnostics(path)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), WeChatWebHandler)
        self.server.license_session_valid = True
        self.server.diagnostics_builder = self.diagnostics
        self.submitter = FakeSubmitter()
        self.server.diagnostics_submitter = self.submitter
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def post(self, payload, *, origin=None):
        request = Request(
            self.base + "/api/diagnostics/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Origin": origin or self.base,
            },
            method="POST",
        )
        return urlopen(request, timeout=3)

    def test_generates_local_bundle_without_exposing_absolute_path(self):
        with self.post({"submit": False}) as response:
            payload = json.loads(response.read().decode("utf-8"))

        self.assertEqual(200, response.status)
        self.assertEqual(
            "wechat-cli-diagnostics-20260805-120000.zip",
            payload["filename"],
        )
        self.assertEqual(3, payload["size_bytes"])
        self.assertFalse(payload["submitted"])
        self.assertTrue(payload["can_submit"])
        self.assertGreaterEqual(len(payload["submission_token"]), 16)
        self.assertNotIn(self.temp.name, json.dumps(payload))
        self.assertEqual(1, self.diagnostics.calls)

    def test_explicit_second_request_uploads_previously_generated_bundle(self):
        with self.post({"submit": False}) as response:
            generated = json.loads(response.read().decode("utf-8"))

        with self.post(
            {
                "submit": True,
                "submission_token": generated["submission_token"],
            }
        ) as response:
            submitted = json.loads(response.read().decode("utf-8"))

        self.assertEqual(200, response.status)
        self.assertTrue(submitted["submitted"])
        self.assertEqual("diag_01", submitted["submission_id"])
        self.assertEqual("complete", submitted["status"])
        self.assertEqual(1, len(self.submitter.calls))
        self.assertEqual(self.diagnostics.path, self.submitter.calls[0])

    def test_submit_without_generated_token_is_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.post({"submit": True, "submission_token": "unknown-token"})

        self.assertEqual(400, caught.exception.code)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual("DIAGNOSTIC_SUBMISSION_INVALID", payload["error"]["code"])
        self.assertEqual(0, self.diagnostics.calls)

    def test_submit_is_disabled_when_upload_client_is_unavailable(self):
        delattr(self.server, "diagnostics_submitter")
        with self.post({"submit": False}) as response:
            generated = json.loads(response.read().decode("utf-8"))
        self.assertFalse(generated["can_submit"])

        with self.assertRaises(HTTPError) as caught:
            self.post(
                {
                    "submit": True,
                    "submission_token": generated["submission_token"],
                }
            )

        self.assertEqual(501, caught.exception.code)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual("DIAGNOSTIC_UPLOAD_NOT_ENABLED", payload["error"]["code"])

    def test_missing_builder_returns_503(self):
        delattr(self.server, "diagnostics_builder")

        with self.assertRaises(HTTPError) as caught:
            self.post({"submit": False})

        self.assertEqual(503, caught.exception.code)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual("DIAGNOSTICS_UNAVAILABLE", payload["error"]["code"])

    def test_cross_origin_generation_is_rejected(self):
        with self.assertRaises(HTTPError) as caught:
            self.post({"submit": False}, origin="https://malicious.example")

        self.assertEqual(403, caught.exception.code)
        self.assertEqual(0, self.diagnostics.calls)


if __name__ == "__main__":
    unittest.main()
