# Group Invite Statistics Implementation Plan

> **Historical construction plan:** This file records the intended implementation steps at the time. Its unchecked boxes are not the current project progress. Read [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md) and the relevant specialist roadmap for current status.

## Final result

- Main delivery commit: `019eed8`; later compatibility fixes: `8431984` and `8d46801`.
- Delivered `invite-stats` in the CLI and Web console with text/CSV output, exact identity resolution, manual identity binding, and later WeChat XML compatibility fixes.
- Verification lives primarily in `tests/test_invite_stats.py` and the Web command tests.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add auditable group invitation statistics to the CLI and localhost Web UI, ranked by unique invitees and resolved to stable WeChat account identities when exact evidence exists.

**Architecture:** A new `wechat_cli.core.invite_stats` module owns notice parsing, exact identity resolution, cross-shard collection, de-duplication, aggregation, and formatters. A thin Click command exposes the result to CLI users, while the Web server allowlists the same command and the existing static UI renders its JSON without recalculating statistics.

**Tech Stack:** Python 3.12, Click, SQLite, existing WeChat database cache/decryption layer, `unittest`/pytest, vanilla HTML/CSS/JavaScript, PyInstaller.

---

## File Map

- Create `.gitignore`: keep generated binaries, caches, logs, secrets, and delivery archives out of source control.
- Create `wechat_cli/core/invite_stats.py`: parse system notices, resolve exact identities, collect rows from every shard, aggregate rankings, and generate text/CSV.
- Create `wechat_cli/commands/invite_stats.py`: validate CLI input and expose JSON/text/CSV output.
- Modify `wechat_cli/main.py`: register `invite-stats` and bump CLI version.
- Modify `wechat_cli/web/server.py`: allowlist the new command and repeated identity bindings.
- Modify `wechat_cli/web/static/index.html`: add the invitation statistics form.
- Modify `wechat_cli/web/static/app.js`: submit bindings, render summaries/rankings/details, and prepare CSV download.
- Modify `wechat_cli/web/static/app.css`: style the statistics dashboard and responsive tables.
- Modify `README_CN.md` and `packaging/windows/README-APP.md`: document the feature and its identity rules.
- Modify `pyproject.toml`: release version 0.2.6.
- Create `tests/test_invite_stats.py`: parser, identity, aggregation, de-duplication, and formatter coverage.
- Create `tests/test_invite_stats_command.py`: CLI behavior and file output.
- Modify `tests/test_web_server.py`: Web allowlist and static UI coverage.

### Task 1: Initialize Git and Commit the Verified 0.2.5 Baseline

**Files:**
- Create: `.gitignore`
- Track: all existing source, tests, documentation, and `docs/superpowers/specs/2026-07-28-group-invite-stats-design.md`
- Exclude: generated packages and local state

- [ ] **Step 1: Create the source-control exclusions**

Create `.gitignore` with exactly:

```gitignore
__pycache__/
*.py[cod]
.pytest_cache/
.coverage
htmlcov/
*.egg-info/

build/
dist/
npm/platforms/*/bin/*.exe
*.spec

*.log
*.tmp
*.db
*.db-wal
*.db-shm

.idea/
.vscode/
.DS_Store
Thumbs.db

.wechat-cli/
all_keys.json
config.json
```

- [ ] **Step 2: Initialize the repository on `main`**

Run:

```powershell
git init -b main
```

Expected: `.git` is created and `git branch --show-current` prints `main`.

- [ ] **Step 3: Configure a repository-local commit identity only if none exists**

Run:

```powershell
if (-not (git config user.name)) { git config user.name "Codex Local" }
if (-not (git config user.email)) { git config user.email "codex@localhost" }
```

Expected: `git config user.name` and `git config user.email` are both non-empty. No global Git configuration is changed.

- [ ] **Step 4: Verify generated and sensitive files are excluded**

Run:

```powershell
git check-ignore dist\wechat-cli-web-app-win32-x64-0.2.5.zip
git check-ignore build\wechat-cli.spec
git check-ignore wechat-web.out.log
```

Expected: all three paths are printed as ignored.

- [ ] **Step 5: Commit the current stable baseline**

Run:

```powershell
git add .
git status --short
git commit -m "chore: establish wechat-cli 0.2.5 baseline"
```

Expected: source and tests are committed; `git status --short` is empty afterward.

### Task 2: Parse Invitation Notices

**Files:**
- Create: `wechat_cli/core/invite_stats.py`
- Create: `tests/test_invite_stats.py`

- [ ] **Step 1: Write failing parser tests**

Create `tests/test_invite_stats.py` with:

```python
import unittest

from wechat_cli.core.invite_stats import (
    is_invite_like_notice,
    parse_invite_notice,
)


class InviteNoticeParserTests(unittest.TestCase):
    def test_parses_direct_invitation(self):
        events = parse_invite_notice(
            '[系统] "只争朝夕"邀请"阿班"加入了群聊'
        )
        self.assertEqual(events, [{
            "method": "direct",
            "inviter_name_raw": "只争朝夕",
            "invitee_name_raw": "阿班",
        }])

    def test_parses_qr_invitation_as_share_owner_credit(self):
        events = parse_invite_notice(
            '"郑桓宇🔥🔥"通过扫描"小陶老师 青年OPC盟主"分享的二维码加入群聊'
        )
        self.assertEqual(events, [{
            "method": "qr",
            "inviter_name_raw": "小陶老师 青年OPC盟主",
            "invitee_name_raw": "郑桓宇🔥🔥",
        }])

    def test_splits_multiple_direct_invitees(self):
        events = parse_invite_notice(
            '"甲"邀请"乙"、"丙"加入了群聊'
        )
        self.assertEqual(
            [event["invitee_name_raw"] for event in events],
            ["乙", "丙"],
        )

    def test_preserves_unattributed_self_qr_join(self):
        events = parse_invite_notice(
            "你通过扫描二维码加入群聊，群聊参与人还有：甲、乙"
        )
        self.assertEqual(events, [{
            "method": "unattributed_qr",
            "inviter_name_raw": "",
            "invitee_name_raw": "你",
        }])

    def test_marks_unknown_join_template_as_invite_like(self):
        text = '"甲"通过新的入群方式加入了群聊'
        self.assertIsNone(parse_invite_notice(text))
        self.assertTrue(is_invite_like_notice(text))

    def test_ignores_unrelated_system_notice(self):
        text = '"甲"修改群名为“项目群”'
        self.assertIsNone(parse_invite_notice(text))
        self.assertFalse(is_invite_like_notice(text))
```

