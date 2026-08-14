import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class WindowsAuthenticodeTests(unittest.TestCase):
    def test_authenticode_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("wechat_cli.windows.authenticode"))

    def test_authenticode_module_exports_policy_and_verifier_contract(self):
        from wechat_cli.windows import authenticode

        self.assertIsNotNone(getattr(authenticode, "AuthenticodePolicy", None))
        self.assertIsNotNone(getattr(authenticode, "AuthenticodeSignature", None))
        self.assertTrue(callable(getattr(authenticode, "verify_windows_authenticode", None)))
        self.assertTrue(callable(getattr(authenticode, "inspect_windows_authenticode", None)))

    def test_powershell_inspector_parses_bounded_signature_result(self):
        from wechat_cli.windows.authenticode import inspect_windows_authenticode

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            calls = []

            class Completed:
                stdout = (
                    '{"Status":"Valid","Subject":"CN=Board6 Test",'
                    '"Thumbprint":"AA11"}'
                )

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return Completed()

            try:
                signature = inspect_windows_authenticode(path, runner=runner)
            except Exception as exc:
                self.fail(f"bounded PowerShell Authenticode inspection failed: {exc}")

        self.assertEqual("Valid", signature.status)
        self.assertEqual("CN=Board6 Test", signature.subject)
        self.assertEqual("AA11", signature.thumbprint)
        command, kwargs = calls[0]
        system_root = Path(os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows")
        expected_executable = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        self.assertEqual(str(expected_executable), command[0])
        self.assertEqual(str(path), kwargs["env"]["WECHAT_CLI_AUTHENTICODE_TARGET"])
        self.assertNotIn(str(path), command)
        self.assertEqual(10, kwargs["timeout"])
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])

    def test_powershell_inspector_uses_deterministic_windows_module_environment(self):
        from wechat_cli.windows.authenticode import inspect_windows_authenticode

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            calls = []

            class Completed:
                stdout = (
                    '{"Status":"Valid","Subject":"CN=Board6 Test",'
                    '"Thumbprint":"AA11"}'
                )

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return Completed()

            with patch.dict(
                os.environ,
                {"PSModulePath": "C:\\Program Files\\PowerShell\\7\\Modules;POLLUTED"},
                clear=False,
            ):
                inspect_windows_authenticode(path, runner=runner)

        command, kwargs = calls[0]
        system_root = Path(os.environ.get("SystemRoot") or os.environ.get("WINDIR") or r"C:\Windows")
        expected_executable = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        expected_module_root = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "Modules"
        self.assertEqual(str(expected_executable), command[0])
        self.assertIn("-NoProfile", command)
        self.assertIn(
            "Import-Module Microsoft.PowerShell.Security -ErrorAction Stop",
            command[command.index("-Command") + 1],
        )
        self.assertEqual(str(expected_module_root), kwargs["env"]["PSModulePath"])
        self.assertNotIn("PowerShell\\7", kwargs["env"]["PSModulePath"])
        self.assertNotIn("POLLUTED", kwargs["env"]["PSModulePath"])

    def test_powershell_inspector_passes_target_only_through_child_environment(self):
        from wechat_cli.windows.authenticode import inspect_windows_authenticode

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate with spaces.exe"
            path.write_bytes(b"candidate")
            calls = []

            class Completed:
                stdout = (
                    '{"Status":"Valid","Subject":"CN=Board6 Test",'
                    '"Thumbprint":"AA11"}'
                )

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return Completed()

            inspect_windows_authenticode(path, runner=runner)

        command, kwargs = calls[0]
        script = command[command.index("-Command") + 1]
        self.assertIn("WECHAT_CLI_AUTHENTICODE_TARGET", kwargs["env"])
        self.assertEqual(str(path), kwargs["env"]["WECHAT_CLI_AUTHENTICODE_TARGET"])
        self.assertIn("$env:WECHAT_CLI_AUTHENTICODE_TARGET", script)
        self.assertNotIn("$args[0]", script)
        self.assertNotIn(str(path), command)

    def test_powershell_inspector_fails_closed_when_security_module_load_fails(self):
        from wechat_cli.windows.authenticode import inspect_windows_authenticode

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")

            def runner(_command, **_kwargs):
                raise subprocess.CalledProcessError(1, "powershell.exe")

            with self.assertRaisesRegex(ValueError, "failed closed"):
                inspect_windows_authenticode(path, runner=runner)

    def test_powershell_inspector_rejects_malformed_output(self):
        from wechat_cli.windows.authenticode import inspect_windows_authenticode

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")

            class Completed:
                stdout = "not-json"

            with self.assertRaisesRegex(ValueError, "failed closed"):
                inspect_windows_authenticode(path, runner=lambda _command, **_kwargs: Completed())

    def test_verifier_uses_bounded_windows_inspector_by_default(self):
        from wechat_cli.windows.authenticode import (
            AuthenticodePolicy,
            AuthenticodeSignature,
            verify_windows_authenticode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            expected = AuthenticodeSignature("Valid", "CN=Board6 Test", "AA11")
            with patch(
                "wechat_cli.windows.authenticode.inspect_windows_authenticode",
                return_value=expected,
            ) as inspect_signature:
                try:
                    actual = verify_windows_authenticode(
                        path,
                        AuthenticodePolicy(required=False),
                    )
                except Exception as exc:
                    self.fail(f"default Authenticode inspector was not used: {exc}")

        self.assertEqual(expected, actual)
        inspect_signature.assert_called_once_with(path)

    def test_verifier_delegates_signature_inspection_for_existing_file(self):
        from wechat_cli.windows.authenticode import (
            AuthenticodePolicy,
            AuthenticodeSignature,
            verify_windows_authenticode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            calls = []
            expected = AuthenticodeSignature("Valid", "CN=Board6 Test", "AA11")

            def inspector(target):
                calls.append(target)
                return expected

            try:
                actual = verify_windows_authenticode(
                    path,
                    AuthenticodePolicy(required=False),
                    inspector=inspector,
                )
            except Exception as exc:
                self.fail(f"signature inspection delegation failed: {exc}")

        self.assertEqual(expected, actual)
        self.assertEqual([path], calls)

    def test_required_policy_rejects_unsigned_candidate(self):
        from wechat_cli.windows.authenticode import (
            AuthenticodePolicy,
            AuthenticodeSignature,
            verify_windows_authenticode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            with self.assertRaisesRegex(ValueError, "signature"):
                verify_windows_authenticode(
                    path,
                    AuthenticodePolicy(required=True),
                    inspector=lambda _path: AuthenticodeSignature(
                        "NotSigned", None, None
                    ),
                )

    def test_required_policy_rejects_valid_signature_from_wrong_publisher(self):
        from wechat_cli.windows.authenticode import (
            AuthenticodePolicy,
            AuthenticodeSignature,
            verify_windows_authenticode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            with self.assertRaisesRegex(ValueError, "publisher"):
                verify_windows_authenticode(
                    path,
                    AuthenticodePolicy(
                        required=True,
                        expected_subject="CN=Expected Publisher",
                    ),
                    inspector=lambda _path: AuthenticodeSignature(
                        "Valid", "CN=Other Publisher", "AA11"
                    ),
                )

    def test_required_policy_accepts_expected_publisher_and_thumbprint(self):
        from wechat_cli.windows.authenticode import (
            AuthenticodePolicy,
            AuthenticodeSignature,
            verify_windows_authenticode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            result = verify_windows_authenticode(
                path,
                AuthenticodePolicy(
                    required=True,
                    expected_subject="CN=Expected Publisher",
                    expected_thumbprints=frozenset({"AA 11"}),
                ),
                inspector=lambda _path: AuthenticodeSignature(
                    "Valid", "CN=Expected Publisher", "aa11"
                ),
            )

        self.assertEqual("Valid", result.status)

    def test_required_policy_rejects_valid_signature_with_unapproved_thumbprint(self):
        from wechat_cli.windows.authenticode import (
            AuthenticodePolicy,
            AuthenticodeSignature,
            verify_windows_authenticode,
        )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "candidate.exe"
            path.write_bytes(b"candidate")
            with self.assertRaisesRegex(ValueError, "thumbprint"):
                verify_windows_authenticode(
                    path,
                    AuthenticodePolicy(
                        required=True,
                        expected_thumbprints=frozenset({"AA11"}),
                    ),
                    inspector=lambda _path: AuthenticodeSignature(
                        "Valid", "CN=Expected Publisher", "BB22"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
