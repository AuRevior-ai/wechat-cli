import unittest
import json
import os
import sys
import subprocess
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from wechat_cli.web import server as web_server
from wechat_cli.web.server import (
    _decode_media_bytes,
    build_cli_args,
    claim_ai_package_download,
    db_dir_candidates_payload,
    media_file_payload,
    run_ai_package_request,
    run_cli_command,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeAvatarResponse:
    def __init__(
        self,
        body=b"\x89PNG\r\n\x1a\navatar",
        content_type="image/png",
        final_url="https://wx.qlogo.cn/avatar/132",
        content_length=None,
    ):
        self.body = body
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(
                len(body) if content_length is None else content_length
            ),
        }
        self.final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def geturl(self):
        return self.final_url

    def read(self, limit=-1):
        return self.body if limit < 0 else self.body[:limit]


class AvatarApiTests(unittest.TestCase):
    @patch("wechat_cli.web.server.urlopen")
    def test_avatar_proxy_returns_allowed_image(self, urlopen_mock):
        urlopen_mock.return_value = FakeAvatarResponse()

        payload = web_server.avatar_remote_payload(
            "https://wx.qlogo.cn/avatar/132?case=allowed"
        )

        self.assertEqual(payload["content_type"], "image/png")
        self.assertTrue(payload["body"].startswith(b"\x89PNG"))

    def test_avatar_proxy_rejects_non_wechat_host(self):
        with self.assertRaises(PermissionError):
            web_server.avatar_remote_payload(
                "https://example.com/avatar.png"
            )

    @patch("wechat_cli.web.server.urlopen")
    def test_avatar_proxy_rejects_non_image_response(self, urlopen_mock):
        urlopen_mock.return_value = FakeAvatarResponse(
            body=b"<html>no</html>",
            content_type="text/html",
        )

        with self.assertRaises(ValueError):
            web_server.avatar_remote_payload(
                "https://wx.qlogo.cn/avatar/132?case=not-image"
            )

    @patch("wechat_cli.web.server.urlopen")
    def test_avatar_proxy_rejects_oversized_response(self, urlopen_mock):
        urlopen_mock.return_value = FakeAvatarResponse(
            content_length=2 * 1024 * 1024 + 1,
        )

        with self.assertRaises(ValueError):
            web_server.avatar_remote_payload(
                "https://wx.qlogo.cn/avatar/132?case=too-large"
            )

    @patch("wechat_cli.web.server.run_cli_command")
    @patch("wechat_cli.web.server.status_payload")
    def test_profile_uses_account_username_from_configured_directory(
        self,
        status_mock,
        run_mock,
    ):
        status_mock.return_value = {
            "db_dir": str(
                Path("root")
                / "xwechat_files"
                / "wxid_owner_fc40"
                / "db_storage"
            )
        }
        def contact_result(payload):
            username = payload["params"]["detail"]
            if username == "wxid_owner_fc40":
                return {"ok": True, "data": None}
            return {
                "ok": True,
                "data": {
                    "username": "wxid_owner",
                    "nick_name": "主人",
                    "remark": "",
                    "avatar": "https://wx.qlogo.cn/owner/132",
                },
            }

        run_mock.side_effect = contact_result

        payload = web_server.profile_payload()

        self.assertEqual(payload["display_name"], "主人")
        self.assertEqual(payload["username"], "wxid_owner")
        self.assertEqual(
            payload["avatar_url"],
            "https://wx.qlogo.cn/owner/132",
        )
        self.assertEqual(
            [call.args[0]["params"]["detail"] for call in run_mock.call_args_list],
            ["wxid_owner_fc40", "wxid_owner"],
        )

    @patch("wechat_cli.web.server.run_cli_command")
    @patch("wechat_cli.web.server.status_payload")
    def test_profile_preserves_real_username_that_looks_like_a_suffix(
        self,
        status_mock,
        run_mock,
    ):
        status_mock.return_value = {
            "db_dir": str(
                Path("root")
                / "xwechat_files"
                / "wxid_abcd"
                / "db_storage"
            )
        }
        run_mock.return_value = {
            "ok": True,
            "data": {
                "username": "wxid_abcd",
                "nick_name": "完整账号",
                "remark": "",
                "avatar": "https://wx.qlogo.cn/full/132",
            },
        }

        payload = web_server.profile_payload()

        self.assertEqual(payload["username"], "wxid_abcd")
        self.assertEqual(payload["display_name"], "完整账号")
        run_mock.assert_called_once_with({
            "command": "contacts",
            "params": {"detail": "wxid_abcd"},
        })


