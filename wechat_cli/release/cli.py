"""Local signed release preparation and private publication command."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..admin.client import (
    AdminApiClient,
    UrllibAdminDownloadTransport,
    UrllibAdminJsonTransport,
)
from ..admin.config import AdminConfigStorage, default_admin_config_path
from ..windows.dpapi import WindowsDpapiProtector
from .builder import ReleaseBuildOptions, SignedRelease, build_signed_release
from .config import ReleaseConfig, ReleaseConfigStorage, default_release_config_path
from .github import GitHubReleaseClient
from .publisher import PublishedRelease, publish_signed_release


def _nonce() -> str:
    return "op_" + uuid.uuid4().hex


def _storage(config_path: str | None) -> ReleaseConfigStorage:
    path = Path(config_path) if config_path else default_release_config_path()
    return ReleaseConfigStorage(path, WindowsDpapiProtector())


def _load_config(config_path: str | None) -> ReleaseConfig:
    config = _storage(config_path).load()
    if config is None:
        raise click.ClickException(
            "尚未配置发布工具。请先运行 wechat-cli-release config set。"
        )
    return config


def _github_client(config: ReleaseConfig) -> GitHubReleaseClient:
    return GitHubReleaseClient(
        repository=config.repository,
        token=config.github_token,
    )


def _admin_client(admin_config_path: str | None) -> AdminApiClient:
    path = Path(admin_config_path) if admin_config_path else default_admin_config_path()
    config = AdminConfigStorage(path, WindowsDpapiProtector()).load()
    if config is None:
        raise click.ClickException(
            "尚未配置管理员 API。请先运行 wechat-cli-admin config set。"
        )
    return AdminApiClient(
        UrllibAdminJsonTransport(
            config.api_base_url,
            allow_insecure_loopback=config.allow_insecure_loopback,
        ),
        admin_token=config.admin_token,
        download_transport=UrllibAdminDownloadTransport(
            config.api_base_url,
            allow_insecure_loopback=config.allow_insecure_loopback,
        ),
    )


def _published_at(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise click.BadParameter("必须是带时区的 ISO-8601 时间") from exc
    if parsed.tzinfo is None:
        raise click.BadParameter("必须包含时区")
    return parsed


def _emit(ctx: click.Context, value: Any) -> None:
    if bool(ctx.find_root().obj.get("json")):
        click.echo(json.dumps(value, ensure_ascii=False, sort_keys=True))
    elif isinstance(value, dict):
        for key, item in value.items():
            click.echo(f"{key}: {item}")
    else:
        click.echo(str(value))


def _build_options(
    *,
    config: ReleaseConfig,
    release_id: str,
    channel: str,
    published_at: datetime,
    minimum_app_version: str,
    minimum_launcher_version: str,
    summary: str,
    notes_url: str | None,
    rollout_percentage: int,
) -> ReleaseBuildOptions:
    return ReleaseBuildOptions(
        release_id=release_id,
        channel=channel,
        published_at=published_at,
        minimum_app_version=minimum_app_version,
        minimum_launcher_version=minimum_launcher_version,
        signing_key_id=config.signing_key_id,
        release_summary=summary,
        release_notes_url=notes_url,
        rollout_percentage=rollout_percentage,
    )


def _write_new(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        created = True
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            descriptor = None
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        if descriptor is not None:
            os.close(descriptor)
        if created:
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        raise


def _write_prepared_assets(output_dir: Path, signed: SignedRelease) -> dict[str, str]:
    manifest = output_dir / f"wechat-cli-update-manifest-{signed.version}.json"
    signature = output_dir / f"wechat-cli-update-manifest-{signed.version}.sig"
    try:
        _write_new(manifest, signed.manifest_bytes)
        _write_new(signature, signed.signature)
    except FileExistsError as exc:
        if manifest.exists() and not signature.exists():
            try:
                manifest.unlink()
            except OSError:
                pass
        raise click.ClickException(f"输出文件已存在，未覆盖：{exc.filename}") from exc
    return {
        "manifest": str(manifest),
        "signature": str(signature),
        "manifest_sha256": signed.manifest_sha256,
        "package_sha256": signed.package_sha256,
        "version": signed.version,
        "release_id": signed.release_id,
    }


_COMMON_OPTIONS = [
    click.option("--release-id", required=True),
    click.option("--channel", type=click.Choice(["stable", "beta"]), default="stable"),
    click.option("--published-at", type=_published_at, required=True),
    click.option("--minimum-app-version", required=True),
    click.option("--minimum-launcher-version", required=True),
    click.option("--summary", default=""),
    click.option("--notes-url"),
    click.option("--rollout-percentage", type=click.IntRange(0, 100), default=100),
]


def common_options(function):
    for option in reversed(_COMMON_OPTIONS):
        function = option(function)
    return function


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--json", "json_output", is_flag=True, help="输出机器可读 JSON。")
@click.option("--config-path", type=click.Path(path_type=str, dir_okay=False))
@click.option("--admin-config-path", type=click.Path(path_type=str, dir_okay=False))
@click.pass_context
def cli(
    ctx: click.Context,
    json_output: bool,
    config_path: str | None,
    admin_config_path: str | None,
) -> None:
    """准备并发布经 Ed25519 签名的私有更新。"""

    ctx.ensure_object(dict)
    ctx.obj.update(
        json=json_output,
        config_path=config_path,
        admin_config_path=admin_config_path,
    )


@cli.group("config")
def config_group() -> None:
    """配置私有 GitHub Release 与本地签名密钥。"""


@config_group.command("set")
@click.option("--repository", required=True, help="私有 release 仓库 owner/name。")
@click.option("--target-commitish", default="main", show_default=True)
@click.option(
    "--signing-key",
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
    required=True,
)
@click.option("--signing-key-id", required=True)
@click.pass_context
def config_set(
    ctx: click.Context,
    repository: str,
    target_commitish: str,
    signing_key: Path,
    signing_key_id: str,
) -> None:
    github_token = click.prompt("GitHub 发布令牌", hide_input=True).strip()
    config = ReleaseConfig(
        repository=repository,
        target_commitish=target_commitish,
        github_token=github_token,
        signing_key_path=str(signing_key),
        signing_key_id=signing_key_id,
    )
    storage = _storage(ctx.find_root().obj.get("config_path"))
    storage.save(config)
    _emit(
        ctx,
        {
            "configured": True,
            "repository": config.repository,
            "target_commitish": config.target_commitish,
            "signing_key_id": config.signing_key_id,
            "config_path": str(storage.path),
        },
    )


@config_group.command("show")
@click.pass_context
def config_show(ctx: click.Context) -> None:
    config = _load_config(ctx.find_root().obj.get("config_path"))
    _emit(
        ctx,
        {
            "repository": config.repository,
            "target_commitish": config.target_commitish,
            "github_token_hint": "••••" + config.github_token[-4:],
            "signing_key_path": config.signing_key_path,
            "signing_key_id": config.signing_key_id,
        },
    )


@cli.command("prepare")
@click.argument(
    "package",
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
)
@common_options
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False),
    required=True,
)
@click.pass_context
def prepare_command(
    ctx: click.Context,
    package: Path,
    release_id: str,
    channel: str,
    published_at: datetime,
    minimum_app_version: str,
    minimum_launcher_version: str,
    summary: str,
    notes_url: str | None,
    rollout_percentage: int,
    output_dir: Path,
) -> None:
    config = _load_config(ctx.find_root().obj.get("config_path"))
    signed = build_signed_release(
        package,
        config.signing_key_path,
        _build_options(
            config=config,
            release_id=release_id,
            channel=channel,
            published_at=published_at,
            minimum_app_version=minimum_app_version,
            minimum_launcher_version=minimum_launcher_version,
            summary=summary,
            notes_url=notes_url,
            rollout_percentage=rollout_percentage,
        ),
    )
    _emit(ctx, _write_prepared_assets(output_dir, signed))


@cli.command("publish")
@click.argument(
    "package",
    type=click.Path(path_type=Path, exists=True, dir_okay=False, resolve_path=True),
)
@common_options
@click.option("--name", "release_name")
@click.option("--body", "release_body", default="")
@click.option(
    "--enable",
    is_flag=True,
    help="注册后立即启用并解除暂停；默认仅注册为禁用草稿。",
)
@click.pass_context
def publish_command(
    ctx: click.Context,
    package: Path,
    release_id: str,
    channel: str,
    published_at: datetime,
    minimum_app_version: str,
    minimum_launcher_version: str,
    summary: str,
    notes_url: str | None,
    rollout_percentage: int,
    release_name: str | None,
    release_body: str,
    enable: bool,
) -> None:
    config = _load_config(ctx.find_root().obj.get("config_path"))
    signed = build_signed_release(
        package,
        config.signing_key_path,
        _build_options(
            config=config,
            release_id=release_id,
            channel=channel,
            published_at=published_at,
            minimum_app_version=minimum_app_version,
            minimum_launcher_version=minimum_launcher_version,
            summary=summary,
            notes_url=notes_url,
            rollout_percentage=rollout_percentage,
        ),
    )
    published = publish_signed_release(
        signed,
        github_client=_github_client(config),
        admin_client=_admin_client(ctx.find_root().obj.get("admin_config_path")),
        repository=config.repository,
        target_commitish=config.target_commitish,
        release_name=release_name or f"WeChat CLI Web {signed.version}",
        release_body=release_body or summary,
        operation_nonce=_nonce(),
        enable=enable,
        enable_operation_nonce=_nonce() if enable else None,
        rollout_percentage=rollout_percentage,
    )
    _emit(ctx, asdict(published))


if __name__ == "__main__":
    cli()
