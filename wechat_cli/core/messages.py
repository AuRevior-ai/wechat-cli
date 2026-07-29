"""消息查询 — 分表查找、分页、格式化"""

import hashlib
import os
import re
import shutil
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import datetime
from pathlib import Path

import zstandard as zstd

from .key_utils import key_path_variants
from .media import export_media_file
from .forwarded import format_forwarded_text, parse_forwarded_message
from .voice import find_voice_record, voice_duration_seconds

_zstd_dctx = zstd.ZstdDecompressor()
_XML_UNSAFE_RE = re.compile(r'<!DOCTYPE|<!ENTITY', re.IGNORECASE)
_XML_PARSE_MAX_LEN = 20000
_QUERY_LIMIT_MAX = 500
_HISTORY_QUERY_BATCH_SIZE = 500

# 消息类型过滤映射: 名称 -> (base_type,) 或 (base_type, sub_type)
MSG_TYPE_FILTERS = {
    'text': (1,),
    'image': (3,),
    'voice': (34,),
    'video': (43,),
    'sticker': (47,),
    'location': (48,),
    'link': (49,),
    'file': (49, 6),
    'call': (50,),
    'system': (10000,),
}
MSG_TYPE_NAMES = list(MSG_TYPE_FILTERS.keys())


# ---- 消息 DB 发现 ----

def find_msg_db_keys(all_keys):
    return sorted([
        k for k in all_keys
        if any(v.startswith("message/") for v in key_path_variants(k))
        and any(re.search(r"message_\d+\.db$", v) for v in key_path_variants(k))
    ])


def find_unkeyed_msg_db_paths(all_keys, db_dir):
    """Return message_N.db shards present on disk but absent from all_keys."""
    def normalize(path):
        return path.replace("\\", "/").lower()

    keyed = {
        normalize(variant)
        for key in all_keys
        for variant in key_path_variants(key)
    }
    message_dir = os.path.join(db_dir, "message")
    try:
        entries = os.scandir(message_dir)
    except OSError:
        return []
    missing = []
    with entries:
        for entry in entries:
            if not entry.is_file() or not re.fullmatch(
                r"message_\d+\.db", entry.name, re.IGNORECASE
            ):
                continue
            rel_path = os.path.relpath(entry.path, db_dir)
            if normalize(rel_path) not in keyed:
                missing.append(rel_path)
    return sorted(
        missing,
        key=lambda path: int(re.search(r"(\d+)\.db$", path).group(1)),
    )


def _is_safe_msg_table_name(table_name):
    return bool(re.fullmatch(r'Msg_[0-9a-f]{32}', table_name))


def _find_msg_tables_for_user(username, msg_db_keys, cache):
    table_hash = hashlib.md5(username.encode()).hexdigest()
    table_name = f"Msg_{table_hash}"
    if not _is_safe_msg_table_name(table_name):
        return []
    matches = []
    for rel_key in msg_db_keys:
        path = cache.get(rel_key)
        if not path:
            continue
        conn = sqlite3.connect(path)
        try:
            exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            if not exists:
                continue
            max_ct = conn.execute(f"SELECT MAX(create_time) FROM [{table_name}]").fetchone()[0] or 0
            matches.append({'db_path': path, 'table_name': table_name, 'max_create_time': max_ct})
        except Exception:
            pass
        finally:
            conn.close()
    matches.sort(key=lambda x: x['max_create_time'], reverse=True)
    return matches


# ---- 消息类型 ----

def _split_msg_type(t):
    try:
        t = int(t)
    except (TypeError, ValueError):
        return 0, 0
    if t > 0xFFFFFFFF:
        return t & 0xFFFFFFFF, t >> 32
    return t, 0


def format_msg_type(t):
    base_type, sub_type = _split_msg_type(t)
    if base_type == 49 and sub_type == 19:
        return "合并转发"
    return {
        1: '文本', 3: '图片', 34: '语音', 42: '名片',
        43: '视频', 47: '表情', 48: '位置', 49: '链接/文件',
        50: '通话', 10000: '系统', 10002: '撤回',
    }.get(base_type, f'type={t}')


# ---- 内容解压 ----

def decompress_content(content, ct):
    if ct and ct == 4 and isinstance(content, bytes):
        try:
            return _zstd_dctx.decompress(content).decode('utf-8', errors='replace')
        except Exception:
            return None
    if isinstance(content, bytes):
        try:
            return content.decode('utf-8', errors='replace')
        except Exception:
            return None
    return content


# ---- 内容解析 ----

def _parse_message_content(content, local_type, is_group):
    if content is None:
        return '', ''
    if isinstance(content, bytes):
        return '', '(二进制内容)'
    sender = ''
    text = content
    if is_group and ':\n' in content:
        sender, text = content.split(':\n', 1)
    return sender, text


def _collapse_text(text):
    if not text:
        return ''
    return re.sub(r'\s+', ' ', text).strip()


