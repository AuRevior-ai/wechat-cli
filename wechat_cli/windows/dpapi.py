"""Current-user Windows DPAPI wrapper and an explicit test-only protector."""

from __future__ import annotations

import ctypes
import hashlib
import os
import secrets
from typing import Protocol

from Crypto.Cipher import AES


class DataProtector(Protocol):
    def protect(self, data: bytes, *, entropy: bytes = b"") -> bytes: ...

    def unprotect(self, data: bytes, *, entropy: bytes = b"") -> bytes: ...


class WindowsDpapiProtector:
    """Encrypt data for the current Windows user with UI disabled."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self) -> None:
        if os.name != "nt":
            raise OSError("Windows DPAPI is only available on Windows")

    @staticmethod
    def _crypt(data: bytes, entropy: bytes, *, decrypt: bool) -> bytes:
        if not isinstance(data, bytes) or not isinstance(entropy, bytes):
            raise TypeError("DPAPI data and entropy must be bytes")
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        def make_blob(value: bytes):
            buffer = ctypes.create_string_buffer(value, max(1, len(value)))
            blob = DataBlob(
                len(value),
                ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
            )
            return blob, buffer

        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        blob_ptr = ctypes.POINTER(DataBlob)

        crypt32.CryptProtectData.argtypes = [
            blob_ptr,
            wintypes.LPCWSTR,
            blob_ptr,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            blob_ptr,
        ]
        crypt32.CryptProtectData.restype = wintypes.BOOL
        crypt32.CryptUnprotectData.argtypes = [
            blob_ptr,
            ctypes.POINTER(wintypes.LPWSTR),
            blob_ptr,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            blob_ptr,
        ]
        crypt32.CryptUnprotectData.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p

        input_blob, input_buffer = make_blob(data)
        entropy_blob = None
        entropy_buffer = None
        entropy_pointer = None
        if entropy:
            entropy_blob, entropy_buffer = make_blob(entropy)
            entropy_pointer = ctypes.byref(entropy_blob)
        output_blob = DataBlob()

        if decrypt:
            success = crypt32.CryptUnprotectData(
                ctypes.byref(input_blob),
                None,
                entropy_pointer,
                None,
                None,
                WindowsDpapiProtector._CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(output_blob),
            )
        else:
            success = crypt32.CryptProtectData(
                ctypes.byref(input_blob),
                "WeChat CLI local license state",
                entropy_pointer,
                None,
                None,
                WindowsDpapiProtector._CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(output_blob),
            )
        # Keep backing buffers alive through the native call.
        _ = input_buffer, entropy_buffer, entropy_blob
        if not success:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            if output_blob.pbData:
                kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))

    def protect(self, data: bytes, *, entropy: bytes = b"") -> bytes:
        return self._crypt(data, entropy, decrypt=False)

    def unprotect(self, data: bytes, *, entropy: bytes = b"") -> bytes:
        return self._crypt(data, entropy, decrypt=True)


class TestOnlyDataProtector:
    """Portable encrypted test backend that requires an explicit unsafe opt-in."""

    _PREFIX = b"WCTEST1"

    def __init__(
        self,
        key: bytes,
        *,
        allow_insecure_test_use: bool = False,
    ) -> None:
        if not allow_insecure_test_use:
            raise RuntimeError(
                "TestOnlyDataProtector requires allow_insecure_test_use=True"
            )
        if not isinstance(key, bytes) or not key:
            raise ValueError("test protector key must be non-empty bytes")
        self._key = hashlib.sha256(b"wechat-cli-test-protector\x00" + key).digest()

    def protect(self, data: bytes, *, entropy: bytes = b"") -> bytes:
        if not isinstance(data, bytes) or not isinstance(entropy, bytes):
            raise TypeError("test protector data and entropy must be bytes")
        nonce = secrets.token_bytes(12)
        cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce, mac_len=16)
        cipher.update(entropy)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        return self._PREFIX + nonce + tag + ciphertext

    def unprotect(self, data: bytes, *, entropy: bytes = b"") -> bytes:
        if not isinstance(data, bytes) or not isinstance(entropy, bytes):
            raise TypeError("test protector data and entropy must be bytes")
        minimum = len(self._PREFIX) + 12 + 16
        if len(data) < minimum or not data.startswith(self._PREFIX):
            raise OSError("test protected payload has an invalid format")
        offset = len(self._PREFIX)
        nonce = data[offset : offset + 12]
        tag = data[offset + 12 : offset + 28]
        ciphertext = data[offset + 28 :]
        cipher = AES.new(self._key, AES.MODE_GCM, nonce=nonce, mac_len=16)
        cipher.update(entropy)
        try:
            return cipher.decrypt_and_verify(ciphertext, tag)
        except ValueError as exc:
            raise OSError("test protected payload authentication failed") from exc
