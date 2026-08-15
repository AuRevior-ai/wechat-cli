"""Compatibility boundary for pywebview pre-load URL access."""

from __future__ import annotations


class WebViewUnavailable(RuntimeError):
    """Raised when the accepted pywebview backend contract is unavailable."""


class PreloadUrlReader:
    """Read the current URL before pywebview's loaded event."""

    def read(self, window) -> str:
        gui = getattr(window, "gui", None)
        uid = getattr(window, "uid", None)
        getter = getattr(gui, "get_current_url", None)
        if not callable(getter) or uid is None:
            raise WebViewUnavailable("pywebview backend URL is unavailable before load")
        url = getter(uid)
        if not isinstance(url, str) or not url:
            raise WebViewUnavailable("pywebview backend returned an invalid URL before load")
        return url
