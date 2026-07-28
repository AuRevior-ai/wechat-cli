"""Local WeChat media reading, decoding, and export helpers."""

import mimetypes
import os
from pathlib import Path

WECHAT_V2_DAT_MAGIC = b"\x07\x08V2\x08\x07\x00\x04"


def read_media_file_payload(path: str, db_dir: str = "") -> dict:
    """Return local media bytes, optionally constrained to a WeChat data root."""
    if not path:
        raise FileNotFoundError("media path is empty")
    if db_dir:
        allowed_root = _allowed_root(db_dir)
        target = os.path.abspath(path)
        try:
            common = os.path.commonpath([allowed_root, target])
        except ValueError as exc:
            raise PermissionError("media path is outside configured WeChat data root") from exc
        if os.path.normcase(common) != os.path.normcase(allowed_root):
            raise PermissionError("media path is outside configured WeChat data root")
    else:
        target = os.path.abspath(path)
    if not os.path.isfile(target):
        raise FileNotFoundError(target)

    with open(target, "rb") as f:
        raw = f.read()
    body, content_type = decode_media_bytes(raw, target)
    return {
        "body": body,
        "content_type": content_type,
        "filename": media_download_filename(target, content_type),
    }


def export_media_file(path: str, output_dir: str, db_dir: str = "") -> dict:
    payload = read_media_file_payload(path, db_dir=db_dir)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = _unique_path(out_dir / payload["filename"])
    target.write_bytes(payload["body"])
    return {
        "path": str(target),
        "filename": target.name,
        "content_type": payload["content_type"],
        "source_path": os.path.abspath(path),
        "bytes": len(payload["body"]),
    }


def decode_media_bytes(raw: bytes, path: str) -> tuple[bytes, str]:
    content_type = image_content_type(raw, path)
    if content_type:
        return raw, content_type
    if path.lower().endswith(".dat"):
        decoded = decode_wechat_dat_image(raw)
        if decoded:
            return decoded
        decoded = decode_wechat_v2_dat_image(raw)
        if decoded:
            return decoded
        return media_placeholder_svg(os.path.basename(path)), "image/svg+xml; charset=utf-8"
    return raw, mimetypes.guess_type(path)[0] or "application/octet-stream"


def media_download_filename(path: str, content_type: str) -> str:
    name = os.path.basename(path) or "wechat-media"
    stem, ext = os.path.splitext(name)
    extension_by_type = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/heif": ".heif",
        "image/avif": ".avif",
        "image/svg+xml; charset=utf-8": ".svg",
    }
    expected_ext = extension_by_type.get(content_type)
    if expected_ext and ext.lower() != expected_ext:
        return f"{stem or 'wechat-media'}{expected_ext}"
    return name


def image_content_type(raw: bytes, path: str) -> str:
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP":
        return "image/webp"
    heif_type = heif_content_type(raw)
    if heif_type:
        return heif_type
    guessed = mimetypes.guess_type(path)[0] or ""
    return guessed if guessed.startswith("image/") else ""


def heif_content_type(raw: bytes) -> str:
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


def decode_wechat_dat_image(raw: bytes) -> tuple[bytes, str] | None:
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


def decode_wechat_v2_dat_image(raw: bytes) -> tuple[bytes, str] | None:
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
        content_type = image_content_type(candidate, "")
        if content_type:
            return candidate, content_type
    return None


def media_placeholder_svg(filename: str) -> bytes:
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


def _allowed_root(db_dir: str) -> str:
    normalized = os.path.abspath(db_dir)
    if os.path.basename(os.path.normpath(normalized)) == "db_storage":
        return os.path.dirname(normalized)
    return normalized


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for i in range(1, 10000):
        candidate = path.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many duplicate filenames for {path}")
