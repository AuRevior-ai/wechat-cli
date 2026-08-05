"""Per-user Windows named mutex for Launcher single-instance control."""

from __future__ import annotations

import ctypes
import hashlib
import os

_ERROR_ALREADY_EXISTS = 183


def default_launcher_mutex_name(user_sid: str) -> str:
    if not isinstance(user_sid, str) or not user_sid.strip():
        raise ValueError("user_sid is required")
    digest = hashlib.sha256(user_sid.strip().encode("utf-8")).hexdigest()[:24]
    return f"Local\\WeChatCliLauncher-{digest}"


class LauncherInstanceLock:
    def __init__(self, name: str) -> None:
        if os.name != "nt":
            raise OSError("Launcher named mutex is only available on Windows")
        if not isinstance(name, str) or not name.startswith("Local\\"):
            raise ValueError("launcher mutex must use the Local namespace")
        self.name = name
        self._handle = None
        self._owned = False

    def acquire(self) -> bool:
        if self._owned:
            return True
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, True, self.name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == _ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False
        self._handle = handle
        self._owned = True
        return True

    def release(self) -> None:
        if not self._handle:
            self._owned = False
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
        kernel32.ReleaseMutex.restype = ctypes.c_bool
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        handle = self._handle
        self._handle = None
        try:
            if self._owned and not kernel32.ReleaseMutex(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            self._owned = False
            kernel32.CloseHandle(handle)

    def __enter__(self) -> "LauncherInstanceLock":
        if not self.acquire():
            raise RuntimeError("another WeChat CLI Launcher instance is already running")
        return self

    def __exit__(self, *_args) -> None:
        self.release()

    def __del__(self) -> None:
        try:
            self.release()
        except Exception:
            pass