- [ ] **Step 2: Run the parser tests and verify RED**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py
```

Expected: collection fails because `wechat_cli.core.invite_stats` does not exist.

- [ ] **Step 3: Implement the minimal parser**

Create `wechat_cli/core/invite_stats.py` with these parser primitives:

```python
"""Group invitation notice parsing and statistics."""

from __future__ import annotations

import re

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
            "inviter_name_raw": normalize_person_name(qr_match.group("inviter")),
            "invitee_name_raw": normalize_person_name(qr_match.group("invitee")),
        }]

    direct_match = _DIRECT_RE.fullmatch(notice)
    if direct_match:
        inviter = normalize_person_name(direct_match.group("inviter"))
        invitees = [
            normalize_person_name(value)
            for value in _QUOTE_RE.findall(direct_match.group("invitees"))
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
```

- [ ] **Step 4: Run parser tests and verify GREEN**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py
```

Expected: 6 tests pass.

- [ ] **Step 5: Commit parser behavior**

Run:

```powershell
git add wechat_cli/core/invite_stats.py tests/test_invite_stats.py
git commit -m "feat: parse group invitation notices"
```

### Task 3: Resolve Stable Member Identities Without Fuzzy Matching

**Files:**
- Modify: `wechat_cli/core/invite_stats.py`
- Modify: `tests/test_invite_stats.py`

- [ ] **Step 1: Add failing exact-identity tests**

Append:

```python
from wechat_cli.core.invite_stats import (
    IdentityResolver,
    parse_identity_bindings,
)


class InviteIdentityTests(unittest.TestCase):
    def setUp(self):
        self.members = [
            {
                "username": "wxid_8ncies5owakx11",
                "display_name": "小陶 老师",
                "nick_name": "小陶老师 陶金会老板",
                "remark": "小陶 老师",
            },
            {
                "username": "wxid_gd9gzapbdq8e12",
                "display_name": "小陶老师 青年OPC盟主",
                "nick_name": "小陶老师 青年OPC盟主",
                "remark": "小陶老师 青年OPC盟主",
            },
        ]

    def test_keeps_similar_names_as_distinct_accounts(self):
        resolver = IdentityResolver(self.members, {})
        first = resolver.resolve("小陶 老师")
        second = resolver.resolve("小陶老师 青年OPC盟主")
        self.assertEqual(first["username"], "wxid_8ncies5owakx11")
        self.assertEqual(second["username"], "wxid_gd9gzapbdq8e12")
        self.assertNotEqual(first["key"], second["key"])

    def test_does_not_fuzzy_match_partial_name(self):
        resolver = IdentityResolver(self.members, {})
        identity = resolver.resolve("小陶老师")
        self.assertEqual(identity["status"], "unresolved")
        self.assertEqual(identity["key"], "name:小陶老师")

    def test_marks_duplicate_exact_names_ambiguous(self):
        duplicate = {
            "username": "wxid_other",
            "display_name": "小陶 老师",
            "nick_name": "另一个人",
            "remark": "小陶 老师",
        }
        resolver = IdentityResolver([*self.members, duplicate], {})
        identity = resolver.resolve("小陶 老师")
        self.assertEqual(identity["status"], "unresolved")
        self.assertEqual(identity["source"], "ambiguous")

    def test_manual_binding_has_highest_priority(self):
        bindings = parse_identity_bindings(
            ["旧昵称=wxid_gd9gzapbdq8e12"]
        )
        resolver = IdentityResolver(self.members, bindings)
        identity = resolver.resolve("旧昵称")
        self.assertEqual(identity["username"], "wxid_gd9gzapbdq8e12")
        self.assertEqual(identity["source"], "manual")

    def test_rejects_conflicting_manual_bindings(self):
        with self.assertRaisesRegex(ValueError, "重复绑定"):
            parse_identity_bindings([
                "旧昵称=wxid_one",
                "旧昵称=wxid_two",
            ])
```

- [ ] **Step 2: Run identity tests and verify RED**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py -k Identity
```

Expected: imports fail because the identity API is absent.

- [ ] **Step 3: Implement bindings and exact identity resolution**

Append to `wechat_cli/core/invite_stats.py`:

```python
def parse_identity_bindings(values: list[str] | tuple[str, ...]) -> dict[str, str]:
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
    def __init__(self, members: list[dict], bindings: dict[str, str]):
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
```

- [ ] **Step 4: Run all core tests and verify GREEN**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py
```

Expected: 11 tests pass.

- [ ] **Step 5: Commit stable identity handling**

Run:

```powershell
git add wechat_cli/core/invite_stats.py tests/test_invite_stats.py
git commit -m "feat: resolve invite identities by exact account match"
```

### Task 4: Collect Across Message Shards and Aggregate Rankings

**Files:**
- Modify: `wechat_cli/core/invite_stats.py`
- Modify: `tests/test_invite_stats.py`

- [ ] **Step 1: Add failing aggregation tests with real temporary SQLite tables**

Append imports and tests:

```python
import sqlite3
import tempfile
from pathlib import Path

from wechat_cli.core.invite_stats import collect_group_invite_stats


def create_message_db(path: Path, table_name: str, rows: list[tuple]):
    conn = sqlite3.connect(path)
    conn.execute(
        f"""CREATE TABLE [{table_name}] (
            local_id INTEGER,
            server_id INTEGER,
            local_type INTEGER,
            create_time INTEGER,
            message_content TEXT,
            WCDB_CT_message_content INTEGER
        )"""
    )
    conn.executemany(
        f"INSERT INTO [{table_name}] VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


class InviteAggregationTests(unittest.TestCase):
    def test_deduplicates_shards_and_ranks_unique_invitees(self):
        table_name = "Msg_" + "a" * 32
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "message_0.db"
            second = Path(tmp) / "message_1.db"
            shared = (1, 101, 10000, 1000, '"甲"邀请"乙"加入了群聊', 0)
            create_message_db(first, table_name, [
                shared,
                (2, 102, 10000, 1010, '"甲"邀请"乙"加入了群聊', 0),
                (3, 103, 10000, 1020, '"甲"邀请"丙"加入了群聊', 0),
            ])
            create_message_db(second, table_name, [
                shared,
                (4, 104, 10000, 1030, '"丁"邀请"戊"加入了群聊', 0),
                (5, 105, 10000, 1040, '你通过扫描二维码加入群聊', 0),
                (6, 106, 10000, 1050, '"己"通过新的入群方式加入了群聊', 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {"db_path": str(first), "table_name": table_name},
                    {"db_path": str(second), "table_name": table_name},
                ],
            }
            result = collect_group_invite_stats(ctx, [], {})

        self.assertEqual(result["summary"]["system_message_count"], 6)
        self.assertEqual(result["summary"]["invite_event_count"], 5)
        self.assertEqual(result["summary"]["attributed_event_count"], 4)
        self.assertEqual(result["summary"]["unattributed_count"], 1)
        self.assertEqual(result["summary"]["unparsed_count"], 1)
        self.assertEqual(result["ranking"][0]["inviter_name"], "甲")
        self.assertEqual(result["ranking"][0]["unique_invitee_count"], 2)
        self.assertEqual(result["ranking"][0]["event_count"], 3)
        self.assertEqual(result["ranking"][1]["inviter_name"], "丁")

    def test_applies_time_range_before_aggregation(self):
        table_name = "Msg_" + "b" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (1, 201, 10000, 1000, '"甲"邀请"乙"加入了群聊', 0),
                (2, 202, 10000, 2000, '"甲"邀请"丙"加入了群聊', 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {"db_path": str(path), "table_name": table_name},
                ],
            }
            result = collect_group_invite_stats(
                ctx, [], {}, start_ts=1500, end_ts=2500
            )
        self.assertEqual(result["ranking"][0]["unique_invitee_count"], 1)
        self.assertEqual(result["events"][0]["invitee_name_raw"], "丙")

    def test_counts_methods_and_breaks_ties_by_first_invite_time(self):
        table_name = "Msg_" + "e" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (1, 501, 10000, 900, '"丁"邀请"戊"加入了群聊', 0),
                (2, 502, 10000, 1000, '"甲"邀请"乙"加入了群聊', 0),
                (3, 503, 10000, 1010, '"丙"通过扫描"甲"分享的二维码加入群聊', 0),
                (4, 504, 10000, 1100, '"己"邀请"庚"加入了群聊', 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {"db_path": str(path), "table_name": table_name},
                ],
            }
            result = collect_group_invite_stats(ctx, [], {})
        self.assertEqual(result["ranking"][0]["inviter_name"], "甲")
        self.assertEqual(result["ranking"][0]["direct_count"], 1)
        self.assertEqual(result["ranking"][0]["qr_count"], 1)
        self.assertEqual(
            [item["inviter_name"] for item in result["ranking"][1:]],
            ["丁", "己"],
        )

    def test_rejects_private_chat_context(self):
        with self.assertRaisesRegex(ValueError, "只支持群聊"):
            collect_group_invite_stats(
                {"is_group": False, "message_tables": []}, [], {}
            )

    def test_returns_empty_success_when_group_has_no_invites(self):
        table_name = "Msg_" + "c" * 32
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "message.db"
            create_message_db(path, table_name, [
                (1, 301, 10000, 1000, '"甲"修改群名为“测试群”', 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {"db_path": str(path), "table_name": table_name},
                ],
            }
            result = collect_group_invite_stats(ctx, [], {})
        self.assertEqual(result["ranking"], [])
        self.assertEqual(result["summary"]["invite_event_count"], 0)

    def test_continues_after_one_message_database_fails(self):
        table_name = "Msg_" + "d" * 32
        with tempfile.TemporaryDirectory() as tmp:
            valid = Path(tmp) / "valid.db"
            create_message_db(valid, table_name, [
                (1, 401, 10000, 1000, '"甲"邀请"乙"加入了群聊', 0),
            ])
            ctx = {
                "display_name": "测试群",
                "username": "room@chatroom",
                "is_group": True,
                "message_tables": [
                    {"db_path": str(Path(tmp) / "missing.db"), "table_name": table_name},
                    {"db_path": str(valid), "table_name": table_name},
                ],
            }
            result = collect_group_invite_stats(ctx, [], {})
        self.assertEqual(result["summary"]["attributed_event_count"], 1)
        self.assertEqual(len(result["failures"]), 1)
```

- [ ] **Step 2: Run aggregation tests and verify RED**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py -k Aggregation
```

Expected: import fails because `collect_group_invite_stats` is absent.

- [ ] **Step 3: Implement row collection, de-duplication, and ranking**

Add imports:

```python
import csv
import io
import sqlite3
from collections import defaultdict
from contextlib import closing
from datetime import datetime

from .messages import (
    _is_safe_msg_table_name,
    decompress_content,
)
```

Add the collector and aggregator. The implementation must:

```python
def _system_rows(conn, table_name, start_ts=None, end_ts=None):
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
            failures.append(
                f'{table.get("db_path", "")}: {exc}'
            )
            continue
        for local_id, server_id, timestamp, content, compression in rows:
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
                        "time": datetime.fromtimestamp(timestamp).strftime(
                            "%Y-%m-%d %H:%M"
                        ),
                        "raw_text": notice,
                        "reason": "unknown_template",
                    })
                continue
            for relation_index, relation in enumerate(parsed):
                base = {
                    "event_id": (
                        f"{server_id}:{relation_index}"
                        if server_id
                        else f"{timestamp}:{local_id}:{relation_index}"
                    ),
                    "server_id": int(server_id or 0),
                    "timestamp": int(timestamp),
                    "time": datetime.fromtimestamp(timestamp).strftime(
                        "%Y-%m-%d %H:%M"
                    ),
                    "method": relation["method"],
                    "inviter_name_raw": relation["inviter_name_raw"],
                    "invitee_name_raw": relation["invitee_name_raw"],
                    "raw_text": notice,
                }
                invitee = resolver.resolve(relation["invitee_name_raw"])
                base.update(_identity_fields("invitee", invitee))
                if relation["method"] == "unattributed_qr":
                    base.update({
                        "inviter_username": "",
                        "inviter_key": "",
                        "inviter_identity_status": "unattributed",
                        "inviter_identity_source": "notice",
                    })
                    unattributed.append(base)
                    continue
                inviter = resolver.resolve(relation["inviter_name_raw"])
                base.update(_identity_fields("inviter", inviter))
                events.append(base)

    buckets = defaultdict(list)
    for event in events:
        buckets[event["inviter_key"]].append(event)
    ranking = []
    for inviter_key, inviter_events in buckets.items():
        unique_invitees = {}
        for event in inviter_events:
            unique_invitees.setdefault(event["invitee_key"], event)
        first = min(event["timestamp"] for event in inviter_events)
        last = max(event["timestamp"] for event in inviter_events)
        sample = inviter_events[0]
        ranking.append({
            "rank": 0,
            "inviter_key": inviter_key,
            "inviter_username": sample["inviter_username"],
            "inviter_name": (
                resolver.resolve(sample["inviter_name_raw"])["name"]
            ),
            "historical_names": sorted({
                event["inviter_name_raw"] for event in inviter_events
            }),
            "identity_status": sample["inviter_identity_status"],
            "identity_source": sample["inviter_identity_source"],
            "unique_invitee_count": len(unique_invitees),
            "event_count": len(inviter_events),
            "direct_count": sum(
                event["method"] == "direct" for event in inviter_events
            ),
            "qr_count": sum(
                event["method"] == "qr" for event in inviter_events
            ),
            "first_invite_time": datetime.fromtimestamp(first).strftime(
                "%Y-%m-%d %H:%M"
            ),
            "last_invite_time": datetime.fromtimestamp(last).strftime(
                "%Y-%m-%d %H:%M"
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

    rank_by_key = {item["inviter_key"]: item["rank"] for item in ranking}
    for event in events:
        event["rank"] = rank_by_key[event["inviter_key"]]

    global_invitees = {event["invitee_key"] for event in events}
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
                datetime.fromtimestamp(min(system_times)).strftime(
                    "%Y-%m-%d %H:%M"
                ) if system_times else None
            ),
            "last_visible_system_time": (
                datetime.fromtimestamp(max(system_times)).strftime(
                    "%Y-%m-%d %H:%M"
                ) if system_times else None
            ),
        },
        "summary": {
            "system_message_count": len(seen_rows),
            "invite_event_count": len(events) + len(unattributed),
            "attributed_event_count": len(events),
            "unique_invitee_count": len(global_invitees),
            "unattributed_count": len(unattributed),
            "unresolved_identity_count": unresolved_count,
            "unparsed_count": len(unparsed),
        },
        "ranking": ranking,
        "events": sorted(events, key=lambda item: item["timestamp"]),
        "unattributed_events": unattributed,
        "unparsed_messages": unparsed,
        "failures": failures,
    }
