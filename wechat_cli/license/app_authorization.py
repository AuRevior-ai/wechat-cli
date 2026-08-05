"""Resolve the application's launcher-issued authorization at startup."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

from ..update.errors import UpdateError
from ..update.layout import InstallLayout
from ..version import APP_VERSION
from ..windows.dpapi import DataProtector, WindowsDpapiProtector
from .session import LaunchSessionError, consume_launch_session
from .storage import LicenseStateStorage


@dataclass(frozen=True)
class AppAuthorization:
    valid: bool
    reason: str
    device_id: str | None = None


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def resolve_app_authorization(
    *,
    environ: Mapping[str, str] | None = None,
    frozen: bool | None = None,
    now: datetime | None = None,
    protector: DataProtector | None = None,
) -> AppAuthorization:
    """Consume the launch session when required, or allow source development.

    Packaged/frozen builds always require a valid session. Source execution is
    allowed for development unless the launcher explicitly enables the gate.
    """

    values = os.environ if environ is None else environ
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    requires_session = is_frozen or _truthy(values.get("WECHAT_CLI_REQUIRE_LAUNCH_SESSION"))
    if not requires_session:
        return AppAuthorization(True, "development_mode")

    session_text = values.get("WECHAT_CLI_LAUNCH_SESSION_PATH")
    if not session_text:
        return AppAuthorization(False, "launch_session_missing")

    try:
        layout = InstallLayout.from_environment(values)
    except ValueError:
        return AppAuthorization(False, "install_layout_unavailable")

    session_path = Path(session_text)
    if not session_path.is_absolute():
        session_path = layout.runtime_dir / session_path
    if not _is_under(session_path, layout.runtime_dir):
        return AppAuthorization(False, "launch_session_path_invalid")

    try:
        selected_protector = protector or WindowsDpapiProtector()
    except OSError:
        return AppAuthorization(False, "credential_protector_unavailable")

    storage = LicenseStateStorage(
        layout.state_dir / "license-state.dat",
        selected_protector,
    )
    try:
        state = storage.load()
    except UpdateError:
        return AppAuthorization(False, "local_state_corrupt")
    if state is None:
        return AppAuthorization(False, "local_state_missing")

    current_time = now or datetime.now(timezone.utc)
    try:
        consume_launch_session(
            session_path,
            local_launch_key=state.local_launch_key,
            expected_app_version=APP_VERSION,
            expected_device_id=state.device_id,
            expected_lease_content=state.lease_content,
            now=current_time,
        )
    except LaunchSessionError as exc:
        return AppAuthorization(False, exc.reason)
    except (OSError, TypeError, ValueError):
        return AppAuthorization(False, "launch_session_invalid")
    return AppAuthorization(True, "launcher_session_valid", state.device_id)
