"""get-chat-history 命令"""

import click

from ..core.contacts import get_contact_avatars, get_contact_names
from ..core.messages import (
    MSG_TYPE_FILTERS,
    MSG_TYPE_NAMES,
    collect_chat_history_items,
    parse_time_range,
    resolve_chat_context,
    save_message_items_media,
    validate_pagination,
)
from ..output.formatter import output


@click.command("history")
@click.argument("chat_name")
@click.option("--limit", default=50, help="返回的消息数量")
@click.option("--offset", default=0, help="分页偏移量")
@click.option("--start-time", default="", help="起始时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--end-time", default="", help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "text"]), help="输出格式")
@click.option("--type", "msg_type", default=None, type=click.Choice(MSG_TYPE_NAMES), help="消息类型过滤")
@click.option("--media", is_flag=True, help="解析媒体文件路径（图片/文件/视频/语音）")
@click.option("--save-dir", default=None, help="保存已定位媒体到指定目录，并自动启用 --media")
@click.pass_context
def history(ctx, chat_name, limit, offset, start_time, end_time, fmt, msg_type, media, save_dir):
    """获取指定聊天的消息记录

    \b
    示例:
      wechat-cli history "张三"                          # 最近 50 条消息
      wechat-cli history "张三" --limit 100 --offset 50  # 分页查询
      wechat-cli history "AI交流群" --start-time "2026-04-01" --end-time "2026-04-02"
      wechat-cli history "张三" --format text             # 纯文本输出
    """
    app = ctx.obj

    try:
        validate_pagination(limit, offset, limit_max=None)
        start_ts, end_ts = parse_time_range(start_time, end_time)
    except ValueError as e:
        click.echo(f"错误: {e}", err=True)
        ctx.exit(2)

    chat_ctx = resolve_chat_context(chat_name, app.msg_db_keys, app.cache, app.decrypted_dir)
    if not chat_ctx:
        click.echo(f"找不到聊天对象: {chat_name}", err=True)
        ctx.exit(1)
    if not chat_ctx['db_path']:
        click.echo(f"找不到 {chat_ctx['display_name']} 的消息记录", err=True)
        ctx.exit(1)

    names = get_contact_names(app.cache, app.decrypted_dir)
    avatars = get_contact_avatars(app.cache, app.decrypted_dir)
    type_filter = MSG_TYPE_FILTERS[msg_type] if msg_type else None
    message_items, failures = collect_chat_history_items(
        chat_ctx, names, app.display_name_fn,
        avatars=avatars,
        start_ts=start_ts, end_ts=end_ts, limit=limit, offset=offset,
        msg_type_filter=type_filter, resolve_media=media or bool(save_dir), db_dir=app.db_dir,
    )
    saved_media = []
    save_failures = []
    if save_dir:
        saved_media, save_failures = save_message_items_media(message_items, save_dir, db_dir=app.db_dir)
    lines = [item["line"] for item in message_items]

    if fmt == 'json':
        output({
            'chat': chat_ctx['display_name'],
            'username': chat_ctx['username'],
            'avatar_url': avatars.get(chat_ctx['username'], ''),
            'is_group': chat_ctx['is_group'],
            'count': len(lines),
            'offset': offset,
            'limit': limit,
            'start_time': start_time or None,
            'end_time': end_time or None,
            'type': msg_type or None,
            'messages': lines,
            'message_items': message_items,
            'saved_media': saved_media,
            'save_dir': save_dir,
            'failures': (failures + save_failures) if (failures or save_failures) else None,
        }, 'json')
    else:
        header = f"{chat_ctx['display_name']} 的消息记录（返回 {len(lines)} 条，offset={offset}, limit={limit}）"
        if chat_ctx['is_group']:
            header += " [群聊]"
        if start_time or end_time:
            header += f"\n时间范围: {start_time or '最早'} ~ {end_time or '最新'}"
        if save_dir:
            header += f"\n已保存媒体: {len(saved_media)} 个 -> {save_dir}"
        all_failures = failures + save_failures
        if all_failures:
            header += "\n查询失败: " + "；".join(all_failures)
        if lines:
            output(header + ":\n\n" + "\n".join(lines), 'text')
        else:
            output(f"{chat_ctx['display_name']} 无消息记录", 'text')