```

- [ ] **Step 4: Run all invite-statistics tests and verify GREEN**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py
```

Expected: all parser, identity, and aggregation tests pass.

- [ ] **Step 5: Commit collector and ranking**

Run:

```powershell
git add wechat_cli/core/invite_stats.py tests/test_invite_stats.py
git commit -m "feat: aggregate invite rankings across message shards"
```

### Task 5: Add the CLI Command and CSV/Text Formats

**Files:**
- Create: `wechat_cli/commands/invite_stats.py`
- Modify: `wechat_cli/core/invite_stats.py`
- Modify: `wechat_cli/main.py`
- Create: `tests/test_invite_stats_command.py`

- [ ] **Step 1: Add failing formatter and CLI registration tests**

Create `tests/test_invite_stats_command.py`:

```python
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from wechat_cli.core.invite_stats import (
    format_invite_stats_csv,
    format_invite_stats_text,
)
from wechat_cli.main import cli


SAMPLE = {
    "chat": "测试群",
    "username": "room@chatroom",
    "scope": {
        "first_visible_system_time": "2026-07-23 18:36",
        "last_visible_system_time": "2026-07-28 09:54",
    },
    "summary": {
        "system_message_count": 10,
        "invite_event_count": 3,
        "attributed_event_count": 3,
        "unique_invitee_count": 2,
        "unattributed_count": 0,
        "unresolved_identity_count": 0,
        "unparsed_count": 0,
    },
    "ranking": [{
        "rank": 1,
        "inviter_key": "user:wxid_a",
        "inviter_username": "wxid_a",
        "inviter_name": "甲",
        "historical_names": ["甲"],
        "identity_status": "resolved",
        "identity_source": "member_exact",
        "unique_invitee_count": 2,
        "event_count": 3,
        "direct_count": 2,
        "qr_count": 1,
        "first_invite_time": "2026-07-23 18:40",
        "last_invite_time": "2026-07-24 10:00",
        "invitees": [],
    }],
    "events": [{
        "event_id": "1:0",
        "server_id": 1,
        "rank": 1,
        "timestamp": 1,
        "time": "2026-07-23 18:40",
        "method": "direct",
        "inviter_name_raw": "甲",
        "inviter_username": "wxid_a",
        "inviter_key": "user:wxid_a",
        "inviter_identity_status": "resolved",
        "inviter_identity_source": "member_exact",
        "invitee_name_raw": "乙",
        "invitee_username": "wxid_b",
        "invitee_key": "user:wxid_b",
        "invitee_identity_status": "resolved",
        "invitee_identity_source": "member_exact",
        "raw_text": '"甲"邀请"乙"加入了群聊',
    }],
    "unattributed_events": [],
    "unparsed_messages": [],
    "failures": [],
}


class InviteFormatterTests(unittest.TestCase):
    def test_text_contains_rank_and_stable_identity(self):
        text = format_invite_stats_text(SAMPLE)
        self.assertIn("1. 甲 (wxid_a) — 2 人", text)
        self.assertIn("直接 2 / 二维码 1 / 事件 3", text)

    def test_csv_has_bom_and_relation_columns(self):
        text = format_invite_stats_csv(SAMPLE)
        self.assertTrue(text.startswith("\ufeff"))
        self.assertIn("邀请者排名,邀请者,邀请者账号,邀请者身份状态", text)
        self.assertIn("1,甲,wxid_a", text)

    def test_command_is_registered(self):
        result = CliRunner().invoke(cli, ["invite-stats", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--bind-identity", result.output)
        self.assertIn("--output", result.output)

    def test_command_outputs_authoritative_json(self):
        fake_app = SimpleNamespace(
            msg_db_keys=[],
            cache=object(),
            decrypted_dir="decrypted",
        )
        chat_ctx = {
            "display_name": "测试群",
            "username": "room@chatroom",
            "is_group": True,
            "db_path": "message.db",
            "message_tables": [],
        }
        with patch(
            "wechat_cli.main.AppContext", return_value=fake_app
        ), patch(
            "wechat_cli.commands.invite_stats.resolve_chat_context",
            return_value=chat_ctx,
        ), patch(
            "wechat_cli.commands.invite_stats.get_group_members",
            return_value={"members": [], "owner": ""},
        ), patch(
            "wechat_cli.commands.invite_stats.collect_group_invite_stats",
            return_value=SAMPLE,
        ):
            result = CliRunner().invoke(
                cli, ["invite-stats", "测试群"]
            )
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn('"ranking"', result.output)
        self.assertIn('"wxid_a"', result.output)

    def test_command_writes_csv_file(self):
        fake_app = SimpleNamespace(
            msg_db_keys=[],
            cache=object(),
            decrypted_dir="decrypted",
        )
        chat_ctx = {
            "display_name": "测试群",
            "username": "room@chatroom",
            "is_group": True,
            "db_path": "message.db",
            "message_tables": [],
        }
        with tempfile.TemporaryDirectory() as tmp, patch(
            "wechat_cli.main.AppContext", return_value=fake_app
        ), patch(
            "wechat_cli.commands.invite_stats.resolve_chat_context",
            return_value=chat_ctx,
        ), patch(
            "wechat_cli.commands.invite_stats.get_group_members",
            return_value={"members": [], "owner": ""},
        ), patch(
            "wechat_cli.commands.invite_stats.collect_group_invite_stats",
            return_value=SAMPLE,
        ):
            target = Path(tmp) / "invite.csv"
            result = CliRunner().invoke(cli, [
                "invite-stats", "测试群",
                "--format", "csv",
                "--output", str(target),
            ])
            raw = target.read_bytes()
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))

    def test_command_reports_unwritable_output_as_click_error(self):
        fake_app = SimpleNamespace(
            msg_db_keys=[],
            cache=object(),
            decrypted_dir="decrypted",
        )
        chat_ctx = {
            "display_name": "测试群",
            "username": "room@chatroom",
            "is_group": True,
            "db_path": "message.db",
            "message_tables": [],
        }
        with patch(
            "wechat_cli.main.AppContext", return_value=fake_app
        ), patch(
            "wechat_cli.commands.invite_stats.resolve_chat_context",
            return_value=chat_ctx,
        ), patch(
            "wechat_cli.commands.invite_stats.get_group_members",
            return_value={"members": [], "owner": ""},
        ), patch(
            "wechat_cli.commands.invite_stats.collect_group_invite_stats",
            return_value=SAMPLE,
        ):
            result = CliRunner().invoke(cli, [
                "invite-stats", "测试群",
                "--format", "csv",
                "--output", "missing/parent/invite.csv",
            ])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("无法写入输出文件", result.output)
```

