"""群邀请提示解析与统计。"""

from __future__ import annotations

import csv
import io
import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime

from .messages import _is_safe_msg_table_name, decompress_content

_SYSTEM_PREFIX_RE = re.compile(r"^\s*\[系统\]\s*")
_QUOTE_RE = re.compile(r'["“](.*?)["”]')
_DIRECT_RE = re.compile(
    r'^\s*["“](?P<inviter>.*?)["”]\s*邀请'
    r'(?P<invitees>.*?)加入了群聊\s*$'
)
_QR_RE = re.compile(
    r'^\s*["“](?P<invitee>.*?)["”]\s*通过扫描'
    r'["“](?P<inviter>.*?)["”]\s*分享的二维码加入群聊\s*$'
)
_UNATTRIBUTED_QR_RE = re.compile(
    r'^\s*(?P<invitee>你|["“].*?["”])通过扫描二维码加入群聊'
)


def normalize_notice_text(text: str) -> str:
    return _SYSTEM_PREFIX_RE.sub("", (text or "").strip())


def normalize_person_name(name: str) -> str:
    return (name or "").strip().strip('"“”').strip()


def parse_invite_notice(text: str) -> list[dict] | None:
    notice = normalize_notice_text(text)
    qr_match = _QR_RE.fullmatch(notice)
    if qr_match:
        return [{
            "method": "qr",
            "inviter_name_raw": normalize_person_name(
                qr_match.group("inviter")
            ),
            "invitee_name_raw": normalize_person_name(
                qr_match.group("invitee")
            ),
        }]

    direct_match = _DIRECT_RE.fullmatch(notice)
    if direct_match:
        inviter = normalize_person_name(direct_match.group("inviter"))
        invitees = [
            normalize_person_name(value)
            for value in _QUOTE_RE.findall(
                direct_match.group("invitees")
            )
        ]
        return [
            {
                "method": "direct",
                "inviter_name_raw": inviter,
                "invitee_name_raw": invitee,
            }
            for invitee in invitees
            if invitee
        ] or None

    unattributed_match = _UNATTRIBUTED_QR_RE.match(notice)
    if unattributed_match:
        return [{
            "method": "unattributed_qr",
            "inviter_name_raw": "",
            "invitee_name_raw": normalize_person_name(
                unattributed_match.group("invitee")
            ),
        }]
    return None


def is_invite_like_notice(text: str) -> bool:
    notice = normalize_notice_text(text)
    return "加入" in notice and "群聊" in notice


def parse_identity_bindings(
    values: list[str] | tuple[str, ...],
) -> dict[str, str]:
    bindings: dict[str, str] = {}
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"身份绑定格式无效: {raw}")
        name, username = raw.split("=", 1)
        name = normalize_person_name(name)
        username = username.strip()
        if not name or not username:
            raise ValueError(f"身份绑定格式无效: {raw}")
        if name in bindings and bindings[name] != username:
            raise ValueError(f"历史昵称重复绑定到不同账号: {name}")
        bindings[name] = username
    return bindings


class IdentityResolver:
    def __init__(
        self,
        members: list[dict],
        bindings: dict[str, str],
    ):
        self._bindings = bindings
        self._members_by_username = {
            member["username"]: member
            for member in members
            if member.get("username")
        }
        self._exact: dict[str, set[str]] = {}
        for member in members:
            username = member.get("username", "")
            if not username:
                continue
            for field in ("display_name", "remark", "nick_name"):
                value = normalize_person_name(member.get(field, ""))
                if value:
                    self._exact.setdefault(value, set()).add(username)

    def resolve(self, raw_name: str) -> dict:
        name = normalize_person_name(raw_name)
        if name in self._bindings:
            username = self._bindings[name]
            member = self._members_by_username.get(username, {})
            return {
                "key": f"user:{username}",
                "username": username,
                "name": member.get("display_name") or name,
                "status": "resolved",
                "source": "manual",
            }

        candidates = self._exact.get(name, set())
        if len(candidates) == 1:
            username = next(iter(candidates))
            member = self._members_by_username[username]
            return {
                "key": f"user:{username}",
                "username": username,
                "name": member.get("display_name") or name,
                "status": "resolved",
                "source": "member_exact",
            }

        return {
            "key": f"name:{name}",
            "username": "",
            "name": name,
            "status": "unresolved",
            "source": "ambiguous" if candidates else "unmatched",
        }


def _system_rows(
    conn,
    table_name,
    start_ts=None,
    end_ts=None,
):
    if not _is_safe_msg_table_name(table_name):
        raise ValueError(f"非法消息表名: {table_name}")
    clauses = ["(local_type & 0xFFFFFFFF) = 10000"]
    params = []
    if start_ts is not None:
        clauses.append("create_time >= ?")
        params.append(start_ts)
    if end_ts is not None:
        clauses.append("create_time <= ?")
        params.append(end_ts)
    return conn.execute(
        f"""SELECT local_id, server_id, create_time, message_content,
                   WCDB_CT_message_content
            FROM [{table_name}]
            WHERE {' AND '.join(clauses)}
            ORDER BY create_time ASC""",
        params,
    ).fetchall()


