import unittest

from wechat_cli.license.device_identity import (
    DeviceIdentityProvider,
    compute_device_fingerprint,
    generate_device_id,
    sanitize_device_name,
)


class DeviceIdentityTests(unittest.TestCase):
    def test_generates_high_entropy_prefixed_device_ids(self):
        first = generate_device_id()
        second = generate_device_id()

        self.assertTrue(first.startswith("dev_"))
        self.assertGreaterEqual(len(first), 30)
        self.assertNotEqual(first, second)

    def test_fingerprint_is_deterministic_and_does_not_expose_raw_identifiers(self):
        fingerprint = compute_device_fingerprint(
            machine_guid="machine-guid-secret",
            user_sid="S-1-5-21-secret",
            fingerprint_salt="fingerprint-salt-v1",
        )

        self.assertEqual(64, len(fingerprint))
        int(fingerprint, 16)
        self.assertNotIn("machine", fingerprint)
        self.assertEqual(
            fingerprint,
            compute_device_fingerprint(
                machine_guid="machine-guid-secret",
                user_sid="S-1-5-21-secret",
                fingerprint_salt="fingerprint-salt-v1",
            ),
        )

    def test_fingerprint_changes_with_sid_machine_or_salt(self):
        baseline = compute_device_fingerprint("machine", "sid", "salt-v1")
        variants = {
            compute_device_fingerprint("machine-2", "sid", "salt-v1"),
            compute_device_fingerprint("machine", "sid-2", "salt-v1"),
            compute_device_fingerprint("machine", "sid", "salt-v2"),
        }

        self.assertEqual(3, len(variants))
        self.assertNotIn(baseline, variants)

    def test_sanitizes_device_display_name(self):
        self.assertEqual(
            "SURTR PC",
            sanitize_device_name("  SURTR\x00\nPC  "),
        )
        self.assertEqual("Windows device", sanitize_device_name("\x00\n\t"))
        self.assertEqual(64, len(sanitize_device_name("x" * 100)))

    def test_provider_uses_injected_os_readers_without_returning_raw_values(self):
        provider = DeviceIdentityProvider(
            machine_guid_reader=lambda: "machine-guid-secret",
            user_sid_reader=lambda: "S-1-5-21-secret",
            computer_name_reader=lambda: "SURTR-PC",
        )

        identity = provider.create(
            fingerprint_salt="fingerprint-salt-v1",
            existing_device_id="dev_existing",
        )

        self.assertEqual("dev_existing", identity.device_id)
        self.assertEqual("SURTR-PC", identity.display_name)
        self.assertEqual(64, len(identity.fingerprint))
        self.assertFalse(hasattr(identity, "machine_guid"))
        self.assertFalse(hasattr(identity, "user_sid"))


if __name__ == "__main__":
    unittest.main()