- [ ] **Step 2: Run command tests and verify RED**

Run:

```powershell
py -m pytest -q tests/test_invite_stats_command.py
```

Expected: formatter imports and CLI command registration fail.

- [ ] **Step 3: Implement text and CSV formatters**

Append to `wechat_cli/core/invite_stats.py`:

```python
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
```

- [ ] **Step 4: Implement the Click command**

Create `wechat_cli/commands/invite_stats.py`:

```python
"""invite-stats command — audit and rank group invitations."""

import json

import click

from ..core.contacts import get_group_members
from ..core.invite_stats import (
    collect_group_invite_stats,
    format_invite_stats_csv,
    format_invite_stats_text,
    parse_identity_bindings,
)
from ..core.messages import parse_time_range, resolve_chat_context
from ..output.formatter import output


@click.command("invite-stats")
@click.argument("group_name")
@click.option("--start-time", default="", help="起始时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--end-time", default="", help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--bind-identity", multiple=True, help="历史昵称=稳定账号，可重复")
@click.option(
    "--format", "fmt", default="json",
    type=click.Choice(["json", "text", "csv"]),
    help="输出格式",
)
@click.option("--output", "output_path", default=None, type=click.Path(dir_okay=False))
@click.pass_context
def invite_stats(
    ctx,
    group_name,
    start_time,
    end_time,
    bind_identity,
    fmt,
    output_path,
):
    """统计群聊邀请关系并按唯一拉人数排行。"""
    app = ctx.obj
    try:
        start_ts, end_ts = parse_time_range(start_time, end_time)
        bindings = parse_identity_bindings(bind_identity)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    chat_ctx = resolve_chat_context(
        group_name, app.msg_db_keys, app.cache, app.decrypted_dir
    )
    if not chat_ctx:
        raise click.ClickException(f"找不到聊天对象: {group_name}")
    if not chat_ctx["is_group"]:
        raise click.ClickException(f"{group_name} 不是一个群聊")
    if not chat_ctx["db_path"]:
        raise click.ClickException(
            f'找不到 {chat_ctx["display_name"]} 的消息记录'
        )
    members = get_group_members(
        chat_ctx["username"], app.cache, app.decrypted_dir
    )["members"]
    result = collect_group_invite_stats(
        chat_ctx,
        members,
        bindings,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if fmt == "json":
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    elif fmt == "csv":
        rendered = format_invite_stats_csv(result)
    else:
        rendered = format_invite_stats_text(result) + "\n"

    if output_path:
        try:
            with open(
                output_path, "w", encoding="utf-8", newline=""
            ) as file:
                file.write(rendered)
        except OSError as exc:
            raise click.ClickException(
                f"无法写入输出文件 {output_path}: {exc}"
            ) from exc
        click.echo(output_path)
    elif fmt == "json":
        output(result, "json")
    else:
        output(rendered, "text")
```

