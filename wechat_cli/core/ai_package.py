"""把聊天记录、媒体和语音转写整理为可交给 AI 的 ZIP。"""

from __future__ import annotations

import copy
import hashlib
import json
import mimetypes
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import urlparse, urlunparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import ZIP_DEFLATED, ZipFile

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

from .asr import OfflineAsrManager
from .forwarded import format_forwarded_text
from .media import image_content_type, read_media_file_payload
from .voice import decode_silk_to_wav, find_voice_record


REMOTE_IMAGE_MAX_BYTES = 20 * 1024 * 1024
_ALLOWED_IMAGE_HOSTS = (
    "tc.qq.com",
    "qpic.cn",
    "qlogo.cn",
    "weixin.qq.com",
)
_TYPE_LABELS = {
    "text": "文字",
    "image": "图片",
    "voice": "语音",
    "video": "视频",
    "sticker": "表情",
    "location": "位置",
    "link": "链接",
    "file": "文件",
    "call": "通话",
    "system": "系统",
    "forwarded": "合并转发",
}
_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/avif": ".avif",
    "image/svg+xml; charset=utf-8": ".svg",
    "image/x-wechat-wxgf": ".wxgf",
    "audio/wav": ".wav",
}


def _validate_remote_image_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in _ALLOWED_IMAGE_HOSTS
    )
    if parsed.scheme not in {"http", "https"} or not allowed:
        raise PermissionError("表情素材不是允许的微信官方图片地址")
    if parsed.scheme == "http" and not (
        host == "tc.qq.com" or host.endswith(".tc.qq.com")
    ):
        raise PermissionError("该微信图片地址必须使用 HTTPS")
    if parsed.username or parsed.password or parsed.port not in {None, 80, 443}:
        raise PermissionError("表情素材地址包含不允许的连接信息")
    return urlunparse(parsed)


class _WechatImageRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validated = _validate_remote_image_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, validated)


def download_remote_image(url: str) -> tuple[bytes, str]:
    validated = _validate_remote_image_url(url)
    opener = build_opener(_WechatImageRedirectHandler())
    request = Request(
        validated,
        headers={"Accept": "image/*", "User-Agent": "wechat-cli/0.4"},
    )
    with opener.open(request, timeout=20) as response:
        _validate_remote_image_url(response.geturl())
        declared = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        if declared and not (
            declared.startswith("image/") or declared == "application/octet-stream"
        ):
            raise ValueError("微信表情地址返回的不是图片")
        declared_size = response.headers.get("Content-Length")
        if declared_size and declared_size.isdigit():
            if int(declared_size) > REMOTE_IMAGE_MAX_BYTES:
                raise ValueError("微信表情图片超过 20 MiB 安全限制")
        raw = response.read(REMOTE_IMAGE_MAX_BYTES + 1)
    if len(raw) > REMOTE_IMAGE_MAX_BYTES:
        raise ValueError("微信表情图片超过 20 MiB 安全限制")
    detected = image_content_type(raw, "")
    if not detected:
        raise ValueError("微信表情内容无法识别为图片")
    return raw, detected


def _decode_cached_sticker(
    raw: bytes,
    filename: str,
    aes_key: str = "",
) -> tuple[bytes, str] | None:
    detected = image_content_type(raw, filename)
    if detected:
        return raw, detected
    if (
        len(raw) % 16
        or not re.fullmatch(r"[0-9A-Fa-f]{32}", aes_key or "")
    ):
        return None
    try:
        clear = AES.new(bytes.fromhex(aes_key), AES.MODE_ECB).decrypt(raw)
        try:
            clear = unpad(clear, AES.block_size)
        except ValueError:
            pass
    except (ValueError, TypeError):
        return None
    detected = image_content_type(clear, filename)
    return (clear, detected) if detected else None


