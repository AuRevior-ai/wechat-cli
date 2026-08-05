import base64
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC

from wechat_cli.admin.bootstrap import (
    generate_demo_bootstrap,
    write_demo_bootstrap,
)


class AdminBootstrapTests(unittest.TestCase):
    def test_generates_distinct_secrets_token_digest_and_ed25519_material(self):
        first = generate_demo_bootstrap()
        second = generate_demo_bootstrap()

        self.assertTrue(first.admin_token.startswith("wcadmin_adm_"))
        self.assertNotEqual(first.admin_token, second.admin_token)
        self.assertEqual(64, len(first.admin_token_digest))
        int(first.admin_token_digest, 16)
        self.assertNotIn(first.admin_token, first.admin_sql)
        self.assertIn(first.admin_token_digest, first.admin_sql)
        self.assertIn("INSERT INTO admin_tokens", first.admin_sql)
        self.assertEqual("*", first.admin_scopes[0])

        for name in (
            "LICENSE_KEY_PEPPER",
            "DEVICE_TOKEN_PEPPER",
            "ADMIN_TOKEN_PEPPER",
            "CONTACT_LOOKUP_PEPPER",
            "CONTACT_ENCRYPTION_KEY_V1",
            "LEASE_SIGNING_PRIVATE_KEY",
            "DOWNLOAD_TICKET_SECRET",
        ):
            self.assertIn(name, first.worker_secrets)
            self.assertGreaterEqual(len(first.worker_secrets[name]), 32)

        token_id, token_secret = first.admin_token.removeprefix("wcadmin_").split(".", 1)
        expected = hmac.new(
            first.worker_secrets["ADMIN_TOKEN_PEPPER"].encode("utf-8"),
            token_secret.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(first.admin_token_digest, expected)
        self.assertIn(token_id, first.admin_sql)

        private_key = ECC.import_key(
            base64.b64decode(first.worker_secrets["LEASE_SIGNING_PRIVATE_KEY"])
        )
        self.assertEqual("Ed25519", private_key.curve)
        self.assertTrue(private_key.has_private())
        self.assertEqual(
            private_key.public_key().export_key(format="raw"),
            base64.b64decode(first.lease_public_key_base64),
        )
        release_key = ECC.import_key(first.release_private_key_pem)
        self.assertEqual("Ed25519", release_key.curve)
        self.assertTrue(release_key.has_private())
        self.assertEqual(
            release_key.public_key().export_key(format="raw"),
            base64.b64decode(first.release_public_key_base64),
        )
        self.assertNotEqual(
            first.release_public_key_base64,
            first.lease_public_key_base64,
        )

    def test_repr_does_not_expose_secrets(self):
        artifacts = generate_demo_bootstrap()
        representation = repr(artifacts)

        self.assertNotIn(artifacts.admin_token, representation)
        for value in artifacts.worker_secrets.values():
            self.assertNotIn(value, representation)

    def test_writes_new_files_without_plaintext_token_in_sql_or_public_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "bootstrap"
            artifacts = generate_demo_bootstrap()

            paths = write_demo_bootstrap(root, artifacts)

            self.assertEqual(
                {
                    "worker_secrets",
                    "admin_sql",
                    "admin_token",
                    "public_keys",
                    "release_private_key",
                    "launcher_config_template",
                    "instructions",
                },
                set(paths),
            )
            token_text = paths["admin_token"].read_text(encoding="utf-8").strip()
            sql_text = paths["admin_sql"].read_text(encoding="utf-8")
            public = json.loads(paths["public_keys"].read_text(encoding="utf-8"))
            self.assertEqual(artifacts.admin_token, token_text)
            self.assertNotIn(artifacts.admin_token, sql_text)
            self.assertNotIn(artifacts.admin_token, json.dumps(public))
            self.assertEqual(
                artifacts.lease_public_key_base64,
                public["lease_public_keys"][artifacts.lease_signing_key_id],
            )
            self.assertEqual(
                artifacts.release_public_key_base64,
                public["release_public_keys"][artifacts.release_signing_key_id],
            )
            release_key = ECC.import_key(
                paths["release_private_key"].read_text(encoding="ascii")
            )
            self.assertTrue(release_key.has_private())
            launcher_config = json.loads(
                paths["launcher_config_template"].read_text(encoding="utf-8")
            )
            self.assertEqual(1, launcher_config["schema_version"])
            self.assertEqual("stable", launcher_config["channel"])
            self.assertEqual(8787, launcher_config["port"])
            self.assertIn("REPLACE_WITH_WORKER_HOSTNAME", launcher_config["api_base_url"])
            self.assertEqual(
                public["release_public_keys"],
                launcher_config["release_public_keys"],
            )
            self.assertEqual(
                public["lease_public_keys"],
                launcher_config["lease_public_keys"],
            )
            self.assertGreaterEqual(len(launcher_config["fingerprint_salt"]), 32)
            self.assertEqual(
                "REPLACE_WITH_PRIVATE_GITHUB_RELEASE_READ_TOKEN",
                paths["worker_secrets"]
                .read_text(encoding="utf-8")
                .split("GITHUB_RELEASE_READ_TOKEN=", 1)[1]
                .splitlines()[0],
            )

    def test_refuses_to_overwrite_any_existing_bootstrap_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.mkdir(exist_ok=True)
            (root / "admin-token.txt").write_text("existing", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                write_demo_bootstrap(root, generate_demo_bootstrap())

            self.assertEqual(
                "existing",
                (root / "admin-token.txt").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                ["admin-token.txt"],
                sorted(path.name for path in root.iterdir()),
            )

    @unittest.skipIf(os.name == "nt", "POSIX mode bits are not authoritative on Windows")
    def test_sensitive_files_are_owner_only_on_posix(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_demo_bootstrap(
                Path(tmp) / "bootstrap",
                generate_demo_bootstrap(),
            )

            self.assertEqual(0o600, paths["worker_secrets"].stat().st_mode & 0o777)
            self.assertEqual(0o600, paths["admin_token"].stat().st_mode & 0o777)
            self.assertEqual(0o600, paths["admin_sql"].stat().st_mode & 0o777)
            self.assertEqual(
                0o600,
                paths["release_private_key"].stat().st_mode & 0o777,
            )


if __name__ == "__main__":
    unittest.main()