Register in `wechat_cli/main.py`:

```python
from .commands.invite_stats import invite_stats
cli.add_command(invite_stats)
```

- [ ] **Step 5: Run command and regression tests**

Run:

```powershell
py -m pytest -q tests/test_invite_stats.py tests/test_invite_stats_command.py tests/test_main.py
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the CLI feature**

Run:

```powershell
git add wechat_cli/core/invite_stats.py wechat_cli/commands/invite_stats.py wechat_cli/main.py tests/test_invite_stats_command.py
git commit -m "feat: expose group invite rankings in cli"
```

### Task 6: Add Web Command Allowlist and Dedicated Interface

**Files:**
- Modify: `wechat_cli/web/server.py`
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Modify: `wechat_cli/web/static/app.css`
- Modify: `tests/test_web_server.py`

- [ ] **Step 1: Add failing Web contract tests**

Append to `BuildCliArgsTests` in `tests/test_web_server.py`:

```python
    def test_builds_invite_stats_with_repeated_identity_bindings(self):
        args = build_cli_args({
            "command": "invite-stats",
            "params": {
                "group_name": "破界青年OPC销冠争霸赛🏆",
                "start_time": "2026-07-23",
                "bind_identity": [
                    "旧昵称=wxid_one",
                    "另一个旧昵称=wxid_two",
                ],
            },
        })
        self.assertEqual(args, [
            "invite-stats", "破界青年OPC销冠争霸赛🏆",
            "--start-time", "2026-07-23",
            "--bind-identity", "旧昵称=wxid_one",
            "--bind-identity", "另一个旧昵称=wxid_two",
            "--format", "json",
        ])

    def test_invite_stats_page_has_form_and_renderer(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        css = (
            ROOT / "wechat_cli" / "web" / "static" / "app.css"
        ).read_text(encoding="utf-8")
        self.assertIn('data-target="invite-stats"', html)
        self.assertIn('data-command="invite-stats"', html)
        self.assertIn('data-param="bind_identity"', html)
        self.assertIn("function renderInviteStats", js)
        self.assertIn("invite-ranking-table", css)
```

- [ ] **Step 2: Run Web tests and verify RED**

Run:

```powershell
py -m pytest -q tests/test_web_server.py -k invite
```

Expected: command is unsupported and static invitation UI markers are absent.

- [ ] **Step 3: Allowlist the command**

Add to `COMMAND_SPECS` in `wechat_cli/web/server.py`:

```python
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
```

- [ ] **Step 4: Add the Web form**

Add a sidebar button after “统计”:

```html
<button data-target="invite-stats">邀请统计</button>
```

Add a screen before export:

```html
<section id="invite-stats" class="screen" data-title="邀请统计">
  <form class="tool-form" data-command="invite-stats">
    <div class="form-grid">
      <label>群名称
        <input data-param="group_name" required placeholder="输入群聊名称">
      </label>
      <label>开始时间
        <input data-param="start_time" placeholder="2026-07-23">
      </label>
      <label>结束时间
        <input data-param="end_time" placeholder="2026-07-28">
      </label>
      <label class="full">历史昵称绑定
        <textarea data-param="bind_identity" rows="4"
          placeholder="每行一个：历史昵称=wxid_xxx"></textarea>
      </label>
    </div>
    <button class="primary" type="submit">生成邀请统计</button>
  </form>
</section>
```

Update cache-busting query values on both static asset URLs.

- [ ] **Step 5: Serialize multiline bindings and render the authoritative JSON**

In `readForm`, when `form.dataset.command === "invite-stats"`, convert the textarea string to:

```javascript
params.bind_identity = String(params.bind_identity || "")
  .split(/\r?\n/)
  .map((value) => value.trim())
  .filter(Boolean);
```

Add:

```javascript
function inviteCsv(data) {
  const rows = [[
    "邀请者排名", "邀请者", "邀请者账号", "邀请者身份状态",
    "唯一拉人数", "被邀请者", "被邀请者账号",
    "被邀请者身份状态", "入群时间", "邀请方式", "原始提示",
  ]];
  const ranking = new Map(
    (data.ranking || []).map((item) => [item.inviter_key, item])
  );
  const events = [
    ...(data.events || []),
    ...(data.unattributed_events || []),
  ];
  for (const event of events) {
    const inviter = ranking.get(event.inviter_key) || {};
    rows.push([
      inviter.rank || "",
      inviter.inviter_name || event.inviter_name_raw || "",
      inviter.inviter_username || "",
      event.inviter_identity_status || "",
      inviter.unique_invitee_count || 0,
      event.invitee_name_raw || "",
      event.invitee_username || "",
      event.invitee_identity_status || "",
      event.time || "",
      ({
        direct: "直接邀请",
        qr: "二维码",
        unattributed_qr: "来源不明扫码",
      })[event.method] || event.method,
      event.raw_text || "",
    ]);
  }
  const quote = (value) => `"${String(value).replaceAll('"', '""')}"`;
  return "\ufeff" + rows.map((row) => row.map(quote).join(",")).join("\r\n");
}

function renderInviteStats(data) {
  const summary = data.summary || {};
  const cards = [
    ["邀请事件", summary.invite_event_count || 0],
    ["已归属", summary.attributed_event_count || 0],
    ["唯一成员", summary.unique_invitee_count || 0],
    ["来源不明", summary.unattributed_count || 0],
    ["身份待确认", summary.unresolved_identity_count || 0],
    ["未解析", summary.unparsed_count || 0],
  ];
  const cardHtml = `<div class="invite-summary">${
    cards.map(([label, value]) => `
      <div class="invite-summary-card">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>`).join("")
  }</div>`;
  const rows = (data.ranking || []).map((item) => `
    <details class="invite-rank-row">
      <summary>
        <span class="invite-rank">#${escapeHtml(item.rank)}</span>
        <strong>${escapeHtml(item.inviter_name)}</strong>
        <code>${escapeHtml(item.inviter_username || "身份待确认")}</code>
        <b>${escapeHtml(item.unique_invitee_count)} 人</b>
        <span>直接 ${escapeHtml(item.direct_count)} · 二维码 ${escapeHtml(item.qr_count)}</span>
      </summary>
      <div class="invitee-list">${
        (item.invitees || []).map((invitee) => `
          <div>${escapeHtml(invitee.name)} · ${escapeHtml(invitee.time)}
          · ${invitee.method === "direct" ? "直接邀请" : "二维码"}</div>
        `).join("") || "没有明细"
      }</div>
    </details>`).join("");
  const tableHtml = `<div class="invite-ranking-table">${
    rows || '<div class="empty">没有邀请记录。</div>'
  }</div>`;
  const eventRows = (data.events || []).map((event) => `
    <tr>
      <td>${escapeHtml(event.time)}</td>
      <td>${escapeHtml(event.inviter_name_raw)}</td>
      <td>${escapeHtml(event.invitee_name_raw)}</td>
      <td>${event.method === "direct" ? "直接邀请" : "二维码"}</td>
      <td>${event.inviter_identity_status === "resolved" &&
             event.invitee_identity_status === "resolved"
             ? "已确认" : "身份待确认"}</td>
    </tr>`).join("");
  const detailsHtml = `
    <h3 class="invite-section-title">全部邀请关系</h3>
    <div class="invite-detail-scroll">
      <table class="invite-detail-table">
        <thead><tr><th>时间</th><th>邀请者</th><th>被邀请者</th><th>方式</th><th>身份</th></tr></thead>
        <tbody>${eventRows || '<tr><td colspan="5">没有明细</td></tr>'}</tbody>
      </table>
    </div>`;
  const issueItems = [
    ...(data.unattributed_events || []).map((event) => ({
      label: "来源不明",
      time: event.time,
      text: event.raw_text,
    })),
    ...(data.unparsed_messages || []).map((item) => ({
      label: "未解析",
      time: item.time,
      text: item.raw_text,
    })),
  ];
  const issuesHtml = issueItems.length ? `
    <h3 class="invite-section-title">待核查记录</h3>
    <div class="invite-issues">${issueItems.map((item) => `
      <div><b>${escapeHtml(item.label)}</b>
      <span>${escapeHtml(item.time)}</span>
      <p>${escapeHtml(item.text)}</p></div>
    `).join("")}</div>` : "";
  return cardHtml + tableHtml + detailsHtml + issuesHtml;
}
```

At the beginning of `renderData`:

```javascript
if (data && typeof data === "object" &&
    Array.isArray(data.ranking) && data.summary &&
    Array.isArray(data.events)) {
  return renderInviteStats(data);
}
```

Replace the existing `if (payload.data)` block in `setResult` with:

```javascript
if (payload.data) {
  result.innerHTML = renderData(payload.data);
  if (payload.command?.[1] === "invite-stats") {
    lastDownload = {
      text: inviteCsv(payload.data),
      filename: "wechat-invite-stats.csv",
    };
    downloadButton.classList.remove("hidden");
  } else {
    downloadButton.classList.add("hidden");
  }
  return;
}
```

- [ ] **Step 6: Style the dedicated dashboard**

Append to `app.css`:

```css
.invite-summary {
  display: grid;
  grid-template-columns: repeat(6, minmax(110px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.invite-summary-card {
  border: 1px solid var(--line);
  border-top: 4px solid var(--green);
  border-radius: 8px;
  background: #fffaf0;
  padding: 12px;
}

.invite-summary-card span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}

.invite-summary-card strong {
  display: block;
  margin-top: 5px;
  color: var(--green);
  font-size: 24px;
}

.invite-ranking-table {
  display: grid;
  gap: 8px;
}

.invite-rank-row {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  overflow: hidden;
}

.invite-rank-row summary {
  display: grid;
  grid-template-columns: 48px minmax(180px, 1fr) minmax(180px, 1fr) 80px 160px;
  gap: 10px;
  align-items: center;
  padding: 12px;
  cursor: pointer;
}

.invite-rank {
  color: var(--ochre);
  font-weight: 900;
}

.invite-rank-row code {
  color: var(--muted);
  overflow-wrap: anywhere;
}

.invitee-list {
  display: grid;
  gap: 6px;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
  background: #f7f4ee;
}

.invite-section-title {
  margin: 20px 0 10px;
  font-size: 16px;
}

.invite-detail-scroll {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
}

.invite-detail-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--panel);
}

.invite-detail-table th,
.invite-detail-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  white-space: nowrap;
}