def _find_local_sticker(
    db_dir: str,
    md5: str,
    aes_key: str = "",
) -> tuple[bytes, str] | None:
    if not db_dir or not re.fullmatch(r"[0-9A-Fa-f]{32}", md5 or ""):
        return None
    account_root = Path(db_dir).resolve().parent
    cache_root = account_root / "cache"
    if not cache_root.is_dir():
        return None
    for target in cache_root.glob(
        f"*/Emoticon/{md5[:2].lower()}/{md5.lower()}*"
    ):
        try:
            resolved = target.resolve()
            if (
                resolved.parent.parent.parent.parent != cache_root.resolve()
                or not resolved.is_file()
                or resolved.stat().st_size > REMOTE_IMAGE_MAX_BYTES
            ):
                continue
            decoded = _decode_cached_sticker(
                resolved.read_bytes(),
                resolved.name,
                aes_key,
            )
            if decoded:
                return decoded
        except OSError:
            continue
    return None


def _safe_error(exc: Exception, source: str = "") -> str:
    text = str(exc).strip() or exc.__class__.__name__
    if source:
        text = text.replace(source, Path(source).name)
    text = re.sub(r"[A-Za-z]:\\[^\r\n；;]+", "<本地路径>", text)
    return text[:500]


def _extension(content_type: str, filename: str = "") -> str:
    if content_type in _EXTENSIONS:
        return _EXTENSIONS[content_type]
    suffix = Path(filename).suffix
    if suffix and re.fullmatch(r"\.[A-Za-z0-9]{1,10}", suffix):
        return suffix.lower()
    guessed = mimetypes.guess_extension(content_type or "")
    return guessed or ".bin"


def _safe_asset_filename(
    item: dict[str, Any],
    kind: str,
    digest: str,
    extension: str,
) -> str:
    try:
        stamp = datetime.fromtimestamp(int(item.get("timestamp") or 0)).strftime(
            "%Y%m%d-%H%M%S"
        )
    except (OSError, OverflowError, TypeError, ValueError):
        stamp = "unknown-time"
    message_id = re.sub(r"[^0-9A-Za-z_-]", "_", str(item.get("id") or "unknown"))
    safe_kind = re.sub(r"[^0-9A-Za-z_-]", "_", kind or "media")
    return f"{stamp}-{message_id}-{safe_kind}-{digest[:10]}{extension}"


def _local_ai_media_payload(
    source: str,
    *,
    kind: str,
    db_dir: str,
    image_aes_key=None,
    image_xor_key=None,
) -> dict[str, Any]:
    payload = read_media_file_payload(
        source,
        db_dir=db_dir,
        image_aes_key=image_aes_key,
        image_xor_key=image_xor_key,
    )
    unsupported_preview = {
        "image/svg+xml; charset=utf-8",
        "image/x-wechat-wxgf",
    }
    if kind != "image" or payload["content_type"] not in unsupported_preview:
        return payload
    path = Path(source)
    stem = re.sub(r"_(?:t|h)$", "", path.stem, flags=re.IGNORECASE)
    thumbnail = path.with_name(f"{stem}_t.dat")
    if not thumbnail.is_file() or thumbnail == path:
        raise RuntimeError("微信 V2 图片密钥不可用，无法读取真实图片")
    fallback = read_media_file_payload(
        str(thumbnail),
        db_dir=db_dir,
        image_aes_key=image_aes_key,
        image_xor_key=image_xor_key,
    )
    if fallback["content_type"] in unsupported_preview:
        raise RuntimeError("微信 V2 图片密钥不可用，无法读取真实图片")
    return fallback


def _clean_message_text(item: dict[str, Any]) -> str:
    kind = item.get("type") or ""
    text = str(item.get("text") or "").strip()
    if kind == "image":
        return "[图片]"
    if kind == "sticker":
        return "[表情]"
    if kind == "video":
        return "[视频]"
    if kind == "file":
        return text.splitlines()[0] if text else "[文件]"
    if kind == "forwarded" and item.get("forwarded"):
        return format_forwarded_text(item["forwarded"])
    return text or f"[{_TYPE_LABELS.get(kind, kind or '消息')}]"


