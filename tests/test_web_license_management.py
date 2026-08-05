import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from wechat_cli.web.server import WeChatWebHandler


class FakeManagement:
    def __init__(self):
        self.unbind_calls = []
        self.rename_calls = []
        self.trigger_calls = 0

    def license_status(self):
        return {
            "state": "online_valid",
            "authorized": True,
            "license_hint": "R4DN",
            "device_id": "dev_01",
            "offline_until": "2026-08-12T12:00:00Z",
            "offline_remaining_seconds": 604800,
            "current_version": "0.5.0",
            "previous_version": "0.4.2",
            "launcher_version": "0.1.0",
            "channel": "stable",
        }

    def list_devices(self):
        return [
            {
                "device_id": "dev_01",
                "display_name": "SURTR-PC",
                "status": "active",
                "is_current": True,
                "last_validated_at": "2026-08-05T12:00:00Z",
                "last_app_version": "0.5.0",
                "last_launcher_version": "0.1.0",
            }
        ]

    def update_status(self):
        return {
            "status": "ready_to_install",
            "current_version": "0.5.0",
            "pending_version": "0.5.1",
            "progress_percent": 100,
        }

    def unbind_device(self, target_device_id, operation_nonce):
        self.unbind_calls.append((target_device_id, operation_nonce))
        return {"ok": True, "unbound_device_id": target_device_id}

    def rename_device(self, target_device_id, display_name, operation_nonce):
        self.rename_calls.append((target_device_id, display_name, operation_nonce))
        return {"ok": True, "device_id": target_device_id}

    def trigger_update_check(self):
        self.trigger_calls += 1
        return {"ok": True, "started": True}


class WebLicenseManagementTests(unittest.TestCase):
    def setUp(self):
        self.management = FakeManagement()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), WeChatWebHandler)
        self.server.license_session_valid = True
        self.server.license_management = self.management
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"
        self.origin = self.base

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def get_json(self, path):
        with urlopen(self.base + path, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def post_json(self, path, payload, *, origin=None):
        request = Request(
            self.base + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Origin": origin or self.origin,
            },
            method="POST",
        )
        with urlopen(request, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def test_get_license_devices_and_update_status(self):
        status, license_payload = self.get_json("/api/license")
        _, devices_payload = self.get_json("/api/license/devices")
        _, update_payload = self.get_json("/api/update-status")

        self.assertEqual(200, status)
        self.assertEqual("R4DN", license_payload["license_hint"])
        self.assertEqual("SURTR-PC", devices_payload["devices"][0]["display_name"])
        self.assertEqual("0.5.1", update_payload["pending_version"])
        serialized = json.dumps(
            [license_payload, devices_payload, update_payload]
        )
        self.assertNotIn("device_token", serialized)
        self.assertNotIn("license_key", serialized)

    def test_post_unbind_rename_and_update_check(self):
        _, unbound = self.post_json(
            "/api/license/devices/unbind",
            {"device_id": "dev_02", "operation_nonce": "nonce_123"},
        )
        _, renamed = self.post_json(
            "/api/license/devices/rename",
            {
                "device_id": "dev_02",
                "display_name": "WORK LAPTOP",
                "operation_nonce": "nonce_456",
            },
        )
        _, update = self.post_json("/api/update/check", {})

        self.assertEqual("dev_02", unbound["unbound_device_id"])
        self.assertEqual("dev_02", renamed["device_id"])
        self.assertTrue(update["started"])
        self.assertEqual([("dev_02", "nonce_123")], self.management.unbind_calls)
        self.assertEqual(
            [("dev_02", "WORK LAPTOP", "nonce_456")],
            self.management.rename_calls,
        )
        self.assertEqual(1, self.management.trigger_calls)

    def test_management_post_rejects_cross_origin_request(self):
        request = Request(
            self.base + "/api/update/check",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "Origin": "https://malicious.example",
            },
            method="POST",
        )

        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=3)

        self.assertEqual(403, caught.exception.code)
        self.assertEqual(0, self.management.trigger_calls)

    def test_missing_management_service_returns_503_without_details(self):
        delattr(self.server, "license_management")

        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/api/license", timeout=3)

        self.assertEqual(503, caught.exception.code)
        payload = json.loads(caught.exception.read().decode("utf-8"))
        self.assertEqual("LICENSE_MANAGEMENT_UNAVAILABLE", payload["error"]["code"])
        self.assertNotIn("traceback", json.dumps(payload).lower())


if __name__ == "__main__":
    unittest.main()