.invite-detail-table th {
  color: var(--muted);
  background: #f1eadf;
}

.invite-issues {
  display: grid;
  gap: 8px;
}

.invite-issues > div {
  border-left: 4px solid var(--ochre);
  border-radius: 6px;
  background: #fff6d7;
  padding: 10px 12px;
}

.invite-issues b {
  color: var(--coral);
  margin-right: 8px;
}

.invite-issues span {
  color: var(--muted);
  font-size: 12px;
}

.invite-issues p {
  margin: 6px 0 0;
}

@media (max-width: 900px) {
  .invite-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .invite-rank-row summary {
    grid-template-columns: 42px minmax(0, 1fr);
  }
}
```

- [ ] **Step 7: Run Web tests and verify GREEN**

Run:

```powershell
py -m pytest -q tests/test_web_server.py
```

Expected: all Web tests pass.

- [ ] **Step 8: Commit the Web feature**

Run:

```powershell
git add wechat_cli/web/server.py wechat_cli/web/static/index.html wechat_cli/web/static/app.js wechat_cli/web/static/app.css tests/test_web_server.py
git commit -m "feat: add invite ranking dashboard to web ui"
```

### Task 7: Validate Against the Real OPC Group and Tighten Edge Cases

**Files:**
- Modify only files implicated by failing real-data checks
- Modify corresponding tests before each fix

- [ ] **Step 1: Run the CLI against all visible target-group history**

Run:

```powershell
$verificationDir = "C:\Users\28276\Documents\Codex\2026-07-28\gei\work\invite-stats-verification"
New-Item -ItemType Directory -Force -Path $verificationDir | Out-Null
wechat-cli invite-stats "破界青年OPC销冠争霸赛🏆" --format json |
  Set-Content -Encoding utf8 (Join-Path $verificationDir "invite-stats-real.json")
