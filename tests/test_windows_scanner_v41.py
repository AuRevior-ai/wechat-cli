import hashlib
import hmac
import os
import struct
import tempfile
import unittest
from unittest.mock import patch

from wechat_cli.keys import scanner_windows


class WindowsScannerV41Tests(unittest.TestCase):
    def test_extracts_internal_key_candidate_from_dll_instruction_sequence(self):
        internal_key = bytes(range(32))
        chunks = []
        for index in range(4):
            chunk = internal_key[index * 8:(index + 1) * 8]
            chunks.append(b"\x48\xba" + chunk + b"\x90")
        dll_bytes = b"prefix" + b"".join(chunks) + b"\x48\x85\xc0" + b"suffix"

        candidates = scanner_windows._extract_internal_key_candidates_from_bytes(dll_bytes)

        self.assertEqual(candidates, [internal_key])

    def test_extracts_candidate_pointer_from_weixin_key_stub(self):
        pointer = 0x0000123456789ABC
        stub = (
            pointer.to_bytes(8, "little")
            + b"\x00" * 8
            + b"\x20"
            + b"\x00" * 7
            + b"\x2f"
            + b"\x00" * 7
        )

        pointers = scanner_windows._extract_candidate_pointers_from_region(
            b"prefix" + stub + b"suffix"
        )

        self.assertEqual(pointers, [pointer])

    def test_recovers_passphrase_by_xoring_memory_block_with_internal_key(self):
        passphrase = bytes(range(32))
        internal_key = bytes(reversed(range(32)))
        memory_block = bytes(a ^ b for a, b in zip(passphrase, internal_key))

        recovered = scanner_windows._decode_passphrase_candidate(
            memory_block, internal_key
        )

        self.assertEqual(recovered, passphrase)

    def test_derives_sqlcipher_key_from_v41_passphrase(self):
        passphrase = bytes(range(32))
        salt = bytes(range(16))

        derived = scanner_windows._derive_v41_encryption_key(
            passphrase, salt, iterations=2
        )

        expected = hashlib.pbkdf2_hmac(
            "sha512", passphrase, salt, 2, dklen=32
        )
        self.assertEqual(derived, expected)

    def test_filters_pointer_targets_that_cannot_be_random_key_material(self):
        self.assertTrue(scanner_windows._is_potential_key_block(bytes(range(32))))
        self.assertFalse(scanner_windows._is_potential_key_block(b"\x00" * 32))
        self.assertFalse(scanner_windows._is_potential_key_block(b"a" * 32))

    def test_finds_versioned_weixin_dll_next_to_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe_path = os.path.join(tmp, "Weixin.exe")
            version_dir = os.path.join(tmp, "4.1.11.24")
            os.makedirs(version_dir)
            with open(exe_path, "wb") as file:
                file.write(b"exe")
            dll_path = os.path.join(version_dir, "Weixin.dll")
            with open(dll_path, "wb") as file:
                file.write(b"dll")

            found = scanner_windows._find_versioned_weixin_dll(exe_path)

        self.assertEqual(found, dll_path)

    def test_verifies_v41_memory_candidate_against_database_page(self):
        passphrase = bytes(range(32))
        internal_key = bytes(reversed(range(32)))
        memory_block = bytes(a ^ b for a, b in zip(passphrase, internal_key))
        salt = bytes(range(16))
        page = bytearray(4096)
        page[:16] = salt
        derived = hashlib.pbkdf2_hmac(
            "sha512", passphrase, salt, 2, dklen=32
        )
        mac_salt = bytes(byte ^ 0x3A for byte in salt)
        mac_key = hashlib.pbkdf2_hmac(
            "sha512", derived, mac_salt, 2, dklen=32
        )
        digest = hmac.new(mac_key, page[16:4032], hashlib.sha512)
        digest.update(struct.pack("<I", 1))
        page[4032:4096] = digest.digest()

        result = scanner_windows._verify_v41_candidate(
            memory_block, internal_key, bytes(page), iterations=2
        )

        self.assertEqual(result, (passphrase, derived))

    def test_finds_verified_passphrase_among_multiple_memory_blocks(self):
        passphrase = bytes(range(32))
        internal_key = bytes(reversed(range(32)))
        good_block = bytes(a ^ b for a, b in zip(passphrase, internal_key))
        salt = bytes(range(16))
        page = bytearray(4096)
        page[:16] = salt
        derived = hashlib.pbkdf2_hmac(
            "sha512", passphrase, salt, 2, dklen=32
        )
        mac_salt = bytes(byte ^ 0x3A for byte in salt)
        mac_key = hashlib.pbkdf2_hmac(
            "sha512", derived, mac_salt, 2, dklen=32
        )
        digest = hmac.new(mac_key, page[16:4032], hashlib.sha512)
        digest.update(struct.pack("<I", 1))
        page[4032:4096] = digest.digest()

        result = scanner_windows._find_verified_v41_candidate(
            [b"x" * 32, good_block],
            [internal_key],
            bytes(page),
            iterations=2,
            max_workers=2,
        )

        self.assertEqual(result, (passphrase, derived))

    def test_collects_unique_potential_blocks_from_pointer_stubs(self):
        pointer = 0x0000123456789ABC
        stub = (
            pointer.to_bytes(8, "little")
            + b"\x00" * 8
            + b"\x20"
            + b"\x00" * 7
            + b"\x2f"
            + b"\x00" * 7
        )
        block = bytes(range(32))

        values = scanner_windows._candidate_blocks_from_region(
            stub + stub,
            lambda address, size: block if address == pointer and size == 32 else b"",
        )

        self.assertEqual(values, [block])

    def test_derives_and_verifies_keys_for_every_database_salt(self):
        passphrase = bytes(range(32))
        db_files = []
        for index in range(2):
            salt = bytes([index]) * 16
            page = bytearray(4096)
            page[:16] = salt
            derived = hashlib.pbkdf2_hmac(
                "sha512", passphrase, salt, 2, dklen=32
            )
            mac_salt = bytes(byte ^ 0x3A for byte in salt)
            mac_key = hashlib.pbkdf2_hmac(
                "sha512", derived, mac_salt, 2, dklen=32
            )
            digest = hmac.new(mac_key, page[16:4032], hashlib.sha512)
            digest.update(struct.pack("<I", 1))
            page[4032:4096] = digest.digest()
            db_files.append(
                (f"message/message_{index}.db", "unused", 4096, salt.hex(), bytes(page))
            )

        key_map = scanner_windows._derive_v41_key_map(
            passphrase, db_files, iterations=2, max_workers=2
        )

        self.assertEqual(set(key_map), {item[3] for item in db_files})

    def test_loads_internal_keys_from_versioned_weixin_dll(self):
        internal_key = bytes(range(32))
        sequence = b"".join(
            b"\x48\xba" + internal_key[index * 8:(index + 1) * 8] + b"\x90"
            for index in range(4)
        ) + b"\x48\x85\xc0"
        with tempfile.TemporaryDirectory() as tmp:
            exe_path = os.path.join(tmp, "Weixin.exe")
            version_dir = os.path.join(tmp, "4.1.11.24")
            os.makedirs(version_dir)
            with open(exe_path, "wb") as file:
                file.write(b"exe")
            with open(os.path.join(version_dir, "Weixin.dll"), "wb") as file:
                file.write(b"prefix" + sequence + b"suffix")

            candidates = scanner_windows._load_internal_key_candidates(exe_path)

        self.assertEqual(candidates, [internal_key])

    def test_collects_v41_blocks_from_readable_process_regions(self):
        region_base = 0x1000
        pointer = 0x9000
        stub = (
            pointer.to_bytes(8, "little")
            + b"\x00" * 8
            + b"\x20"
            + b"\x00" * 7
            + b"\x2f"
            + b"\x00" * 7
        )
        block = bytes(range(32))

        def fake_read(handle, address, size):
            if address == region_base:
                return b"prefix" + stub + b"suffix"
            if address == pointer and size == 32:
                return block
            return None

        with patch.object(scanner_windows, "_enum_regions", return_value=[(region_base, 64)]), \
                patch.object(scanner_windows, "_read_mem", side_effect=fake_read):
            values = scanner_windows._collect_v41_memory_blocks(object())

        self.assertEqual(values, [block])

    def test_prefers_highest_message_shard_for_v41_verification(self):
        db_files = [
            ("contact/contact.db", "a", 4096, "00" * 16, b"a" * 4096),
            ("message/message_0.db", "b", 4096, "01" * 16, b"b" * 4096),
            ("message\\message_12.db", "c", 4096, "02" * 16, b"c" * 4096),
        ]

        target = scanner_windows._select_v41_verification_db(db_files)

        self.assertEqual(target[0], "message\\message_12.db")

    def test_gets_weixin_executable_path_from_process_handle(self):
        expected = r"C:\Program Files\Tencent\Weixin\Weixin.exe"

        def fake_query(handle, flags, buffer, size_pointer):
            buffer.value = expected
            return 1

        found = scanner_windows._get_process_executable_path(
            object(), query_fn=fake_query
        )

        self.assertEqual(found, expected)

    def test_recovers_all_v41_database_keys_from_one_verified_passphrase(self):
        passphrase = bytes(range(32))
        internal_key = bytes(reversed(range(32)))
        memory_block = bytes(a ^ b for a, b in zip(passphrase, internal_key))
        db_files = []
        for index in range(2):
            salt = bytes([index + 10]) * 16
            page = bytearray(4096)
            page[:16] = salt
            derived = hashlib.pbkdf2_hmac(
                "sha512", passphrase, salt, 2, dklen=32
            )
            mac_salt = bytes(byte ^ 0x3A for byte in salt)
            mac_key = hashlib.pbkdf2_hmac(
                "sha512", derived, mac_salt, 2, dklen=32
            )
            digest = hmac.new(mac_key, page[16:4032], hashlib.sha512)
            digest.update(struct.pack("<I", 1))
            page[4032:4096] = digest.digest()
            db_files.append(
                (
                    f"message/message_{index}.db",
                    "unused",
                    4096,
                    salt.hex(),
                    bytes(page),
                )
            )

        with patch.object(
            scanner_windows,
            "_load_internal_key_candidates",
            return_value=[internal_key],
        ), patch.object(
            scanner_windows,
            "_collect_v41_memory_blocks",
            return_value=[memory_block],
        ):
            key_map = scanner_windows._recover_v41_key_map(
                object(),
                "Weixin.exe",
                db_files,
                iterations=2,
                max_workers=2,
            )

        self.assertEqual(set(key_map), {item[3] for item in db_files})

    def test_extract_keys_uses_v41_fallback_when_raw_keys_are_absent(self):
        salt_hex = "11" * 16
        page = b"\x11" * 4096
        db_files = [
            ("message/message_1.db", "unused", 4096, salt_hex, page)
        ]
        recovered = {salt_hex: "22" * 32}

        class FakeKernel:
            @staticmethod
            def OpenProcess(access, inherit, pid):
                return object()

            @staticmethod
            def CloseHandle(handle):
                return 1

        logs = []
        with patch.object(scanner_windows, "kernel32", FakeKernel()), \
                patch.object(
                    scanner_windows,
                    "collect_db_files",
                    return_value=(db_files, {salt_hex: ["message/message_1.db"]}),
                ), patch.object(
                    scanner_windows, "_get_pids", return_value=[(123, 100)]
                ), patch.object(
                    scanner_windows, "_enum_regions", return_value=[]
                ), patch.object(
                    scanner_windows,
                    "_get_process_executable_path",
                    return_value="Weixin.exe",
                ), patch.object(
                    scanner_windows,
                    "_recover_v41_key_map",
                    return_value=recovered,
                ) as fallback, patch.object(
                    scanner_windows, "cross_verify_keys"
                ), patch.object(
                    scanner_windows,
                    "save_results",
                    side_effect=lambda db, salts, keys, output, print_fn: keys,
                ):
            result = scanner_windows.extract_keys(
                "db", "keys.json", print_fn=logs.append
            )

        fallback.assert_called_once()
        self.assertEqual(result, recovered)
        self.assertTrue(any("4.1+" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
