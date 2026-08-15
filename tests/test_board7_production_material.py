import base64
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC


class Board7ProductionMaterialTests(unittest.TestCase):
    def test_direct_script_execution_resolves_repository_imports(self):
        root = Path(__file__).resolve().parents[1]
        script = root / "scripts" / "board7_prepare_production_material.py"
        original_path = list(sys.path)
        original_argv = list(sys.argv)
        try:
            sys.path[:] = [str(root / "scripts"), *[item for item in original_path if Path(item or ".").resolve() != root]]
            sys.argv[:] = [str(script), "--help"]
            with self.assertRaises(SystemExit) as raised:
                runpy.run_path(str(script), run_name="__main__")
            self.assertEqual(0, raised.exception.code)
        finally:
            sys.path[:] = original_path
            sys.argv[:] = original_argv

    def test_generation_matches_exact_g4_contract(self):
        from scripts.board7_prepare_production_material import generate_material

        artifacts = generate_material(human_identity="operator@example.com")

        self.assertEqual(
            {
                "ADMIN_SESSION_PEPPER_V1",
                "CONTACT_ENCRYPTION_KEY_V1",
                "CONTACT_LOOKUP_PEPPER_V1",
                "DEVICE_TOKEN_PEPPER_V1",
                "DIAGNOSTIC_UPLOAD_SECRET_V1",
                "DOWNLOAD_TICKET_SECRET_V1",
                "LEASE_SIGNING_PRIVATE_KEY",
                "LICENSE_KEY_PEPPER_V1",
                "RATE_LIMIT_PEPPER_V1",
            },
            set(artifacts.worker_secrets),
        )
        self.assertNotIn("GITHUB_RELEASE_READ_TOKEN", artifacts.worker_secrets)
        self.assertNotIn("ADMIN_TOKEN_PEPPER", artifacts.worker_secrets)
        self.assertNotIn("*", artifacts.human_scopes)
        self.assertEqual(
            (
                "licenses:read",
                "licenses:write",
                "devices:read",
                "devices:write",
                "releases:upload",
                "releases:read",
                "releases:register",
                "releases:state",
                "diagnostics:read",
                "diagnostics:delete",
                "contacts:rotate",
            ),
            artifacts.human_scopes,
        )
        self.assertIn("production-primary-admin", artifacts.human_principal_sql)
        self.assertIn("operator@example.com", artifacts.human_principal_sql)
        self.assertNotIn("*", artifacts.human_principal_sql)

    def test_generated_key_material_and_trust_profile_are_consistent(self):
        from scripts.board7_prepare_production_material import generate_material

        artifacts = generate_material(human_identity="operator@example.com")

        contact_key = base64.b64decode(
            artifacts.worker_secrets["CONTACT_ENCRYPTION_KEY_V1"],
            validate=True,
        )
        self.assertEqual(32, len(contact_key))

        lease_private = ECC.import_key(
            base64.b64decode(
                artifacts.worker_secrets["LEASE_SIGNING_PRIVATE_KEY"],
                validate=True,
            )
        )
        self.assertEqual("Ed25519", lease_private.curve)
        self.assertTrue(lease_private.has_private())
        self.assertEqual(
            lease_private.public_key().export_key(format="raw"),
            base64.b64decode(artifacts.lease_public_key_base64, validate=True),
        )

        release_private = ECC.import_key(artifacts.release_private_key_pem)
        self.assertEqual("Ed25519", release_private.curve)
        self.assertTrue(release_private.has_private())
        self.assertEqual(
            release_private.public_key().export_key(format="raw"),
            base64.b64decode(artifacts.release_public_key_base64, validate=True),
        )
        self.assertNotEqual(
            artifacts.release_public_key_base64,
            artifacts.lease_public_key_base64,
        )

        profile = artifacts.trust_profile
        self.assertEqual(2, profile["schema_version"])
        self.assertEqual("private_controlled", profile["distribution_profile"])
        self.assertEqual("production", profile["environment"])
        self.assertEqual("stable", profile["expected_channel"])
        self.assertEqual(
            "https://wechat-cli-api.aurevior-devspace.com",
            profile["api_base_url"],
        )
        self.assertEqual("", profile["windows_publisher_policy"])
        self.assertEqual(
            {"release-key-production-01": artifacts.release_public_key_base64},
            profile["release_public_keys"],
        )
        self.assertEqual(
            {"lease-key-production-01": artifacts.lease_public_key_base64},
            profile["lease_public_keys"],
        )
        self.assertGreaterEqual(len(profile["fingerprint_salt"]), 32)

    def test_repr_and_safe_metadata_do_not_expose_sensitive_values_or_identity(self):
        from scripts.board7_prepare_production_material import generate_material

        artifacts = generate_material(human_identity="operator@example.com")
        representation = repr(artifacts)
        safe = artifacts.safe_metadata()
        serialized = json.dumps(safe, sort_keys=True)

        self.assertNotIn("operator@example.com", serialized)
        self.assertNotIn(artifacts.release_private_key_pem, representation)
        for value in artifacts.worker_secrets.values():
            self.assertNotIn(value, representation)
            self.assertNotIn(value, serialized)
        self.assertEqual(
            sorted(artifacts.worker_secrets),
            safe["worker_secret_names"],
        )
        self.assertEqual(
            "release-key-production-01",
            safe["release_signing_key_id"],
        )
        self.assertEqual(
            "lease-key-production-01",
            safe["lease_signing_key_id"],
        )

    def test_write_material_is_repo_external_exclusive_and_separates_private_public_files(self):
        from scripts.board7_prepare_production_material import (
            ROOT,
            generate_material,
            write_material,
        )

        artifacts = generate_material(human_identity="operator@example.com")
        with self.assertRaises(ValueError):
            write_material(ROOT / "forbidden-production-material", artifacts, apply_acl=False)

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "production-material"
            paths = write_material(output, artifacts, apply_acl=False)
            self.assertEqual(
                {
                    "worker_secrets",
                    "release_private_key",
                    "public_keys",
                    "trust_profile",
                    "human_principal_sql",
                    "safe_metadata",
                    "instructions",
                },
                set(paths),
            )
            worker_secrets = json.loads(paths["worker_secrets"].read_text(encoding="utf-8"))
            self.assertEqual(dict(artifacts.worker_secrets), worker_secrets)
            public_keys = json.loads(paths["public_keys"].read_text(encoding="utf-8"))
            self.assertEqual(
                artifacts.release_public_key_base64,
                public_keys["release_public_keys"]["release-key-production-01"],
            )
            self.assertEqual(
                artifacts.lease_public_key_base64,
                public_keys["lease_public_keys"]["lease-key-production-01"],
            )
            profile = json.loads(paths["trust_profile"].read_text(encoding="utf-8"))
            self.assertEqual(artifacts.trust_profile, profile)
            self.assertNotIn("operator@example.com", paths["safe_metadata"].read_text(encoding="utf-8"))
            self.assertIn("operator@example.com", paths["human_principal_sql"].read_text(encoding="utf-8"))

            with self.assertRaises(FileExistsError):
                write_material(output, artifacts, apply_acl=False)

    def test_windows_acl_command_is_bounded_to_output_root_and_fixed_trustees(self):
        from scripts.board7_prepare_production_material import restrict_windows_acl

        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            class Result:
                returncode = 0
            return Result()

        restrict_windows_acl(
            Path(r"D:\safe\production-material"),
            current_identity=r"DESKTOP\operator",
            runner=runner,
        )
        self.assertEqual(1, len(calls))
        command, kwargs = calls[0]
        self.assertEqual("icacls", command[0].lower())
        self.assertEqual(r"D:\safe\production-material", command[1])
        self.assertIn("/inheritance:r", command)
        self.assertIn(r"DESKTOP\operator:(OI)(CI)F", command)
        self.assertIn("*S-1-5-18:(OI)(CI)F", command)
        self.assertIn("*S-1-5-32-544:(OI)(CI)F", command)
        self.assertIn("/T", command)
        self.assertIs(kwargs["check"], True)


if __name__ == "__main__":
    unittest.main()
