"""Localhost web console server.

The server intentionally exposes a narrow JSON API that maps browser form
payloads to the existing click CLI. It never accepts arbitrary commands.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..core.config import CONFIG_FILE, KEYS_FILE, STATE_DIR, detect_db_dir_candidates
from ..core.media import decode_media_bytes as _core_decode_media_bytes
from ..core.media import media_download_filename as _core_media_download_filename
from ..core.media import read_media_file_payload
from ..core.messages import validate_search_scope

AVATAR_MAX_BYTES = 2 * 1024 * 1024
AVATAR_ALLOWED_HOSTS = ("qlogo.cn", "qpic.cn", "weixin.qq.com")
AVATAR_CACHE_LIMIT = 512
AVATAR_CACHE_MAX_BYTES = 32 * 1024 * 1024
_AVATAR_CACHE: dict[str, dict[str, Any]] = {}
_AVATAR_CACHE_LOCK = Lock()
_AVATAR_CACHE_BYTES = 0
AI_PACKAGE_DIR = os.path.join(STATE_DIR, "ai-packages")
AI_PACKAGE_EXPIRES_SECONDS = 10 * 60
_AI_PACKAGE_DOWNLOADS: dict[str, dict[str, Any]] = {}
_AI_PACKAGE_DOWNLOADS_LOCK = Lock()
STATIC_ASSET_NAMES = {
    "app.css",
    "app.js",
    "au-revior-wechat.jpg",
    "au-revior-payment.jpg",
}


class _AvatarRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_avatar_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


urlopen = build_opener(_AvatarRedirectHandler()).open


def _is_local_request_source(
    host_header: str,
    origin_header: str,
    server_port: int,
    *,
    require_origin: bool,
) -> bool:
    expected = {
        f"127.0.0.1:{server_port}",
        f"localhost:{server_port}",
    }
    if (host_header or "").strip().lower() not in expected:
        return False
    if not require_origin or not (origin_header or "").strip():
        return True
    parsed = urlparse(origin_header.strip())
    return (
        parsed.scheme == "http"
        and not parsed.username
        and not parsed.password
        and (parsed.netloc or "").lower() in expected
        and parsed.path in {"", "/"}
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


@dataclass(frozen=True)
class OptionSpec:
    flag: str
    kind: str = "value"


@dataclass(frozen=True)
class CommandSpec:
    positional: tuple[str, ...] = ()
    optional_positional: tuple[str, ...] = ()
    options: dict[str, OptionSpec] | None = None
    default_format: str | None = None


COMMAND_SPECS: dict[str, CommandSpec] = {
    "init": CommandSpec(
        options={
            "db_dir": OptionSpec("--db-dir"),
            "force": OptionSpec("--force", "bool"),
        },
    ),
    "sessions": CommandSpec(
        options={"limit": OptionSpec("--limit"), "format": OptionSpec("--format")},
        default_format="json",
    ),
    "history": CommandSpec(
        positional=("chat_name",),
        options={
            "limit": OptionSpec("--limit"),
            "offset": OptionSpec("--offset"),
            "start_time": OptionSpec("--start-time"),
            "end_time": OptionSpec("--end-time"),
            "format": OptionSpec("--format"),
            "type": OptionSpec("--type"),
            "media": OptionSpec("--media", "bool"),
        },
        default_format="json",
    ),
    "search": CommandSpec(
        optional_positional=("keyword",),
        options={
            "chat": OptionSpec("--chat", "multi"),
            "start_time": OptionSpec("--start-time"),
            "end_time": OptionSpec("--end-time"),
            "limit": OptionSpec("--limit"),
            "offset": OptionSpec("--offset"),
            "format": OptionSpec("--format"),
            "type": OptionSpec("--type"),
        },
        default_format="json",
    ),
    "contacts": CommandSpec(
        options={
            "query": OptionSpec("--query"),
            "detail": OptionSpec("--detail"),
            "limit": OptionSpec("--limit"),
            "format": OptionSpec("--format"),
        },
        default_format="json",
    ),
    "members": CommandSpec(
        positional=("group_name",),
        options={"format": OptionSpec("--format")},
        default_format="json",
    ),
    "stats": CommandSpec(
        positional=("chat_name",),
        options={
            "start_time": OptionSpec("--start-time"),
            "end_time": OptionSpec("--end-time"),
            "format": OptionSpec("--format"),
        },
        default_format="json",
    ),
    "invite-stats": CommandSpec(
        positional=("group_name",),
        options={
            "start_time": OptionSpec("--start-time"),
            "end_time": OptionSpec("--end-time"),
            "bind_identity": OptionSpec("--bind-identity", "multi"),
            "format": OptionSpec("--format"),
        },
        default_format="json",
    ),
    "export": CommandSpec(
        positional=("chat_name",),
        options={
            "format": OptionSpec("--format"),
            "output_path": OptionSpec("--output"),
            "start_time": OptionSpec("--start-time"),
            "end_time": OptionSpec("--end-time"),
            "limit": OptionSpec("--limit"),
        },
    ),
    "favorites": CommandSpec(
        options={
            "limit": OptionSpec("--limit"),
            "type": OptionSpec("--type"),
            "query": OptionSpec("--query"),
            "format": OptionSpec("--format"),
        },
        default_format="json",
    ),
    "unread": CommandSpec(
        options={"limit": OptionSpec("--limit"), "format": OptionSpec("--format")},
        default_format="json",
    ),
    "new-messages": CommandSpec(
        options={"format": OptionSpec("--format")},
        default_format="json",
    ),
}

WECHAT_V2_DAT_MAGIC = b"\x07\x08V2\x08\x07\x00\x04"


def _is_blank(value: Any) -> bool:
    return value is None or value == "" or value == []


def _stringify(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def build_cli_args(payload: dict[str, Any]) -> list[str]:
    """Build a safe argv list for the existing wechat-cli command group."""
    command = payload.get("command")
    if command not in COMMAND_SPECS:
        raise ValueError(f"Unsupported command: {command}")

    params = payload.get("params") or {}
    if not isinstance(params, dict):
        raise ValueError("params must be an object")

    spec = COMMAND_SPECS[command]
    allowed = set(spec.positional)
    allowed.update(spec.optional_positional)
    allowed.update((spec.options or {}).keys())
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"Unsupported parameter(s) for {command}: {', '.join(unknown)}")

    args = [command]
    for name in spec.positional:
        value = params.get(name)
        if _is_blank(value):
            raise ValueError(f"Missing required parameter: {name}")
        args.append(_stringify(value))
    for name in spec.optional_positional:
        value = params.get(name)
        if not _is_blank(value):
            args.append(_stringify(value).strip())

    if command == "search":
        validate_search_scope(
            params.get("keyword", ""),
            params.get("start_time", ""),
            params.get("end_time", ""),
        )

    options = spec.options or {}
    normalized = dict(params)
    if spec.default_format and _is_blank(normalized.get("format")):
        normalized["format"] = spec.default_format

    for name, opt in options.items():
        value = normalized.get(name)
        if _is_blank(value):
            continue
        if opt.kind == "bool":
            if bool(value):
                args.append(opt.flag)
        elif opt.kind == "multi":
            if not isinstance(value, list):
                raise ValueError(f"{name} must be a list")
            for item in value:
                if not _is_blank(item):
                    args.extend([opt.flag, _stringify(item)])
        else:
            args.extend([opt.flag, _stringify(value)])

    return args


def _cli_subprocess_argv(args: list[str]) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "wechat_cli.main", *args]


def _execute_cli_args(
    args: list[str],
    *,
    response_mode: str = "",
) -> dict[str, Any]:
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }
    proc = subprocess.run(
        _cli_subprocess_argv(args),
        cwd=os.getcwd(),
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=600,
    )
    data = None
    stdout = proc.stdout.strip()
    if stdout:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            data = None
    if response_mode == "summary" and isinstance(data, dict):
        data = dict(data)
        for duplicate_key in ("messages", "saved_media", "save_dir"):
            data.pop(duplicate_key, None)

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": ["wechat-cli", *args],
        "stdout": "" if response_mode == "summary" and data is not None else proc.stdout,
        "stderr": proc.stderr,
        "data": data,
    }


def run_cli_command(payload: dict[str, Any]) -> dict[str, Any]:
    response_mode = payload.get("response_mode", "")
    if response_mode not in {"", "summary"}:
        raise ValueError(f"Unsupported response mode: {response_mode}")
    if response_mode == "summary" and payload.get("command") != "history":
        raise ValueError("Summary response mode is only available for history")

    args = build_cli_args(payload)
    return _execute_cli_args(args, response_mode=response_mode)


def _safe_ai_package_download_name(chat_name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", chat_name).strip(" ._")
    safe = (safe or "微信聊天")[:80]
    return f"{safe}-AI资料包.zip"


def _remove_ai_package_file(path: str) -> None:
    target = Path(path).resolve()
    package_root = Path(AI_PACKAGE_DIR).resolve()
    if target.parent != package_root:
        return
    try:
        target.unlink()
    except FileNotFoundError:
        pass


def _expire_ai_package_downloads(now: float | None = None) -> None:
    now = time.time() if now is None else now
    expired = []
    with _AI_PACKAGE_DOWNLOADS_LOCK:
        for token, entry in list(_AI_PACKAGE_DOWNLOADS.items()):
            if now - entry["created_at"] >= AI_PACKAGE_EXPIRES_SECONDS:
                expired.append(_AI_PACKAGE_DOWNLOADS.pop(token))
    for entry in expired:
        _remove_ai_package_file(entry["path"])
    package_root = Path(AI_PACKAGE_DIR)
    try:
        entries = list(package_root.iterdir())
    except FileNotFoundError:
        return
    for target in entries:
        if target.suffix not in {".zip", ".part"}:
            continue
        try:
            if target.resolve().parent != package_root.resolve():
                continue
            if now - target.stat().st_mtime >= AI_PACKAGE_EXPIRES_SECONDS:
                target.unlink()
        except (FileNotFoundError, OSError):
            continue


def run_ai_package_request(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the CLI with a server-owned output path and issue a one-time URL."""
    allowed = {"chat_name", "start_time", "end_time", "transcribe_voice"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"不支持的 AI 资料包参数: {', '.join(unknown)}")
    chat_name = payload.get("chat_name")
    if not isinstance(chat_name, str) or not chat_name.strip():
        raise ValueError("请先选择一个聊天")
    start_time = payload.get("start_time") or ""
    end_time = payload.get("end_time") or ""
    for label, value in (("开始日期", start_time), ("结束日期", end_time)):
        if value:
            try:
                datetime.strptime(str(value), "%Y-%m-%d")
            except ValueError as exc:
                raise ValueError(f"{label}必须为 YYYY-MM-DD") from exc
    if start_time and end_time and start_time > end_time:
        raise ValueError("开始日期不能晚于结束日期")
    transcribe = payload.get("transcribe_voice", True)
    if not isinstance(transcribe, bool):
        raise ValueError("语音转文字选项必须为布尔值")

    _expire_ai_package_downloads()
    Path(AI_PACKAGE_DIR).mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(24)
    target = str((Path(AI_PACKAGE_DIR) / f"{token}.zip").resolve())
    args = ["ai-package", chat_name.strip()]
    if start_time:
        args.extend(["--start-time", str(start_time)])
    if end_time:
        args.extend(["--end-time", str(end_time)])
    args.extend(["--output", target, "--include-copy-data"])
    if not transcribe:
        args.append("--no-transcribe-voice")

    result = _execute_cli_args(args)
    data = result.get("data")
    if not result.get("ok") or not isinstance(data, dict):
        _remove_ai_package_file(target)
        return {
            "ok": False,
            "error": result.get("stderr") or result.get("stdout") or "AI 资料包生成失败",
        }
    if not Path(target).is_file():
        return {"ok": False, "error": "AI 资料包生成后未找到压缩文件"}

    filename = _safe_ai_package_download_name(
        str(data.get("chat") or chat_name)
    )
    with _AI_PACKAGE_DOWNLOADS_LOCK:
        _AI_PACKAGE_DOWNLOADS[token] = {
            "path": target,
            "filename": filename,
            "created_at": time.time(),
        }
    return {
        "ok": True,
        "chat": data.get("chat") or chat_name,
        "username": data.get("username") or "",
        "message_count": int(data.get("message_count") or 0),
        "asset_count": int(data.get("asset_count") or 0),
        "transcription_count": int(data.get("transcription_count") or 0),
        "failures": data.get("failures"),
        "copy_text": str(data.get("copy_text") or ""),
        "key_copy_text": str(data.get("key_copy_text") or ""),
        "download_url": f"/api/ai-package/{token}",
        "filename": filename,
    }


