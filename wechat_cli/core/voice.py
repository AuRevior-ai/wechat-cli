"""读取微信语音分库并将 SILK_V3 解码为标准 WAV。"""

from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
import wave
import xml.etree.ElementTree as ET
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

from .key_utils import key_path_variants


_UNSAFE_XML_RE = re.compile(r"<!DOCTYPE|<!ENTITY", re.IGNORECASE)


@dataclass(frozen=True)
class VoiceRecord:
    data: bytes
    local_id: int
    create_time: int
    svr_id: int
    media_db: str
    chunks: int = 1


def find_media_db_keys(all_keys) -> list[str]:
    matches = []
    seen = set()
    for key in all_keys:
        variants = key_path_variants(key)
        matched = next(
            (
                value
                for value in variants
                if re.search(r"(?:^|/)message/media_\d+\.db$", value.replace("\\", "/"), re.IGNORECASE)
            ),
            None,
        )
        if matched is None:
            continue
        normalized = matched.replace("\\", "/").lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        matches.append(key)
    return sorted(
        matches,
        key=lambda value: int(
            re.search(r"media_(\d+)\.db$", value.replace("\\", "/"), re.IGNORECASE).group(1)
        ),
    )


def decrypted_media_db_paths(all_keys, cache) -> list[tuple[str, str]]:
    paths = []
    for key in find_media_db_keys(all_keys):
        path = cache.get(key)
        if path:
            paths.append((key.replace("\\", "/"), path))
    return paths


def _readonly_connection(path: Path):
    return sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)


def find_voice_record(
    media_db_paths: Iterable[
        str | os.PathLike[str] | tuple[str, str | os.PathLike[str]]
    ],
    chat_username: str,
    local_id: int,
    create_time: int,
    *,
    max_time_delta: int = 300,
) -> VoiceRecord | None:
    """用会话稳定 ID 和 local_id 从解密后的 media_N.db 读取语音。"""
    if not chat_username:
        return None
    for raw_entry in media_db_paths:
        if isinstance(raw_entry, tuple):
            logical_name, raw_path = raw_entry
        else:
            raw_path = raw_entry
            logical_name = Path(raw_path).name
        path = Path(raw_path)
        try:
            with closing(_readonly_connection(path)) as conn:
                rows = conn.execute(
                    """SELECT v.voice_data, v.local_id, v.create_time, v.svr_id,
                              COALESCE(v.data_index, 0)
                       FROM VoiceInfo AS v
                       JOIN Name2Id AS n ON n.rowid = v.chat_name_id
                       WHERE n.user_name = ? AND v.local_id = ?
                       ORDER BY COALESCE(v.data_index, 0)""",
                    (chat_username, int(local_id)),
                ).fetchall()
        except (OSError, sqlite3.Error):
            continue
        if not rows:
            continue
        row_time = int(rows[0][2] or 0)
        if create_time and row_time and abs(row_time - int(create_time)) > max_time_delta:
            continue
        chunks = [bytes(row[0]) for row in rows if row[0]]
        if not chunks:
            continue
        return VoiceRecord(
            data=b"".join(chunks),
            local_id=int(rows[0][1]),
            create_time=row_time,
            svr_id=int(rows[0][3] or 0),
            media_db=Path(logical_name).name,
            chunks=len(chunks),
        )
    return None


def voice_duration_seconds(content: str | None) -> float | None:
    if not content or _UNSAFE_XML_RE.search(content) or len(content) > 20000:
        return None
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    node = root if root.tag == "voicemsg" else root.find(".//voicemsg")
    if node is None:
        return None
    try:
        milliseconds = int(node.attrib.get("voicelength") or 0)
    except (TypeError, ValueError):
        return None
    return milliseconds / 1000 if milliseconds > 0 else None


def bundled_binary(name: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "wechat_cli" / "bin" / name
    return Path(__file__).resolve().parent.parent / "bin" / name


def write_pcm_wav(
    output_path: str | os.PathLike[str],
    pcm_bytes: bytes,
    *,
    sample_rate: int = 16000,
) -> Path:
    if len(pcm_bytes) % 2:
        raise ValueError("PCM 数据长度必须是 16-bit 采样的整数倍")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(pcm_bytes)
    return target


def decode_silk_to_wav(
    silk_bytes: bytes,
    output_path: str | os.PathLike[str],
    *,
    decoder_path: str | os.PathLike[str] | None = None,
) -> Path:
    if not silk_bytes:
        raise ValueError("语音数据为空")
    decoder = Path(decoder_path) if decoder_path else bundled_binary("silk_v3_decoder.exe")
    if not decoder.is_file():
        raise FileNotFoundError(f"缺少 SILK 解码器: {decoder}")
    with TemporaryDirectory(prefix="wechat-cli-voice-") as folder:
        silk_path = Path(folder) / "input.silk"
        pcm_path = Path(folder) / "output.pcm"
        silk_path.write_bytes(silk_bytes)
        subprocess.run(
            [
                str(decoder),
                str(silk_path),
                str(pcm_path),
                "-Fs_API",
                "16000",
                "-quiet",
            ],
            check=True,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=120,
        )
        if not pcm_path.is_file() or pcm_path.stat().st_size == 0:
            raise RuntimeError("SILK 解码器没有生成音频")
        return write_pcm_wav(output_path, pcm_path.read_bytes())
