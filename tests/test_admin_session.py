import importlib
import json
import threading
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from wechat_cli.admin.config import AdminConfigStorage
from wechat_cli.windows.dpapi import TestOnlyDataProtector


class FakeLoginTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, headers, payload):
        self.calls.append((method, path, dict(headers), dict(payload or {})))
        return (
            200,
            {
                "session_token": "wcas_adms_identifier123456.secret_value_abcdefghijklmnopqrstuvwxyz123456",
                "authenticated_at": "2099-01-01T00:00:00Z",
                "expires_at": "2099-01-01T00:30:00Z",
                "principal_id": "prn_admin_1",
            },
        )


def session_module():
    try:
        module = importlib.import_module("wechat_cli.admin.session")
    except ModuleNotFoundError:
        module = None
    return module


class AdminSessionTests(unittest.TestCase):
    def test_generates_pkce_material_and_never_embeds_verifier_in_start_url(self):
        module = session_module()
        self.assertIsNotNone(module, "wechat_cli.admin.session must exist")
        self.assertTrue(callable(getattr(module, "generate_login_material", None)))
        self.assertTrue(callable(getattr(module, "build_login_start_url", None)))

        material = module.generate_login_material()
        self.assertGreaterEqual(len(material.verifier), 43)
        self.assertGreaterEqual(len(material.state), 20)
        url = module.build_login_start_url(
            "https://admin.example.test",
            "http://127.0.0.1:54321/callback",
            material,
        )
        self.assertIn("challenge=", url)
        self.assertIn("state=", url)
        self.assertIn("redirect_uri=", url)
        self.assertNotIn(material.verifier, url)

    def test_loopback_callback_server_binds_only_ipv4_loopback_and_validates_state(self):
        module = session_module()
        self.assertIsNotNone(module, "wechat_cli.admin.session must exist")
        self.assertTrue(callable(getattr(module, "LoopbackCallbackServer", None)))
        server = module.LoopbackCallbackServer(expected_state="state_abcdefghijklmnop123456")
        try:
            callback = server.callback_url
            self.assertTrue(callback.startswith("http://127.0.0.1:"))
            self.assertTrue(callback.endswith("/callback"))

            def send_callback():
                time.sleep(0.05)
                with urlopen(
                    callback
                    + "?code=wcal_abcdefghijklmnopqrstuvwx&state=state_abcdefghijklmnop123456",
                    timeout=2,
                ) as response:
                    response.read()

            thread = threading.Thread(target=send_callback)
            thread.start()
            self.assertEqual(
                "wcal_abcdefghijklmnopqrstuvwx",
                server.wait_for_code(timeout_seconds=2),
            )
            thread.join(timeout=2)
        finally:
            server.close()

    def test_exchange_persists_only_short_lived_session_in_v2_config(self):
        module = session_module()
        self.assertIsNotNone(module, "wechat_cli.admin.session must exist")
        self.assertTrue(callable(getattr(module, "exchange_and_store_session", None)))
        transport = FakeLoginTransport()
        protector = TestOnlyDataProtector(
            b"admin-session-test",
            allow_insecure_test_use=True,
        )
        with TemporaryDirectory() as tmp:
            storage = AdminConfigStorage(Path(tmp) / "admin-config.dat", protector)
            result = module.exchange_and_store_session(
                api_base_url="https://admin.example.test",
                environment="production",
                code="wcal_abcdefghijklmnopqrstuvwx",
                verifier="v" * 64,
                transport=transport,
                storage=storage,
            )
            raw = storage.path.read_bytes()
            loaded = storage.load()

        self.assertEqual("prn_admin_1", result["principal_id"])
        self.assertIsNotNone(loaded)
        self.assertTrue(loaded.session_token.startswith("wcas_"))
        self.assertIsNone(loaded.legacy_admin_token)
        self.assertNotIn(b"secret_value", raw)
        self.assertEqual("/v1/admin/login/exchange", transport.calls[0][1])
        self.assertNotIn("Authorization", transport.calls[0][2])
        self.assertNotIn("wcas_", json.dumps(transport.calls[0]))


if __name__ == "__main__":
    unittest.main()