class BuildCliArgsTests(unittest.TestCase):
    def test_local_request_source_rejects_dns_rebinding_and_foreign_origin(self):
        self.assertTrue(web_server._is_local_request_source(
            "127.0.0.1:8787", "", 8787, require_origin=False
        ))
        self.assertTrue(web_server._is_local_request_source(
            "localhost:8787", "http://localhost:8787", 8787, require_origin=True
        ))
        self.assertFalse(web_server._is_local_request_source(
            "attacker.example:8787", "", 8787, require_origin=False
        ))
        self.assertFalse(web_server._is_local_request_source(
            "127.0.0.1:8787", "https://attacker.example", 8787, require_origin=True
        ))
        self.assertFalse(web_server._is_local_request_source(
            "127.0.0.1:9999", "", 8787, require_origin=False
        ))

    def test_web_ai_package_uses_server_owned_path_and_one_time_download(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            web_server,
            "AI_PACKAGE_DIR",
            tmp,
        ), patch(
            "wechat_cli.web.server._execute_cli_args",
        ) as execute:
            def fake_execute(args):
                output_path = Path(args[args.index("--output") + 1])
                output_path.write_bytes(b"PK\x03\x04test")
                return {
                    "ok": True,
                    "returncode": 0,
                    "command": ["wechat-cli", *args],
                    "stdout": "",
                    "stderr": "",
                    "data": {
                        "path": str(output_path),
                        "chat": "测试群",
                        "message_count": 12,
                        "asset_count": 3,
                        "transcription_count": 1,
                        "failures": None,
                        "copy_text": "带素材引用的全文",
                        "key_copy_text": "带素材引用的精简信息",
                    },
                }

            execute.side_effect = fake_execute
            payload = run_ai_package_request({
                "chat_name": "测试群",
                "start_time": "2026-07-29",
                "end_time": "2026-07-29",
                "transcribe_voice": True,
            })
            token = payload["download_url"].rsplit("/", 1)[-1]
            claimed = claim_ai_package_download(token)
            second_claim = claim_ai_package_download(token)

        args = execute.call_args.args[0]
        output_path = Path(args[args.index("--output") + 1]).resolve()
        self.assertEqual(output_path.parent, Path(tmp).resolve())
        self.assertIn("--include-copy-data", args)
        self.assertNotIn("--no-transcribe", args)
        self.assertEqual(payload["copy_text"], "带素材引用的全文")
        self.assertNotIn("path", payload)
        self.assertIsNotNone(claimed)
        self.assertIsNone(second_claim)

    def test_expiry_removes_orphan_packages_left_by_previous_server(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            web_server,
            "AI_PACKAGE_DIR",
            tmp,
        ):
            old_package = Path(tmp) / ("a" * 32 + ".zip")
            current_package = Path(tmp) / ("b" * 32 + ".zip")
            unrelated = Path(tmp) / "keep.txt"
            old_package.write_bytes(b"old")
            current_package.write_bytes(b"current")
            unrelated.write_text("keep", encoding="utf-8")
            now = 10_000.0
            os.utime(
                old_package,
                (now - web_server.AI_PACKAGE_EXPIRES_SECONDS - 1,) * 2,
            )
            os.utime(current_package, (now,) * 2)

            web_server._expire_ai_package_downloads(now)

            self.assertFalse(old_package.exists())
            self.assertTrue(current_package.exists())
            self.assertTrue(unrelated.exists())

    def test_web_ai_package_rejects_unknown_fields(self):
        with self.assertRaisesRegex(ValueError, "不支持"):
            run_ai_package_request({
                "chat_name": "测试群",
                "output": r"C:\outside.zip",
            })

    def test_history_page_can_prepare_ai_material_package(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        css = (
            ROOT / "wechat_cli" / "web" / "static" / "app.css"
        ).read_text(encoding="utf-8")

        self.assertIn('id="build-ai-package"', html)
        self.assertIn('id="ai-package-transcribe"', html)
        self.assertIn('fetchJson("/api/ai-package"', js)
        self.assertIn("payload.download_url", js)
        self.assertIn("payload.copy_text", js)
        self.assertIn("payload.key_copy_text", js)
        self.assertIn("package-button", css)

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

    def test_invite_stats_uses_reusable_group_picker_and_day_inputs(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'id="invite-group-picker" class="session-picker" '
            'data-session-picker data-filter="group" data-multiple="false"',
            html,
        )
        self.assertIn(
            'class="session-picker-value" data-param="group_name" type="hidden"',
            html,
        )
        self.assertEqual(
            html.count('class="date-input" data-param='),
            8,
        )
        self.assertEqual(
            html.count('class="date-input" data-param="start_time" type="date"'),
            4,
        )
        self.assertEqual(
            html.count('class="date-input" data-param="end_time" type="date"'),
            4,
        )
        self.assertIn("function renderSessionPickerOptions", js)
        self.assertIn('picker.filter === "group" && !session.is_group', js)
        self.assertIn("function selectSessionPickerOption", js)
        self.assertNotIn("function renderInviteGroupOptions", js)
        self.assertNotIn("function selectInviteGroup", js)

    def test_all_chat_and_group_fields_use_reusable_session_pickers(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        expected_pickers = {
            "history-chat-picker": ("all", "false"),
            "search-chat-picker": ("all", "true"),
            "members-group-picker": ("group", "false"),
            "stats-chat-picker": ("all", "false"),
            "invite-group-picker": ("group", "false"),
        }

        self.assertEqual(html.count("data-session-picker"), len(expected_pickers))
        for picker_id, (session_filter, multiple) in expected_pickers.items():
            self.assertIn(
                f'id="{picker_id}" class="session-picker" data-session-picker '
                f'data-filter="{session_filter}" data-multiple="{multiple}"',
                html,
            )
        self.assertIn(
            'class="session-picker-value" data-param="chat" '
            'data-list="lines" type="hidden"',
            html,
        )
        self.assertIn('class="session-picker-chips"', html)
        self.assertIn(
            "const sessionPickers = [...document.querySelectorAll(\"[data-session-picker]\")]",
            js,
        )
        self.assertIn("function createSessionPicker(root)", js)
        self.assertIn("function resetSessionPickers()", js)
        self.assertIn("async function loadSessions(shouldApply = () => true)", js)
        self.assertIn(
            'activeScreen?.querySelector("[data-session-picker]")',
            js,
        )
        self.assertNotIn("async function loadSummarySessions", js)
        self.assertNotIn("renderSummarySessionOptions", js)

    def test_search_picker_supports_multiple_selected_sessions(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'id="search-chat-picker" class="session-picker" '
            'data-session-picker data-filter="all" data-multiple="true"',
            html,
        )
        self.assertIn("picker.selectedUsernames.add(session.username);", js)
        self.assertIn("picker.selectedUsernames.delete(username);", js)
        self.assertIn(
            'picker.value.value = [...picker.selectedUsernames].join("\\n");',
            js,
        )
        self.assertIn("function renderSessionPickerChips", js)
        self.assertIn('class="session-picker-chip"', js)
        self.assertIn('aria-label="移除 ${escapeHtml(session.chat)}"', js)

    def test_escape_only_closes_picker_without_clearing_selected_value(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        escape_start = js.index('} else if (event.key === "Escape") {')
        escape_end = js.index("\n    }", escape_start)
        escape_block = js[escape_start:escape_end]

        self.assertIn("event.preventDefault();", escape_block)
        self.assertLess(
            escape_block.index("event.preventDefault();"),
            escape_block.index("setSessionPickerOpen(picker, false);"),
        )

    def test_web_uses_local_avatar_proxy_for_profile_sessions_and_messages(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn('id="profile-avatar"', html)
        self.assertIn('id="profile-name"', html)
        self.assertIn('fetchJson("/api/profile")', js)
        self.assertIn('`/api/avatar?url=${encodeURIComponent(url)}`', js)
        self.assertIn("session.avatar_url", js)
        self.assertIn("avatar_url: payload.data.avatar_url || \"\"", js)
        self.assertIn("allowRemoteAvatars: true", js)
        self.assertIn("allowRemoteMedia: false", js)

    def test_successful_initialization_refreshes_profile_and_session_choices(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "async function refreshAccountData(shouldApply = () => true)",
            js,
        )
        self.assertIn("sessionsLoaded = false;", js)
        self.assertIn(
            "await refreshAccountData(() => screenRequestVersions.get(screenId) === requestVersion);",
            js,
        )
        self.assertIn("loadProfile(shouldApply)", js)
        self.assertIn("loadSessions(shouldApply)", js)
        self.assertIn("if (!shouldApply()) return profile;", js)
        self.assertIn("if (!shouldApply()) return [];", js)
        self.assertIn("showSessionsError(sessionsResult.reason)", js)
        self.assertIn("resetSessionPickers();", js)

    def test_stale_session_requests_cannot_overwrite_or_show_errors(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        load_start = js.index("async function loadSessions")
        load_end = js.index("\n}\n", load_start)
        load_block = js[load_start:load_end]
        stale_guard = (
            "if (!shouldApply() || requestVersion !== sessionsRequestVersion) "
            "return [];"
        )

        self.assertIn("try {", load_block)
        self.assertIn("} catch (error) {", load_block)
        self.assertGreaterEqual(load_block.count(stale_guard), 2)
        self.assertLess(
            load_block.index(stale_guard, load_block.index("catch (error)")),
            load_block.index("throw error;"),
        )
        self.assertLess(
            load_block.index(stale_guard, load_block.index("payload = await fetchJson")),
            load_block.index("if (!payload.ok"),
        )

    def test_results_are_saved_and_restored_per_screen(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn("const screenResultStates = new Map();", js)
        self.assertIn("const screenRequestVersions = new Map();", js)
        self.assertIn("function saveResultState(screenId)", js)
        self.assertIn("function restoreResultState(screenId)", js)
        self.assertIn("function setResult(payload, screenId", js)
        self.assertIn("restoreResultState(id)", js)
        self.assertIn("screenRequestVersions.get(screenId) !== requestVersion", js)

    def test_async_errors_keep_the_originating_screen(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        self.assertIn("function showTransientError(error, screenId = currentScreenId)", js)
        self.assertIn('showTransientError(error, "setup")', js)
        self.assertIn('showTransientError(error, "dashboard")', js)

    def test_generic_result_fields_are_localized_to_chinese(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        expected_labels = {
            "chat": "聊天名称",
            "username": "账号",
            "is_group": "是否群聊",
            "unread": "未读数量",
            "last_message": "最后一条消息",
            "msg_type": "消息类型",
            "sender": "发送者",
            "timestamp": "时间戳",
            "time": "时间",
        }

        self.assertIn("const FIELD_LABELS = {", js)
        for key, label in expected_labels.items():
            self.assertIn(f'{key}: "{label}"', js)
        self.assertIn("fieldLabel(key)", js)
        self.assertIn('if (typeof value === "boolean") return value ? "是" : "否";', js)

    def test_history_page_has_reusable_chat_picker_and_day_inputs(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")
        css = (
            ROOT / "wechat_cli" / "web" / "static" / "app.css"
        ).read_text(encoding="utf-8")

        self.assertIn('<button data-target="history">聊天记录</button>', html)
        self.assertIn('id="history" class="screen" data-title="聊天记录"', html)
        self.assertNotIn('data-target="chat-summary"', html)
        self.assertNotIn('id="chat-summary"', html)
        self.assertIn('data-result-mode="summary"', html)
        self.assertIn(
            'id="history-chat-picker" class="session-picker" '
            'data-session-picker data-filter="all" data-multiple="false"',
            html,
        )
        self.assertEqual(html.count("data-default-today"), 2)
        self.assertIn('data-param="limit" type="hidden" value="50000"', html)
        self.assertIn(
            "async function loadSessions(shouldApply = () => true)",
            js,
        )
        self.assertIn("function renderSessionPickerOptions", js)
        self.assertIn("function formatSummaryCopy(data)", js)
        self.assertIn("function formatSummaryKeyCopy(data)", js)
        self.assertIn("`聊天记录 · ${summaryData.chat", js)
        self.assertNotIn("`聊天总结 · ${summaryData.chat", js)
        self.assertIn("const SUMMARY_PREVIEW_LIMIT = 200;", js)
        self.assertIn("共 ${items.length} 条，仅在网页预览前 ${previewItems.length} 条", js)
        self.assertIn("allowRemoteAvatars: true", js)
        self.assertIn("allowRemoteMedia: false", js)
        self.assertIn("function renderMessageMedia(item, { allowRemote = true } = {})", js)
        self.assertIn('class="session-picker-retry hidden"', html)
        self.assertIn("aria-activedescendant", html)
        self.assertIn("aria-selected", js)
        self.assertIn(".session-picker", css)
        self.assertIn(".summary-result-hero", css)

    def test_web_navigation_is_reduced_to_eight_focused_entries(self):
        html = (
            ROOT / "wechat_cli" / "web" / "static" / "index.html"
        ).read_text(encoding="utf-8")
        expected_buttons = [
            '<button data-target="dashboard" class="active">总览</button>',
            '<button data-target="setup">初始化</button>',
            '<button data-target="history">聊天记录</button>',
            '<button data-target="search">消息搜索</button>',
            '<button data-target="contacts">联系人</button>',
            '<button data-target="members">群聊成员统计和导出</button>',
            '<button data-target="stats">单个聊天数据统计</button>',
            '<button data-target="invite-stats">群聊成员邀请统计</button>',
        ]

        self.assertEqual(html.count("data-target="), len(expected_buttons))
        for button in expected_buttons:
            self.assertIn(button, html)
        for removed_id in ("sessions", "chat-summary", "export", "favorites", "unread"):
            self.assertNotIn(f'id="{removed_id}" class="screen', html)
        self.assertNotIn("快捷操作", html)
        self.assertIn("统计范围：从微信数据库记载的日子开始", html)

    def test_init_status_refresh_obeys_latest_request_version(self):
        js = (
            ROOT / "wechat_cli" / "web" / "static" / "app.js"
        ).read_text(encoding="utf-8")

        refresh_start = js.index("async function refreshStatus")
        refresh_end = js.index("\n}\n", refresh_start)
        refresh_block = js[refresh_start:refresh_end]
        self.assertLess(
            refresh_block.index("if (!shouldApply()) return status;"),
            refresh_block.index("initPill.textContent"),
        )
        self.assertIn(
            "await refreshStatus(() => screenRequestVersions.get(screenId) === requestVersion);",
            js,
        )

    @patch("wechat_cli.web.server.subprocess.run")
    def test_summary_response_omits_duplicate_messages_and_stdout(self, run_mock):
        run_mock.return_value = CompletedProcess(
            [],
            0,
            stdout=json.dumps({
                "chat": "项目群",
                "messages": ["[10:00] 张三: 原始文本"],
                "message_items": [{"time": "10:00", "sender": "张三", "text": "原始文本"}],
                "saved_media": [],
                "save_dir": None,
            }, ensure_ascii=False),
            stderr="",
        )

        payload = run_cli_command({
            "command": "history",
            "response_mode": "summary",
            "params": {
                "chat_name": "项目群",
                "start_time": "2026-07-29",
                "end_time": "2026-07-29",
                "limit": 50000,
            },
        })

        self.assertEqual(payload["stdout"], "")
        self.assertNotIn("messages", payload["data"])
        self.assertNotIn("saved_media", payload["data"])
        self.assertNotIn("save_dir", payload["data"])
        self.assertEqual(payload["data"]["message_items"][0]["text"], "原始文本")

    def test_builds_sessions_with_json_format(self):
        args = build_cli_args({
            "command": "sessions",
            "params": {"limit": 5},
        })

        self.assertEqual(args, ["sessions", "--limit", "5", "--format", "json"])

    def test_builds_search_with_multiple_chats_and_filters(self):
        args = build_cli_args({
            "command": "search",
            "params": {
                "keyword": "截止日期",
                "chat": ["项目组", "AI交流群"],
                "start_time": "2026-04-01",
                "end_time": "2026-04-30",
                "limit": 10,
                "offset": 5,
                "type": "file",
            },
        })

        self.assertEqual(args, [
            "search", "截止日期",
            "--chat", "项目组",
            "--chat", "AI交流群",
            "--start-time", "2026-04-01",
            "--end-time", "2026-04-30",
            "--limit", "10",
            "--offset", "5",
            "--format", "json",
            "--type", "file",
        ])

    def test_builds_search_without_keyword_when_time_range_is_complete(self):
        args = build_cli_args({
            "command": "search",
            "params": {
                "start_time": "2026-05-01",
                "end_time": "2026-05-13",
                "limit": 20,
            },
        })

        self.assertEqual(args, [
            "search",
            "--start-time", "2026-05-01",
            "--end-time", "2026-05-13",
            "--limit", "20",
            "--format", "json",
        ])

    def test_rejects_search_without_keyword_when_time_range_is_incomplete(self):
        with self.assertRaisesRegex(ValueError, "关键词为空"):
            build_cli_args({
                "command": "search",
                "params": {
                    "start_time": "2026-05-01",
                    "limit": 20,
                },
            })

    def test_search_keyword_field_is_optional_in_web_ui(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-param="keyword"', html)
        self.assertNotIn('data-param="keyword" required', html)

    def test_web_ui_static_assets_use_cache_busting_urls(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn('/static/app.css?v=', html)
        self.assertIn('/static/app.js?v=', html)

    def test_builds_init_with_db_dir_and_force(self):
        args = build_cli_args({
            "command": "init",
            "params": {
                "db_dir": r"D:\WeChat\db_storage",
                "force": True,
            },
        })

        self.assertEqual(args, ["init", "--db-dir", r"D:\WeChat\db_storage", "--force"])

    @patch("wechat_cli.web.server.detect_db_dir_candidates")
    def test_db_dir_candidates_payload_lists_detected_directories(self, detect_mock):
        detect_mock.return_value = [
            r"D:\weixin_download\xwechat_files\wxid_one\db_storage",
            r"D:\weixin_download\xwechat_files\wxid_two\db_storage",
        ]

        payload = db_dir_candidates_payload()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["candidates"][0]["path"], r"D:\weixin_download\xwechat_files\wxid_one\db_storage")
        self.assertEqual(payload["candidates"][0]["account"], "wxid_one")

    def test_setup_page_has_db_dir_selector_controls(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")

        self.assertIn('id="db-dir-candidates"', html)
        self.assertIn('id="detect-db-dirs"', html)
        self.assertIn('id="setup-db-dir"', html)

    def test_history_summary_requests_local_media_metadata_for_ai_copy(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "wechat_cli" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertNotIn('data-param="media" type="checkbox" checked', html)
        self.assertIn('id="history" class="screen" data-title="聊天记录"', html)
        self.assertIn('data-result-mode="summary"', html)
        self.assertIn('form.dataset.command === "history"', js)
        self.assertIn('params.media = true', js)
        summary_start = js.index("function summaryMessageLine")
        summary_end = js.index("\n}\n", summary_start)
        summary_block = js[summary_start:summary_end]
        self.assertIn("item?.transcript", summary_block)
        self.assertIn('startsWith("素材/")', summary_block)
        self.assertNotIn("media.url", summary_block)
        self.assertNotIn("media.path", summary_block)

    def test_history_result_has_key_info_copy_button(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "wechat_cli" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="copy-key-result"', html)
        self.assertIn("复制精简信息", html)
        self.assertIn('document.querySelector("#copy-key-result")', js)
        self.assertIn("let lastKeyText = \"\";", js)
        self.assertIn("function formatMessagesForKeyCopy(messages)", js)
        self.assertIn("Array.isArray(payload.data.messages)", js)
        self.assertIn("lastKeyText || (lastCopyData ? formatSummaryKeyCopy(lastCopyData)", js)
        self.assertIn("navigator.clipboard.writeText(copyText)", js)

    def test_own_private_chat_messages_align_next_to_avatar(self):
        css = (ROOT / "wechat_cli" / "web" / "static" / "app.css").read_text(encoding="utf-8")

        self.assertIn(".message-row.mine .message-main", css)
        self.assertIn("justify-items: end", css)
        self.assertIn(".message-row.mine .message-meta", css)
        self.assertIn("justify-content: flex-end", css)

    def test_web_ui_loads_db_dir_candidates_api(self):
        js = (ROOT / "wechat_cli" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('fetchJson("/api/db-dirs")', js)
        self.assertIn('renderDbDirCandidates', js)

    @patch("wechat_cli.web.server.subprocess.run")
    def test_run_cli_command_disables_interactive_stdin(self, run_mock):
        run_mock.return_value = CompletedProcess([], 0, stdout='{"ok": true}', stderr="")

        run_cli_command({"command": "init", "params": {"db_dir": r"D:\WeChat\db_storage"}})

        kwargs = run_mock.call_args.kwargs
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)

    def test_builds_export_without_forcing_json(self):
        args = build_cli_args({
            "command": "export",
            "params": {
                "chat_name": "张三",
                "format": "markdown",
                "start_time": "2026-04-01",
                "limit": 100,
            },
        })

        self.assertEqual(args, [
            "export", "张三",
            "--format", "markdown",
            "--start-time", "2026-04-01",
            "--limit", "100",
        ])

    def test_rejects_unknown_command(self):
        with self.assertRaises(ValueError):
            build_cli_args({"command": "shell", "params": {}})

    def test_rejects_unknown_parameter(self):
        with self.assertRaises(ValueError):
            build_cli_args({
                "command": "sessions",
                "params": {"limit": 5, "danger": "nope"},
            })

    @patch("wechat_cli.web.server.subprocess.run")
    def test_run_cli_command_forces_utf8_subprocess_output(self, run_mock):
        run_mock.return_value = CompletedProcess([], 0, stdout='{"ok": true}', stderr="")

        run_cli_command({"command": "sessions", "params": {"limit": 1}})

        kwargs = run_mock.call_args.kwargs
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["env"]["PYTHONIOENCODING"], "utf-8")
        self.assertEqual(kwargs["env"]["PYTHONUTF8"], "1")

    @patch("wechat_cli.web.server.subprocess.run")
    def test_run_cli_command_uses_frozen_executable_without_python_module_flag(self, run_mock):
        run_mock.return_value = CompletedProcess([], 0, stdout='{"ok": true}', stderr="")

        with patch.object(sys, "frozen", True, create=True):
            run_cli_command({"command": "sessions", "params": {"limit": 1}})

        argv = run_mock.call_args.args[0]
        self.assertEqual(argv[:2], [sys.executable, "sessions"])
        self.assertNotIn("-m", argv)

    def test_media_file_payload_serves_files_under_wechat_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            db_dir.mkdir()
            image = root / "msg" / "attach" / "a.jpg"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"\xff\xd8\xff\xe0jpeg")

            with patch("wechat_cli.web.server.status_payload", return_value={"db_dir": str(db_dir)}):
                payload = media_file_payload(str(image))

        self.assertEqual(payload["content_type"], "image/jpeg")
        self.assertEqual(payload["body"], b"\xff\xd8\xff\xe0jpeg")
        self.assertEqual(payload["filename"], "a.jpg")

    def test_media_file_payload_preserves_gif_download_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            db_dir.mkdir()
            image = root / "msg" / "attach" / "animated.gif"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"GIF89aanimated")

            with patch("wechat_cli.web.server.status_payload", return_value={"db_dir": str(db_dir)}):
                payload = media_file_payload(str(image))

        self.assertEqual(payload["content_type"], "image/gif")
        self.assertEqual(payload["body"], b"GIF89aanimated")
        self.assertEqual(payload["filename"], "animated.gif")

    def test_media_file_payload_saves_decoded_dat_gif_as_gif(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            db_dir = root / "db_storage"
            db_dir.mkdir()
            image = root / "msg" / "attach" / "animated.dat"
            image.parent.mkdir(parents=True)
            decoded = b"GIF89aanimated"
            key = 0x37
            image.write_bytes(bytes(byte ^ key for byte in decoded))

            with patch("wechat_cli.web.server.status_payload", return_value={"db_dir": str(db_dir)}):
                payload = media_file_payload(str(image))

        self.assertEqual(payload["content_type"], "image/gif")
        self.assertEqual(payload["body"], decoded)
        self.assertEqual(payload["filename"], "animated.gif")

    def test_media_file_payload_rejects_paths_outside_wechat_base(self):
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            db_dir = Path(allowed) / "db_storage"
            db_dir.mkdir()
            image = Path(outside) / "secret.jpg"
            image.write_bytes(b"\xff\xd8\xff\xe0jpeg")

            with patch("wechat_cli.web.server.status_payload", return_value={"db_dir": str(db_dir)}):
                with self.assertRaises(PermissionError):
                    media_file_payload(str(image))

    def test_decode_media_bytes_returns_svg_placeholder_for_modern_undecodable_dat(self):
        body, content_type = _decode_media_bytes(b"\x07\x08\x56\x32\x08\x07\x00\x04modern", "image.dat")

        self.assertEqual(content_type, "image/svg+xml; charset=utf-8")
        self.assertIn(b"DAT", body)
        self.assertIn(b"V2", body)

    def test_decode_media_bytes_extracts_clear_v2_dat_payload(self):
        payload = b"\xff\xd8\xff\xe0jpeg"
        raw = b"\x07\x08V2\x08\x07\x00\x04" + b"\x00" * 7 + payload + b"\x00" * 16

        body, content_type = _decode_media_bytes(raw, "image.dat")

        self.assertEqual(content_type, "image/jpeg")
        self.assertEqual(body, payload)

    def test_decode_media_bytes_extracts_v2_heic_payload(self):
        payload = b"\x00\x00\x00\x18ftypheic" + b"\x00" * 16
        raw = b"\x07\x08V2\x08\x07\x00\x04" + b"\x00" * 7 + payload + b"\x00" * 16

        body, content_type = _decode_media_bytes(raw, "image.dat")

        self.assertEqual(content_type, "image/heic")
        self.assertEqual(body, payload)


if __name__ == "__main__":
    unittest.main()