```

Expected: exit code 0; JSON contains 110 or more visible system messages, direct and QR events, and non-empty ranking.

- [ ] **Step 2: Verify the two similar accounts stay separate**

Run:

```powershell
$data = Get-Content -Raw (Join-Path $verificationDir "invite-stats-real.json") | ConvertFrom-Json
$data.ranking | Where-Object {
  $_.inviter_username -in @(
    'wxid_8ncies5owakx11',
    'wxid_gd9gzapbdq8e12'
  )
} | Select-Object rank,inviter_name,inviter_username,unique_invitee_count
```

Expected: two rows with two distinct usernames.

- [ ] **Step 3: Cross-check parsed counts against raw system history**

Run:

```powershell
$raw = wechat-cli history "破界青年OPC销冠争霸赛🏆" --type system --limit 100000 --format json | ConvertFrom-Json
$stats = Get-Content -Raw (Join-Path $verificationDir "invite-stats-real.json") | ConvertFrom-Json
$rawInviteLike = @($raw.message_items | Where-Object {
  $_.text -match '邀请|加入.*群聊|二维码'
})
Write-Output "raw_invite_like=$($rawInviteLike.Count)"
Write-Output "parsed=$($stats.summary.invite_event_count)"
Write-Output "unparsed=$($stats.summary.unparsed_count)"
```

Expected: every relevant raw row is represented by parsed, unattributed, or unparsed output.

- [ ] **Step 4: If real data reveals a missed template, add a failing fixture first**

Add the exact sanitized system text to `InviteNoticeParserTests`, run that one test to verify RED, change only the parser needed for that template, then run the whole invite-statistics suite.

- [ ] **Step 5: Verify text and CSV output**

Run:

```powershell
wechat-cli invite-stats "破界青年OPC销冠争霸赛🏆" --format text
wechat-cli invite-stats "破界青年OPC销冠争霸赛🏆" --format csv `
  --output (Join-Path $verificationDir "invite-stats-real.csv")
```

