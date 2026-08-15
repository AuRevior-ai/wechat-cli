"""Start and stop versioned WeChat CLI application processes."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, MutableMapping, Sequence

from ..update.health import fetch_health_json, wait_for_health
from ..update.layout import InstallLayout
from ..version import PRODUCT
from ..windows.authenticode import AuthenticodePolicy, verify_windows_authenticode


@dataclass(frozen=True)
class ApplicationLaunch:
    command: list[str]
    environment: dict[str, str]
    working_directory: str


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def build_application_launch(
    layout: InstallLayout,
    *,
    version: str,
    session_path: str | Path,
    port: int,
    base_environment: Mapping[str, str] | None = None,
) -> ApplicationLaunch:
    if not 1 <= port <= 65535:
        raise ValueError("port must be between 1 and 65535")
    version_dir = layout.version_path(version)
    executable = version_dir / "wechat-cli.exe"
    if not executable.is_file():
        raise FileNotFoundError(executable)
    session = Path(session_path)
    if not session.is_absolute():
        session = layout.runtime_dir / session
    if not _is_under(session, layout.runtime_dir):
        raise ValueError("launch session path must be under the runtime directory")
    if not session.is_file():
        raise FileNotFoundError(session)
    environment = dict(os.environ if base_environment is None else base_environment)
    environment["WECHAT_CLI_REQUIRE_LAUNCH_SESSION"] = "1"
    environment["WECHAT_CLI_LAUNCH_SESSION_PATH"] = str(session)
    return ApplicationLaunch(
        command=[str(executable), "web", "--port", str(port)],
        environment=environment,
        working_directory=str(version_dir),
    )


def _loopback_port_is_occupied(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def _terminate_windows_process_tree(pid: int) -> None:
    subprocess.run(
        ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
    )


class LocalApplicationRuntime:
    def __init__(
        self,
        layout: InstallLayout,
        *,
        port: int,
        process_manager: "ApplicationProcessManager | None" = None,
        health_fetcher: Callable[[str], Mapping[str, object]] = fetch_health_json,
        timeout_seconds: float = 30.0,
        interval_seconds: float = 0.5,
        port_probe: Callable[[int], bool] = _loopback_port_is_occupied,
        stop_timeout_seconds: float = 5.0,
        stop_interval_seconds: float = 0.05,
        sleep: Callable[[float], None] = time.sleep,
        authenticode_policy: AuthenticodePolicy | None = None,
        authenticode_verifier: Callable[..., object] = verify_windows_authenticode,
    ) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout_seconds <= 0 or interval_seconds <= 0:
            raise ValueError("health timeout and interval must be positive")
        if stop_timeout_seconds <= 0 or stop_interval_seconds <= 0:
            raise ValueError("stop timeout and interval must be positive")
        self.layout = layout
        self.port = port
        self.process_manager = process_manager or ApplicationProcessManager()
        self.health_fetcher = health_fetcher
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
        self._port_probe = port_probe
        self._stop_timeout_seconds = stop_timeout_seconds
        self._stop_interval_seconds = stop_interval_seconds
        self._sleep = sleep
        self._authenticode_policy = authenticode_policy
        self._authenticode_verifier = authenticode_verifier
        self._process = None

    @property
    def health_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/api/health"

    def start(self, version: str, session_path: Path):
        launch = build_application_launch(
            self.layout,
            version=version,
            session_path=session_path,
            port=self.port,
        )
        if self._authenticode_policy is not None:
            self._authenticode_verifier(
                Path(launch.command[0]),
                self._authenticode_policy,
            )
        self._process = self.process_manager.start(launch)
        return self._process

    def wait_healthy(self, version: str):
        def fetch():
            if self._process is None:
                raise OSError("application process has not been started")
            returncode = self._process.poll()
            if returncode is not None:
                raise OSError(f"application process exited with code {returncode}")
            return self.health_fetcher(self.health_url)

        return wait_for_health(
            fetch,
            expected_product=PRODUCT,
            expected_version=version,
            timeout_seconds=self.timeout_seconds,
            interval_seconds=self.interval_seconds,
        )

    def stop(self, process) -> None:
        self.process_manager.stop(process)
        deadline = time.monotonic() + self._stop_timeout_seconds
        while self._port_probe(self.port):
            if time.monotonic() >= deadline:
                raise OSError("application port did not release after process stop")
            self._sleep(self._stop_interval_seconds)
        if process is self._process:
            self._process = None


class ApplicationProcessManager:
    def __init__(
        self,
        *,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
        tree_terminator: Callable[[int], None] = _terminate_windows_process_tree,
    ) -> None:
        self._popen = popen
        self._tree_terminator = tree_terminator

    def start(self, launch: ApplicationLaunch):
        stdin = open(os.devnull, "rb")
        kwargs = {
            "cwd": launch.working_directory,
            "env": launch.environment,
            "stdin": stdin,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "shell": False,
        }
        if os.name == "nt":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            return self._popen(launch.command, **kwargs)
        finally:
            stdin.close()

    def stop(self, process, *, timeout_seconds: float = 5.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if process is None or process.poll() is not None:
            return
        if os.name == "nt":
            self._tree_terminator(int(process.pid))
            try:
                process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                raise OSError("application process tree did not stop in time") from exc
            return
        process.terminate()
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout_seconds)
