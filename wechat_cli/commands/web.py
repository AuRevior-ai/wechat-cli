"""web 命令 — 启动本机图形化控制台"""

import click

from ..web.server import serve


@click.command("web")
@click.option("--port", default=8787, help="本机端口")
@click.option("--open", "open_browser", is_flag=True, help="启动后自动打开浏览器")
def web(port, open_browser):
    """启动本机网页控制台。"""
    serve(port=port, open_browser=open_browser)
