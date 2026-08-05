"""Local pywebview/EdgeChromium launcher window and allow-listed bridge."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import unquote, urlparse


class WebViewUnavailable(RuntimeError):
    pass


_ALLOWED_UI_FIELDS = {
    "status",
    "title",
    "message",
    "error_code",
    "error_message",
    "license_hint",
    "device_name",
    "device_count",
    "maximum_devices",
    "offline_until",
    "offline_remaining_seconds",
    "current_version",
    "target_version",
    "progress",
    "can_retry_validation",
    "can_retry_update",
    "can_start",
}


def launcher_ui_directory() -> Path:
    return Path(__file__).resolve().parent / "ui"


def _safe_ui_state(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("launcher UI state provider must return an object")
    result: dict[str, Any] = {}
    for key in _ALLOWED_UI_FIELDS:
        if key in value:
            result[key] = value[key]
    return result


class LauncherBridge:
    """Only methods on this class are exposed to local launcher JavaScript."""

    def __init__(
        self,
        *,
        state_provider: Callable[[], Mapping[str, Any]],
        activation_handler: Callable[[str, str], Mapping[str, Any]] | None = None,
        retry_validation_handler: Callable[[], Mapping[str, Any]] | None = None,
        start_handler: Callable[[], Mapping[str, Any]] | None = None,
        retry_update_handler: Callable[[], Mapping[str, Any]] | None = None,
        open_log_handler: Callable[[], Any] | None = None,
        open_help_handler: Callable[[str], Any] | None = None,
        close_handler: Callable[[], Any] | None = None,
    ) -> None:
        self._state_provider = state_provider
        self._activation_handler = activation_handler
        self._retry_validation_handler = retry_validation_handler
        self._start_handler = start_handler
        self._retry_update_handler = retry_update_handler
        self._open_log_handler = open_log_handler
        self._open_help_handler = open_help_handler
        self._close_handler = close_handler

    def get_ui_state(self) -> dict[str, Any]:
        return _safe_ui_state(self._state_provider())

    def activate_license(self, license_key: str, device_name: str) -> dict[str, Any]:
        if not isinstance(license_key, str):
            raise ValueError("许可证密钥格式无效")
        key = license_key.strip()
        if not 1 <= len(key) <= 128:
            raise ValueError("许可证密钥长度无效")
        if not isinstance(device_name, str):
            raise ValueError("设备名称格式无效")
        name = device_name.strip()
        if len(name) > 64:
            raise ValueError("设备名称不能超过 64 个字符")
        if self._activation_handler is None:
            raise RuntimeError("许可证激活功能尚未初始化")
        return _safe_ui_state(self._activation_handler(key, name))

    def retry_validation(self) -> dict[str, Any]:
        if self._retry_validation_handler is None:
            return self.get_ui_state()
        return _safe_ui_state(self._retry_validation_handler())

    def start_application(self) -> dict[str, Any]:
        if self._start_handler is None:
            return self.get_ui_state()
        return _safe_ui_state(self._start_handler())

    def retry_update(self) -> dict[str, Any]:
        if self._retry_update_handler is None:
            return self.get_ui_state()
        return _safe_ui_state(self._retry_update_handler())

    def open_log_folder(self) -> bool:
        if self._open_log_handler is None:
            return False
        self._open_log_handler()
        return True

    def open_external_help(self, topic: str) -> bool:
        if not isinstance(topic, str) or not topic or len(topic) > 64:
            raise ValueError("帮助主题无效")
        if self._open_help_handler is None:
            return False
        self._open_help_handler(topic)
        return True

    def close_launcher(self) -> bool:
        if self._close_handler is None:
            return False
        self._close_handler()
        return True


class LauncherWindow:
    def __init__(
        self,
        *,
        webview_module: Any | None = ...,
        importer: Callable[[str], Any] = importlib.import_module,
    ) -> None:
        self._webview_module = webview_module
        self._importer = importer
        self.window = None

    def _load_webview(self):
        if self._webview_module is ...:
            try:
                module = self._importer("webview")
            except (ImportError, ModuleNotFoundError) as exc:
                raise WebViewUnavailable(
                    "pywebview 未安装，无法创建 WebView2 启动窗口"
                ) from exc
        else:
            module = self._webview_module
        if module is None or not hasattr(module, "create_window") or not hasattr(module, "start"):
            raise WebViewUnavailable("pywebview/EdgeChromium 后端不可用")
        return module

    @staticmethod
    def _navigation_is_local(url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme != "file":
            return False
        try:
            current = Path(unquote(parsed.path)).resolve(strict=False)
            current.relative_to(launcher_ui_directory().resolve(strict=False))
            return True
        except (OSError, ValueError):
            return False

    def show(self, bridge: LauncherBridge) -> None:
        webview = self._load_webview()
        index = launcher_ui_directory() / "index.html"
        if not index.is_file():
            raise WebViewUnavailable(f"Launcher UI 文件缺失：{index}")
        self.window = webview.create_window(
            "WeChat CLI Launcher",
            url=index.as_uri(),
            js_api=bridge,
            width=700,
            height=650,
            min_size=(520, 500),
            resizable=True,
            confirm_close=False,
            text_select=True,
            background_color="#f0ede6",
        )

        def guard_navigation(window=None):
            target = window or self.window
            try:
                url = target.get_current_url()
            except Exception:
                target.destroy()
                return
            if not self._navigation_is_local(url):
                target.destroy()

        self.window.events.before_load += guard_navigation
        webview.start(gui="edgechromium", debug=False, private_mode=True)
