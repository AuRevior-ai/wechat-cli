"""invite-stats command — audit and rank group invitations."""

import json

import click

from ..core.contacts import get_group_members
from ..core.invite_stats import (
    collect_group_invite_stats,
    format_invite_stats_csv,
    format_invite_stats_text,
    parse_identity_bindings,
)
from ..core.messages import parse_time_range, resolve_chat_context
from ..output.formatter import output


@click.command("invite-stats")
@click.argument("group_name")
@click.option("--start-time", default="", help="起始时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--end-time", default="", help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--bind-identity", multiple=True, help="历史昵称=稳定账号，可重复")
@click.option(
    "--format", "fmt", default="json",
    type=click.Choice(["json", "text", "csv"]),
    help="输出格式",
)
@click.option("--output", "output_path", default=None, type=click.Path(dir_okay=False))
@click.pass_context
def invite_stats(
    ctx,
    group_name,
    start_time,
    end_time,
    bind_identity,
    fmt,
    output_path,
):
    """统计群聊邀请关系并按唯一拉人数排行。"""
    app = ctx.obj
    try:
        start_ts, end_ts = parse_time_range(start_time, end_time)
        bindings = parse_identity_bindings(bind_identity)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    chat_ctx = resolve_chat_context(
        group_name, app.msg_db_keys, app.cache, app.decrypted_dir
    )
    if not chat_ctx:
        raise click.ClickException(f"找不到聊天对象: {group_name}")
    if not chat_ctx["is_group"]:
        raise click.ClickException(f"{group_name} 不是一个群聊")
    if not chat_ctx["db_path"]:
        raise click.ClickException(
            f'找不到 {chat_ctx["display_name"]} 的消息记录'
        )
    members = get_group_members(
        chat_ctx["username"], app.cache, app.decrypted_dir
    )["members"]
    result = collect_group_invite_stats(
        chat_ctx,
        members,
        bindings,
        start_ts=start_ts,
        end_ts=end_ts,
    )
    if fmt == "json":
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    elif fmt == "csv":
        rendered = format_invite_stats_csv(result)
    else:
        rendered = format_invite_stats_text(result) + "\n"

    if output_path:
        try:
            with open(
                output_path, "w", encoding="utf-8", newline=""
            ) as file:
                file.write(rendered)
        except OSError as exc:
            raise click.ClickException(
                f"无法写入输出文件 {output_path}: {exc}"
            ) from exc
        click.echo(output_path)
    elif fmt == "json":
        output(result, "json")
    else:
        output(rendered, "text")
