"""Stateful controller connecting LauncherService to the local WebView2 UI."""

from __future__ import annotations

import os
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from ..license.device_identity import (
    DeviceIdentityProvider,
    sanitize_device_name,
)
from ..license.models import ClientLicenseState
from ..license.storage import LicenseStateStorage
from ..update.layout import InstallLayout
from .service import LauncherResult, LauncherService, LauncherStatus
from .webview import LauncherBridge


_LICENSE_ERROR_CODES = {
    ClientLicenseState.UNACTIVATED: "LIC-ACTIVATION-REQUIRED",
    ClientLicenseState.OFFLINE_EXPIRED: "LIC-OFFLINE-EXPIRED",
    ClientLicenseState.DEVICE_UNBOUND: "LIC-DEVICE-UNBOUND",
    ClientLicenseState.DEVICE_DISABLED: "LIC-DEVICE-DISABLED",
    ClientLicenseState.LICENSE_SUSPENDED: "LIC-LICENSE-SUSPENDED",
    ClientLicenseState.LICENSE_REVOKED: "LIC-LICENSE-REVOKED",
    ClientLicenseState.LOCAL_STATE_CORRUPT: "LIC-LOCAL-STATE-CORRUPT",
}


def _license_hint(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    compact = "".join(char for char in value if char.isalnum())
    return compact[-4:].upper() if len(compact) >= 4 else None


class LauncherUiController:
    def __init__(
        self,
        *,
        service: LauncherService,
        storage: LicenseStateStorage,
        identity_provider: DeviceIdentityProvider,
        fingerprint_salt: str,
        layout: InstallLayout,
        initial_result: LauncherResult,
        success_handler: Callable[[LauncherResult], Any] | None = None,
        retry_update_handler: Callable[[], Mapping[str, Any]] | None = None,
        help_handler: Callable[[str], Any] | None = None,
        close_handler: Callable[[], Any] | None = None,
    ) -> None:
        self.service = service
        self.storage = storage
        self.identity_provider = identity_provider
        self.fingerprint_salt = fingerprint_salt
        self.layout = layout
        self.success_handler = success_handler
        self.retry_update_handler = retry_update_handler
        self.help_handler = help_handler
        self.close_handler = close_handler
        self._lock = threading.RLock()
        self._state = self._state_from_result(initial_result)

    def _stored_state(self):
        try:
            return self.storage.load()
        except Exception:
            return None

    def _base_details(self, version: str | None = None) -> dict[str, Any]:
        stored = self._stored_state()
        return {
            "license_hint": _license_hint(
                stored.license_key if stored is not None else None
            ),
            "device_name": None,
            "current_version": version,
        }

    def _state_from_result(self, result: LauncherResult) -> dict[str, Any]:
        details = self._base_details(result.version)
        if result.status == LauncherStatus.ACTIVATION_REQUIRED:
            return {
                **details,
                "status": "activation_required",
                "message": "请输入永久许可证密钥以激活当前设备。",
                "can_retry_validation": False,
                "can_retry_update": False,
                "can_start": False,
            }
        if result.status in {
            LauncherStatus.STARTED,
            LauncherStatus.UPDATED,
            LauncherStatus.ROLLED_BACK,
        }:
            message = {
                LauncherStatus.STARTED: "许可证验证成功，应用已启动。",
                LauncherStatus.UPDATED: "新版本安装成功，应用已启动。",
                LauncherStatus.ROLLED_BACK: "新版本未能正常启动，已恢复上一版本。",
            }[result.status]
            return {
                **details,
                "status": "ready" if result.status != LauncherStatus.ROLLED_BACK else "update_failed",
                "message": message,
                "error_code": (
                    "UPD-ROLLED-BACK"
                    if result.status == LauncherStatus.ROLLED_BACK
                    else None
                ),
                "can_retry_validation": False,
                "can_retry_update": result.status == LauncherStatus.ROLLED_BACK,
                "can_start": False,
            }
        if result.status == LauncherStatus.BLOCKED:
            license_state = result.license_state or ClientLicenseState.UNACTIVATED
            retryable = license_state in {
                ClientLicenseState.OFFLINE_EXPIRED,
                ClientLicenseState.LOCAL_STATE_CORRUPT,
                ClientLicenseState.UNACTIVATED,
            }
            return {
                **details,
                "status": "blocked",
                "message": "许可证验证未通过，请根据错误编号处理。",
                "error_code": _LICENSE_ERROR_CODES.get(
                    license_state,
                    "LIC-VALIDATION-FAILED",
                ),
                "error_message": result.reason or "许可证当前不可用。",
                "can_retry_validation": retryable,
                "can_retry_update": False,
                "can_start": False,
            }
        return {
            **details,
            "status": "blocked",
            "message": "应用启动失败。",
            "error_code": "LAUNCH-FAILED",
            "error_message": result.reason or "未知启动错误。",
            "can_retry_validation": True,
            "can_retry_update": False,
            "can_start": False,
        }

    def _set_state(self, value: Mapping[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._state = dict(value)
            return dict(self._state)

    def get_ui_state(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._state)

    def _run_start(self) -> dict[str, Any]:
        self._set_state(
            {
                **self._base_details(),
                "status": "validating",
                "message": "正在验证许可证并启动应用。",
            }
        )
        result = self.service.start()
        state = self._set_state(self._state_from_result(result))
        if result.status in {
            LauncherStatus.STARTED,
            LauncherStatus.UPDATED,
            LauncherStatus.ROLLED_BACK,
        } and self.success_handler is not None:
            self.success_handler(result)
        return state

    def activate_license(self, license_key: str, device_name: str) -> dict[str, Any]:
        with self._lock:
            self._state = {
                **self._base_details(),
                "status": "validating",
                "message": "正在激活许可证，请稍候。",
            }
        existing = self._stored_state()
        try:
            identity = self.identity_provider.create(
                fingerprint_salt=self.fingerprint_salt,
                existing_device_id=(
                    existing.device_id if existing is not None else None
                ),
            )
            selected_name = sanitize_device_name(device_name)
            identity = replace(identity, display_name=selected_name)
            self.service.activate(license_key=license_key, identity=identity)
        except Exception:
            return self._set_state(
                {
                    **self._base_details(),
                    "status": "activation_required",
                    "message": "许可证激活失败，请检查密钥或网络后重试。",
                    "error_code": "LIC-ACTIVATE-FAILED",
                    "error_message": "激活请求未成功，敏感信息未写入日志。",
                    "can_retry_validation": False,
                    "can_retry_update": False,
                    "can_start": False,
                }
            )
        return self._run_start()

    def retry_validation(self) -> dict[str, Any]:
        return self._run_start()

    def start_application(self) -> dict[str, Any]:
        return self._run_start()

    def retry_update(self) -> dict[str, Any]:
        if self.retry_update_handler is None:
            return self.get_ui_state()
        try:
            return self._set_state(self.retry_update_handler())
        except Exception:
            return self._set_state(
                {
                    **self._base_details(),
                    "status": "update_failed",
                    "message": "更新重试失败，当前版本仍可继续使用。",
                    "error_code": "UPD-RETRY-FAILED",
                    "can_retry_update": True,
                    "can_retry_validation": False,
                    "can_start": True,
                }
            )

    def open_log_folder(self) -> None:
        self.layout.logs_dir.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(self.layout.logs_dir)  # type: ignore[attr-defined]

    def open_external_help(self, topic: str) -> None:
        if self.help_handler is not None:
            self.help_handler(topic)

    def close_launcher(self) -> None:
        if self.close_handler is not None:
            self.close_handler()

    def create_bridge(self) -> LauncherBridge:
        return LauncherBridge(
            state_provider=self.get_ui_state,
            activation_handler=self.activate_license,
            retry_validation_handler=self.retry_validation,
            start_handler=self.start_application,
            retry_update_handler=self.retry_update,
            open_log_handler=self.open_log_folder,
            open_help_handler=self.open_external_help,
            close_handler=self.close_launcher,
        )
