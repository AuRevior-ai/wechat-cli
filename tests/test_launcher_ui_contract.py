import importlib.util
import inspect
import tempfile
import unittest
from pathlib import Path

from wechat_cli.launcher.webview import (
    LauncherBridge,
    LauncherWindow,
    WebViewUnavailable,
    launcher_ui_directory,
)


class LauncherBridgeTests(unittest.TestCase):
    def test_get_ui_state_returns_only_allowlisted_non_secret_fields(self):
        bridge = LauncherBridge(
            state_provider=lambda: {
                "status": "activation_required",
                "message": "需要激活",
                "license_hint": "R4DN",
                "license_key": "WCL-SECRET",
                "device_token": "wcdt-secret",
                "unknown": "hidden",
            }
        )

        state = bridge.get_ui_state()

        self.assertEqual("activation_required", state["status"])
        self.assertEqual("R4DN", state["license_hint"])
        self.assertNotIn("license_key", state)
        self.assertNotIn("device_token", state)
        self.assertNotIn("unknown", state)

    def test_activate_validates_input_and_never_returns_license_key(self):
        calls = []
        bridge = LauncherBridge(
            state_provider=lambda: {"status": "activation_required"},
            activation_handler=lambda key, name: calls.append((key, name))
            or {"status": "activated", "license_key": key},
        )

        result = bridge.activate_license(" WCL-TEST-KEY ", " SURTR-PC ")

        self.assertEqual([("WCL-TEST-KEY", "SURTR-PC")], calls)
        self.assertEqual("activated", result["status"])
        self.assertNotIn("license_key", result)

    def test_activate_rejects_empty_or_excessive_values(self):
        bridge = LauncherBridge(state_provider=lambda: {})
        for key, name in (("", "PC"), ("x" * 129, "PC"), ("WCL-KEY", "x" * 65)):
            with self.subTest(key_length=len(key), name_length=len(name)):
                with self.assertRaises(ValueError):
                    bridge.activate_license(key, name)

    def test_bridge_exposes_only_explicit_public_methods(self):
        public = {
            name
            for name in dir(LauncherBridge)
            if not name.startswith("_") and callable(getattr(LauncherBridge, name))
        }
        self.assertEqual(
            {
                "activate_license",
                "close_launcher",
                "get_ui_state",
                "open_external_help",
                "open_log_folder",
                "retry_update",
                "retry_validation",
                "start_application",
            },
            public,
        )