def _identity_fields(prefix, identity):
    return {
        f"{prefix}_username": identity["username"],
        f"{prefix}_key": identity["key"],
        f"{prefix}_identity_status": identity["status"],
        f"{prefix}_identity_source": identity["source"],
    }


def _format_time(timestamp):
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def collect_group_invite_stats(
    chat_ctx,
    members,
    bindings,
    start_ts=None,
    end_ts=None,
):
    if not chat_ctx.get("is_group"):
        raise ValueError("邀请统计只支持群聊")

    resolver = IdentityResolver(members, bindings)
    seen_rows = set()
    events = []
    unattributed = []
    unparsed = []
    failures = []
    system_times = []

    for table in chat_ctx.get("message_tables") or []:
        try:
            with closing(sqlite3.connect(table["db_path"])) as conn:
                rows = _system_rows(
                    conn,
                    table["table_name"],
                    start_ts=start_ts,
                    end_ts=end_ts,
                )
        except Exception as exc:
            failures.append(f'{table.get("db_path", "")}: {exc}')
            continue

        for (
            local_id,
            server_id,
            timestamp,
            content,
            compression,
        ) in rows:
            text = decompress_content(content, compression)
            if text is None:
                text = ""
            notice = normalize_notice_text(text)
            row_key = (
                ("server", int(server_id))
                if server_id
                else ("fallback", int(timestamp), notice)
            )
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            system_times.append(int(timestamp))

            parsed = parse_invite_notice(notice)
            if parsed is None:
                if is_invite_like_notice(notice):
                    unparsed.append({
                        "timestamp": int(timestamp),
                        "time": _format_time(timestamp),
                        "raw_text": notice,
                        "reason": "unknown_template",
                    })
                continue

            for relation_index, relation in enumerate(parsed):
                event = {
                    "event_id": (
                        f"{server_id}:{relation_index}"
                        if server_id
                        else (
                            f"{timestamp}:{local_id}:"
                            f"{relation_index}"
                        )
                    ),
                    "server_id": int(server_id or 0),
                    "timestamp": int(timestamp),
                    "time": _format_time(timestamp),
                    "method": relation["method"],
                    "inviter_name_raw": (
                        relation["inviter_name_raw"]
                    ),
                    "invitee_name_raw": (
                        relation["invitee_name_raw"]
                    ),
                    "raw_text": notice,
                }
                invitee = resolver.resolve(
                    relation["invitee_name_raw"]
                )
                event.update(_identity_fields("invitee", invitee))

                if relation["method"] == "unattributed_qr":
                    event.update({
                        "inviter_username": "",
                        "inviter_key": "",
                        "inviter_identity_status": "unattributed",
                        "inviter_identity_source": "notice",
                    })
                    unattributed.append(event)
                    continue

                inviter = resolver.resolve(
                    relation["inviter_name_raw"]
                )
                event.update(_identity_fields("inviter", inviter))
                events.append(event)

    buckets = defaultdict(list)
    for event in events:
        buckets[event["inviter_key"]].append(event)

    ranking = []
    for inviter_key, inviter_events in buckets.items():
        unique_invitees = {}
        for event in inviter_events:
            unique_invitees.setdefault(
                event["invitee_key"], event
            )
        first_timestamp = min(
            event["timestamp"] for event in inviter_events
        )
        last_timestamp = max(
            event["timestamp"] for event in inviter_events
        )
        sample = inviter_events[0]
        resolved_inviter = resolver.resolve(
            sample["inviter_name_raw"]
        )
        ranking.append({
            "rank": 0,
            "inviter_key": inviter_key,
            "inviter_username": sample["inviter_username"],
            "inviter_name": resolved_inviter["name"],
            "historical_names": sorted({
                event["inviter_name_raw"]
                for event in inviter_events
            }),
            "identity_status": (
                sample["inviter_identity_status"]
            ),
            "identity_source": (
                sample["inviter_identity_source"]
            ),
            "unique_invitee_count": len(unique_invitees),
            "event_count": len(inviter_events),
            "direct_count": sum(
                event["method"] == "direct"
                for event in inviter_events
            ),
            "qr_count": sum(
                event["method"] == "qr"
                for event in inviter_events
            ),
            "first_invite_time": _format_time(
                first_timestamp
            ),
            "last_invite_time": _format_time(
                last_timestamp
            ),
            "invitees": [
                {
                    "name": event["invitee_name_raw"],
                    "username": event["invitee_username"],
                    "time": event["time"],
                    "method": event["method"],
                }
                for event in unique_invitees.values()
            ],
        })

    ranking.sort(key=lambda item: (
        -item["unique_invitee_count"],
        item["first_invite_time"],
        item["inviter_name"],
    ))
    for index, item in enumerate(ranking, 1):
        item["rank"] = index

    rank_by_key = {
        item["inviter_key"]: item["rank"]
        for item in ranking
    }
    for event in events:
        event["rank"] = rank_by_key[event["inviter_key"]]

    global_invitees = {
        event["invitee_key"] for event in events
    }
    unresolved_count = sum(
        event["inviter_identity_status"] != "resolved"
        or event["invitee_identity_status"] != "resolved"
        for event in events
    )

    return {
        "chat": chat_ctx.get("display_name", ""),
        "username": chat_ctx.get("username", ""),
        "scope": {
            "start_timestamp": start_ts,
            "end_timestamp": end_ts,
            "first_visible_system_time": (
                _format_time(min(system_times))
                if system_times else None
            ),
            "last_visible_system_time": (
                _format_time(max(system_times))
                if system_times else None
            ),
        },
        "summary": {
            "system_message_count": len(seen_rows),
            "invite_event_count": (
                len(events) + len(unattributed)
            ),
            "attributed_event_count": len(events),
            "unique_invitee_count": len(global_invitees),
            "unattributed_count": len(unattributed),
            "unresolved_identity_count": unresolved_count,
            "unparsed_count": len(unparsed),
        },
        "ranking": ranking,
        "events": sorted(
            events, key=lambda item: item["timestamp"]
        ),
        "unattributed_events": unattributed,
        "unparsed_messages": unparsed,
        "failures": failures,
    }


