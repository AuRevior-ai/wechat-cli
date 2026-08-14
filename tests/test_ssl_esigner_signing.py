import inspect
import subprocess
import tempfile
import unittest
from pathlib import Path


class SslEsignerSigningProviderTests(unittest.TestCase):
    def test_module_exports_provider_without_credential_parameters(self):
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        parameters = inspect.signature(SslEsignerSigningProvider).parameters
        self.assertEqual({"signtool_path", "certificate_thumbprint", "runner"}, set(parameters))

    def test_provider_signs_with_exact_signtool_thumbprint_and_timestamp_contract(self):
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signtool = root / "signtool.exe"
            target = root / "wechat-cli.exe"
            signtool.write_bytes(b"signtool")
            target.write_bytes(b"candidate")
            calls = []

            class Completed:
                returncode = 0
                stdout = ""
                stderr = ""

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return Completed()

            provider = SslEsignerSigningProvider(
                signtool_path=signtool,
                certificate_thumbprint="aa bb cc dd ee ff 00 11 22 33 44 55 66 77 88 99 aa bb cc dd",
                runner=runner,
            )
            provider.sign(target)

        self.assertEqual(1, len(calls))
        command, kwargs = calls[0]
        self.assertEqual(
            [
                str(signtool),
                "sign",
                "/fd",
                "sha256",
                "/tr",
                "http://ts.ssl.com",
                "/td",
                "sha256",
                "/sha1",
                "AABBCCDDEEFF00112233445566778899AABBCCDD",
                str(target),
            ],
            command,
        )
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])
        self.assertEqual(120, kwargs["timeout"])
        self.assertFalse(kwargs["shell"])

    def test_provider_rejects_non_sha1_thumbprint_before_invoking_signtool(self):
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signtool = root / "signtool.exe"
            signtool.write_bytes(b"signtool")
            calls = []

            with self.assertRaisesRegex(ValueError, "thumbprint"):
                SslEsignerSigningProvider(
                    signtool_path=signtool,
                    certificate_thumbprint="AA11",
                    runner=lambda *args, **kwargs: calls.append((args, kwargs)),
                )

        self.assertEqual([], calls)

    def test_provider_rejects_missing_or_symlink_signing_tool(self):
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing-signtool.exe"
            with self.assertRaisesRegex(ValueError, "SignTool"):
                SslEsignerSigningProvider(
                    signtool_path=missing,
                    certificate_thumbprint="AABBCCDDEEFF00112233445566778899AABBCCDD",
                )

    def test_provider_rejects_invalid_target_before_invoking_signtool(self):
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signtool = root / "signtool.exe"
            signtool.write_bytes(b"signtool")
            calls = []
            provider = SslEsignerSigningProvider(
                signtool_path=signtool,
                certificate_thumbprint="AABBCCDDEEFF00112233445566778899AABBCCDD",
                runner=lambda *args, **kwargs: calls.append((args, kwargs)),
            )

            with self.assertRaisesRegex(ValueError, "target"):
                provider.sign(root / "missing.exe")

        self.assertEqual([], calls)

    def test_provider_fails_closed_without_exposing_provider_output(self):
        from scripts.ssl_esigner_signing import SslEsignerSigningProvider

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signtool = root / "signtool.exe"
            target = root / "wechat-cli.exe"
            signtool.write_bytes(b"signtool")
            target.write_bytes(b"candidate")
            provider = SslEsignerSigningProvider(
                signtool_path=signtool,
                certificate_thumbprint="AABBCCDDEEFF00112233445566778899AABBCCDD",
                runner=lambda command, **kwargs: (_ for _ in ()).throw(
                    subprocess.CalledProcessError(
                        1,
                        command,
                        output="provider-sensitive-output",
                        stderr="provider-sensitive-error",
                    )
                ),
            )

            with self.assertRaisesRegex(ValueError, "SSL.com eSigner signing failed") as raised:
                provider.sign(target)

        self.assertNotIn("provider-sensitive-output", str(raised.exception))
        self.assertNotIn("provider-sensitive-error", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
