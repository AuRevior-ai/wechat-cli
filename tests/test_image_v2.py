import struct
import tempfile
import unittest
from pathlib import Path

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from wechat_cli.core.image_keys import (
    candidate_image_keys,
    derive_image_xor_key,
    scan_buffers_for_image_key,
    scan_buffers_for_image_keys,
    validate_image_aes_key,
)
from wechat_cli.core.media import (
    WECHAT_V2_DAT_MAGIC,
    decode_media_bytes,
    decode_wechat_v2_dat_image,
)


AES_KEY = b"1dc529ff9650a5af"
XOR_KEY = 0x51


def _encrypt_v2_image(clear, aes_key=AES_KEY, xor_key=XOR_KEY):
    aes_size = min(1024, len(clear))
    aes_plain = clear[:aes_size]
    tail = clear[aes_size:]
    encrypted = AES.new(aes_key, AES.MODE_ECB).encrypt(pad(aes_plain, 16))
    xored = bytes(value ^ xor_key for value in tail)
    return (
        WECHAT_V2_DAT_MAGIC
        + struct.pack("<II", aes_size, len(tail))
        + b"\x01"
        + encrypted
        + xored
    )


class WeChatV2ImageTests(unittest.TestCase):
    def test_decrypts_v2_aes_and_xor_image(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"image-data" * 200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)

        decoded = decode_wechat_v2_dat_image(
            encrypted,
            aes_key=AES_KEY.decode(),
            xor_key=XOR_KEY,
        )

        self.assertEqual(decoded, (clear, "image/jpeg"))

    def test_decode_media_bytes_uses_v2_keys(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)

        body, content_type = decode_media_bytes(
            encrypted,
            "sample.dat",
            image_aes_key=AES_KEY.decode(),
            image_xor_key=XOR_KEY,
        )

        self.assertEqual(body, clear)
        self.assertEqual(content_type, "image/jpeg")

    def test_decode_media_bytes_tries_multiple_session_keys(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)

        body, content_type = decode_media_bytes(
            encrypted,
            "sample.dat",
            image_aes_key=["wrongwrongwrong1", AES_KEY.decode()],
            image_xor_key=XOR_KEY,
        )

        self.assertEqual(body, clear)
        self.assertEqual(content_type, "image/jpeg")

    def test_v2_without_key_does_not_claim_to_be_decoded(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)

        self.assertIsNone(decode_wechat_v2_dat_image(encrypted))

    def test_decrypts_wxgf_variant_without_mislabeling_it_as_jpeg(self):
        clear = b"wxgf" + b"\x13\x00\x02\x05" + b"x" * 1400
        encrypted = _encrypt_v2_image(clear)

        body, content_type = decode_wechat_v2_dat_image(
            encrypted,
            aes_key=AES_KEY.decode(),
            xor_key=XOR_KEY,
        )

        self.assertEqual(body, clear)
        self.assertEqual(content_type, "image/x-wechat-wxgf")


class WeChatImageKeyTests(unittest.TestCase):
    def test_candidate_keys_use_exact_16_and_first_half_of_32_tokens(self):
        region = (
            b" " + AES_KEY + b" "
            + b"1dc529ff9650a5af8b75856e3de8231f" + b" "
            + b"x" + AES_KEY + b"y"
        )

        candidates = list(candidate_image_keys(region))

        self.assertIn(AES_KEY, candidates)
        self.assertEqual(candidates.count(AES_KEY), 2)

    def test_validates_key_against_ciphertext_image_magic(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)
        ciphertexts = [encrypted[15:31]]

        self.assertTrue(validate_image_aes_key(AES_KEY, ciphertexts))
        self.assertFalse(validate_image_aes_key(b"wrongwrongwrong1", ciphertexts))

    def test_accepts_key_matching_one_sample_from_mixed_sessions(self):
        matching = AES.new(AES_KEY, AES.MODE_ECB).encrypt(
            b"\xff\xd8\xff" + b"\x00" * 13
        )
        other_session = AES.new(
            b"otherSessionKey1",
            AES.MODE_ECB,
        ).encrypt(b"\x89PNG" + b"\x00" * 12)

        self.assertTrue(
            validate_image_aes_key(AES_KEY, [matching, other_session])
        )

    def test_scans_memory_buffers_and_returns_first_verified_key(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)
        buffers = [
            b" no useful value ",
            b" token 1dc529ff9650a5af8b75856e3de8231f done ",
        ]

        key = scan_buffers_for_image_key(buffers, [encrypted[15:31]])

        self.assertEqual(key, AES_KEY)

    def test_scans_memory_once_and_collects_keys_for_multiple_sessions(self):
        other_key = b"otherSessionKey1"
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        first = _encrypt_v2_image(clear, aes_key=AES_KEY)
        second = _encrypt_v2_image(clear, aes_key=other_key)
        buffers = [
            b" token " + AES_KEY + b" done ",
            b" token " + other_key + b" done ",
        ]

        keys = scan_buffers_for_image_keys(
            buffers,
            [first[15:31], second[15:31]],
        )

        self.assertEqual(keys, [AES_KEY, other_key])

    def test_derives_xor_key_from_recent_v2_thumbnail_tails(self):
        clear = b"\xff\xd8\xff\xe0JFIF" + b"x" * 1200 + b"\xff\xd9"
        encrypted = _encrypt_v2_image(clear)
        with tempfile.TemporaryDirectory() as tmp:
            paths = []
            for index in range(3):
                path = Path(tmp) / f"{index}_t.dat"
                path.write_bytes(encrypted)
                paths.append(path)

            key = derive_image_xor_key(paths)

        self.assertEqual(key, XOR_KEY)


if __name__ == "__main__":
    unittest.main()