class LauncherUiAssetTests(unittest.TestCase):
    def test_ui_assets_are_local_and_use_strict_csp(self):
        root = launcher_ui_directory()
        html = (root / "index.html").read_text(encoding="utf-8")
        script = (root / "app.js").read_text(encoding="utf-8")

        self.assertIn("default-src 'none'", html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn("script-src 'self'", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("sessionStorage", script)
        self.assertIn("pywebviewready", script)


class FakeEvent:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


class FakeGui:
    def __init__(self, window):
        self.window = window

    def get_current_url(self, uid):
        if uid != self.window.uid:
            raise AssertionError("unexpected window uid")
        return self.window.url


class FakeWindow:
    def __init__(self, url):
        self.url = url
        self.uid = "fake-window"
        self.gui = FakeGui(self)
        self.events = type("Events", (), {"before_load": FakeEvent()})()
        self.destroy_calls = 0
        self.public_get_current_url_calls = 0

    def get_current_url(self):
        self.public_get_current_url_calls += 1
        return self.url

    def destroy(self):
        self.destroy_calls += 1


class FakeWebview:
    def __init__(self):
        self.create_calls = []
        self.start_calls = []
        self.window = None

    def create_window(self, *args, **kwargs):
        self.create_calls.append((args, kwargs))
        self.window = FakeWindow(kwargs["url"])
        return self.window

    def start(self, **kwargs):
        self.start_calls.append(kwargs)


class WebViewCompatibilityTests(unittest.TestCase):
    def test_preload_url_adapter_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("wechat_cli.launcher.webview_compat"))

    def test_preload_url_adapter_exports_contract(self):
        from wechat_cli.launcher import webview_compat

        error_type = getattr(webview_compat, "WebViewUnavailable", None)
        reader_type = getattr(webview_compat, "PreloadUrlReader", None)
        self.assertIsNotNone(error_type)
        self.assertIsNotNone(reader_type)
        self.assertTrue(issubclass(error_type, RuntimeError))
        self.assertTrue(callable(reader_type))

    def test_preload_reader_uses_backend_uid_without_public_accessor(self):
        from wechat_cli.launcher.webview_compat import PreloadUrlReader

        window = FakeWindow("file:///launcher/index.html")
        reader = PreloadUrlReader()
        read = getattr(reader, "read", None)
        self.assertTrue(callable(read))

        self.assertEqual(window.url, read(window))
        self.assertEqual(0, window.public_get_current_url_calls)

    def test_preload_reader_fails_closed_when_backend_contract_is_missing(self):
        from wechat_cli.launcher.webview_compat import PreloadUrlReader, WebViewUnavailable

        reader = PreloadUrlReader()
        try:
            reader.read(object())
        except Exception as exc:
            self.assertIsInstance(exc, WebViewUnavailable)
        else:
            self.fail("missing backend contract must fail closed")

    def test_preload_reader_rejects_empty_or_non_string_backend_url(self):
        from wechat_cli.launcher.webview_compat import PreloadUrlReader, WebViewUnavailable

        class InvalidGui:
            def __init__(self, value):
                self.value = value

            def get_current_url(self, _uid):
                return self.value

        class InvalidWindow:
            uid = "invalid-window"

            def __init__(self, value):
                self.gui = InvalidGui(value)

        reader = PreloadUrlReader()
        for value in ("", None, 123):
            with self.subTest(value=value):
                try:
                    reader.read(InvalidWindow(value))
                except Exception as exc:
                    self.assertIsInstance(exc, WebViewUnavailable)
                else:
                    self.fail("invalid backend URL must fail closed")


class LauncherWindowTests(unittest.TestCase):
    def test_launcher_window_accepts_preload_url_reader_adapter(self):
        self.assertIn("preload_url_reader", inspect.signature(LauncherWindow).parameters)

    def test_navigation_guard_delegates_preload_url_reading_to_adapter(self):
        fake = FakeWebview()

        class FakeReader:
            def __init__(self):
                self.calls = []

            def read(self, target):
                self.calls.append(target)
                return target.url

        reader = FakeReader()
        window = LauncherWindow(webview_module=fake, preload_url_reader=reader)
        window.show(LauncherBridge(state_provider=lambda: {}))
        handler = fake.window.events.before_load.handlers[0]

        handler(fake.window)

        self.assertEqual([fake.window], reader.calls)
        self.assertEqual(0, fake.window.destroy_calls)

    def test_show_loads_only_local_html_and_forces_edgechromium(self):
        fake = FakeWebview()
        bridge = LauncherBridge(state_provider=lambda: {"status": "ready"})
        window = LauncherWindow(webview_module=fake)

        window.show(bridge)

        _, create_kwargs = fake.create_calls[0]
        self.assertTrue(create_kwargs["url"].startswith("file:"))
        self.assertIs(bridge, create_kwargs["js_api"])
        self.assertEqual(False, create_kwargs["confirm_close"])
        self.assertEqual(
            {"gui": "edgechromium", "debug": False, "private_mode": True},
            fake.start_calls[0],
        )

    def test_navigation_guard_allows_own_local_index_uri(self):
        index_uri = (launcher_ui_directory() / "index.html").as_uri()

        self.assertTrue(LauncherWindow._navigation_is_local(index_uri))

    def test_navigation_guard_rejects_remote_file_authority(self):
        index_uri = (launcher_ui_directory() / "index.html").as_uri()
        remote_uri = index_uri.replace("file:///", "file://remote-host/", 1)

        self.assertFalse(LauncherWindow._navigation_is_local(remote_uri))

    def test_navigation_guard_reads_backend_url_before_loaded_event(self):
        fake = FakeWebview()
        window = LauncherWindow(webview_module=fake)
        window.show(LauncherBridge(state_provider=lambda: {}))
        handler = fake.window.events.before_load.handlers[0]

        handler(fake.window)

        self.assertEqual(0, fake.window.destroy_calls)
        self.assertEqual(0, fake.window.public_get_current_url_calls)

    def test_navigation_guard_destroys_window_for_remote_navigation(self):
        fake = FakeWebview()
        window = LauncherWindow(webview_module=fake)
        window.show(LauncherBridge(state_provider=lambda: {}))
        handler = fake.window.events.before_load.handlers[0]
        fake.window.url = "https://malicious.example/"

        handler(fake.window)

        self.assertEqual(1, fake.window.destroy_calls)

    def test_missing_pywebview_has_clear_error(self):
        window = LauncherWindow(webview_module=None, importer=lambda _name: None)

        with self.assertRaises(WebViewUnavailable):
            window.show(LauncherBridge(state_provider=lambda: {}))


if __name__ == "__main__":
    unittest.main()
