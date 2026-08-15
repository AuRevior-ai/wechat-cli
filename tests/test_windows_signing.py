import importlib.util
import tempfile
import unittest
from pathlib import Path


class WindowsSigningTests(unittest.TestCase):
    def test_signing_tool_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.sign_windows_artifacts"))

    def test_signing_tool_exports_explicit_provider_contract(self):
        from scripts import sign_windows_artifacts

        self.assertIsNotNone(
            getattr(sign_windows_artifacts, "WindowsSigningProvider", None)
        )
        self.assertTrue(
            callable(getattr(sign_windows_artifacts, "sign_and_verify_windows_artifacts", None))
        )

    def test_signing_orchestration_signs_then_verifies_each_artifact(self):
        from scripts.sign_windows_artifacts import sign_and_verify_windows_artifacts
        from wechat_cli.windows.authenticode import AuthenticodePolicy

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = root / "wechat-cli.exe"
            launcher = root / "wechat-cli-launcher.exe"
            app.write_bytes(b"app")
            launcher.write_bytes(b"launcher")
            events = []

            class Provider:
                def sign(self, path):
                    events.append(("sign", path.name))

            def verifier(path, policy):
                events.append(("verify", path.name))
                self.assertTrue(policy.required)

            try:
                result = sign_and_verify_windows_artifacts(
                    [app, launcher],
                    provider=Provider(),
                    policy=AuthenticodePolicy(required=True),
                    verifier=verifier,
                )
            except Exception as exc:
                self.fail(f"explicit signing orchestration failed: {exc}")

        self.assertEqual((app, launcher), result)
        self.assertEqual(
            [
                ("sign", "wechat-cli.exe"),
                ("verify", "wechat-cli.exe"),
                ("sign", "wechat-cli-launcher.exe"),
                ("verify", "wechat-cli-launcher.exe"),
            ],
            events,
        )


if __name__ == "__main__":
    unittest.main()
