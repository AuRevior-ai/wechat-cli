"""Sole-administrator CLI for licenses, devices, releases, and diagnostics."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Mapping, Sequence

import click

from ..windows.dpapi import WindowsDpapiProtector
from .bootstrap import generate_demo_bootstrap, write_demo_bootstrap
from .client import (
    AdminApiClient,
    AdminApiError,
    UrllibAdminDownloadTransport,
    UrllibAdminJsonTransport,
)
from .config import AdminConfig, AdminConfigStorage, default_admin_config_path
from .csv_export import export_license_csv
from .session import login_and_store_admin_session


def _nonce() -> str:
    return "op_" + uuid.uuid4().hex


def _storage(config_path: str | None) -> AdminConfigStorage:
    path = Path(config_path) if config_path else default_admin_config_path()
    return AdminConfigStorage(path, WindowsDpapiProtector())


def _load_client(config_path: str | None) -> AdminApiClient:
    config = _storage(config_path).load()
    if config is None:
        raise click.ClickException(
            "尚未配置管理员 API。请先运行 wechat-cli-admin config set。"
        )
    try:
        credential = config.api_credential()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    return AdminApiClient(
        UrllibAdminJsonTransport(
            config.api_base_url,
            allow_insecure_loopback=config.allow_insecure_loopback,
        ),
        admin_token=credential,
        download_transport=UrllibAdminDownloadTransport(
            config.api_base_url,
            allow_insecure_loopback=config.allow_insecure_loopback,
        ),
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"not JSON serializable: {type(value).__name__}")


def _emit(ctx: click.Context, value: Any) -> None:
    if bool(ctx.find_root().obj.get("json")):
        click.echo(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=_json_default,
            )
        )
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            click.echo(f"{key}: {item}")
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if not value:
            click.echo("没有记录。")
            return
        for item in value:
            if isinstance(item, Mapping):
                click.echo("  ".join(f"{key}={entry}" for key, entry in item.items()))
            else:
                click.echo(str(item))
        return
    click.echo(str(value))


def _client(ctx: click.Context) -> AdminApiClient:
    return _load_client(ctx.find_root().obj.get("config_path"))


def _run_admin(action):
    try:
        return action()
    except AdminApiError as exc:
        raise click.ClickException(str(exc)) from exc


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--json", "json_output", is_flag=True, help="输出机器可读 JSON。")
@click.option(
    "--config-path",
    type=click.Path(path_type=str, dir_okay=False),
    help="覆盖 DPAPI 管理员配置文件路径。",
)
@click.pass_context
def cli(ctx: click.Context, json_output: bool, config_path: str | None) -> None:
    """管理 WeChat CLI 永久许可证、设备、发布与诊断包。"""

    ctx.ensure_object(dict)
    ctx.obj.update(json=json_output, config_path=config_path)


@cli.group("bootstrap")
def bootstrap_group() -> None:
    """生成 Demo Worker 密钥和首个管理员令牌。"""


@bootstrap_group.command("demo")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    required=True,
    help="新建的敏感输出目录；已有文件绝不覆盖。",
)
@click.pass_context
def bootstrap_demo(ctx: click.Context, output_dir: Path) -> None:
    artifacts = generate_demo_bootstrap()
    try:
        paths = write_demo_bootstrap(output_dir, artifacts)
    except FileExistsError as exc:
        raise click.ClickException(f"输出文件已存在，未覆盖：{exc.filename}") from exc
    _emit(ctx, {name: path.as_posix() for name, path in paths.items()})


@cli.group("config")
def config_group() -> None:
    """配置管理员 API 地址与受保护令牌。"""


@config_group.command("set")
@click.option("--api-url", required=True, help="Worker HTTPS API 根地址。")
@click.option(
    "--allow-insecure-loopback",
    is_flag=True,
    help="仅本地开发时允许 HTTP loopback。",
)
@click.pass_context
def config_set(
    ctx: click.Context,
    api_url: str,
    allow_insecure_loopback: bool,
) -> None:
    token = click.prompt("本地管理员令牌", hide_input=True).strip()
    config = AdminConfig(
        api_base_url=api_url,
        environment="local",
        legacy_admin_token=token,
        allow_insecure_loopback=allow_insecure_loopback,
    )
    storage = _storage(ctx.find_root().obj.get("config_path"))
    storage.save(config)
    _emit(
        ctx,
        {
            "configured": True,
            "api_base_url": config.api_base_url,
            "config_path": str(storage.path),
        },
    )


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    storage = _storage(ctx.find_root().obj.get("config_path"))
    config = storage.load()
    if config is None:
        raise click.ClickException("管理员配置不存在。")
    credential = config.session_token or config.legacy_admin_token or ""
    _emit(
        ctx,
        {
            "api_base_url": config.api_base_url,
            "environment": config.environment,
            "credential_type": "session" if config.session_token else "legacy_local",
            "credential_hint": "••••" + credential[-4:],
            "session_expires_at": config.session_expires_at,
            "allow_insecure_loopback": config.allow_insecure_loopback,
            "config_path": str(storage.path),
        },
    )


@cli.command("login")
@click.option("--api-url", required=True, help="Access 保护的 Worker HTTPS API 根地址。")
@click.option(
    "--environment",
    type=click.Choice(["staging", "production"]),
    required=True,
    help="目标管理员环境。",
)
@click.pass_context
def login_command(ctx: click.Context, api_url: str, environment: str) -> None:
    storage = _storage(ctx.find_root().obj.get("config_path"))
    try:
        result = login_and_store_admin_session(
            api_base_url=api_url,
            environment=environment,
            storage=storage,
        )
    except (AdminApiError, OSError, TimeoutError, ValueError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(
        ctx,
        {
            "principal_id": result.get("principal_id"),
            "expires_at": result.get("expires_at"),
            "api_base_url": api_url.rstrip("/"),
            "environment": environment,
            "config_path": str(storage.path),
        },
    )


@cli.group("licenses")
def licenses_group() -> None:
    """创建、搜索和更改许可证状态。"""


@licenses_group.command("create")
@click.option("--maximum-devices", type=click.IntRange(1, 100), default=3, show_default=True)
@click.option("--channel", type=click.Choice(["stable", "beta"]), default="stable")
@click.option("--email")
@click.option("--wechat")
@click.option("--other")
@click.option("--notes")
@click.pass_context
def license_create(
    ctx: click.Context,
    maximum_devices: int,
    channel: str,
    email: str | None,
    wechat: str | None,
    other: str | None,
    notes: str | None,
) -> None:
    contacts = {
        key: value
        for key, value in {
            "email": email,
            "wechat": wechat,
            "other": other,
            "notes": notes,
        }.items()
        if value
    }
    result = _run_admin(
        lambda: _client(ctx).create_license(
            maximum_devices=maximum_devices,
            release_channel=channel,
            contacts=contacts,
            operation_nonce=_nonce(),
        )
    )
    _emit(ctx, result)


@licenses_group.command("batch-create")
@click.option("--count", type=click.IntRange(1, 100), required=True)
@click.option("--maximum-devices", type=click.IntRange(1, 100), default=3, show_default=True)
@click.option("--channel", type=click.Choice(["stable", "beta"]), default="stable")
@click.option(
    "--output",
    type=click.Path(path_type=Path, dir_okay=False),
    required=True,
    help="新建的敏感 CSV；已有文件绝不覆盖。",
)
@click.pass_context
def license_batch_create(
    ctx: click.Context,
    count: int,
    maximum_devices: int,
    channel: str,
    output: Path,
) -> None:
    rows = _run_admin(
        lambda: _client(ctx).batch_create_licenses(
            count=count,
            maximum_devices=maximum_devices,
            release_channel=channel,
            operation_nonce=_nonce(),
        )
    )
    try:
        export_license_csv(output, rows)
    except FileExistsError as exc:
        raise click.ClickException(f"输出文件已存在，未覆盖：{output}") from exc
    if bool(ctx.find_root().obj.get("json")):
        _emit(ctx, {"count": len(rows), "output": str(output)})
    else:
        click.echo(f"已写入 {len(rows)} 个许可证：{output}")


@licenses_group.command("list")
@click.option("--query", help="许可证 ID、后四位或精确联系方式。")
@click.option("--status", type=click.Choice(["active", "suspended", "revoked"]))
@click.option("--limit", type=click.IntRange(1, 200), default=50)
@click.pass_context
def license_list(
    ctx: click.Context,
    query: str | None,
    status: str | None,
    limit: int,
) -> None:
    result = _run_admin(
        lambda: _client(ctx).list_licenses(
            query=query,
            status=status,
            limit=limit,
        )
    )
    _emit(ctx, result)


@licenses_group.command("status")
@click.argument("license_id")
@click.argument("status", type=click.Choice(["active", "suspended", "revoked"]))
@click.pass_context
def license_status(ctx: click.Context, license_id: str, status: str) -> None:
    result = _run_admin(
        lambda: _client(ctx).set_license_status(
            license_id,
            status,
            _nonce(),
        )
    )
    _emit(ctx, result)


@cli.group("devices")
def devices_group() -> None:
    """查看、停用、启用或解绑设备。"""


@devices_group.command("list")
@click.argument("license_id")
@click.pass_context
def device_list(ctx: click.Context, license_id: str) -> None:
    _emit(ctx, _run_admin(lambda: _client(ctx).list_devices(license_id)))


@devices_group.command("status")
@click.argument("device_id")
@click.argument("status", type=click.Choice(["active", "disabled"]))
@click.pass_context
def device_status(ctx: click.Context, device_id: str, status: str) -> None:
    _emit(
        ctx,
        _run_admin(
            lambda: _client(ctx).set_device_status(
                device_id,
                status,
                _nonce(),
            )
        ),
    )


@devices_group.command("unbind")
@click.argument("device_id")
@click.option("--yes", is_flag=True, help="跳过确认。")
@click.pass_context
def device_unbind(ctx: click.Context, device_id: str, yes: bool) -> None:
    if not yes and not click.confirm(f"确定永久解绑设备 {device_id}？"):
        raise click.Abort()
    _emit(
        ctx,
        _run_admin(lambda: _client(ctx).unbind_device(device_id, _nonce())),
    )


@cli.group("releases")
def releases_group() -> None:
    """查看、启用、暂停和调整发布比例。"""


@releases_group.command("list")
@click.pass_context
def release_list(ctx: click.Context) -> None:
    _emit(ctx, _run_admin(lambda: _client(ctx).list_releases()))


def _update_release(
    ctx: click.Context,
    release_id: str,
    **changes: Any,
) -> None:
    _emit(
        ctx,
        _run_admin(
            lambda: _client(ctx).update_release(
                release_id,
                operation_nonce=_nonce(),
                **changes,
            )
        ),
    )


@releases_group.command("enable")
@click.argument("release_id")
@click.pass_context
def release_enable(ctx: click.Context, release_id: str) -> None:
    _update_release(ctx, release_id, enabled=True, paused=False)


@releases_group.command("disable")
@click.argument("release_id")
@click.pass_context
def release_disable(ctx: click.Context, release_id: str) -> None:
    _update_release(ctx, release_id, enabled=False)


@releases_group.command("pause")
@click.argument("release_id")
@click.pass_context
def release_pause(ctx: click.Context, release_id: str) -> None:
    _update_release(ctx, release_id, paused=True)


@releases_group.command("resume")
@click.argument("release_id")
@click.pass_context
def release_resume(ctx: click.Context, release_id: str) -> None:
    _update_release(ctx, release_id, paused=False)


@releases_group.command("rollout")
@click.argument("release_id")
@click.argument("percentage", type=click.IntRange(0, 100))
@click.pass_context
def release_rollout(
    ctx: click.Context,
    release_id: str,
    percentage: int,
) -> None:
    _update_release(ctx, release_id, rollout_percentage=percentage)


@cli.group("diagnostics")
def diagnostics_group() -> None:
    """查看、下载或删除用户明确提交的诊断包。"""


@diagnostics_group.command("list")
@click.pass_context
def diagnostic_list(ctx: click.Context) -> None:
    _emit(ctx, _run_admin(lambda: _client(ctx).list_diagnostics()))


@diagnostics_group.command("download")
@click.argument("submission_id")
@click.option("--output", type=click.Path(path_type=Path, dir_okay=False), required=True)
@click.pass_context
def diagnostic_download(
    ctx: click.Context,
    submission_id: str,
    output: Path,
) -> None:
    try:
        result = _client(ctx).download_diagnostic(submission_id, output)
    except (AdminApiError, FileExistsError) as exc:
        raise click.ClickException(str(exc)) from exc
    _emit(ctx, {"submission_id": submission_id, "output": str(result)})


@diagnostics_group.command("delete")
@click.argument("submission_id")
@click.option("--yes", is_flag=True, help="跳过确认。")
@click.pass_context
def diagnostic_delete(
    ctx: click.Context,
    submission_id: str,
    yes: bool,
) -> None:
    if not yes and not click.confirm(f"确定删除诊断包 {submission_id}？"):
        raise click.Abort()
    _emit(
        ctx,
        _run_admin(lambda: _client(ctx).delete_diagnostic(submission_id)),
    )


@cli.group("contacts")
def contacts_group() -> None:
    """查看联系人加密密钥版本。"""


@contacts_group.command("status")
@click.pass_context
def contacts_status(ctx: click.Context) -> None:
    _emit(ctx, _run_admin(lambda: _client(ctx).contact_encryption_status()))


@contacts_group.command("rotate")
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_context
def contacts_rotate(ctx: click.Context, limit: int) -> None:
    """将一批联系人记录轮换到当前 Worker 密钥版本。"""

    _emit(
        ctx,
        _run_admin(
            lambda: _client(ctx).rotate_contact_encryption(
                limit=limit,
                operation_nonce=_nonce(),
            )
        ),
    )


if __name__ == "__main__":
    cli()