def _manifest_message(item: dict[str, Any]) -> dict[str, Any]:
    message = {
        "id": item.get("id"),
        "timestamp": item.get("timestamp"),
        "time": item.get("time") or "",
        "sender": item.get("sender") or ("我" if item.get("is_self") else ""),
        "sender_username": item.get("sender_username") or "",
        "is_self": bool(item.get("is_self")),
        "type": item.get("type") or "",
        "type_label": _TYPE_LABELS.get(
            item.get("type") or "",
            item.get("type_label") or item.get("type") or "消息",
        ),
        "text": _clean_message_text(item),
    }
    if item.get("asset_path"):
        message["asset_path"] = item["asset_path"]
    if item.get("transcript"):
        message["transcript"] = item["transcript"]
        message["transcript_source"] = "machine_offline_asr"
    if item.get("forwarded"):
        message["forwarded"] = copy.deepcopy(item["forwarded"])
    return message


def _message_line(item: dict[str, Any]) -> str:
    sender = item.get("sender") or ("我" if item.get("is_self") else "未知发送者")
    if sender == "me":
        sender = "我"
    label = _TYPE_LABELS.get(
        item.get("type") or "",
        item.get("type_label") or item.get("type") or "消息",
    )
    lines = [
        f"[{item.get('time') or '时间未知'}] {sender}（{label}）：{_clean_message_text(item)}"
    ]
    if item.get("transcript"):
        lines.append(f"  语音转文字（机器识别）：{item['transcript']}")
    if item.get("asset_path"):
        lines.append(f"  素材：{item['asset_path']}")
    return "\n".join(lines)


def format_key_copy_text(
    chat: dict[str, Any],
    messages: list[dict[str, Any]],
    start_time: str = "",
    end_time: str = "",
) -> str:
    lines = [
        f"会话：{chat.get('display_name') or chat.get('username') or '未知会话'}",
        f"日期：{start_time or '最早'} 至 {end_time or '最新'}",
        f"消息数量：{len(messages)}",
        "素材说明：正文中的“素材/文件名”位于同名 AI 资料包内。",
        "",
    ]
    lines.extend(_message_line(item) for item in messages)
    return "\n".join(lines)


def format_copy_text(
    chat: dict[str, Any],
    messages: list[dict[str, Any]],
    start_time: str = "",
    end_time: str = "",
) -> str:
    prompt = [
        "请总结下面这段微信聊天记录，并结合随附 AI 资料包中“素材/”目录的图片、表情和音频：",
        "1. 核心主题与明确结论",
        "2. 已确认的决定、承诺和分工",
        "3. 待办事项（负责人、截止时间、下一步）",
        "4. 重要数字、日期、链接、图片信息和风险",
        "5. 尚未解决的问题",
        "",
        "—— 聊天记录开始 ——",
        format_key_copy_text(chat, messages, start_time, end_time),
        "—— 聊天记录结束 ——",
    ]
    return "\n".join(prompt)


@dataclass
class AiPackageResult:
    path: str
    chat: str
    username: str
    message_count: int
    assets: list[dict[str, Any]]
    transcription_count: int
    failures: list[dict[str, Any]]
    messages: list[dict[str, Any]]
    copy_text: str
    key_copy_text: str

    @property
    def asset_count(self) -> int:
        return len(self.assets)

    def to_dict(self, *, include_messages: bool = False) -> dict[str, Any]:
        payload = {
            "path": self.path,
            "chat": self.chat,
            "username": self.username,
            "message_count": self.message_count,
            "asset_count": self.asset_count,
            "transcription_count": self.transcription_count,
            "failures": self.failures or None,
        }
        if include_messages:
            payload.update({
                "messages": self.messages,
                "copy_text": self.copy_text,
                "key_copy_text": self.key_copy_text,
            })
        return payload


