import unittest

from scripts.verify_no_tracked_secrets import scan_text


class TrackedSensitiveScanTests(unittest.TestCase):
    def test_detects_high_confidence_credential_shapes(self):
        cases = {
            "private-key-block": "-----BEGIN PRIVATE KEY-----",
            "github-token": "github_pat_1234567890abcdefghijklmnop",
            "admin-session": "wcas_adms_identifier123456.secret_value_abcdefghijklmnopqrstuvwxyz123456",
            "legacy-admin": "wcadmin_adm_identifier123.secret_value_abcdefghijklmnopqrstuvwxyz",
            "license-key": "WCL-7K3M-9Q2P-H6TX-R4DN",
        }
        for label, value in cases.items():
            with self.subTest(label=label):
                self.assertIn(label, scan_text(value))

    def test_ignores_names_placeholders_and_redacted_shapes(self):
        safe = "\n".join(
            [
                "PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY",
                "ADMIN_SESSION_PEPPER_V1",
                "REPLACE_WITH_PRODUCTION_ACCESS_AUDIENCE",
                "wcas_[REDACTED]",
                "wcadmin_[REDACTED]",
                "WCL-****-****-****-[REDACTED]",
                "github_pat_<redacted>",
            ]
        )
        self.assertEqual((), scan_text(safe))


if __name__ == "__main__":
    unittest.main()
