"""ai-package 命令 — 生成可直接交给 AI 的聊天记录与素材包。"""

from pathlib import Path

import click

from ..core.ai_package import build_ai_package
from ..core.contacts import get_contact_avatars, get_contact_names
from ..core.image_keys import ensure_image_keys
from ..core.messages import (
    collect_chat_history_items,
    parse_time_range,
    resolve_chat_context,
)
from ..core.stickers import enrich_sticker_media, load_sticker_metadata
from ..core.voice import decrypted_media_db_paths
from ..output.formatter import output


@click.command("ai-package")
@click.argument("chat_name")
@click.option("--start-time", default="", help="起始时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option("--end-time", default="", help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
@click.option(
    "--output",
    "output_path",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="AI 资料压缩包保存位置",
)
@click.option(
    "--transcribe-voice/--no-transcribe-voice",
    "transcribe",
    default=True,
    help="是否离线识别语音（默认识别）",
)
@click.option(
    "--include-copy-data",
    is_flag=True,
    help="在 JSON 结果中包含复制全文和复制关键信息内容",
)
@click.pass_context
def ai_package(
    ctx,
    chat_name,
    start_time,
    end_time,
    output_path,
    transcribe,
    include_copy_data,
):
    """生成含聊天文字、合并转发、图片、表情和语音的 AI 资料包。"""
    app = ctx.obj
    try:
        start_ts, end_ts = parse_time_range(start_time, end_time)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    chat_ctx = resolve_chat_context(
        chat_name,
        app.msg_db_keys,
        app.cache,
        app.decrypted_dir,
    )
    if not chat_ctx:
        raise click.ClickException(f"找不到聊天对象: {chat_name}")
    if not chat_ctx["db_path"]:
        raise click.ClickException(
            f'找不到 {chat_ctx["display_name"]} 的消息记录'
        )

    names = get_contact_names(app.cache, app.decrypted_dir)
    avatars = get_contact_avatars(app.cache, app.decrypted_dir)
    media_db_paths = decrypted_media_db_paths(app.all_keys, app.cache)
    items, query_failures = collect_chat_history_items(
        chat_ctx,
        names,
        app.display_name_fn,
        avatars=avatars,
        start_ts=start_ts,
        end_ts=end_ts,
        limit=1_000_000,
        offset=0,
        resolve_media=True,
        db_dir=app.db_dir,
        media_db_paths=media_db_paths,
    )
    enrich_sticker_media(items, load_sticker_metadata(app.cache))

    def progress(message):
        click.echo(message, err=True)

    image_paths = [
        str((item.get("media") or {}).get("path"))
        for item in items
        if item.get("type") == "image"
        and (item.get("media") or {}).get("path")
    ]
    image_keys = ensure_image_keys(
        app.cfg,
        config_path=app.config_path,
        sample_paths=image_paths,
        progress=progress,
    )
    image_aes_key, image_xor_key = image_keys or (None, None)
    initial_failures = [{
        "message_id": None,
        "time": "",
        "type": "",
        "phase": "query",
        "error": str(failure),
    } for failure in query_failures]
    result = build_ai_package(
        chat_ctx,
        items,
        output_path,
        db_dir=app.db_dir,
        media_db_paths=media_db_paths,
        start_time=start_time,
        end_time=end_time,
        transcribe_voice=transcribe,
        initial_failures=initial_failures,
        image_aes_key=image_aes_key,
        image_xor_key=image_xor_key,
        progress=progress,
    )
    output(result.to_dict(include_messages=include_copy_data), "json")
