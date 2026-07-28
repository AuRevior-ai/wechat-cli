"""Localhost web console server.

The server intentionally exposes a narrow JSON API that maps browser form
payloads to the existing click CLI. It never accepts arbitrary commands.
"""

from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from typing import Any
from urllib.parse import parse_qs, quote, urlparse

from ..core.config import CONFIG_FILE, KEYS_FILE, STATE_DIR, detect_db_dir_candidates
from ..core.media import decode_media_bytes as _core_decode_media_bytes
from ..core.media import media_download_filename as _core_media_download_filename
from ..core.media import read_media_file_payload
from ..core.messages import validate_search_scope


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


def run_cli_command(payload: dict[str, Any]) -> dict[str, Any]:
    args = build_cli_args(payload)
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

    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "command": ["wechat-cli", *args],
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "data": data,
    }


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


def _static_bytes(name: str) -> bytes:
    root = resources.files("wechat_cli.web.static")
    return root.joinpath(name).read_bytes()


def media_file_payload(path: str) -> dict[str, Any]:
    """Return local media bytes if path is inside the configured WeChat data root."""
    cfg = status_payload()
    db_dir = cfg.get("db_dir", "")
    if not db_dir:
        raise PermissionError("wechat db_dir is not configured")
    return read_media_file_payload(path, db_dir=db_dir)


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
        parsed = urlparse(self.path)
        if parsed.path in ("", "/"):
            self._send_bytes(_static_bytes("index.html"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/status":
            self._send_json(status_payload())
            return
        if parsed.path == "/api/db-dirs":
            self._send_json(db_dir_candidates_payload())
            return
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
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
        if parsed.path.startswith("/static/"):
            name = os.path.basename(parsed.path)
            if name not in {"app.css", "app.js"}:
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
        parsed = urlparse(self.path)
        if parsed.path != "/api/run":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            payload = self._read_json()
            result = run_cli_command(payload)
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

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("[wechat-web] " + fmt % args + "\n")


def serve(host: str = "127.0.0.1", port: int = 8787, open_browser: bool = False) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The web console is limited to localhost in this version")
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