Expected: text ranking is descending; CSV opens as UTF-8 and has one relation per row.

- [ ] **Step 6: Start and inspect the Web UI**

Run:

```powershell
wechat-cli web --port 8787
```

Open `http://127.0.0.1:8787`, submit the target group, confirm the six summary cards, descending ranking, distinct stable accounts, expandable invitees, and CSV download.

- [ ] **Step 7: Commit only test-backed real-data fixes**

Run:

```powershell
git add wechat_cli tests
git commit -m "fix: cover real wechat invitation templates"
```

Skip this commit if no production or test files changed.

### Task 8: Document, Version, Build, and Verify the Delivery Package

**Files:**
- Modify: `README_CN.md`
- Modify: `packaging/windows/README-APP.md`
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`
- Build: `dist/wechat-cli-web-app-win32-x64-0.2.6.zip` (ignored by Git)
- Copy delivery artifact to the Codex `outputs` directory

- [ ] **Step 1: Update user documentation**

Document:

````markdown
### `invite-stats` — 群邀请统计

统计直接邀请和分享二维码入群事件，按唯一被邀请人数排行：

```powershell
wechat-cli invite-stats "群名"
wechat-cli invite-stats "群名" --format text
wechat-cli invite-stats "群名" --format csv --output invite-stats.csv
wechat-cli invite-stats "群名" --bind-identity "历史昵称=wxid_xxx"
```

身份只做精确匹配；相似昵称不会自动合并。Web 端在侧边栏“邀请统计”页面提供相同能力。
````

- [ ] **Step 2: Bump the release version**

Change both:

```toml
version = "0.2.6"
```

and:

```python
_VERSION = "0.2.6"
```

- [ ] **Step 3: Run the full fresh test suite**

Run:

```powershell
py -m pytest -q
```

Expected: every test passes with zero failures.

- [ ] **Step 4: Commit the source release**

Run:

```powershell
git add README_CN.md packaging/windows/README-APP.md pyproject.toml wechat_cli/main.py docs
git commit -m "docs: release invite statistics in 0.2.6"
```

- [ ] **Step 5: Build the standalone EXE and one-click package**

Run:

```powershell
py scripts\package_windows_app.py
```

Expected:

```text
Built: ...\wechat-cli.exe
Zip archive: ...\wechat-cli-web-app-win32-x64-0.2.6.zip
```

- [ ] **Step 6: Verify the packaged EXE, not the editable source**

Run:

```powershell
$exe = "dist\wechat-cli-web-app-win32-x64-0.2.6\app\wechat-cli.exe"
& $exe --version
& $exe invite-stats "破界青年OPC销冠争霸赛🏆" --format json |
  Set-Content -Encoding utf8 "C:\Users\28276\Documents\Codex\2026-07-28\gei\work\invite-stats-verification\packaged-invite-stats.json"
```

Expected: version 0.2.6 and valid invitation statistics JSON.

- [ ] **Step 7: Verify `.git` is absent from the delivery archive**

Run:

```powershell
$zip = "dist\wechat-cli-web-app-win32-x64-0.2.6.zip"
$entries = tar -tf $zip
if ($entries -match '(^|/)\.git(/|$)') { throw ".git leaked into package" }
```

Expected: no exception.

- [ ] **Step 8: Copy the verified package and record its checksum**

Run:

```powershell
Copy-Item -LiteralPath $zip -Destination "C:\Users\28276\Documents\Codex\2026-07-28\gei\outputs\wechat-cli-web-app-win32-x64-0.2.6.zip" -Force
Get-FileHash -Algorithm SHA256 -LiteralPath "C:\Users\28276\Documents\Codex\2026-07-28\gei\outputs\wechat-cli-web-app-win32-x64-0.2.6.zip"
```

Expected: a SHA-256 digest is printed.

- [ ] **Step 9: Verify repository history and clean state**

Run:

```powershell
git log --oneline --decorate -8
git status --short
```

Expected: baseline and feature commits are visible; working tree is clean. Generated delivery artifacts remain ignored.
