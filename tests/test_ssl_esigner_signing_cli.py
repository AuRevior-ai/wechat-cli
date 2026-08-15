import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class SslEsignerSigningCliTests(unittest.TestCase):
    def test_cli_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.build_signed_windows_ssl_esigner"))

    def test_help_exposes_only_public_provider_inputs(self):
        from scripts.build_signed_windows_ssl_esigner import build_parser

        help_text = build_parser().format_help().lower()
        for required in (
            "--signtool-path",
            "--certificate-thumbprint",
            "--launcher-config",
            "--trust-profile",
        ):
            self.assertIn(required, help_text)
        for forbidden in (
            "username",
            "password",
            "totp",
            "master-key",
            "private-key",
            ".env",
        ):
            self.assertNotIn(forbidden, help_text)

    def test_cli_constructs_exact_ssl_provider_and_production_installer_call(self):
        from scripts.build_signed_windows_ssl_esigner import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signtool = root / "signtool.exe"
            launcher_config = root / "launcher-config.json"
            trust_profile = root / "deployment-trust-profile.json"
            signtool.write_bytes(b"signtool")
            launcher_config.write_text("{}", encoding="utf-8")
            trust_profile.write_text("{}", encoding="utf-8")
            provider_calls = []
            installer_calls = []
            provider = object()

            def provider_factory(*, signtool_path, certificate_thumbprint):
                provider_calls.append((signtool_path, certificate_thumbprint))
                return provider

            def installer_creator(**kwargs):
                installer_calls.append(kwargs)
                return root / "installer.exe", root / "legacy.zip", root / "update.zip"

            result = main(
                [
                    "--signtool-path",
                    str(signtool),
                    "--certificate-thumbprint",
                    "AABBCCDDEEFF00112233445566778899AABBCCDD",
                    "--launcher-config",
                    str(launcher_config),
                    "--trust-profile",
                    str(trust_profile),
                ],
                provider_factory=provider_factory,
                installer_creator=installer_creator,
            )

        self.assertEqual(0, result)
        self.assertEqual(
            [(signtool, "AABBCCDDEEFF00112233445566778899AABBCCDD")],
            provider_calls,
        )
        self.assertEqual(1, len(installer_calls))
        self.assertEqual(str(launcher_config), installer_calls[0]["launcher_config_path"])
        self.assertEqual(str(trust_profile), installer_calls[0]["trust_profile_path"])
        self.assertIs(provider, installer_calls[0]["signing_provider"])

    def test_cli_does_not_print_certificate_thumbprint(self):
        from scripts.build_signed_windows_ssl_esigner import main

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            signtool = root / "signtool.exe"
            launcher_config = root / "launcher-config.json"
            trust_profile = root / "deployment-trust-profile.json"
            signtool.write_bytes(b"signtool")
            launcher_config.write_text("{}", encoding="utf-8")
            trust_profile.write_text("{}", encoding="utf-8")
            thumbprint = "AABBCCDDEEFF00112233445566778899AABBCCDD"

            with patch("builtins.print") as printer:
                result = main(
                    [
                        "--signtool-path",
                        str(signtool),
                        "--certificate-thumbprint",
                        thumbprint,
                        "--launcher-config",
                        str(launcher_config),
                        "--trust-profile",
                        str(trust_profile),
                    ],
                    provider_factory=lambda **_kwargs: object(),
                    installer_creator=lambda **_kwargs: (
                        root / "installer.exe",
                        root / "legacy.zip",
                        root / "update.zip",
                    ),
                )

        self.assertEqual(0, result)
        rendered = " ".join(" ".join(map(str, call.args)) for call in printer.call_args_list)
        self.assertNotIn(thumbprint, rendered)


if __name__ == "__main__":
    unittest.main()
