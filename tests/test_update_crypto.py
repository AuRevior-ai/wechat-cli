import base64
import hashlib
import tempfile
import unittest
from pathlib import Path

from Crypto.PublicKey import ECC
from Crypto.Signature import eddsa

from wechat_cli.update.crypto import TrustedEd25519Keys, sha256_file, verify_file_sha256
from wechat_cli.update.errors import ErrorCode, UpdateError


TEST_PRIVATE_KEY = ECC.construct(curve="Ed25519", seed=bytes(range(32)))
TEST_PUBLIC_KEY = TEST_PRIVATE_KEY.public_key().export_key(format="raw")


class TrustedEd25519KeysTests(unittest.TestCase):
    def test_verifies_raw_signature_with_known_key(self):
        message = b"signed manifest bytes\n"
        signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(message)
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

        keys.verify("release-key-test-01", message, signature)

    def test_accepts_base64_encoded_public_keys(self):
        keys = TrustedEd25519Keys.from_base64(
            {"release-key-test-01": base64.b64encode(TEST_PUBLIC_KEY).decode("ascii")}
        )
        message = b"manifest"
        signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(message)

        keys.verify("release-key-test-01", message, signature)

    def test_rejects_unknown_key_id(self):
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

        with self.assertRaises(UpdateError) as caught:
            keys.verify("unknown-key", b"manifest", b"x" * 64)

        self.assertEqual(ErrorCode.UPDATE_SIGNING_KEY_UNKNOWN, caught.exception.code)

    def test_rejects_modified_message(self):
        original = b"manifest"
        signature = eddsa.new(TEST_PRIVATE_KEY, "rfc8032").sign(original)
        keys = TrustedEd25519Keys({"release-key-test-01": TEST_PUBLIC_KEY})

        with self.assertRaises(UpdateError) as caught:
            keys.verify("release-key-test-01", original + b" ", signature)

        self.assertEqual(ErrorCode.UPDATE_SIGNATURE_INVALID, caught.exception.code)

    def test_rejects_invalid_public_key_length(self):
        with self.assertRaises(ValueError):
            TrustedEd25519Keys({"bad": b"short"})


class FileDigestTests(unittest.TestCase):
    def test_sha256_file_and_verify_match_expected_digest(self):
        content = b"wechat-cli-update" * 1024
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "package.zip"
            path.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()

            self.assertEqual(expected, sha256_file(path))
            verify_file_sha256(path, expected.upper())

    def test_verify_file_sha256_rejects_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "package.zip"
            path.write_bytes(b"tampered")

            with self.assertRaises(UpdateError) as caught:
                verify_file_sha256(path, "00" * 32)

        self.assertEqual(ErrorCode.UPDATE_HASH_MISMATCH, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
