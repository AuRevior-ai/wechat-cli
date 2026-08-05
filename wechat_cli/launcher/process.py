"""Start and stop versioned WeChat CLI application processes."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, MutableMapping, Sequence

from ..update.health import fetch_health_json, wait_for_health
from ..update.layout import InstallLayout
from ..version import PRODUCT


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
    ) -> None:
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if timeout_seconds <= 0 or interval_seconds <= 0:
            raise ValueError("health timeout and interval must be positive")
        self.layout = layout
        self.port = port
        self.process_manager = process_manager or ApplicationProcessManager()
        self.health_fetcher = health_fetcher
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
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
        if process is self._process:
            self._process = None


class ApplicationProcessManager:
    def __init__(
        self,
        *,
        popen: Callable[..., subprocess.Popen] = subprocess.Popen,
    ) -> None:
        self._popen = popen

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
        process.terminate()
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=timeout_seconds)