def _parse_xml_root(content):
    if not content or len(content) > _XML_PARSE_MAX_LEN or _XML_UNSAFE_RE.search(content):
        return None
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        return None


def _parse_int(value, fallback=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _format_app_message_text(content, local_type, is_group, chat_username, chat_display_name, names, _display_name_fn, resolve_media=False, db_dir=None, create_time_ts=0):
    if not content or '<appmsg' not in content:
        return None
    _, sub_type = _split_msg_type(local_type)
    root = _parse_xml_root(content)
    if root is None:
        return None
    appmsg = root.find('.//appmsg')
    if appmsg is None:
        return None
    title = _collapse_text(appmsg.findtext('title') or '')
    app_type = _parse_int((appmsg.findtext('type') or '').strip(), _parse_int(sub_type, 0))

    if app_type == 19:
        forwarded = parse_forwarded_message(content)
        return format_forwarded_text(forwarded) if forwarded else "[合并转发]"
    if app_type == 57:
        ref = appmsg.find('.//refermsg')
        ref_content = ''
        ref_display_name = ''
        if ref is not None:
            ref_display_name = (ref.findtext('displayname') or '').strip()
            ref_content = _collapse_text(ref.findtext('content') or '')
        if len(ref_content) > 160:
            ref_content = ref_content[:160] + "..."
        quote_text = title or "[引用消息]"
        if ref_content:
            prefix = f"回复 {ref_display_name}: " if ref_display_name else "回复: "
            quote_text += f"\n  ↳ {prefix}{ref_content}"
        return quote_text
    if app_type == 6:
        # Try to resolve file path
        if resolve_media and db_dir:
            msg_dir = os.path.join(os.path.dirname(db_dir), "msg", "file")
            if title and os.path.isdir(msg_dir):
                from datetime import datetime as _dt
                dt = _dt.fromtimestamp(create_time_ts) if create_time_ts else None
                if dt:
                    file_dir = os.path.join(msg_dir, dt.strftime("%Y-%m"))
                    if os.path.isdir(file_dir):
                        target = os.path.join(file_dir, title)
                        if os.path.isfile(target):
                            return f"[文件] {title}\n  {target}"
                        # Fuzzy match
                        for f in os.listdir(file_dir):
                            if title in f or f in title:
                                return f"[文件] {title}\n  {os.path.join(file_dir, f)}"
        return f"[文件] {title}" if title else "[文件]"
    if app_type == 5:
        return f"[链接] {title}" if title else "[链接]"
    if app_type in (33, 36, 44):
        return f"[小程序] {title}" if title else "[小程序]"
    if title:
        return f"[链接/文件] {title}"
    return "[链接/文件]"


def _format_voip_message_text(content):
    if not content or '<voip' not in content:
        return None
    root = _parse_xml_root(content)
    if root is None:
        return "[通话]"
    raw_text = _collapse_text(root.findtext('.//msg') or '')
    if not raw_text:
        return "[通话]"
    status_map = {
        'Canceled': '已取消', 'Line busy': '对方忙线',
        'Call not answered': '未接听', "Call wasn't answered": '未接听',
    }
    if raw_text.startswith('Duration:'):
        duration = raw_text.split(':', 1)[1].strip()
        return f"[通话] 通话时长 {duration}" if duration else "[通话]"
    return f"[通话] {status_map.get(raw_text, raw_text)}"


def _extract_sticker_payload(content):
    root = _parse_xml_root(content)
    if root is None:
        return None
    emoji = root.find('.//emoji')
    if emoji is None:
        return None
    payload = {
        "kind": "sticker",
        "url": emoji.attrib.get("cdnurl") or emoji.attrib.get("thumburl") or emoji.attrib.get("encrypturl") or "",
        "md5": emoji.attrib.get("md5") or emoji.attrib.get("androidmd5") or "",
        "product_id": emoji.attrib.get("productid") or "",
    }
    return {key: value for key, value in payload.items() if value != ""}


def _resolve_media_path(db_dir, content, local_type, create_time_ts, chat_username=None):
    """尝试解析媒体文件在磁盘上的路径。

    Args:
        db_dir: 微信 db_storage 目录
        content: 解压后的 message_content
        local_type: 消息类型
        create_time_ts: 消息时间戳
        chat_username: 聊天对象 username（用于定位 attach 子目录）

    Returns:
        (path, exists) 元组，path 为 None 表示无法解析
    """
    base_type = local_type & 0xFFFFFFFF
    wechat_base = os.path.dirname(db_dir)
    msg_dir = os.path.join(wechat_base, "msg")
    if not os.path.isdir(msg_dir):
        return None, False

    from datetime import datetime
    dt = datetime.fromtimestamp(create_time_ts)
    date_prefix = dt.strftime("%Y-%m")

    # 文件消息 (type 49, sub 6): msg/file/YYYY-MM/filename
    if base_type == 49 and content:
        root = _parse_xml_root(content)
        if root is not None:
            appmsg = root.find('.//appmsg')
            if appmsg is not None:
                app_type = _parse_int((appmsg.findtext('type') or '').strip())
                if app_type == 6:
                    title = (appmsg.findtext('title') or '').strip()
                    if title:
                        file_dir = os.path.join(msg_dir, "file", date_prefix)
                        if os.path.isdir(file_dir):
                            # 精确匹配文件名
                            target = os.path.join(file_dir, title)
                            if os.path.isfile(target):
                                return target, True
                            # 模糊匹配（文件名可能有细微差异）
                            for f in os.listdir(file_dir):
                                if title in f or f in title:
                                    return os.path.join(file_dir, f), True
        return None, False

    # 图片消息 (type 3): msg/attach/<hash>/YYYY-MM/Img/*.dat
    # 视频/语音消息: msg/video/YYYY-MM/ 或 msg/attach/
    if base_type in (3, 34, 43):
        # 搜索 attach 目录下对应月份的文件
        attach_dir = os.path.join(msg_dir, "attach")
        if not os.path.isdir(attach_dir):
            return None, False

        # 尝试用 chat_username 的 MD5 匹配 attach 子目录
        target_hash = None
        if chat_username:
            h = hashlib.md5(chat_username.encode()).hexdigest()
            candidate = os.path.join(attach_dir, h)
            if os.path.isdir(candidate):
                target_hash = h

        # 限定搜索范围：目标目录或所有目录
        search_dirs = [target_hash] if target_hash else [
            d for d in os.listdir(attach_dir)
            if os.path.isdir(os.path.join(attach_dir, d))
        ]

        sub_dir_name = "Img" if base_type == 3 else ("Video" if base_type == 43 else "Voice")

        for d in search_dirs:
            sub = os.path.join(attach_dir, d, date_prefix, sub_dir_name)
            if os.path.isdir(sub):
                selected = _select_media_file_by_time(sub, create_time_ts, base_type)
                if selected:
                    return selected, True

        # 视频：也检查 msg/video/
        if base_type == 43:
            video_dir = os.path.join(msg_dir, "video", date_prefix)
            if os.path.isdir(video_dir):
                thumbs = [f for f in os.listdir(video_dir) if f.endswith("_thumb.jpg")]
                if thumbs:
                    return os.path.join(video_dir, thumbs[0]), True

    return None, False


def _select_media_file_by_time(directory, create_time_ts, base_type):
    try:
        names = [
            name for name in os.listdir(directory)
            if os.path.isfile(os.path.join(directory, name))
        ]
    except OSError:
        return None
    if not names:
        return None

    groups = {}
    for name in names:
        stem = re.sub(r'_(?:t|h)(?=\.dat$)', '', name, flags=re.IGNORECASE)
        groups.setdefault(stem, []).append(name)

    def group_score(item):
        _, group_names = item
        diffs = []
        for name in group_names:
            path = os.path.join(directory, name)
            try:
                diffs.append(abs(os.path.getmtime(path) - create_time_ts))
            except OSError:
                continue
        return min(diffs) if diffs else float("inf")

    _, selected_group = min(groups.items(), key=group_score)

    def file_rank(name):
        lower = name.lower()
        if base_type == 3:
            if lower.endswith("_h.dat"):
                return 2
            if lower.endswith("_t.dat"):
                return 1
            return 0
        return 0

    selected_name = sorted(selected_group, key=file_rank)[0]
    return os.path.join(directory, selected_name)


def _format_message_text(local_id, local_type, content, is_group, chat_username, chat_display_name, names, display_name_fn, db_dir=None, create_time_ts=0, resolve_media=False):
    sender, text = _parse_message_content(content, local_type, is_group)
    base_type, _ = _split_msg_type(local_type)

    media_path = None
    media_exists = False
    if resolve_media and db_dir and content:
        try:
            media_path, media_exists = _resolve_media_path(
                db_dir, content, local_type, create_time_ts, chat_username
            )
        except Exception:
            pass

    if base_type == 3:
        if media_path:
            tag = f"[图片] {media_path}"
            if not media_exists:
                tag += " (文件不存在)"
        else:
            tag = f"[图片] (local_id={local_id})"
        text = tag
    elif base_type == 34:
        duration = voice_duration_seconds(text)
        text = f"[语音 {duration:.1f}秒]" if duration else "[语音]"
    elif base_type == 47:
        sticker = _extract_sticker_payload(text)
        sticker_id = sticker.get("md5", "") if sticker else ""
        text = f"[表情] {sticker_id}" if sticker_id else "[表情]"
    elif base_type == 50:
        text = _format_voip_message_text(text) or "[通话]"
    elif base_type == 49:
        text = _format_app_message_text(
            text, local_type, is_group, chat_username, chat_display_name, names, display_name_fn,
            resolve_media=resolve_media, db_dir=db_dir, create_time_ts=create_time_ts
        ) or "[链接/文件]"
    elif base_type != 1:
        type_label = format_msg_type(local_type)
        text = f"[{type_label}] {text}" if text else f"[{type_label}]"
    return sender, text


# ---- Name2Id ----

def _load_name2id_maps(conn):
    id_to_username = {}
    try:
        rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
    except sqlite3.Error:
        return id_to_username
    for rowid, user_name in rows:
        if not user_name:
            continue
        id_to_username[rowid] = user_name
    return id_to_username


# ---- 发送者解析 ----

def _resolve_sender_label(real_sender_id, sender_from_content, is_group, chat_username, chat_display_name, names, id_to_username, display_name_fn):
    sender_username = id_to_username.get(real_sender_id, '')
    if is_group:
        if sender_username and sender_username != chat_username:
            return display_name_fn(sender_username, names)
        if sender_from_content:
            return display_name_fn(sender_from_content, names)
        return ''
    if sender_username == chat_username:
        return chat_display_name
    if sender_username:
        return display_name_fn(sender_username, names)
    return ''


def _resolve_sender_identity(real_sender_id, sender_from_content, is_group, chat_username, chat_display_name, names, id_to_username, display_name_fn):
    sender_username = id_to_username.get(real_sender_id, '')
    if is_group:
        if sender_username and sender_username != chat_username:
            return sender_username, display_name_fn(sender_username, names)
        if sender_from_content:
            return sender_from_content, display_name_fn(sender_from_content, names)
        return '', ''
    if sender_username == chat_username:
        return chat_username, chat_display_name
    if sender_username:
        return sender_username, display_name_fn(sender_username, names)
    return '', ''


def _message_kind(local_type):
    base_type, sub_type = _split_msg_type(local_type)
    if base_type == 1:
        return "text"
    if base_type == 3:
        return "image"
    if base_type == 34:
        return "voice"
    if base_type == 43:
        return "video"
    if base_type == 47:
        return "sticker"
    if base_type == 48:
        return "location"
    if base_type == 49 and sub_type == 6:
        return "file"
    if base_type == 49 and sub_type == 19:
        return "forwarded"
    if base_type == 49:
        return "link"
    if base_type == 50:
        return "call"
    if base_type in (10000, 10002):
        return "system"
    return f"type_{base_type}"


def _media_kind(local_type):
    base_type, sub_type = _split_msg_type(local_type)
    if base_type == 3:
        return "image"
    if base_type == 34:
        return "voice"
    if base_type == 43:
        return "video"
    if base_type == 49 and sub_type == 6:
        return "file"
    return ""


def _build_media_payload(local_type, media_path, media_exists):
    kind = _media_kind(local_type)
    if not kind or not media_path:
        return None
    return {
        "kind": kind,
        "path": media_path,
        "exists": bool(media_exists),
        "filename": os.path.basename(media_path),
    }


def save_message_item_media(item, output_dir, db_dir=""):
    media = item.get("media") or {}
    source = media.get("path") or ""
    if not source or not media.get("exists", True):
        return None
    kind = media.get("kind") or item.get("type") or "media"
    try:
        saved = export_media_file(source, output_dir, db_dir=db_dir)
    except Exception:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = _unique_media_copy_path(out_dir / (media.get("filename") or os.path.basename(source) or "wechat-media"))
        shutil.copy2(source, target)
        saved = {
            "path": str(target),
            "filename": target.name,
            "content_type": "",
            "source_path": os.path.abspath(source),
            "bytes": target.stat().st_size,
        }
    result = {
        "kind": kind,
        "path": saved["path"],
        "filename": saved["filename"],
        "original_path": source,
        "content_type": saved.get("content_type", ""),
        "bytes": saved.get("bytes", 0),
    }
    media["saved_path"] = result["path"]
    media["saved_filename"] = result["filename"]
    item["media"] = media
    return result


def save_message_items_media(items, output_dir, db_dir=""):
    saved = []
    failures = []
    for item in items:
        media = item.get("media") or {}
        if not media.get("path"):
            continue
        try:
            result = save_message_item_media(item, output_dir, db_dir=db_dir)
            if result:
                result["message_id"] = item.get("id")
                result["time"] = item.get("time")
                saved.append(result)
        except Exception as exc:
            failures.append(f"local_id={item.get('id')}: {exc}")
    return saved, failures


def _unique_media_copy_path(path):
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    for i in range(1, 10000):
        candidate = path.with_name(f"{stem}-{i}{suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many duplicate filenames for {path}")


# ---- SQL 查询 ----

def _build_message_filters(start_ts=None, end_ts=None, keyword='', msg_type_filter=None):
    clauses = []
    params = []
    if start_ts is not None:
        clauses.append('create_time >= ?')
        params.append(start_ts)
    if end_ts is not None:
        clauses.append('create_time <= ?')
        params.append(end_ts)
    if keyword:
        clauses.append('message_content LIKE ?')
        params.append(f'%{keyword}%')
    if msg_type_filter is not None:
        base_type = msg_type_filter[0]
        clauses.append('(local_type & 0xFFFFFFFF) = ?')
        params.append(base_type)
        if len(msg_type_filter) > 1:
            clauses.append('((local_type >> 32) & 0xFFFFFFFF) = ?')
            params.append(msg_type_filter[1])
    return clauses, params


def _query_messages(conn, table_name, start_ts=None, end_ts=None, keyword='', limit=20, offset=0, msg_type_filter=None):
    if not _is_safe_msg_table_name(table_name):
        raise ValueError(f'非法消息表名: {table_name}')
    clauses, params = _build_message_filters(start_ts, end_ts, keyword, msg_type_filter)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    sql = f"""
        SELECT local_id, local_type, create_time, real_sender_id, message_content,
               WCDB_CT_message_content
        FROM [{table_name}]
        {where_sql}
        ORDER BY create_time DESC
    """
    if limit is None:
        return conn.execute(sql, params).fetchall()
    sql += "\n        LIMIT ? OFFSET ?"
    return conn.execute(sql, (*params, limit, offset)).fetchall()


# ---- 时间解析 ----

def parse_time_value(value, field_name, is_end=False):
    value = (value or '').strip()
    if not value:
        return None
    formats = [
        ('%Y-%m-%d %H:%M:%S', False),
        ('%Y-%m-%d %H:%M', False),
        ('%Y-%m-%d', True),
    ]
    for fmt, date_only in formats:
        try:
            dt = datetime.strptime(value, fmt)
            if date_only and is_end:
                dt = dt.replace(hour=23, minute=59, second=59)
            return int(dt.timestamp())
        except ValueError:
            continue
    raise ValueError(f"{field_name} 格式无效: {value}。支持 YYYY-MM-DD / YYYY-MM-DD HH:MM / YYYY-MM-DD HH:MM:SS")


def parse_time_range(start_time='', end_time=''):
    start_ts = parse_time_value(start_time, 'start_time', is_end=False)
    end_ts = parse_time_value(end_time, 'end_time', is_end=True)
    if start_ts is not None and end_ts is not None and start_ts > end_ts:
        raise ValueError('start_time 不能晚于 end_time')
    return start_ts, end_ts


def validate_pagination(limit, offset=0, limit_max=_QUERY_LIMIT_MAX):
    if limit <= 0:
        raise ValueError("limit 必须大于 0")
    if limit_max is not None and limit > limit_max:
        raise ValueError(f"limit 不能大于 {limit_max}")
    if offset < 0:
        raise ValueError("offset 不能小于 0")


def validate_search_scope(keyword='', start_time='', end_time=''):
    """搜索全部消息时必须提供完整时间范围。"""
    if (keyword or '').strip():
        return
    if not (start_time or '').strip() or not (end_time or '').strip():
        raise ValueError("关键词为空时，必须同时填写开始时间和结束时间")


# ---- 聊天上下文 ----

def resolve_chat_context(chat_name, msg_db_keys, cache, decrypted_dir):
    from .contacts import resolve_username, get_contact_names
    username = resolve_username(chat_name, cache, decrypted_dir)
    if not username:
        return None
    names = get_contact_names(cache, decrypted_dir)
    display_name = names.get(username, username)
    message_tables = _find_msg_tables_for_user(username, msg_db_keys, cache)
    if not message_tables:
        return {
            'query': chat_name, 'username': username, 'display_name': display_name,
            'db_path': None, 'table_name': None, 'message_tables': [],
            'is_group': '@chatroom' in username,
        }
    primary = message_tables[0]
    return {
        'query': chat_name, 'username': username, 'display_name': display_name,
        'db_path': primary['db_path'], 'table_name': primary['table_name'],
        'message_tables': message_tables, 'is_group': '@chatroom' in username,
    }


def _iter_table_contexts(ctx):
    tables = ctx.get('message_tables') or []
    if not tables and ctx.get('db_path') and ctx.get('table_name'):
        tables = [{'db_path': ctx['db_path'], 'table_name': ctx['table_name']}]
    for table in tables:
        yield {
            'query': ctx['query'], 'username': ctx['username'], 'display_name': ctx['display_name'],
            'db_path': table['db_path'], 'table_name': table['table_name'],
            'is_group': ctx['is_group'],
        }


def _candidate_page_size(limit, offset):
    return limit + offset


def _page_ranked_entries(entries, limit, offset):
    ordered = sorted(entries, key=lambda item: item[0], reverse=True)
    paged = ordered[offset:offset + limit]
    paged.sort(key=lambda item: item[0])
    return paged


# ---- 构建行 ----

def _build_history_line(row, ctx, names, id_to_username, display_name_fn, resolve_media=False, db_dir=None):
    local_id, local_type, create_time, real_sender_id, content, ct = row
    time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M')
    content = decompress_content(content, ct)
    if content is None:
        content = '(无法解压)'
    sender, text = _format_message_text(
        local_id, local_type, content, ctx['is_group'], ctx['username'], ctx['display_name'], names, display_name_fn,
        db_dir=db_dir, create_time_ts=create_time, resolve_media=resolve_media,
    )
    sender_label = _resolve_sender_label(
        real_sender_id, sender, ctx['is_group'], ctx['username'], ctx['display_name'], names, id_to_username, display_name_fn
    )
    if sender_label:
        return create_time, f'[{time_str}] {sender_label}: {text}'
    return create_time, f'[{time_str}] {text}'


def _build_history_item(
    row,
    ctx,
    names,
    id_to_username,
    display_name_fn,
    avatars=None,
    resolve_media=False,
    db_dir=None,
    media_db_paths=None,
):
    local_id, local_type, create_time, real_sender_id, content, ct = row
    time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M')
    content = decompress_content(content, ct)
    if content is None:
        content = '(无法解压)'
    sender_from_content, text = _format_message_text(
        local_id, local_type, content, ctx['is_group'], ctx['username'], ctx['display_name'], names, display_name_fn,
        db_dir=db_dir, create_time_ts=create_time, resolve_media=resolve_media,
    )
    sender_username, sender_label = _resolve_sender_identity(
        real_sender_id, sender_from_content, ctx['is_group'], ctx['username'], ctx['display_name'], names, id_to_username, display_name_fn
    )
    base_type, _ = _split_msg_type(local_type)
    media_payload = None
    _, parsed_content = _parse_message_content(content, local_type, ctx['is_group'])
    forwarded = parse_forwarded_message(parsed_content) if base_type == 49 else None
    if base_type == 47:
        media_payload = _extract_sticker_payload(content)
    voice_payload = None
    if base_type == 34 and resolve_media and media_db_paths:
        record = find_voice_record(
            media_db_paths, ctx['username'], local_id, create_time
        )
        if record:
            voice_payload = {
                "source": "media_database",
                "media_db": record.media_db,
                "local_id": record.local_id,
                "svr_id": record.svr_id,
                "bytes": len(record.data),
                "chunks": record.chunks,
            }
    if resolve_media and db_dir and content:
        try:
            media_path, media_exists = _resolve_media_path(
                db_dir, content, local_type, create_time, ctx['username']
            )
            media_payload = _build_media_payload(local_type, media_path, media_exists) or media_payload
        except Exception:
            pass

    avatars = avatars or {}
    line = f'[{time_str}] {sender_label}: {text}' if sender_label else f'[{time_str}] {text}'
    item = {
        "id": local_id,
        "timestamp": create_time,
        "time": time_str,
        "chat": ctx['display_name'],
        "chat_username": ctx['username'],
        "chat_avatar_url": avatars.get(ctx['username'], ''),
        "is_group": ctx['is_group'],
        "sender": sender_label,
        "sender_username": sender_username,
        "sender_avatar_url": avatars.get(sender_username, ''),
        "is_self": sender_label == 'me',
        "type": "forwarded" if forwarded else _message_kind(local_type),
        "type_label": "合并转发" if forwarded else format_msg_type(local_type),
        "text": text,
        "line": line,
    }
    if media_payload:
        item["media"] = media_payload
    if voice_payload:
        item["voice"] = voice_payload
    if forwarded:
        item["forwarded"] = forwarded
    return item


def _build_search_entry(row, ctx, names, id_to_username, display_name_fn, resolve_media=False, db_dir=None):
    local_id, local_type, create_time, real_sender_id, content, ct = row
    content = decompress_content(content, ct)
    if content is None:
        return None
    sender, text = _format_message_text(
        local_id, local_type, content, ctx['is_group'], ctx['username'], ctx['display_name'], names, display_name_fn,
        db_dir=db_dir, create_time_ts=create_time, resolve_media=resolve_media,
    )
    if text and len(text) > 300:
        text = text[:300] + '...'
    sender_label = _resolve_sender_label(
        real_sender_id, sender, ctx['is_group'], ctx['username'], ctx['display_name'], names, id_to_username, display_name_fn
    )
    time_str = datetime.fromtimestamp(create_time).strftime('%Y-%m-%d %H:%M')
    entry = f"[{time_str}] [{ctx['display_name']}]"
    if sender_label:
        entry += f" {sender_label}:"
    entry += f" {text}"
    return create_time, entry


# ---- 聊天记录查询 ----

def collect_chat_history(ctx, names, display_name_fn, start_ts=None, end_ts=None, limit=20, offset=0, msg_type_filter=None, resolve_media=False, db_dir=None):
    collected = []
    failures = []
    candidate_limit = _candidate_page_size(limit, offset)
    batch_size = min(candidate_limit, _HISTORY_QUERY_BATCH_SIZE)

    for table_ctx in _iter_table_contexts(ctx):
        try:
            with closing(sqlite3.connect(table_ctx['db_path'])) as conn:
                id_to_username = _load_name2id_maps(conn)
                fetch_offset = 0
                before = len(collected)
                while len(collected) - before < candidate_limit:
                    rows = _query_messages(conn, table_ctx['table_name'], start_ts=start_ts, end_ts=end_ts, limit=batch_size, offset=fetch_offset, msg_type_filter=msg_type_filter)
                    if not rows:
                        break
                    fetch_offset += len(rows)
                    for row in rows:
                        try:
                            collected.append(_build_history_line(row, table_ctx, names, id_to_username, display_name_fn, resolve_media=resolve_media, db_dir=db_dir))
                        except Exception as e:
                            failures.append(f"local_id={row[0]}: {e}")
                        if len(collected) - before >= candidate_limit:
                            break
                    if len(rows) < batch_size:
                        break
        except Exception as e:
            failures.append(f"{table_ctx['db_path']}: {e}")

    paged = _page_ranked_entries(collected, limit, offset)
    return [line for _, line in paged], failures


def collect_chat_history_items(
    ctx,
    names,
    display_name_fn,
    avatars=None,
    start_ts=None,
    end_ts=None,
    limit=20,
    offset=0,
    msg_type_filter=None,
    resolve_media=False,
    db_dir=None,
    media_db_paths=None,
):
    collected = []
    failures = []
    candidate_limit = _candidate_page_size(limit, offset)
    batch_size = min(candidate_limit, _HISTORY_QUERY_BATCH_SIZE)

    for table_ctx in _iter_table_contexts(ctx):
        try:
            with closing(sqlite3.connect(table_ctx['db_path'])) as conn:
                id_to_username = _load_name2id_maps(conn)
                fetch_offset = 0
                before = len(collected)
                while len(collected) - before < candidate_limit:
                    rows = _query_messages(conn, table_ctx['table_name'], start_ts=start_ts, end_ts=end_ts, limit=batch_size, offset=fetch_offset, msg_type_filter=msg_type_filter)
                    if not rows:
                        break
                    fetch_offset += len(rows)
                    for row in rows:
                        try:
                            item = _build_history_item(
                                row, table_ctx, names, id_to_username, display_name_fn,
                                avatars=avatars, resolve_media=resolve_media, db_dir=db_dir,
                                media_db_paths=media_db_paths,
                            )
                            collected.append((item["timestamp"], item))
                        except Exception as e:
                            failures.append(f"local_id={row[0]}: {e}")
                        if len(collected) - before >= candidate_limit:
                            break
                    if len(rows) < batch_size:
                        break
        except Exception as e:
            failures.append(f"{table_ctx['db_path']}: {e}")

    paged = _page_ranked_entries(collected, limit, offset)
    return [item for _, item in paged], failures


# ---- 搜索查询 ----

def _collect_search_entries(conn, contexts, names, keyword, display_name_fn, start_ts=None, end_ts=None, candidate_limit=20, msg_type_filter=None):
    collected = []
    failures = []
    id_to_username = _load_name2id_maps(conn)
    batch_size = candidate_limit

    for ctx in contexts:
        try:
            fetch_offset = 0
            before = len(collected)
            while len(collected) - before < candidate_limit:
                rows = _query_messages(conn, ctx['table_name'], start_ts=start_ts, end_ts=end_ts, keyword=keyword, limit=batch_size, offset=fetch_offset, msg_type_filter=msg_type_filter)
                if not rows:
                    break
                fetch_offset += len(rows)
                for row in rows:
                    formatted = _build_search_entry(row, ctx, names, id_to_username, display_name_fn)
                    if formatted:
                        collected.append(formatted)
                        if len(collected) - before >= candidate_limit:
                            break
                if len(rows) < batch_size:
                    break
        except Exception as e:
            failures.append(f"{ctx['display_name']}: {e}")
    return collected, failures


def collect_chat_search(ctx, names, keyword, display_name_fn, start_ts=None, end_ts=None, candidate_limit=20, msg_type_filter=None):
    collected = []
    failures = []
    contexts_by_db = {}
    for table_ctx in _iter_table_contexts(ctx):
        contexts_by_db.setdefault(table_ctx['db_path'], []).append(table_ctx)

    for db_path, db_contexts in contexts_by_db.items():
        try:
            with closing(sqlite3.connect(db_path)) as conn:
                db_entries, db_failures = _collect_search_entries(
                    conn, db_contexts, names, keyword, display_name_fn,
                    start_ts=start_ts, end_ts=end_ts, candidate_limit=candidate_limit,
                    msg_type_filter=msg_type_filter,
                )
                collected.extend(db_entries)
                failures.extend(db_failures)
        except Exception as e:
            failures.extend(f"{tc['display_name']}: {e}" for tc in db_contexts)
    return collected, failures


def search_all_messages(msg_db_keys, cache, names, keyword, display_name_fn, start_ts=None, end_ts=None, candidate_limit=20, msg_type_filter=None):
    collected = []
    failures = []
    for rel_key in msg_db_keys:
        path = cache.get(rel_key)
        if not path:
            continue
        try:
            with closing(sqlite3.connect(path)) as conn:
                contexts = _load_search_contexts_from_db(conn, path, names)
                db_entries, db_failures = _collect_search_entries(
                    conn, contexts, names, keyword, display_name_fn,
                    start_ts=start_ts, end_ts=end_ts, candidate_limit=candidate_limit,
                    msg_type_filter=msg_type_filter,
                )
                collected.extend(db_entries)
                failures.extend(db_failures)
        except Exception as e:
            failures.append(f"{rel_key}: {e}")
    return collected, failures


def _load_search_contexts_from_db(conn, db_path, names):
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
    ).fetchall()
    table_to_username = {}
    try:
        for (user_name,) in conn.execute("SELECT user_name FROM Name2Id").fetchall():
            if not user_name:
                continue
            table_hash = hashlib.md5(user_name.encode()).hexdigest()
            table_to_username[f"Msg_{table_hash}"] = user_name
    except sqlite3.Error:
        pass
    contexts = []
    for (table_name,) in tables:
        username = table_to_username.get(table_name, '')
        display_name = names.get(username, username) if username else table_name
        contexts.append({
            'query': display_name, 'username': username, 'display_name': display_name,
            'db_path': db_path, 'table_name': table_name, 'is_group': '@chatroom' in username,
        })
    return contexts