def format_invite_stats_text(result):
    summary = result["summary"]
    lines = [
        f'{result["chat"]} 群邀请统计',
        (
            "可见范围: "
            f'{result["scope"]["first_visible_system_time"] or "无"}'
            " ~ "
            f'{result["scope"]["last_visible_system_time"] or "无"}'
        ),
        (
            f'邀请事件 {summary["invite_event_count"]}；'
            f'已归属 {summary["attributed_event_count"]}；'
            f'唯一被邀请人 {summary["unique_invitee_count"]}；'
            f'来源不明 {summary["unattributed_count"]}；'
            f'身份待确认 {summary["unresolved_identity_count"]}；'
            f'未解析 {summary["unparsed_count"]}'
        ),
        "",
        "排行榜:",
    ]
    for item in result["ranking"]:
        identity = (
            f' ({item["inviter_username"]})'
            if item["inviter_username"] else " (身份待确认)"
        )
        lines.append(
            f'{item["rank"]}. {item["inviter_name"]}{identity}'
            f' — {item["unique_invitee_count"]} 人'
        )
        lines.append(
            f'   直接 {item["direct_count"]} / '
            f'二维码 {item["qr_count"]} / 事件 {item["event_count"]}'
        )
    lines.append("")
    lines.append("邀请关系明细:")
    for event in result["events"]:
        method = "直接邀请" if event["method"] == "direct" else "二维码"
        identity_note = (
            " [身份待确认]"
            if event["inviter_identity_status"] != "resolved"
            or event["invitee_identity_status"] != "resolved"
            else ""
        )
        lines.append(
            f'  [{event["time"]}] {event["inviter_name_raw"]}'
            f' -> {event["invitee_name_raw"]} ({method}){identity_note}'
        )
    if result["unattributed_events"]:
        lines.append("")
        lines.append("来源不明:")
        for event in result["unattributed_events"]:
            lines.append(
                f'  [{event["time"]}] {event["invitee_name_raw"]}: '
                f'{event["raw_text"]}'
            )
    if result["unparsed_messages"]:
        lines.append("")
        lines.append("未解析提示:")
        for item in result["unparsed_messages"]:
            lines.append(f'  [{item["time"]}] {item["raw_text"]}')
    if result["failures"]:
        lines.append("读取失败: " + "；".join(result["failures"]))
    return "\n".join(lines)


def format_invite_stats_csv(result):
    stream = io.StringIO(newline="")
    stream.write("\ufeff")
    writer = csv.writer(stream)
    writer.writerow([
        "邀请者排名", "邀请者", "邀请者账号", "邀请者身份状态",
        "唯一拉人数", "被邀请者", "被邀请者账号",
        "被邀请者身份状态", "入群时间", "邀请方式", "原始提示",
    ])
    ranking = {
        item["inviter_key"]: item for item in result["ranking"]
    }
    all_events = [
        *result["events"],
        *result["unattributed_events"],
    ]
    for event in all_events:
        item = ranking.get(event["inviter_key"], {})
        writer.writerow([
            item.get("rank", ""),
            item.get("inviter_name", ""),
            item.get("inviter_username", ""),
            event["inviter_identity_status"],
            item.get("unique_invitee_count", 0),
            event["invitee_name_raw"],
            event["invitee_username"],
            event["invitee_identity_status"],
            event["time"],
            {
                "direct": "直接邀请",
                "qr": "二维码",
                "unattributed_qr": "来源不明扫码",
            }[event["method"]],
            event["raw_text"],
        ])
    return stream.getvalue()
