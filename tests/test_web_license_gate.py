import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen

from wechat_cli.web.server import WeChatWebHandler


class WebLicenseGateTests(unittest.TestCase):
    def start_server(self, valid: bool, reason: str | None = None):
        server = ThreadingHTTPServer(("127.0.0.1", 0), WeChatWebHandler)
        server.license_session_valid = valid
        server.license_session_reason = reason
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def stop_server(self, server, thread):
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    def test_health_remains_available_but_reports_invalid_session(self):
        server, thread = self.start_server(False, "missing_or_consumed")
        try:
            host, port = server.server_address
            with urlopen(f"http://{host}:{port}/api/health", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(200, response.status)
            self.assertFalse(payload["license_session_valid"])
            self.assertNotIn("license_key", payload)
            self.assertNotIn("device_token", payload)
        finally:
            self.stop_server(server, thread)

    def test_business_api_is_blocked_when_launch_session_is_invalid(self):
        server, thread = self.start_server(False, "expired")
        try:
            host, port = server.server_address
            with self.assertRaises(HTTPError) as caught:
                urlopen(f"http://{host}:{port}/api/status", timeout=3)

            self.assertEqual(403, caught.exception.code)
            payload = json.loads(caught.exception.read().decode("utf-8"))
            self.assertEqual("LICENSE_SESSION_INVALID", payload["error"]["code"])
            self.assertEqual("expired", payload["error"]["reason"])
        finally:
            self.stop_server(server, thread)

    def test_root_shows_restricted_page_instead_of_full_application(self):
        server, thread = self.start_server(False, "signature_invalid")
        try:
            host, port = server.server_address
            with urlopen(f"http://{host}:{port}/", timeout=3) as response:
                html = response.read().decode("utf-8")

            self.assertIn("许可证验证未通过", html)
            self.assertIn("signature_invalid", html)
            self.assertNotIn("/static/app.js", html)
        finally:
            self.stop_server(server, thread)

    def test_valid_session_preserves_existing_status_api(self):
        server, thread = self.start_server(True)
        try:
            host, port = server.server_address
            with urlopen(f"http://{host}:{port}/api/status", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(200, response.status)
            self.assertIn("initialized", payload)
        finally:
            self.stop_server(server, thread)


if __name__ == "__main__":
    unittest.main()
