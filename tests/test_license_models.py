import unittest

from wechat_cli.license.models import (
    ActivationResult,
    ClientLicenseState,
    DeviceRecord,
    ValidationResult,
)


class LicenseModelTests(unittest.TestCase):
    def test_activation_result_decodes_required_fields(self):
        result = ActivationResult.from_mapping(
            {
                "license_id": "lic_01",
                "device_id": "dev_01",
                "device_token": "wcdt_token.secret",
                "device_count": 1,
                "maximum_devices": 3,
                "lease_content_base64": "e30=",
                "lease_signature_base64": "c2ln",
            }
        )

        self.assertEqual("lic_01", result.license_id)
        self.assertEqual("wcdt_token.secret", result.device_token)
        self.assertEqual(b"{}", result.lease_content)
        self.assertEqual(b"sig", result.lease_signature)

    def test_validation_result_rejects_missing_server_time(self):
        with self.assertRaises(ValueError):
            ValidationResult.from_mapping(
                {
                    "license_id": "lic_01",
                    "device_id": "dev_01",
                    "lease_content_base64": "e30=",
                    "lease_signature_base64": "c2ln",
                }
            )

    def test_device_record_is_masked_management_data(self):
        record = DeviceRecord.from_mapping(
            {
                "device_id": "dev_01",
                "display_name": "SURTR-PC",
                "status": "active",
                "is_current": True,
                "last_validated_at": "2026-08-04T15:00:00Z",
                "last_app_version": "0.5.0",
                "last_launcher_version": "0.1.0",
            }
        )

        self.assertEqual("SURTR-PC", record.display_name)
        self.assertTrue(record.is_current)
        self.assertFalse(hasattr(record, "device_token"))

    def test_client_license_states_include_online_and_offline_boundaries(self):
        expected = {
            "unactivated",
            "online_valid",
            "offline_valid",
            "offline_expiring",
            "offline_expired",
            "device_unbound",
            "license_suspended",
            "license_revoked",
            "local_state_corrupt",
        }
        self.assertTrue(expected.issubset({state.value for state in ClientLicenseState}))


if __name__ == "__main__":
    unittest.main()
