import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from wechat_cli.license.app_authorization import resolve_app_authorization
from wechat_cli.license.lease import TrustedTimeState
from wechat_cli.license.session import create_launch_session
from wechat_cli.license.storage import LicenseStateStorage, LocalLicenseState
from wechat_cli.update.layout import InstallLayout
from wechat_cli.version import APP_VERSION
from wechat_cli.windows.dpapi import TestOnlyDataProtector


class AppAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 4, 15, 0, tzinfo=timezone.utc)
        self.protector = TestOnlyDataProtector(
            b"app-authorization-test",
            allow_insecure_test_use=True,
        )

    def make_state(self):
        return LocalLicenseState(
            license_id="lic_01",
            license_key="WCL-SECRET",
            device_id="dev_01",
            device_token="wcdt_token.secret",
            lease_content=b'{"lease":true}',
            lease_signature=b"signature",
            local_launch_key=b"K" * 32,
            trusted_time=TrustedTimeState(
                last_server_time="2026-08-04T15:00:00Z",
                last_wall_clock="2026-08-04T15:00:00Z",
            ),
        )

    def test_source_development_mode_is_allowed_without_session(self):
        decision = resolve_app_authorization(
            environ={},
            frozen=False,
            now=self.now,
        )

        self.assertTrue(decision.valid)
        self.assertEqual("development_mode", decision.reason)

    def test_frozen_app_without_session_is_restricted(self):
        with tempfile.TemporaryDirectory() as tmp:
            decision = resolve_app_authorization(
                environ={"LOCALAPPDATA": tmp},
                frozen=True,
                now=self.now,
                protector=self.protector,
            )

        self.assertFalse(decision.valid)
        self.assertEqual("launch_session_missing", decision.reason)

    def test_required_session_loads_dpapi_state_and_consumes_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            state = self.make_state()
            LicenseStateStorage(
                layout.state_dir / "license-state.dat",
                self.protector,
            ).save(state)
            session_path = create_launch_session(
                runtime_dir=layout.runtime_dir,
                local_launch_key=state.local_launch_key,
                app_version=APP_VERSION,
                device_id=state.device_id,
                lease_content=state.lease_content,
                now=self.now,
            )

            decision = resolve_app_authorization(
                environ={
                    "LOCALAPPDATA": tmp,
                    "WECHAT_CLI_REQUIRE_LAUNCH_SESSION": "1",
                    "WECHAT_CLI_LAUNCH_SESSION_PATH": str(session_path),
                },
                frozen=False,
                now=self.now,
                protector=self.protector,
            )

            self.assertTrue(decision.valid)
            self.assertEqual("dev_01", decision.device_id)
            self.assertFalse(session_path.exists())

    def test_session_outside_runtime_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}", encoding="utf-8")

            decision = resolve_app_authorization(
                environ={
                    "LOCALAPPDATA": tmp,
                    "WECHAT_CLI_REQUIRE_LAUNCH_SESSION": "1",
                    "WECHAT_CLI_LAUNCH_SESSION_PATH": str(outside),
                },
                frozen=False,
                now=self.now,
                protector=self.protector,
            )

        self.assertFalse(decision.valid)
        self.assertEqual("launch_session_path_invalid", decision.reason)

    def test_corrupt_local_license_state_is_restricted(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            (layout.state_dir / "license-state.dat").write_bytes(b"corrupt")
            session_path = layout.runtime_dir / "launch-session-test.json"
            session_path.write_text("{}", encoding="utf-8")

            decision = resolve_app_authorization(
                environ={
                    "LOCALAPPDATA": tmp,
                    "WECHAT_CLI_REQUIRE_LAUNCH_SESSION": "1",
                    "WECHAT_CLI_LAUNCH_SESSION_PATH": str(session_path),
                },
                frozen=False,
                now=self.now,
                protector=self.protector,
            )

        self.assertFalse(decision.valid)
        self.assertEqual("local_state_corrupt", decision.reason)


if __name__ == "__main__":
    unittest.main()