def build_ai_package(
    chat: dict[str, Any],
    items: list[dict[str, Any]],
    output_path: str | os.PathLike[str],
    *,
    db_dir: str = "",
    media_db_paths=None,
    start_time: str = "",
    end_time: str = "",
    transcribe_voice: bool = True,
    initial_failures: list[dict[str, Any]] | None = None,
    image_aes_key=None,
    image_xor_key=None,
    remote_image_loader: Callable[[str], tuple[bytes, str]] = download_remote_image,
    voice_finder: Callable = find_voice_record,
    voice_decoder: Callable = decode_silk_to_wav,
    transcriber: Callable[[str | os.PathLike[str]], str] | None = None,
    progress: Callable[[str], None] | None = None,
) -> AiPackageResult:
    """生成 AI 资料包；单个素材失败只进入清单，不终止整个包。"""
    progress = progress or (lambda _message: None)
    target = Path(output_path)
    if target.exists() and target.is_dir():
        raise IsADirectoryError(str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{secrets.token_hex(4)}.part")
    messages = copy.deepcopy(items)
    assets: list[dict[str, Any]] = []
    asset_by_hash: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = copy.deepcopy(initial_failures or [])
    transcription_count = 0
    asr_manager = None

    def record_failure(item, phase, exc, source=""):
        failures.append({
            "message_id": item.get("id"),
            "time": item.get("time") or "",
            "type": item.get("type") or "",
            "phase": phase,
            "error": _safe_error(exc, source),
        })

    try:
        with TemporaryDirectory(prefix="wechat-cli-ai-package-") as work:
            work_dir = Path(work)
            with ZipFile(
                temporary,
                "w",
                compression=ZIP_DEFLATED,
                allowZip64=True,
            ) as archive:
                def add_asset(item, raw, kind, content_type, filename=""):
                    digest = hashlib.sha256(raw).hexdigest()
                    existing = asset_by_hash.get(digest)
                    if existing is not None:
                        if item.get("id") not in existing["message_ids"]:
                            existing["message_ids"].append(item.get("id"))
                        item["asset_path"] = existing["path"]
                        return existing["path"]
                    extension = _extension(content_type, filename)
                    name = _safe_asset_filename(item, kind, digest, extension)
                    relative = f"素材/{name}"
                    archive.writestr(relative, raw)
                    metadata = {
                        "path": relative,
                        "kind": kind,
                        "sha256": digest,
                        "bytes": len(raw),
                        "content_type": content_type,
                        "message_ids": [item.get("id")],
                    }
                    assets.append(metadata)
                    asset_by_hash[digest] = metadata
                    item["asset_path"] = relative
                    return relative

                def materialize_forwarded_items(
                    forwarded_items,
                    parent_item,
                    lineage="forward",
                ):
                    nonlocal asr_manager, transcription_count
                    for nested_index, nested in enumerate(forwarded_items or [], 1):
                        nested_kind = nested.get("kind") or ""
                        media = nested.get("media") or {}
                        nested_id = (
                            media.get("data_id")
                            or media.get("source_local_id")
                            or f"{lineage}-{nested_index}"
                        )
                        proxy = {
                            "id": f"{parent_item.get('id')}-{nested_id}",
                            "timestamp": (
                                media.get("source_create_time")
                                or parent_item.get("timestamp")
                                or 0
                            ),
                            "time": nested.get("time") or parent_item.get("time") or "",
                            "type": nested_kind,
                        }
                        try:
                            if nested_kind in {"image", "file", "video"}:
                                if media.get("path"):
                                    payload = _local_ai_media_payload(
                                        str(media["path"]),
                                        kind=nested_kind,
                                        db_dir=db_dir,
                                        image_aes_key=image_aes_key,
                                        image_xor_key=image_xor_key,
                                    )
                                    add_asset(
                                        proxy,
                                        payload["body"],
                                        f"forwarded_{nested_kind}",
                                        payload["content_type"],
                                        media.get("filename") or payload["filename"],
                                    )
                                elif nested_kind == "image" and media.get("url"):
                                    raw, content_type = remote_image_loader(
                                        str(media["url"])
                                    )
                                    declared_md5 = str(media.get("md5") or "")
                                    if (
                                        re.fullmatch(
                                            r"[0-9A-Fa-f]{32}",
                                            declared_md5,
                                        )
                                        and hashlib.md5(raw).hexdigest().lower()
                                        != declared_md5.lower()
                                    ):
                                        raise ValueError(
                                            "合并转发图片 MD5 校验失败"
                                        )
                                    add_asset(
                                        proxy,
                                        raw,
                                        "forwarded_image",
                                        content_type,
                                        media.get("filename") or "forwarded-image",
                                    )
                                else:
                                    raise FileNotFoundError(
                                        "合并转发素材没有可用的本地文件"
                                    )
                            elif nested_kind == "sticker":
                                cached = _find_local_sticker(
                                    db_dir,
                                    str(media.get("md5") or ""),
                                    str(media.get("aes_key") or ""),
                                )
                                if cached:
                                    raw, content_type = cached
                                elif media.get("url"):
                                    raw, content_type = remote_image_loader(
                                        str(media["url"])
                                    )
                                else:
                                    raise FileNotFoundError(
                                        "合并转发表情没有可用素材"
                                    )
                                add_asset(
                                    proxy,
                                    raw,
                                    "forwarded_sticker",
                                    content_type,
                                    media.get("filename") or "forwarded-sticker",
                                )
                            elif nested_kind == "voice":
                                local_id = int(media.get("source_local_id") or 0)
                                create_time = int(
                                    media.get("source_create_time")
                                    or proxy["timestamp"]
                                    or 0
                                )
                                source_chat = (
                                    media.get("source_chat_username")
                                    or parent_item.get("chat_username")
                                    or chat.get("username")
                                    or ""
                                )
                                if not local_id:
                                    raise FileNotFoundError(
                                        "合并转发语音缺少本地消息编号"
                                    )
                                record = voice_finder(
                                    media_db_paths or [],
                                    source_chat,
                                    local_id,
                                    create_time,
                                )
                                if record is None:
                                    raise FileNotFoundError(
                                        "微信语音数据库中没有找到合并转发音频"
                                    )
                                wav_path = work_dir / (
                                    f"forwarded-voice-{proxy['id']}.wav"
                                )
                                voice_decoder(record.data, wav_path)
                                add_asset(
                                    proxy,
                                    wav_path.read_bytes(),
                                    "forwarded_voice",
                                    "audio/wav",
                                    wav_path.name,
                                )
                                if transcribe_voice:
                                    if transcriber is None:
                                        if asr_manager is None:
                                            asr_manager = OfflineAsrManager(
                                                progress=progress
                                            )
                                        transcript = asr_manager.transcribe(
                                            wav_path
                                        )
                                    else:
                                        transcript = transcriber(wav_path)
                                    nested["transcript"] = str(transcript).strip()
                                    if nested["transcript"]:
                                        transcription_count += 1
                        except Exception as exc:
                            record_failure(proxy, "forwarded_media", exc)
                        if proxy.get("asset_path"):
                            nested["asset_path"] = proxy["asset_path"]
                        if media:
                            nested["media"] = {
                                key: value
                                for key, value in media.items()
                                if key not in {"url", "path", "aes_key"}
                            }
                        materialize_forwarded_items(
                            nested.get("children") or [],
                            parent_item,
                            f"{lineage}-{nested_index}",
                        )

                for index, item in enumerate(messages, 1):
                    progress(f"正在准备第 {index}/{len(messages)} 条消息")
                    media = item.get("media") or {}
                    kind = item.get("type") or media.get("kind") or ""
                    if kind in {"image", "video", "file"} and media.get("path"):
                        source = str(media["path"])
                        try:
                            payload = _local_ai_media_payload(
                                source,
                                kind=kind,
                                db_dir=db_dir,
                                image_aes_key=image_aes_key,
                                image_xor_key=image_xor_key,
                            )
                            add_asset(
                                item,
                                payload["body"],
                                kind,
                                payload["content_type"],
                                payload["filename"],
                            )
                        except Exception as exc:
                            record_failure(item, "local_media", exc, source)
                    elif kind == "sticker":
                        try:
                            cached = _find_local_sticker(
                                db_dir,
                                str(media.get("md5") or ""),
                                str(media.get("aes_key") or ""),
                            )
                            if cached:
                                raw, content_type = cached
                            elif media.get("url"):
                                raw, content_type = remote_image_loader(
                                    str(media["url"])
                                )
                                declared_md5 = str(media.get("md5") or "")
                                if (
                                    re.fullmatch(
                                        r"[0-9A-Fa-f]{32}",
                                        declared_md5,
                                    )
                                    and hashlib.md5(raw).hexdigest().lower()
                                    != declared_md5.lower()
                                ):
                                    raise ValueError("微信表情素材 MD5 校验失败")
                            else:
                                raise FileNotFoundError(
                                    "本地缓存和微信素材地址均不可用"
                                )
                            add_asset(
                                item,
                                raw,
                                "sticker",
                                content_type,
                                media.get("md5") or "sticker",
                            )
                        except Exception as exc:
                            record_failure(item, "sticker", exc)

                    if kind == "voice":
                        record = None
                        try:
                            record = voice_finder(
                                media_db_paths or [],
                                item.get("chat_username") or chat.get("username") or "",
                                int(item.get("id") or 0),
                                int(item.get("timestamp") or 0),
                            )
                            if record is None:
                                raise FileNotFoundError("微信语音数据库中没有找到对应音频")
                            wav_path = work_dir / f"voice-{item.get('id')}.wav"
                            voice_decoder(record.data, wav_path)
                            wav_bytes = wav_path.read_bytes()
                            add_asset(
                                item,
                                wav_bytes,
                                "voice",
                                "audio/wav",
                                f"voice-{item.get('id')}.wav",
                            )
                        except Exception as exc:
                            record_failure(item, "voice_decode", exc)
                            continue

                        if transcribe_voice:
                            try:
                                if transcriber is None:
                                    if asr_manager is None:
                                        asr_manager = OfflineAsrManager(progress=progress)
                                    transcript = asr_manager.transcribe(wav_path)
                                else:
                                    transcript = transcriber(wav_path)
                                item["transcript"] = str(transcript).strip()
                                if item["transcript"]:
                                    transcription_count += 1
                            except Exception as exc:
                                record_failure(item, "voice_transcription", exc)
                    if kind == "forwarded" and item.get("forwarded"):
                        materialize_forwarded_items(
                            item["forwarded"].get("items") or [],
                            item,
                        )

                manifest_messages = [_manifest_message(item) for item in messages]
                key_copy_text = format_key_copy_text(
                    chat, messages, start_time, end_time
                )
                copy_text = format_copy_text(chat, messages, start_time, end_time)
                manifest = {
                    "package_version": 1,
                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "chat": {
                        "name": chat.get("display_name") or "",
                        "username": chat.get("username") or "",
                        "is_group": bool(chat.get("is_group")),
                    },
                    "date_range": {
                        "start": start_time or None,
                        "end": end_time or None,
                    },
                    "message_count": len(messages),
                    "asset_count": len(assets),
                    "transcription_count": transcription_count,
                    "assets": assets,
                    "failures": failures,
                    "messages": manifest_messages,
                }
                archive.writestr("聊天记录.txt", copy_text.encode("utf-8"))
                archive.writestr(
                    "清单.json",
                    json.dumps(
                        manifest,
                        ensure_ascii=False,
                        indent=2,
                    ).encode("utf-8"),
                )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass

    result_messages = [_manifest_message(item) for item in messages]
    return AiPackageResult(
        path=str(target.resolve()),
        chat=chat.get("display_name") or "",
        username=chat.get("username") or "",
        message_count=len(messages),
        assets=assets,
        transcription_count=transcription_count,
        failures=failures,
        messages=result_messages,
        copy_text=format_copy_text(chat, messages, start_time, end_time),
        key_copy_text=format_key_copy_text(chat, messages, start_time, end_time),
    )
