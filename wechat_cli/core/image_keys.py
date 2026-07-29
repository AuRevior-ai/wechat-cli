"""提取并验证微信 4.1 V2 图片的 AES/XOR 密钥。"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import re
import time
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
        return any(
            any(cipher.decrypt(block).startswith(magic) for magic in _IMAGE_MAGICS)
            for block in blocks
        )
    except (TypeError, ValueError):
        return False


def _matching_ciphertext_indexes(
    key: str | bytes,
    ciphertexts: Iterable[bytes],
) -> set[int]:
    key_bytes = key.encode("ascii") if isinstance(key, str) else bytes(key)
    if len(key_bytes) != 16:
        return set()
    try:
        cipher = AES.new(key_bytes, AES.MODE_ECB)
    except (TypeError, ValueError):
        return set()
    matches = set()
    for index, block in enumerate(ciphertexts):
        if len(block) != 16:
            continue
        clear = cipher.decrypt(bytes(block))
        if any(clear.startswith(magic) for magic in _IMAGE_MAGICS):
            matches.add(index)
    return matches


def scan_buffers_for_image_keys(
    buffers: Iterable[bytes],
    ciphertexts: Iterable[bytes],
) -> list[bytes]:
    templates = [bytes(block) for block in ciphertexts if len(block) == 16]
    missing = set(range(len(templates)))
    found = []
    seen = set()
    for buffer in buffers:
        for key in candidate_image_keys(buffer):
            if key in seen:
                continue
            seen.add(key)
            matches = _matching_ciphertext_indexes(key, templates)
            if not matches:
                continue
            found.append(key)
            missing.difference_update(matches)
            if not missing:
                return found
    return found


def scan_buffers_for_image_key(
    buffers: Iterable[bytes],
    ciphertexts: Iterable[bytes],
) -> bytes | None:
    keys = scan_buffers_for_image_keys(buffers, ciphertexts)
    return keys[0] if keys else None


def derive_image_xor_key(paths: Iterable[str | os.PathLike[str]]) -> int | None:
    keys = []
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
            first_key = tail[0] ^ 0xFF
            second_key = tail[1] ^ 0xD9
            if first_key == second_key:
                keys.append(first_key)
    if not keys:
        return None
    return Counter(keys).most_common(1)[0][0]


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


def _ciphertext_templates(
    paths: Iterable[Path],
    limit: int | None = None,
) -> list[bytes]:
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
            if limit is not None and len(templates) >= limit:
                break
    return templates


def _memory_scan_phases():
    return (
        ("可写内存", {0x04, 0x40}),
        ("其余可读内存", None),
    )


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


def scan_windows_image_keys(
    db_dir: str,
    *,
    pid: int | None = None,
    sample_paths: Iterable[str | os.PathLike[str]] | None = None,
    max_seconds: float = 30,
    progress=None,
) -> tuple[list[str], int] | None:
    if platform.system().lower() != "windows":
        return None
    from ..keys import scanner_windows as scanner

    emit = progress or (lambda _message: None)
    samples = (
        _valid_v2_samples(sample_paths)
        if sample_paths is not None
        else find_v2_image_samples(db_dir)
    )
    templates = _ciphertext_templates(samples)
    xor_key = derive_image_xor_key(find_v2_image_samples(db_dir))
    if not templates or xor_key is None:
        return None
    started = time.monotonic()
    missing = list(templates)
    found: list[str] = []
    pids = scanner._get_pids(emit) if pid is None else [(pid, 0)]
    for pid_value, _ in pids:
        if time.monotonic() - started >= max_seconds:
            break
        handle = scanner.kernel32.OpenProcess(
            0x0010 | 0x0400, False, pid_value
        )
        if not handle:
            continue
        try:
            regions = list(_windows_regions(handle))
            for phase_name, protection_filter in _memory_scan_phases():
                emit(f"正在扫描 Weixin.exe {phase_name}中的图片密钥")
                for base, size, protection in regions:
                    if time.monotonic() - started >= max_seconds:
                        break
                    if protection_filter is not None and protection not in protection_filter:
                        continue
                    if protection_filter is None and protection in {0x04, 0x40}:
                        continue
                    data = scanner._read_mem(handle, base, size)
                    if not data:
                        continue
                    keys = scan_buffers_for_image_keys([data], missing)
                    for key in keys:
                        matches = _matching_ciphertext_indexes(key, missing)
                        if not matches:
                            continue
                        value = key.decode("ascii")
                        if value not in found:
                            found.append(value)
                        missing = [
                            block
                            for index, block in enumerate(missing)
                            if index not in matches
                        ]
                    if not missing:
                        emit("[+] 已验证微信 V2 图片密钥")
                        return found, xor_key
        finally:
            scanner.kernel32.CloseHandle(handle)
    if found:
        emit(f"[+] 已验证 {len(found)} 个微信 V2 图片密钥")
        return found, xor_key
    return None


def scan_windows_image_key(
    db_dir: str,
    *,
    pid: int | None = None,
    progress=None,
) -> tuple[str, int] | None:
    """Backward-compatible one-key facade."""
    result = scan_windows_image_keys(
        db_dir,
        pid=pid,
        progress=progress,
    )
    if result is None:
        return None
    keys, xor_key = result
    return keys[0], xor_key


def _valid_v2_samples(
    paths: Iterable[str | os.PathLike[str]],
) -> list[Path]:
    samples = []
    seen = set()
    for raw_path in paths:
        path = Path(raw_path)
        try:
            resolved = path.resolve()
            if resolved in seen or resolved.stat().st_size < 31:
                continue
            with resolved.open("rb") as source:
                if source.read(6) != V2_MAGIC:
                    continue
        except OSError:
            continue
        seen.add(resolved)
        samples.append(resolved)
    return samples


def ensure_image_keys(
    config: dict,
    *,
    config_path: str | os.PathLike[str] | None = None,
    sample_paths: Iterable[str | os.PathLike[str]] | None = None,
    progress=None,
) -> tuple[str | list[str], int] | None:
    """复用仍有效的密钥，否则从正在运行的微信提取并原子保存。"""
    db_dir = config.get("db_dir") or ""
    samples = (
        _valid_v2_samples(sample_paths)
        if sample_paths is not None
        else find_v2_image_samples(db_dir)
    )
    if not samples:
        return None
    templates = _ciphertext_templates(samples)
    existing_values = config.get("image_aes_keys") or []
    if not isinstance(existing_values, list):
        existing_values = []
    legacy = config.get("image_aes_key")
    if legacy:
        existing_values = [legacy, *existing_values]
    existing_values = list(dict.fromkeys(
        str(value) for value in existing_values if value
    ))
    xor_key = config.get("image_xor_key")
    valid_existing = [
        key for key in existing_values
        if validate_image_aes_key(key, templates)
    ]
    missing = [
        block for block in templates
        if not any(validate_image_aes_key(key, [block]) for key in valid_existing)
    ]
    if not isinstance(xor_key, int):
        xor_key = derive_image_xor_key(find_v2_image_samples(db_dir))
    discovered = []
    if missing:
        result = scan_windows_image_keys(
            db_dir,
            sample_paths=samples,
            progress=progress,
        )
        if result is not None:
            discovered, xor_key = result
    aes_keys = list(dict.fromkeys([
        *existing_values,
        *discovered,
    ]))
    usable = [
        key for key in aes_keys
        if validate_image_aes_key(key, templates)
    ]
    if not usable or not isinstance(xor_key, int):
        return None
    config["image_aes_key"] = usable[-1]
    config["image_aes_keys"] = aes_keys
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
    return (usable[0] if len(usable) == 1 else usable), xor_key
