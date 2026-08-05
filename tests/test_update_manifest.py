import base64
import json
import tempfile
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from tests.test_update_models import make_manifest
from wechat_cli.update.crypto import TrustedEd25519Keys
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.manifest import verify_manifest_package, verify_signed_manifest


TEST_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes(range(32)))
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key().export_key(format="raw")


def signed_manifest_bytes():
    raw = json.dumps(make_manifest(), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(raw)
    return raw, signature


class SignedManifestTests(unittest.TestCase):
    def test_verifies_signature_over_original_utf8_bytes(self):
        raw, signature = signed_manifest_bytes()
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

        manifest = verify_signed_manifest(raw, signature, keys)

        self.assertEqual("0.5.0", str(manifest.version))

    def test_accepts_base64_signature(self):
        raw, signature = signed_manifest_bytes()
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

        manifest = verify_signed_manifest(
            raw,
            base64.b64encode(signature).decode("ascii"),
            keys,
        )

        self.assertEqual("rel_test_050", manifest.release_id)

    def test_reserialized_equivalent_json_does_not_reuse_signature(self):
        raw, signature = signed_manifest_bytes()
        parsed = json.loads(raw)
        reformatted = json.dumps(parsed, ensure_ascii=False, indent=2).encode("utf-8")
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

        with self.assertRaises(UpdateError) as caught:
            verify_signed_manifest(reformatted, signature, keys)

        self.assertEqual(ErrorCode.UPDATE_SIGNATURE_INVALID, caught.exception.code)

    def test_manifest_key_id_selects_trusted_public_key(self):
        raw, signature = signed_manifest_bytes()
        keys = TrustedEd25519Keys({"another-key": TEST_PUBLIC_KEY})

        with self.assertRaises(UpdateError) as caught:
            verify_signed_manifest(raw, signature, keys)

        self.assertEqual(ErrorCode.UPDATE_SIGNING_KEY_UNKNOWN, caught.exception.code)

    def test_package_verification_uses_manifest_size_and_hash(self):
        content = b"valid update package"
        data = make_manifest()
        import hashlib

        data["package"] = dict(
            data["package"],
            size=len(content),
            sha256=hashlib.sha256(content).hexdigest(),
        )
        raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
        signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(raw)
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})
        manifest = verify_signed_manifest(raw, signature, keys)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / manifest.package.filename
            path.write_bytes(content)
            verify_manifest_package(path, manifest)

    def test_package_verification_rejects_wrong_size_before_install(self):
        raw, signature = signed_manifest_bytes()
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})
        manifest = verify_signed_manifest(raw, signature, keys)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / manifest.package.filename
            path.write_bytes(b"tiny")
            with self.assertRaises(UpdateError) as caught:
                verify_manifest_package(path, manifest)

        self.assertEqual(ErrorCode.UPDATE_HASH_MISMATCH, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
