import os
import tempfile
import unittest
from pathlib import Path

from wechat_cli.windows.webview2 import (
    WEBVIEW2_BOOTSTRAPPER_URL,
    WebView2Runtime,
    detect_webview2_runtime,
    install_webview2_runtime,
)


class FakeRegistry:
    HKEY_LOCAL_MACHINE = "HKLM"
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_WOW64_64KEY = 256
    REG_SZ = 1
    REG_EXPAND_SZ = 2

    def __init__(self, values):
        self.values = values
        self.opened = []

    class Key:
        def __init__(self, registry, root, path):
            self.registry = registry
            self.root = root
            self.path = path

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def OpenKey(self, root, path, _reserved, access):
        self.opened.append((root, path, access))
        if (root, path) not in self.values:
            raise FileNotFoundError(path)
        return self.Key(self, root, path)

    def QueryValueEx(self, key, name):
        if name != "pv":
            raise FileNotFoundError(name)
        return self.values[(key.root, key.path)]


class WebView2DetectionTests(unittest.TestCase):
    def test_detects_highest_valid_machine_or_user_version(self):
        registry = FakeRegistry(
            {
                (
                    "HKLM",
                    r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                ): ("126.0.1000.1", FakeRegistry.REG_SZ),
                (
                    "HKCU",
                    r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                ): ("127.0.2000.2", FakeRegistry.REG_SZ),
            }
        )

        runtime = detect_webview2_runtime(registry=registry, is_64bit_windows=True)

        self.assertEqual(WebView2Runtime("127.0.2000.2", "current_user"), runtime)

    def test_zero_empty_invalid_and_wrong_type_values_are_absent(self):
        values = ("", "0.0.0.0", "not-a-version", None)
        for value in values:
            with self.subTest(value=value):
                registry = FakeRegistry(
                    {
                        (
                            "HKCU",
                            r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                        ): (value, FakeRegistry.REG_SZ),
                    }
                )
                self.assertIsNone(
                    detect_webview2_runtime(
                        registry=registry,
                        is_64bit_windows=True,
                    )
                )

        registry = FakeRegistry(
            {
                (
                    "HKCU",
                    r"Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                ): ("127.0.1.2", 99),
            }
        )
        self.assertIsNone(
            detect_webview2_runtime(registry=registry, is_64bit_windows=True)
        )

    def test_32bit_windows_uses_non_wow6432node_machine_key(self):
        registry = FakeRegistry(
            {
                (
                    "HKLM",
                    r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
                ): ("127.0.1.2", FakeRegistry.REG_SZ),
            }
        )

        runtime = detect_webview2_runtime(registry=registry, is_64bit_windows=False)

        self.assertEqual("127.0.1.2", runtime.version)
        self.assertTrue(
            any(
                path.startswith(r"SOFTWARE\Microsoft")
                for _root, path, _access in registry.opened
            )
        )
        self.assertFalse(
            any("WOW6432Node" in path for _root, path, _access in registry.opened)
        )


class FakeDownloader:
    def __init__(self, content=b"bootstrapper"):
        self.content = content
        self.calls = []

    def __call__(self, url, destination):
        self.calls.append((url, Path(destination)))
        Path(destination).write_bytes(self.content)


class FakeRunner:
    def __init__(self, returncode=0):
        self.returncode = returncode
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((list(command), kwargs))
        return type("Result", (), {"returncode": self.returncode})()


class WebView2InstallTests(unittest.TestCase):
    def test_downloads_official_bootstrapper_and_runs_silent_install(self):
        downloader = FakeDownloader()
        runner = FakeRunner()
        detections = iter([None, WebView2Runtime("127.0.1.2", "local_machine")])

        with tempfile.TemporaryDirectory() as tmp:
            runtime = install_webview2_runtime(
                cache_dir=Path(tmp),
                detector=lambda: next(detections),
                downloader=downloader,
                runner=runner,
            )

        self.assertEqual("127.0.1.2", runtime.version)
        self.assertEqual(WEBVIEW2_BOOTSTRAPPER_URL, downloader.calls[0][0])
        command, kwargs = runner.calls[0]
        self.assertEqual(["/silent", "/install"], command[1:])
        self.assertFalse(kwargs["shell"])
        self.assertTrue(kwargs["check"])

    def test_existing_runtime_skips_download_and_install(self):
        downloader = FakeDownloader()
        runner = FakeRunner()
        existing = WebView2Runtime("127.0.1.2", "current_user")

        with tempfile.TemporaryDirectory() as tmp:
            runtime = install_webview2_runtime(
                cache_dir=Path(tmp),
                detector=lambda: existing,
                downloader=downloader,
                runner=runner,
            )

        self.assertEqual(existing, runtime)
        self.assertEqual([], downloader.calls)
        self.assertEqual([], runner.calls)

    def test_runtime_still_missing_after_installer_is_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError) as caught:
                install_webview2_runtime(
                    cache_dir=Path(tmp),
                    detector=lambda: None,
                    downloader=FakeDownloader(),
                    runner=FakeRunner(),
                )

        self.assertIn("仍未检测到", str(caught.exception))

    def test_bootstrapper_download_must_not_be_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                install_webview2_runtime(
                    cache_dir=Path(tmp),
                    detector=lambda: None,
                    downloader=FakeDownloader(b""),
                    runner=FakeRunner(),
                )


if __name__ == "__main__":
    unittest.main()
