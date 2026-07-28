"""media 命令 — 导出已定位的微信本地媒体文件"""

import click

from ..core.media import export_media_file
from ..output.formatter import output


@click.group("media")
def media():
    """处理 history --media 返回的本地媒体路径。"""


@media.command("export")
@click.argument("path")
@click.option("--output-dir", default="wechat-media", help="导出目录")
@click.option("--format", "fmt", default="json", type=click.Choice(["json", "text"]), help="输出格式")
@click.pass_context
def export(ctx, path, output_dir, fmt):
    """导出单个媒体文件，图片 .dat 会尽量解码为可查看格式。"""
    app = ctx.obj
    try:
        result = export_media_file(path, output_dir, db_dir=app.db_dir)
    except PermissionError as exc:
        click.echo(f"错误: {exc}", err=True)
        ctx.exit(3)
    except FileNotFoundError as exc:
        click.echo(f"错误: 文件不存在: {exc}", err=True)
        ctx.exit(2)
    except Exception as exc:
        click.echo(f"错误: 导出失败: {exc}", err=True)
        ctx.exit(1)

    if fmt == "json":
        output({"media": result}, "json")
    else:
        output(f"已导出: {result['path']} ({result['content_type'] or 'unknown'}, {result['bytes']} bytes)", "text")
