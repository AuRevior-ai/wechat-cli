"""Command-line entry point for the Windows Launcher executable."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import click

from ..license.client import LicenseApiClient, UrllibJsonTransport
from ..license.device_identity import DeviceIdentityProvider, read_current_user_sid
from ..license.models import ClientLicenseState
from ..license.storage import LicenseStateStorage
from ..update.client import UpdateApiClient
from ..update.health import fetch_health_json, validate_health_payload
from ..update.layout import InstallLayout
from ..update.prepare import prepare_checked_update
from ..update.transaction import TransactionState, UpdateTransactionEngine
from ..version import ARCHITECTURE, LAUNCHER_VERSION, PLATFORM, PRODUCT
from ..windows.dpapi import WindowsDpapiProtector
from .config import LauncherConfig
from .locks import LauncherInstanceLock, default_launcher_mutex_name
from .process import LocalApplicationRuntime
from .service import LauncherResult, LauncherService, LauncherStatus
from .ui_controller import LauncherUiController
from .webview import LauncherWindow


_SUCCESS_STATUSES = {
    LauncherStatus.STARTED,
    LauncherStatus.UPDATED,
    LauncherStatus.ROLLED_BACK,
}


def _default_config_path(layout: InstallLayout) -> Path:
    return layout.launcher_dir / "launcher-config.json"


def _allow_loopback(config_path: Path) -> bool:
    return os.environ.get("WECHAT_CLI_ALLOW_INSECURE_LOOPBACK", "").lower() in {
        "1",
        "true",
        "yes",
    }


def _transport(config: LauncherConfig) -> UrllibJsonTransport:
    parsed = urlparse(config.api_base_url)
    return UrllibJsonTransport(
        config.api_base_url,
        allow_insecure_loopback=(parsed.scheme == "http"),
    )


def _build_service(
    layout: InstallLayout,
    config: LauncherConfig,
) -> tuple[LauncherService, LicenseStateStorage]:
    protector = WindowsDpapiProtector()
    storage = LicenseStateStorage(
        layout.state_dir / "license-state.dat",
        protector,
    )
    license_client = LicenseApiClient(_transport(config))
    runtime = LocalApplicationRuntime(layout, port=config.port)
    service = LauncherService(
        layout=layout,
        state_storage=storage,
        license_client=license_client,
        lease_keys=config.lease_keys,
        runtime=runtime,
    )
    return service, storage


def _existing_application_is_healthy(config: LauncherConfig) -> bool:
    try:
        payload = fetch_health_json(
            f"http://127.0.0.1:{config.port}/api/health",
            timeout_seconds=1.0,
        )
        current_version = payload.get("version")
        if not isinstance(current_version, str):
            return False
        validate_health_payload(
            payload,
            expected_product=PRODUCT,
            expected_version=current_version,
        )
        return True
    except Exception:
        return False


def _open_application(config: LauncherConfig) -> None:
    webbrowser.open(f"http://127.0.0.1:{config.port}")


def _background_command(config_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        command = [sys.executable, "--download-update"]
    else:
        command = [sys.executable, "-m", "wechat_cli.launcher.cli", "--download-update"]
    command.extend(["--config-path", str(config_path)])
    return command


def _spawn_background_update(config_path: Path) -> None:
    stdin = open(os.devnull, "rb")
    try:
        kwargs = {
            "stdin": stdin,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "shell": False,
            "close_fds": True,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0)
                | getattr(subprocess, "DETACHED_PROCESS", 0)
            )
        subprocess.Popen(_background_command(config_path), **kwargs)
    finally:
        stdin.close()


def _run_update_download(
    layout: InstallLayout,
    config: LauncherConfig,
    storage: LicenseStateStorage,
) -> int:
    state = storage.load()
    if state is None:
        click.echo("尚未激活，无法检查更新。", err=True)
        return 2
    current = layout.load_current()
    client = UpdateApiClient(
        _transport(config),
        trusted_keys=config.release_keys,
    )
    failed_versions = UpdateTransactionEngine(
        layout
    ).failed_versions.failed_versions()
    result = client.check(
        device_token=state.device_token,
        current_version=current.current_version,
        launcher_version=LAUNCHER_VERSION,
        channel=current.channel,
        platform=PLATFORM,
        architecture=ARCHITECTURE,
        product=PRODUCT,
        device_id=state.device_id,
        failed_versions=failed_versions,
    )
    if not result.update_available:
        return 0
    pending = prepare_checked_update(
        result,
        layout,
        download_url=config.update_download_url,
    )
    click.echo(f"更新 {pending.version} 已下载，将在下次启动安装。")
    return 0


def _repair(layout: InstallLayout) -> int:
    layout.ensure_directories()
    engine = UpdateTransactionEngine(layout)
    transaction = engine.load()
    if transaction is not None and transaction.state in {
        TransactionState.SWITCHING,
        TransactionState.STARTING,
        TransactionState.HEALTH_CHECKING,
        TransactionState.ROLLING_BACK,
    }:
        engine.recover_interrupted(
            failed_at=datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
            reason="manual_repair",
        )
    try:
        current = layout.load_current()
    except Exception as exc:
        click.echo(f"当前版本指针无法读取：{exc}", err=True)
        return 3
    executable = layout.version_path(current.current_version) / "wechat-cli.exe"
    if not executable.is_file():
        click.echo(f"当前版本程序缺失：{executable}", err=True)
        return 3
    click.echo(f"安装结构正常，当前版本：{current.current_version}")
    return 0


def _show_launcher_window(
    *,
    service: LauncherService,
    storage: LicenseStateStorage,
    config: LauncherConfig,
    layout: InstallLayout,
    config_path: Path,
    initial_result: LauncherResult,
) -> int:
    window = LauncherWindow()

    def close_window() -> None:
        if window.window is not None:
            window.window.destroy()

    def on_success(_result: LauncherResult) -> None:
        _open_application(config)
        _spawn_background_update(config_path)
        close_window()

    def retry_update() -> dict[str, object]:
        exit_code = _run_update_download(layout, config, storage)
        if exit_code == 0:
            return {
                "status": "ready",
                "message": "更新检查完成。发现的新版本将在下次启动安装。",
                "current_version": layout.load_current().current_version,
                "can_retry_update": False,
                "can_retry_validation": False,
                "can_start": True,
            }
        return {
            "status": "update_failed",
            "message": "更新检查未完成，当前版本仍可继续使用。",
            "error_code": "UPD-RETRY-FAILED",
            "can_retry_update": True,
            "can_retry_validation": False,
            "can_start": True,
        }

    controller = LauncherUiController(
        service=service,
        storage=storage,
        identity_provider=DeviceIdentityProvider(),
        fingerprint_salt=config.fingerprint_salt,
        layout=layout,
        initial_result=initial_result,
        success_handler=on_success,
        retry_update_handler=retry_update,
        close_handler=close_window,
    )
    window.show(controller.create_bridge())
    final_state = controller.get_ui_state()
    if final_state.get("status") in {"ready", "update_failed"}:
        return 0
    if final_state.get("status") == "activation_required":
        return 2
    return 3


def run_launcher_mode(
    mode: str,
    *,
    config_path: str | None,
) -> int:
    if os.name != "nt":
        click.echo("WeChat CLI Launcher 当前仅支持 Windows。", err=True)
        return 4
    layout = InstallLayout.from_environment()
    path = Path(config_path) if config_path else _default_config_path(layout)
    config = LauncherConfig.load(
        path,
        allow_insecure_loopback=_allow_loopback(path),
    )
    mutex_name = default_launcher_mutex_name(read_current_user_sid())
    if mode == "download-update":
        lock = LauncherInstanceLock(mutex_name + "-Update")
    else:
        lock = LauncherInstanceLock(mutex_name)

    with lock:
        if mode == "repair":
            return _repair(layout)
        service, storage = _build_service(layout, config)
        if mode == "download-update":
            return _run_update_download(layout, config, storage)
        if mode not in {"start", "activate", "apply-update"}:
            raise ValueError(f"unknown launcher mode: {mode}")

        if mode == "activate":
            current = layout.load_current()
            return _show_launcher_window(
                service=service,
                storage=storage,
                config=config,
                layout=layout,
                config_path=path,
                initial_result=LauncherResult(
                    LauncherStatus.ACTIVATION_REQUIRED,
                    version=current.current_version,
                    license_state=ClientLicenseState.UNACTIVATED,
                    reason="manual_activation",
                ),
            )

        if mode == "start" and _existing_application_is_healthy(config):
            _open_application(config)
            _spawn_background_update(path)
            return 0
        result = service.start()
        if result.status in _SUCCESS_STATUSES:
            _open_application(config)
            _spawn_background_update(path)
            return 0
        return _show_launcher_window(
            service=service,
            storage=storage,
            config=config,
            layout=layout,
            config_path=path,
            initial_result=result,
        )


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--activate", is_flag=True, help="激活许可证后启动应用。")
@click.option("--download-update", is_flag=True, help="检查并准备后台更新。")
@click.option("--apply-update", is_flag=True, help="安装待更新版本并启动。")
@click.option("--repair", is_flag=True, help="检查并修复安装事务。")
@click.option(
    "--config-path",
    type=click.Path(path_type=str, dir_okay=False),
    hidden=True,
)
def cli(
    activate: bool,
    download_update: bool,
    apply_update: bool,
    repair: bool,
    config_path: str | None,
) -> None:
    """Start, activate, update, or repair WeChat CLI Web."""

    selected = [
        name
        for name, enabled in (
            ("activate", activate),
            ("download-update", download_update),
            ("apply-update", apply_update),
            ("repair", repair),
        )
        if enabled
    ]
    if len(selected) > 1:
        raise click.UsageError("Only one launcher mode may be selected at a time.")
    mode = selected[0] if selected else "start"
    try:
        exit_code = run_launcher_mode(
            mode,
            config_path=config_path,
        )
    except Exception as exc:
        click.echo(f"Launcher 错误：{exc}", err=True)
        raise click.exceptions.Exit(3) from exc
    raise click.exceptions.Exit(exit_code)


if __name__ == "__main__":
    cli()
