import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen

from wechat_cli.version import APP_VERSION, BUILD_ID, PRODUCT
from wechat_cli.web.server import WeChatWebHandler, health_payload


class WebHealthTests(unittest.TestCase):
    def test_health_payload_has_no_user_or_secret_data(self):
        payload = health_payload(license_session_valid=True)

        self.assertEqual(PRODUCT, payload["product"])
        self.assertEqual(APP_VERSION, payload["version"])
        self.assertEqual(BUILD_ID, payload["build_id"])
        self.assertTrue(payload["license_session_valid"])
        for forbidden in (
            "license_key",
            "device_token",
            "db_key",
            "config_file",
            "keys_file",
            "chat_data",
        ):
            self.assertNotIn(forbidden, payload)

    def test_api_health_returns_launcher_contract(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), WeChatWebHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            with urlopen(f"http://{host}:{port}/api/health", timeout=3) as response:
                payload = json.loads(response.read().decode("utf-8"))

            self.assertEqual(200, response.status)
            self.assertEqual("ok", payload["status"])
            self.assertEqual(PRODUCT, payload["product"])
            self.assertEqual(APP_VERSION, payload["version"])
            self.assertEqual(
                {"server": "ok", "storage": "ok", "routes": "ok"},
                payload["core_modules"],
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
