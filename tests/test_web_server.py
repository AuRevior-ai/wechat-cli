import unittest
import sys
import subprocess
import tempfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

from wechat_cli.web.server import _decode_media_bytes, build_cli_args, db_dir_candidates_payload, media_file_payload, run_cli_command


ROOT = Path(__file__).resolve().parents[1]


class BuildCliArgsTests(unittest.TestCase):
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

    def test_history_media_resolution_is_enabled_by_default(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "wechat_cli" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('data-param="media" type="checkbox" checked', html)
        self.assertIn('form.dataset.command === "history"', js)
        self.assertIn('params.media = true', js)

    def test_history_result_has_key_info_copy_button(self):
        html = (ROOT / "wechat_cli" / "web" / "static" / "index.html").read_text(encoding="utf-8")
        js = (ROOT / "wechat_cli" / "web" / "static" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="copy-key-result"', html)
        self.assertIn("复制关键信息", html)
        self.assertIn('document.querySelector("#copy-key-result")', js)
        self.assertIn("let lastKeyText = \"\";", js)
        self.assertIn("function formatMessagesForKeyCopy(messages)", js)
        self.assertIn("Array.isArray(payload.data.messages)", js)
        self.assertIn("navigator.clipboard.writeText(lastKeyText)", js)

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