# ---- 多聊天上下文解析 ----

def resolve_chat_contexts(chat_names, msg_db_keys, cache, decrypted_dir):
    resolved = []
    unresolved = []
    missing_tables = []
    seen = set()
    for chat_name in chat_names:
        name = (chat_name or '').strip()
        if not name:
            unresolved.append('(空)')
            continue
        ctx = resolve_chat_context(name, msg_db_keys, cache, decrypted_dir)
        if not ctx:
            unresolved.append(name)
            continue
        if not ctx['message_tables']:
            missing_tables.append(ctx['display_name'])
            continue
        if ctx['username'] in seen:
            continue
        seen.add(ctx['username'])
        resolved.append(ctx)
    return resolved, unresolved, missing_tables


# ---- 聊天统计 ----

def collect_chat_stats(ctx, names, display_name_fn, start_ts=None, end_ts=None):
    """聚合统计指定聊天的消息数据。

    返回: {
        total, type_breakdown: {type_name: count},
        top_senders: [{name, count}],
        hourly: {0:N, ..., 23:N}
    }
    """
    type_map = {
        1: '文本', 3: '图片', 34: '语音', 42: '名片',
        43: '视频', 47: '表情', 48: '位置', 49: '链接/文件',
        50: '通话', 10000: '系统', 10002: '撤回',
    }

    total = 0
    type_counts = {}
    sender_counts = {}
    hourly_counts = {}

    for table_ctx in _iter_table_contexts(ctx):
        try:
            with closing(sqlite3.connect(table_ctx['db_path'])) as conn:
                id_to_username = _load_name2id_maps(conn)
                tbl = table_ctx['table_name']
                if not _is_safe_msg_table_name(tbl):
                    continue

                where_parts = []
                params = []
                if start_ts is not None:
                    where_parts.append('create_time >= ?')
                    params.append(start_ts)
                if end_ts is not None:
                    where_parts.append('create_time <= ?')
                    params.append(end_ts)
                where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ''

                # 总数 + 类型分布
                for bt, cnt in conn.execute(
                    f"SELECT (local_type & 0xFFFFFFFF), COUNT(*) FROM [{tbl}] {where_sql} GROUP BY (local_type & 0xFFFFFFFF)",
                    params
                ).fetchall():
                    label = type_map.get(bt, f'type={bt}')
                    type_counts[label] = type_counts.get(label, 0) + cnt
                    total += cnt

                # 发送者排名
                for sid, cnt in conn.execute(
                    f"SELECT real_sender_id, COUNT(*) FROM [{tbl}] {where_sql} GROUP BY real_sender_id ORDER BY COUNT(*) DESC LIMIT 20",
                    params
                ).fetchall():
                    uname = id_to_username.get(sid, str(sid))
                    if uname:
                        sender_counts[uname] = sender_counts.get(uname, 0) + cnt

                # 24小时分布
                for h, cnt in conn.execute(
                    f"SELECT cast(strftime('%H', create_time, 'unixepoch', 'localtime') as integer), COUNT(*) FROM [{tbl}] {where_sql} GROUP BY cast(strftime('%H', create_time, 'unixepoch', 'localtime') as integer)",
                    params
                ).fetchall():
                    if h is not None:
                        hourly_counts[h] = hourly_counts.get(h, 0) + cnt
        except Exception:
            pass

    top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    top_senders = [{'name': display_name_fn(u, names), 'count': c} for u, c in top_senders]

    hourly = {h: hourly_counts.get(h, 0) for h in range(24)}

    return {
        'total': total,
        'type_breakdown': dict(sorted(type_counts.items(), key=lambda x: x[1], reverse=True)),
        'top_senders': top_senders,
        'hourly': hourly,
    }