def claim_ai_package_download(token: str) -> dict[str, Any] | None:
    """Claim a prepared download exactly once."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,80}", token or ""):
        return None
    _expire_ai_package_downloads()
    with _AI_PACKAGE_DOWNLOADS_LOCK:
        entry = _AI_PACKAGE_DOWNLOADS.pop(token, None)
    if entry is None or not Path(entry["path"]).is_file():
        return None
    return entry


def _account_name_from_db_dir(path: str) -> str:
    normalized = os.path.normpath(path)
    if os.path.basename(normalized) == "db_storage":
        return os.path.basename(os.path.dirname(normalized))
    return os.path.basename(normalized)


def db_dir_candidates_payload() -> dict[str, Any]:
    candidates = detect_db_dir_candidates()
    return {
        "ok": True,
        "count": len(candidates),
        "candidates": [
            {
                "path": path,
                "account": _account_name_from_db_dir(path),
                "exists": os.path.isdir(path),
            }
            for path in candidates
        ],
    }


def status_payload() -> dict[str, Any]:
    cfg: dict[str, Any] = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
        except (OSError, json.JSONDecodeError):
            cfg = {}

    keys_count = 0
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, encoding="utf-8") as f:
                keys = json.load(f)
            keys_count = len([k for k in keys if not str(k).startswith("_")])
        except (OSError, json.JSONDecodeError):
            keys_count = 0

    db_dir = cfg.get("db_dir", "")
    return {
        "initialized": os.path.exists(CONFIG_FILE) and os.path.exists(KEYS_FILE),
        "state_dir": STATE_DIR,
        "config_file": CONFIG_FILE,
        "keys_file": KEYS_FILE,
        "db_dir": db_dir,
        "db_dir_exists": bool(db_dir and os.path.isdir(db_dir)),
        "keys_count": keys_count,
    }


def _validate_avatar_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = any(
        host == suffix or host.endswith(f".{suffix}")
        for suffix in AVATAR_ALLOWED_HOSTS
    )
    if parsed.scheme != "https" or not allowed:
        raise PermissionError("avatar URL is not an allowed WeChat image URL")
    return url


def avatar_remote_payload(url: str) -> dict[str, Any]:
    """Fetch and validate one WeChat avatar through the localhost server."""
    global _AVATAR_CACHE_BYTES
    _validate_avatar_url(url)
    with _AVATAR_CACHE_LOCK:
        cached = _AVATAR_CACHE.get(url)
    if cached is not None:
        return cached

    request = Request(
        url,
        headers={
            "Accept": "image/*",
            "User-Agent": "wechat-cli-web",
        },
    )
    with urlopen(request, timeout=5) as response:
        _validate_avatar_url(response.geturl())
        declared_type = (response.headers.get("Content-Type") or "").split(";", 1)[0].lower()
        if not declared_type.startswith("image/"):
            raise ValueError("avatar response is not an image")
        declared_size = response.headers.get("Content-Length")
        if declared_size and declared_size.isdigit() and int(declared_size) > AVATAR_MAX_BYTES:
            raise ValueError("avatar response is too large")
        raw = response.read(AVATAR_MAX_BYTES + 1)

    if len(raw) > AVATAR_MAX_BYTES:
        raise ValueError("avatar response is too large")
    detected_type = _image_content_type(raw, "")
    if not detected_type:
        raise ValueError("avatar payload is not a supported image")

    payload = {"body": raw, "content_type": detected_type}
    with _AVATAR_CACHE_LOCK:
        existing = _AVATAR_CACHE.get(url)
        if existing is not None:
            return existing
        while _AVATAR_CACHE and (
            len(_AVATAR_CACHE) >= AVATAR_CACHE_LIMIT
            or _AVATAR_CACHE_BYTES + len(raw) > AVATAR_CACHE_MAX_BYTES
        ):
            removed = _AVATAR_CACHE.pop(next(iter(_AVATAR_CACHE)))
            _AVATAR_CACHE_BYTES -= len(removed["body"])
        _AVATAR_CACHE[url] = payload
        _AVATAR_CACHE_BYTES += len(raw)
    return payload


def profile_payload() -> dict[str, str]:
    """Return the current account identity shown in the web console."""
    db_dir = str(status_payload().get("db_dir") or "")
    if not db_dir:
        return {"username": "", "display_name": "", "avatar_url": ""}

    account_dir = os.path.basename(os.path.dirname(os.path.normpath(db_dir)))
    match = re.fullmatch(r"(.+?)_[0-9a-fA-F]{4,}", account_dir)
    candidates = [account_dir]
    if match and match.group(1) != account_dir:
        candidates.append(match.group(1))
    if not account_dir:
        return {"username": "", "display_name": "", "avatar_url": ""}

    for candidate in candidates:
        result = run_cli_command({
            "command": "contacts",
            "params": {"detail": candidate},
        })
        data = result.get("data") if result.get("ok") else {}
        if not isinstance(data, dict) or data.get("username") != candidate:
            continue
        return {
            "username": candidate,
            "display_name": str(
                data.get("remark") or data.get("nick_name") or candidate
            ),
            "avatar_url": str(
                data.get("avatar") or data.get("avatar_url") or ""
            ),
        }
    return {
        "username": account_dir,
        "display_name": account_dir,
        "avatar_url": "",
    }


def _static_bytes(name: str) -> bytes:
    root = resources.files("wechat_cli.web.static")
    return root.joinpath(name).read_bytes()


def media_file_payload(path: str) -> dict[str, Any]:
    """Return local media bytes if path is inside the configured WeChat data root."""
    status = status_payload()
    db_dir = status.get("db_dir", "")
    if not db_dir:
        raise PermissionError("wechat db_dir is not configured")
    cfg = {}
    try:
        with open(CONFIG_FILE, encoding="utf-8") as source:
            cfg = json.load(source)
    except (OSError, json.JSONDecodeError):
        pass
    return read_media_file_payload(
        path,
        db_dir=db_dir,
        image_aes_key=cfg.get("image_aes_keys") or cfg.get("image_aes_key"),
        image_xor_key=cfg.get("image_xor_key"),
    )


def _decode_media_bytes(raw: bytes, path: str) -> tuple[bytes, str]:
    return _core_decode_media_bytes(raw, path)


def _media_download_filename(path: str, content_type: str) -> str:
    return _core_media_download_filename(path, content_type)


def _image_content_type(raw: bytes, path: str) -> str:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    heif_type = _heif_content_type(raw)
    if heif_type:
        return heif_type
    guessed = mimetypes.guess_type(path)[0] or ""
    return guessed if guessed.startswith("image/") else ""


def _heif_content_type(raw: bytes) -> str:
    if len(raw) < 12 or raw[4:8] != b"ftyp":
        return ""
    brand = raw[8:12]
    if brand in {b"avif", b"avis"}:
        return "image/avif"
    if brand in {b"heic", b"heix"}:
        return "image/heic"
    if brand in {b"mif1", b"msf1", b"hevc", b"heim", b"heis"}:
        return "image/heif"
    return ""


def _decode_wechat_dat_image(raw: bytes) -> tuple[bytes, str] | None:
    signatures = [
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
        (b"GIF87a", "image/gif"),
        (b"GIF89a", "image/gif"),
        (b"RIFF", "image/webp"),
    ]
    if not raw:
        return None
    for signature, content_type in signatures:
        key = raw[0] ^ signature[0]
        decoded = bytes(byte ^ key for byte in raw)
        if content_type == "image/webp":
            if decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP":
                return decoded, content_type
        elif decoded.startswith(signature):
            return decoded, content_type
    return None


def _decode_wechat_v2_dat_image(raw: bytes) -> tuple[bytes, str] | None:
    if not raw.startswith(WECHAT_V2_DAT_MAGIC):
        return None
    candidates = []
    if len(raw) > 31:
        candidates.append(raw[15:-16])
        candidates.append(raw[31:])
    if len(raw) > 15:
        candidates.append(raw[15:])
    for candidate in candidates:
        if not candidate:
            continue
        content_type = _image_content_type(candidate, "")
        if content_type:
            return candidate, content_type
    return None


def _media_placeholder_svg(filename: str) -> bytes:
    safe_name = (
        filename.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360" viewBox="0 0 640 360">
  <rect width="640" height="360" rx="24" fill="#f3eee5"/>
  <rect x="28" y="28" width="584" height="304" rx="18" fill="#fffaf0" stroke="#d8d2c8" stroke-width="2"/>
  <text x="320" y="150" text-anchor="middle" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="30" font-weight="700" fill="#116b5f">图片已定位</text>
  <text x="320" y="196" text-anchor="middle" font-family="Segoe UI, Microsoft YaHei, sans-serif" font-size="20" fill="#6f6a61">现代微信 V2 DAT 暂不能直接解码预览</text>
  <text x="320" y="238" text-anchor="middle" font-family="Consolas, monospace" font-size="18" fill="#b7791f">{safe_name}</text>
</svg>"""
    return svg.encode("utf-8")


