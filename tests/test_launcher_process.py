import os
import inspect
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
from wechat_cli.windows.authenticode import AuthenticodePolicy


class FakeProcess:
    def __init__(self, command, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.returncode = None
        self.pid = kwargs.pop("pid", 1234)
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

        with patch("wechat_cli.launcher.process.os.name", "posix"):
            manager.stop(process, timeout_seconds=1)

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(0, process.kill_calls)

    def test_windows_stop_terminates_entire_process_tree(self):
        calls = []
        manager = ApplicationProcessManager(
            popen=lambda *_args, **_kwargs: None,
            tree_terminator=lambda pid: calls.append(pid),
        )
        process = FakeProcess([], shell=False, pid=4242)

        with patch("wechat_cli.launcher.process.os.name", "nt"):
            manager.stop(process, timeout_seconds=1)

        self.assertEqual([4242], calls)
        self.assertEqual(0, process.terminate_calls)
        self.assertEqual([1], process.wait_calls)

    def test_windows_stop_propagates_tree_termination_failure(self):
        def fail_tree_stop(_pid):
            raise OSError("tree stop failed")

        manager = ApplicationProcessManager(
            popen=lambda *_args, **_kwargs: None,
            tree_terminator=fail_tree_stop,
        )
        process = FakeProcess([], shell=False, pid=4242)

        with patch("wechat_cli.launcher.process.os.name", "nt"):
            with self.assertRaisesRegex(OSError, "tree stop failed"):
                manager.stop(process, timeout_seconds=1)

    def test_local_runtime_accepts_authenticode_policy_and_verifier(self):
        parameters = inspect.signature(LocalApplicationRuntime).parameters
        self.assertIn("authenticode_policy", parameters)
        self.assertIn("authenticode_verifier", parameters)

    def test_local_runtime_verifies_authenticode_before_process_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout, _ = self.make_layout(Path(tmp))
            session = layout.runtime_dir / "launch-session-test.json"
            session.write_text("{}", encoding="utf-8")
            starts = []
            verified = []

            class Manager:
                def start(self, launch):
                    starts.append(launch)
                    return FakeProcess(launch.command)

                def stop(self, process, timeout_seconds=5):
                    process.terminate()

            def reject_signature(path, policy):
                verified.append((path, policy))
                raise ValueError("signature rejected")

            runtime = LocalApplicationRuntime(
                layout,
                port=8787,
                process_manager=Manager(),
                authenticode_policy=AuthenticodePolicy(
                    required=True,
                    expected_subject="CN=Expected Publisher",
                ),
                authenticode_verifier=reject_signature,
            )

            with self.assertRaisesRegex(ValueError, "signature rejected"):
                runtime.start("0.5.0", session)

            self.assertEqual(1, len(verified))
            self.assertEqual(layout.version_path("0.5.0") / "wechat-cli.exe", verified[0][0])
            self.assertEqual([], starts)

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

    def test_local_runtime_stop_waits_until_port_is_released(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout, _ = self.make_layout(Path(tmp))
            process = FakeProcess([], shell=False)

            class Manager:
                def stop(self, stopped, timeout_seconds=5):
                    stopped.terminate()

            probes = []
            states = iter([True, False])
            runtime = LocalApplicationRuntime(
                layout,
                port=8787,
                process_manager=Manager(),
                port_probe=lambda port: probes.append(port) or next(states),
                stop_timeout_seconds=1.0,
                stop_interval_seconds=0.001,
                sleep=lambda _seconds: None,
            )
            runtime._process = process

            runtime.stop(process)

            self.assertEqual([8787, 8787], probes)
            self.assertIsNone(runtime._process)

    def test_local_runtime_stop_fails_if_port_remains_occupied(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout, _ = self.make_layout(Path(tmp))
            process = FakeProcess([], shell=False)

            class Manager:
                def stop(self, stopped, timeout_seconds=5):
                    stopped.terminate()

            runtime = LocalApplicationRuntime(
                layout,
                port=8787,
                process_manager=Manager(),
                port_probe=lambda _port: True,
                stop_timeout_seconds=0.01,
                stop_interval_seconds=0.001,
                sleep=lambda _seconds: None,
            )
            runtime._process = process

            with self.assertRaisesRegex(OSError, "port.*release"):
                runtime.stop(process)

            self.assertIs(process, runtime._process)

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

        with patch("wechat_cli.launcher.process.os.name", "posix"):
            manager.stop(process, timeout_seconds=0.1)

        self.assertEqual(1, process.terminate_calls)
        self.assertEqual(1, process.kill_calls)


if __name__ == "__main__":
    unittest.main()
