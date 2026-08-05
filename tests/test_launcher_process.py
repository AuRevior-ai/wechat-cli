import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.launcher.process import (
    ApplicationLaunch,
    ApplicationProcessManager,
    LocalApplicationRuntime,
    build_application_launch,
)
from wechat_cli.update.layout import InstallLayout


class FakeProcess:
    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = None
        self.terminate_calls = 0
        self.kill_calls = 0
        self.wait_calls = []

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminate_calls += 1
        self.returncode = 0

    def kill(self):
        self.kill_calls += 1
        self.returncode = -9

    def wait(self, timeout=None):
        self.wait_calls.append(timeout)
        return self.returncode


class LauncherProcessTests(unittest.TestCase):
    def make_layout(self, root: Path):
        layout = InstallLayout(root / "WeChatCliWeb")
        layout.ensure_directories()
        version_dir = layout.version_path("0.5.0")
        version_dir.mkdir()
        executable = version_dir / "wechat-cli.exe"
        executable.write_bytes(b"binary")
        return layout, executable

    def test_build_launch_uses_session_path_in_environment_not_command_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout, executable = self.make_layout(Path(tmp))
            session = layout.runtime_dir / "launch-session-test.json"
            session.write_text("{}", encoding="utf-8")

            launch = build_application_launch(
                layout,
                version="0.5.0",
                session_path=session,
                port=8787,
                base_environment={"PATH": "test-path"},
            )

            self.assertEqual(
                [str(executable), "web", "--port", "8787"],
                launch.command,
            )
            self.assertEqual(str(session), launch.environment["WECHAT_CLI_LAUNCH_SESSION_PATH"])
            self.assertEqual("1", launch.environment["WECHAT_CLI_REQUIRE_LAUNCH_SESSION"])
            self.assertNotIn(str(session), " ".join(launch.command))
            self.assertNotIn("license", " ".join(launch.command).lower())
            self.assertEqual(str(executable.parent), launch.working_directory)

    def test_build_launch_rejects_missing_executable_or_outside_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = InstallLayout(Path(tmp) / "WeChatCliWeb")
            layout.ensure_directories()
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}", encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                build_application_launch(
                    layout,
                    version="0.5.0",
                    session_path=layout.runtime_dir / "session.json",
                    port=8787,
                )

            version_dir = layout.version_path("0.5.0")
            version_dir.mkdir()
            (version_dir / "wechat-cli.exe").write_bytes(b"binary")
            with self.assertRaises(ValueError):
                build_application_launch(
                    layout,
                    version="0.5.0",
                    session_path=outside,
                    port=8787,
                )

    def test_process_manager_starts_without_shell_and_with_hidden_stdin(self):
        created = []

        def factory(command, **kwargs):
            process = FakeProcess(command, **kwargs)
            created.append(process)
            return process

        manager = ApplicationProcessManager(popen=factory)
        launch = ApplicationLaunch(
            command=[r"C:\App\wechat-cli.exe", "web", "--port", "8787"],
            environment={"PATH": "x"},
            working_directory=r"C:\App",
        )

        process = manager.start(launch)

        self.assertIs(process, created[0])
        self.assertFalse(created[0].kwargs["shell"])
        self.assertEqual(os.devnull, created[0].kwargs["stdin"].name)
        self.assertEqual(r"C:\App", created[0].kwargs["cwd"])
        self.assertEqual({"PATH": "x"}, created[0].kwargs["env"])
        created[0].kwargs["stdin"].close()

    def test_stop_terminates_then_kills_only_on_timeout(self):
        manager = ApplicationProcessManager(popen=lambda *_args, **_kwargs: None)
        process = FakeProcess([], shell=False)

        manager.stop(process, timeout_seconds=1)

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(0, process.kill_calls)

    def test_local_runtime_builds_launch_and_waits_for_expected_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout, _ = self.make_layout(Path(tmp))
            session = layout.runtime_dir / "launch-session-test.json"
            session.write_text("{}", encoding="utf-8")
            started = []

            class Manager:
                def start(self, launch):
                    process = FakeProcess(launch.command, **{"launch": launch})
                    started.append(process)
                    return process

                def stop(self, process, timeout_seconds=5):
                    process.terminate()

            health_calls = []

            def fetch(url):
                health_calls.append(url)
                return {
                    "status": "ok",
                    "product": "wechat-cli-web",
                    "version": "0.5.0",
                    "build_id": "dev",
                    "config_loaded": True,
                    "license_session_valid": True,
                    "core_modules": {"server": "ok", "storage": "ok", "routes": "ok"},
                }

            runtime = LocalApplicationRuntime(
                layout,
                port=8787,
                process_manager=Manager(),
                health_fetcher=fetch,
                timeout_seconds=2,
            )

            process = runtime.start("0.5.0", session)
            payload = runtime.wait_healthy("0.5.0")

            self.assertIs(process, started[0])
            self.assertEqual("ok", payload["status"])
            self.assertEqual(["http://127.0.0.1:8787/api/health"], health_calls)

    def test_local_runtime_detects_process_exit_during_health_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout, _ = self.make_layout(Path(tmp))
            session = layout.runtime_dir / "launch-session-test.json"
            session.write_text("{}", encoding="utf-8")
            process = FakeProcess([], shell=False)
            process.returncode = 7

            class Manager:
                def start(self, launch):
                    return process

                def stop(self, process, timeout_seconds=5):
                    pass

            runtime = LocalApplicationRuntime(
                layout,
                port=8787,
                process_manager=Manager(),
                health_fetcher=lambda _url: {},
                timeout_seconds=0.01,
                interval_seconds=0.005,
            )
            runtime.start("0.5.0", session)

            with self.assertRaises(Exception) as caught:
                runtime.wait_healthy("0.5.0")

            self.assertIn("exited", str(caught.exception))

    def test_stop_kills_process_that_does_not_exit(self):
        class StubbornProcess(FakeProcess):
            def terminate(self):
                self.terminate_calls += 1

            def wait(self, timeout=None):
                self.wait_calls.append(timeout)
                if self.kill_calls == 0:
                    import subprocess

                    raise subprocess.TimeoutExpired("app", timeout)
                return -9

        manager = ApplicationProcessManager(popen=lambda *_args, **_kwargs: None)
        process = StubbornProcess([], shell=False)

        manager.stop(process, timeout_seconds=0.1)

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(1, process.kill_calls)


if __name__ == "__main__":
    unittest.main()
