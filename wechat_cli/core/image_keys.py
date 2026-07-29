"""提取并验证微信 4.1 V2 图片的 AES/XOR 密钥。"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

from Crypto.Cipher import AES

from .config import CONFIG_FILE


V2_MAGIC = b"\x07\x08V2\x08\x07"
_IMAGE_MAGICS = (
    b"\xff\xd8\xff",
    b"\x89PNG",
    b"GIF",
    b"RIFF",
    b"wxgf",
    b"BM",
    b"II*\x00",
)
_KEY32_RE = re.compile(rb"(?<![A-Za-z0-9])[A-Za-z0-9]{32}(?![A-Za-z0-9])")
_KEY16_RE = re.compile(rb"(?<![A-Za-z0-9])[A-Za-z0-9]{16}(?![A-Za-z0-9])")


def candidate_image_keys(region: bytes):
    for match in _KEY32_RE.finditer(region):
        yield match.group(0)[:16]
    for match in _KEY16_RE.finditer(region):
        yield match.group(0)


def validate_image_aes_key(
    key: str | bytes,
    ciphertexts: Iterable[bytes],
) -> bool:
    key_bytes = key.encode("ascii") if isinstance(key, str) else bytes(key)
    if len(key_bytes) != 16:
        return False
    blocks = [bytes(block) for block in ciphertexts if len(block) == 16]
    if not blocks:
        return False
    try:
        cipher = AES.new(key_bytes, AES.MODE_ECB)
        return all(
            any(cipher.decrypt(block).startswith(magic) for magic in _IMAGE_MAGICS)
            for block in blocks
        )
    except (TypeError, ValueError):
        return False


def scan_buffers_for_image_key(
    buffers: Iterable[bytes],
    ciphertexts: Iterable[bytes],
) -> bytes | None:
    templates = list(ciphertexts)
    for buffer in buffers:
        for key in candidate_image_keys(buffer):
            if validate_image_aes_key(key, templates):
                return key
    return None


def derive_image_xor_key(paths: Iterable[str | os.PathLike[str]]) -> int | None:
    pairs = []
    for raw_path in paths:
        path = Path(raw_path)
        try:
            with path.open("rb") as source:
                if source.read(6) != V2_MAGIC:
                    continue
                source.seek(-2, os.SEEK_END)
                tail = source.read(2)
        except OSError:
            continue
        if len(tail) == 2:
            pairs.append((tail[0], tail[1]))
    if not pairs:
        return None
    first, second = Counter(pairs).most_common(1)[0][0]
    key = first ^ 0xFF
    if second ^ 0xD9 != key:
        return key
    return key


def find_v2_image_samples(
    db_dir: str | os.PathLike[str],
    *,
    limit: int = 32,
) -> list[Path]:
    base = Path(db_dir)
    if base.name.lower() == "db_storage":
        base = base.parent
    attach = base / "msg" / "attach"
    if not attach.is_dir():
        return []
    thumbnails = list(attach.glob("*/*/Img/*_t.dat"))
    candidates = thumbnails or list(attach.glob("*/*/Img/*.dat"))
    valid = []
    for path in candidates:
        try:
            if path.stat().st_size >= 31 and path.read_bytes()[:6] == V2_MAGIC:
                valid.append(path)
        except OSError:
            continue
    valid.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return valid[:limit]


def _ciphertext_templates(paths: Iterable[Path], limit: int = 4) -> list[bytes]:
    templates = []
    seen = set()
    for path in paths:
        try:
            with path.open("rb") as source:
                source.seek(15)
                block = source.read(16)
        except OSError:
            continue
        if len(block) == 16 and block not in seen:
            seen.add(block)
            templates.append(block)
            if len(templates) >= limit:
                break
    return templates


def _windows_regions(handle):
    from ..keys import scanner_windows as scanner

    addr = 0
    mbi = scanner.MBI()
    while addr < 0x7FFFFFFFFFFF:
        if scanner.kernel32.VirtualQueryEx(
            handle,
            ctypes.c_uint64(addr),
            ctypes.byref(mbi),
            ctypes.sizeof(mbi),
        ) == 0:
            break
        protect = int(mbi.Protect)
        base_protect = protect & 0xFF
        if (
            mbi.State == scanner.MEM_COMMIT
            and base_protect in scanner.READABLE
            and not (protect & 0x100)
            and 0 < mbi.RegionSize <= 50 * 1024 * 1024
        ):
            yield int(mbi.BaseAddress), int(mbi.RegionSize), base_protect
        next_addr = int(mbi.BaseAddress + mbi.RegionSize)
        if next_addr <= addr:
            break
        addr = next_addr


def scan_windows_image_key(
    db_dir: str,
    *,
    pid: int | None = None,
    progress=None,
) -> tuple[str, int] | None:
    if platform.system().lower() != "windows":
        return None
    from ..keys import scanner_windows as scanner

    emit = progress or (lambda _message: None)
    samples = find_v2_image_samples(db_dir)
    templates = _ciphertext_templates(samples)
    xor_key = derive_image_xor_key(samples)
    if not templates or xor_key is None:
        return None
    pids = scanner._get_pids(emit) if pid is None else [(pid, 0)]
    for pid_value, _ in pids:
        handle = scanner.kernel32.OpenProcess(
            0x0010 | 0x0400, False, pid_value
        )
        if not handle:
            continue
        try:
            regions = list(_windows_regions(handle))
            phases = (
                ("可写内存", {0x04, 0x40}),
                ("其余可读内存", None),
            )
            for phase_name, protection_filter in phases:
                emit(f"正在扫描 Weixin.exe {phase_name}中的图片密钥")
                for base, size, protection in regions:
                    if protection_filter is not None and protection not in protection_filter:
                        continue
                    if protection_filter is None and protection in {0x04, 0x40}:
                        continue
                    data = scanner._read_mem(handle, base, size)
                    if not data:
                        continue
                    key = scan_buffers_for_image_key([data], templates)
                    if key is not None:
                        emit("[+] 已验证微信 V2 图片密钥")
                        return key.decode("ascii"), xor_key
        finally:
            scanner.kernel32.CloseHandle(handle)
    return None


def ensure_image_keys(
    config: dict,
    *,
    config_path: str | os.PathLike[str] | None = None,
    progress=None,
) -> tuple[str, int] | None:
    """复用仍有效的密钥，否则从正在运行的微信提取并原子保存。"""
    db_dir = config.get("db_dir") or ""
    samples = find_v2_image_samples(db_dir)
    if not samples:
        return None
    templates = _ciphertext_templates(samples)
    existing = config.get("image_aes_key")
    xor_key = config.get("image_xor_key")
    if existing and validate_image_aes_key(existing, templates):
        if not isinstance(xor_key, int):
            xor_key = derive_image_xor_key(samples)
        if isinstance(xor_key, int):
            return str(existing), xor_key

    result = scan_windows_image_key(db_dir, progress=progress)
    if result is None:
        return None
    aes_key, xor_key = result
    config["image_aes_key"] = aes_key
    config["image_xor_key"] = xor_key
    path = Path(config_path or CONFIG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
    return result
