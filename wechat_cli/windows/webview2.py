"""Detect and install the Microsoft Evergreen WebView2 Runtime on Windows."""

from __future__ import annotations

import os
import platform
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol
from urllib.request import Request, urlopen

WEBVIEW2_PRODUCT_ID = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_BOOTSTRAPPER_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
_VERSION_RE = re.compile(r"^\d+(?:\.\d+){3}$")


@dataclass(frozen=True)
class WebView2Runtime:
    version: str
    scope: str

    def __post_init__(self) -> None:
        if _VERSION_RE.fullmatch(self.version) is None:
            raise ValueError("WebView2 Runtime version must contain four numeric parts")
        if self.version == "0.0.0.0":
            raise ValueError("0.0.0.0 does not represent an installed Runtime")
        if self.scope not in {"local_machine", "current_user"}:
            raise ValueError("WebView2 Runtime scope is invalid")

    @property
    def version_tuple(self) -> tuple[int, int, int, int]:
        return tuple(int(part) for part in self.version.split("."))  # type: ignore[return-value]


class RegistryLike(Protocol):
    HKEY_LOCAL_MACHINE: object
    HKEY_CURRENT_USER: object
    KEY_READ: int
    KEY_WOW64_64KEY: int
    REG_SZ: int
    REG_EXPAND_SZ: int

    def OpenKey(self, root, path: str, reserved: int, access: int): ...

    def QueryValueEx(self, key, name: str): ...


def _registry_candidates(registry: RegistryLike, is_64bit_windows: bool):
    machine_prefix = (
        r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients"
        if is_64bit_windows
        else r"SOFTWARE\Microsoft\EdgeUpdate\Clients"
    )
    return (
        (
            registry.HKEY_LOCAL_MACHINE,
            machine_prefix + "\\" + WEBVIEW2_PRODUCT_ID,
            "local_machine",
        ),
        (
            registry.HKEY_CURRENT_USER,
            r"Software\Microsoft\EdgeUpdate\Clients" + "\\" + WEBVIEW2_PRODUCT_ID,
            "current_user",
        ),
    )


def _parse_runtime(value, value_type: int, registry: RegistryLike, scope: str):
    if value_type not in {registry.REG_SZ, registry.REG_EXPAND_SZ}:
        return None
    if not isinstance(value, str):
        return None
    version = value.strip()
    if not version or version == "0.0.0.0" or _VERSION_RE.fullmatch(version) is None:
        return None
    try:
        return WebView2Runtime(version, scope)
    except ValueError:
        return None


def detect_webview2_runtime(
    *,
    registry: RegistryLike | None = None,
    is_64bit_windows: bool | None = None,
) -> WebView2Runtime | None:
    """Return the highest installed Evergreen Runtime from official pv keys."""

    if registry is None:
        if os.name != "nt":
            return None
        import winreg as registry_module

        registry = registry_module
    if is_64bit_windows is None:
        is_64bit_windows = platform.machine().endswith("64") or bool(
            os.environ.get("PROGRAMFILES(X86)")
        )

    runtimes: list[WebView2Runtime] = []
    access = registry.KEY_READ
    if is_64bit_windows:
        access |= getattr(registry, "KEY_WOW64_64KEY", 0)
    for root, path, scope in _registry_candidates(registry, is_64bit_windows):
        try:
            with registry.OpenKey(root, path, 0, access) as key:
                value, value_type = registry.QueryValueEx(key, "pv")
        except (FileNotFoundError, OSError):
            continue
        runtime = _parse_runtime(value, value_type, registry, scope)
        if runtime is not None:
            runtimes.append(runtime)
    if not runtimes:
        return None
    return max(runtimes, key=lambda item: item.version_tuple)


def download_webview2_bootstrapper(
    url: str,
    destination: str | Path,
    *,
    timeout_seconds: float = 60.0,
) -> None:
    if url != WEBVIEW2_BOOTSTRAPPER_URL:
        raise ValueError("WebView2 bootstrapper must use the approved Microsoft URL")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": "WeChatCliLauncher/0.1",
        },
    )
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as output:
            temporary = Path(output.name)
            with urlopen(request, timeout=timeout_seconds) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if temporary.stat().st_size == 0:
            raise RuntimeError("Microsoft WebView2 bootstrapper download was empty")
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def install_webview2_runtime(
    *,
    cache_dir: str | Path,
    detector: Callable[[], WebView2Runtime | None] = detect_webview2_runtime,
    downloader: Callable[[str, str | Path], None] = download_webview2_bootstrapper,
    runner: Callable[..., object] = subprocess.run,
) -> WebView2Runtime:
    """Ensure the Evergreen Runtime exists, downloading Microsoft's bootstrapper."""

    existing = detector()
    if existing is not None:
        return existing
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    bootstrapper = cache / "MicrosoftEdgeWebview2Setup.exe"
    downloader(WEBVIEW2_BOOTSTRAPPER_URL, bootstrapper)
    if not bootstrapper.is_file() or bootstrapper.stat().st_size == 0:
        raise RuntimeError("Microsoft WebView2 bootstrapper was not downloaded")
    runner(
        [str(bootstrapper), "/silent", "/install"],
        shell=False,
        check=True,
    )
    installed = detector()
    if installed is None:
        raise RuntimeError("WebView2 安装程序已运行，但仍未检测到 Runtime")
    return installed
