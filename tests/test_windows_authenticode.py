import importlib.util
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
        self.assertEqual("powershell.exe", command[0])
        self.assertEqual(str(path), command[-1])
        self.assertEqual(10, kwargs["timeout"])
        self.assertTrue(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        self.assertTrue(kwargs["text"])

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