class WeChatWebHandler(BaseHTTPRequestHandler):
    server_version = "wechat-cli-web/0.1"

    def do_GET(self) -> None:  # noqa: N802
        if not self._validate_request_source(require_origin=False):
            return
        parsed = urlparse(self.path)
        if parsed.path in ("", "/"):
            self._send_bytes(_static_bytes("index.html"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/status":
            self._send_json(status_payload())
            return
        if parsed.path == "/api/profile":
            self._send_json(profile_payload())
            return
        if parsed.path == "/api/db-dirs":
            self._send_json(db_dir_candidates_payload())
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path.startswith("/api/ai-package/"):
            token = parsed.path.rsplit("/", 1)[-1]
            entry = claim_ai_package_download(token)
            if entry is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            self._send_file_once(
                entry["path"],
                "application/zip",
                entry["filename"],
            )
            return
        if parsed.path == "/api/media":
            path = parse_qs(parsed.query).get("path", [""])[0]
            try:
                payload = media_file_payload(path)
                self._send_bytes(payload["body"], payload["content_type"], payload.get("filename"))
            except PermissionError:
                self.send_error(HTTPStatus.FORBIDDEN)
            except FileNotFoundError:
                self.send_error(HTTPStatus.NOT_FOUND)
            return
        if parsed.path == "/api/avatar":
            url = parse_qs(parsed.query).get("url", [""])[0]
            try:
                payload = avatar_remote_payload(url)
                self._send_bytes(payload["body"], payload["content_type"])
            except PermissionError:
                self.send_error(HTTPStatus.FORBIDDEN)
            except ValueError:
                self.send_error(HTTPStatus.BAD_REQUEST)
            except (URLError, OSError):
                self.send_error(HTTPStatus.BAD_GATEWAY)
            return
        if parsed.path.startswith("/static/"):
            name = os.path.basename(parsed.path)
            if name not in STATIC_ASSET_NAMES:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            if name.endswith(".css"):
                content_type += "; charset=utf-8"
            if name.endswith(".js"):
                content_type = "application/javascript; charset=utf-8"
            self._send_bytes(_static_bytes(name), content_type)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if not self._validate_request_source(require_origin=True):
            return
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/run", "/api/ai-package"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            result = (
                run_ai_package_request(payload)
                if parsed.path == "/api/ai-package"
                else run_cli_command(payload)
            )
            self._send_json(result, HTTPStatus.OK if result["ok"] else HTTPStatus.BAD_REQUEST)
        except ValueError as exc:
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except subprocess.TimeoutExpired:
            self._send_json({"ok": False, "error": "Command timed out"}, HTTPStatus.REQUEST_TIMEOUT)
        except Exception as exc:  # keep local console resilient
            self._send_json({"ok": False, "error": str(exc)}, HTTPStatus.INTERNAL_SERVER_ERROR)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 1024 * 1024:
            raise ValueError("Request body too large")
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc
        if not isinstance(payload, dict):
            raise ValueError("Request body must be an object")
        return payload

    def _validate_request_source(self, *, require_origin: bool) -> bool:
        server_port = int(self.server.server_address[1])
        allowed = _is_local_request_source(
            self.headers.get("Host", ""),
            self.headers.get("Origin", ""),
            server_port,
            require_origin=require_origin,
        )
        if not allowed:
            self.send_error(HTTPStatus.FORBIDDEN)
        return allowed

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline'; script-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'",
        )
        super().end_headers()

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _send_bytes(self, raw: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "wechat-media"
            self.send_header("Content-Disposition", f"inline; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}")
        self.end_headers()
        self.wfile.write(raw)

    def _send_file_once(
        self,
        path: str,
        content_type: str,
        filename: str,
    ) -> None:
        target = Path(path)
        try:
            size = target.stat().st_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(size))
            self.send_header("Cache-Control", "no-store")
            ascii_name = (
                filename.encode("ascii", "ignore").decode("ascii")
                or "wechat-ai-package.zip"
            )
            self.send_header(
                "Content-Disposition",
                f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(filename)}",
            )
            self.end_headers()
            with target.open("rb") as source:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        finally:
            _remove_ai_package_file(str(target))

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[wechat-web] " + fmt % args + "\n")


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = False) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The web console is limited to localhost in this version")
    _expire_ai_package_downloads()
    httpd = ThreadingHTTPServer((host, port), WeChatWebHandler)
    url = f"http://{host}:{httpd.server_address[1]}"
    print(f"WeChat CLI Web is running at {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping WeChat CLI Web.", flush=True)
    finally:
        httpd.server_close()
