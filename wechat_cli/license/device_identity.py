"""Privacy-preserving local device identity helpers for Windows activation."""

from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import re
import secrets
import unicodedata
from dataclasses import dataclass
from typing import Callable

_DEVICE_ID_RE = re.compile(r"^dev_[A-Za-z0-9_-]{8,128}$")
_FINGERPRINT_PROTOCOL = b"wechat-cli-device-fingerprint-v1"


def generate_device_id() -> str:
    return "dev_" + secrets.token_urlsafe(24)


def compute_device_fingerprint(
    machine_guid: str,
    user_sid: str,
    fingerprint_salt: str,
) -> str:
    values = (machine_guid, user_sid, fingerprint_salt)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise ValueError("machine GUID, user SID, and fingerprint salt are required")
    digest = hashlib.sha256()
    digest.update(_FINGERPRINT_PROTOCOL)
    for value in values:
        encoded = value.strip().encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def sanitize_device_name(value: str, *, max_length: int = 64) -> str:
    if max_length <= 0:
        raise ValueError("max_length must be positive")
    if not isinstance(value, str):
        value = str(value)
    normalized = unicodedata.normalize("NFKC", value)
    visible = "".join(
        " " if unicodedata.category(char).startswith("C") else char
        for char in normalized
    )
    collapsed = " ".join(visible.split())
    if not collapsed:
        collapsed = "Windows device"
    return collapsed[:max_length].rstrip() or "Windows device"


def read_machine_guid() -> str:
    if os.name != "nt":
        raise OSError("Windows MachineGuid is only available on Windows")
    import winreg

    access = winreg.KEY_READ
    access |= getattr(winreg, "KEY_WOW64_64KEY", 0)
    with winreg.OpenKey(
        winreg.HKEY_LOCAL_MACHINE,
        r"SOFTWARE\Microsoft\Cryptography",
        0,
        access,
    ) as key:
        value, value_type = winreg.QueryValueEx(key, "MachineGuid")
    if value_type not in {winreg.REG_SZ, winreg.REG_EXPAND_SZ}:
        raise OSError("MachineGuid has an unexpected registry type")
    if not isinstance(value, str) or not value.strip():
        raise OSError("MachineGuid is missing")
    return value.strip()


def read_current_user_sid() -> str:
    if os.name != "nt":
        raise OSError("Windows user SID is only available on Windows")

    from ctypes import wintypes

    token_query = 0x0008
    token_user_class = 1
    error_insufficient_buffer = 122

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [
            ("Sid", ctypes.c_void_p),
            ("Attributes", wintypes.DWORD),
        ]

    class TokenUser(ctypes.Structure):
        _fields_ = [("User", SidAndAttributes)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL

    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_uint,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL

    token = wintypes.HANDLE()
    if not advapi32.OpenProcessToken(
        kernel32.GetCurrentProcess(),
        token_query,
        ctypes.byref(token),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        required = wintypes.DWORD(0)
        advapi32.GetTokenInformation(
            token,
            token_user_class,
            None,
            0,
            ctypes.byref(required),
        )
        error = ctypes.get_last_error()
        if error != error_insufficient_buffer or required.value == 0:
            raise ctypes.WinError(error)
        buffer = ctypes.create_string_buffer(required.value)
        if not advapi32.GetTokenInformation(
            token,
            token_user_class,
            buffer,
            required,
            ctypes.byref(required),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        token_user = ctypes.cast(buffer, ctypes.POINTER(TokenUser)).contents
        sid_text = wintypes.LPWSTR()
        if not advapi32.ConvertSidToStringSidW(
            token_user.User.Sid,
            ctypes.byref(sid_text),
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            value = sid_text.value
        finally:
            kernel32.LocalFree(ctypes.cast(sid_text, wintypes.HLOCAL))
    finally:
        kernel32.CloseHandle(token)
    if not value:
        raise OSError("current Windows user SID is empty")
    return value


def read_computer_name() -> str:
    return os.environ.get("COMPUTERNAME") or platform.node() or "Windows device"


@dataclass(frozen=True)
class DeviceIdentity:
    device_id: str
    fingerprint: str
    display_name: str


@dataclass
class DeviceIdentityProvider:
    machine_guid_reader: Callable[[], str] = read_machine_guid
    user_sid_reader: Callable[[], str] = read_current_user_sid
    computer_name_reader: Callable[[], str] = read_computer_name

    def create(
        self,
        *,
        fingerprint_salt: str,
        existing_device_id: str | None = None,
    ) -> DeviceIdentity:
        device_id = existing_device_id or generate_device_id()
        if _DEVICE_ID_RE.fullmatch(device_id) is None:
            raise ValueError("device ID has an invalid format")
        fingerprint = compute_device_fingerprint(
            self.machine_guid_reader(),
            self.user_sid_reader(),
            fingerprint_salt,
        )
        return DeviceIdentity(
            device_id=device_id,
            fingerprint=fingerprint,
            display_name=sanitize_device_name(self.computer_name_reader()),
        )
