"""Secret-safe license, device, and update management for the local Web UI."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any, Callable

from ..update.crypto import TrustedEd25519Keys
from ..update.layout import InstallLayout
from ..update.state import load_pending_update, read_json_object
from ..version import LAUNCHER_VERSION
from .client import LicenseApiClient
from .device_identity import sanitize_device_name
from .lease import OfflineLease, verify_signed_lease
from .models import ClientLicenseState, DeviceRecord
from .storage import LicenseStateStorage, LocalLicenseState


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("time must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _license_hint(value: str) -> str:
    compact = "".join(char for char in value if char.isalnum())
    return compact[-4:].upper() if len(compact) >= 4 else ""


def _device_mapping(record: DeviceRecord) -> dict[str, Any]:
    return {
        "device_id": record.device_id,
        "display_name": record.display_name,
        "status": record.status,
        "is_current": record.is_current,
        "last_validated_at": record.last_validated_at,
        "last_app_version": record.last_app_version,
        "last_launcher_version": record.last_launcher_version,
    }


class AppManagementService:
    """Expose only masked management data to the local browser application."""

    def __init__(
        self,
        *,
        layout: InstallLayout,
        storage: LicenseStateStorage,
        client: LicenseApiClient,
        lease_keys: TrustedEd25519Keys,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        update_trigger: Callable[[], bool] | None = None,
    ) -> None:
        self.layout = layout
        self.storage = storage
        self.client = client
        self.lease_keys = lease_keys
        self.now = now
        self.update_trigger = update_trigger or (lambda: False)

    def _state(self) -> LocalLicenseState:
        state = self.storage.load()
        if state is None:
            raise RuntimeError("local license state is missing")
        return state

    def _verified_lease(self, state: LocalLicenseState) -> OfflineLease:
        return verify_signed_lease(
            state.lease_content,
            state.lease_signature,
            self.lease_keys,
            expected_device_id=state.device_id,
            expected_license_id=state.license_id,
        )

    def _refresh_online(self, state: LocalLicenseState) -> LocalLicenseState:
        current = self.layout.load_current()
        validation = self.client.validate(
            device_token=state.device_token,
            app_version=current.current_version,
            launcher_version=LAUNCHER_VERSION,
        )
        if validation.license_id != state.license_id or validation.device_id != state.device_id:
            raise RuntimeError("license validation identity mismatch")
        lease = verify_signed_lease(
            validation.lease_content,
            validation.lease_signature,
            self.lease_keys,
            expected_device_id=state.device_id,
            expected_license_id=state.license_id,
        )
        current_time = self.now()
        if current_time.tzinfo is None:
            raise ValueError("management clock must include a timezone")
        server_time = datetime.fromisoformat(
            validation.server_time.replace("Z", "+00:00")
        )
        refreshed = replace(
            state,
            lease_content=validation.lease_content,
            lease_signature=validation.lease_signature,
            trusted_time=state.trusted_time.updated(
                server_time=server_time,
                wall_clock=current_time,
            ),
        )
        # Ensure a server cannot return a validly signed lease for the wrong state.
        if lease.status != "active":
            raise RuntimeError(f"license is not active: {lease.status}")
        self.storage.save(refreshed)
        return refreshed

    def license_status(self) -> dict[str, Any]:
        current = self.layout.load_current()
        state = self._state()
        now = self.now()
        if now.tzinfo is None:
            raise ValueError("management clock must include a timezone")
        try:
            state.trusted_time.assert_not_rolled_back(now)
            lease = self._verified_lease(state)
            client_state = lease.client_state_at(now)
            offline_until = lease.offline_until
            remaining = max(
                0,
                int((lease.offline_until_datetime - now.astimezone(timezone.utc)).total_seconds()),
            )
        except Exception:
            client_state = ClientLicenseState.LOCAL_STATE_CORRUPT
            offline_until = None
            remaining = 0
        return {
            "state": client_state.value,
            "authorized": client_state
            in {
                ClientLicenseState.OFFLINE_VALID,
                ClientLicenseState.OFFLINE_EXPIRING,
                ClientLicenseState.ONLINE_VALID,
            },
            "license_hint": _license_hint(state.license_key),
            "device_id": state.device_id,
            "offline_until": offline_until,
            "offline_remaining_seconds": remaining,
            "current_version": current.current_version,
            "previous_version": current.previous_version,
            "launcher_version": LAUNCHER_VERSION,
            "channel": current.channel,
        }

    def list_devices(self) -> list[dict[str, Any]]:
        state = self._state()
        records = self.client.list_devices(state.device_token)
        return [_device_mapping(record) for record in records]

    def unbind_device(self, target_device_id: str, operation_nonce: str) -> dict[str, Any]:
        state = self._state()
        if not isinstance(target_device_id, str) or not target_device_id:
            raise ValueError("target_device_id is required")
        if target_device_id == state.device_id:
            raise ValueError("the current device cannot unbind itself")
        if not isinstance(operation_nonce, str) or not 8 <= len(operation_nonce) <= 256:
            raise ValueError("operation_nonce is invalid")
        state = self._refresh_online(state)
        self.client.unbind_device(
            state.device_token,
            target_device_id=target_device_id,
            operation_nonce=operation_nonce,
        )
        return {"ok": True, "unbound_device_id": target_device_id}

    def rename_device(
        self,
        target_device_id: str,
        display_name: str,
        operation_nonce: str,
    ) -> dict[str, Any]:
        state = self._state()
        if not isinstance(target_device_id, str) or not target_device_id:
            raise ValueError("target_device_id is required")
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("display_name is required")
        if not isinstance(operation_nonce, str) or not 8 <= len(operation_nonce) <= 256:
            raise ValueError("operation_nonce is invalid")
        selected_name = sanitize_device_name(display_name)
        state = self._refresh_online(state)
        self.client.rename_device(
            state.device_token,
            target_device_id=target_device_id,
            display_name=selected_name,
            operation_nonce=operation_nonce,
        )
        return {"ok": True, "device_id": target_device_id}

    def update_status(self) -> dict[str, Any]:
        current = self.layout.load_current()
        result: dict[str, Any] = {
            "current_version": current.current_version,
            "previous_version": current.previous_version,
            "launcher_version": LAUNCHER_VERSION,
            "channel": current.channel,
            "status": "idle",
            "pending_version": None,
            "downloaded_bytes": 0,
            "expected_size": 0,
            "progress_percent": 0,
        }
        pending = load_pending_update(self.layout.pending_update_path)
        if pending is not None:
            result.update(
                {
                    "status": "ready_to_install",
                    "pending_version": pending.version,
                    "prepared_at": pending.prepared_at,
                    "install_on_next_start": pending.install_on_next_start,
                }
            )
        if self.layout.update_status_path.exists():
            status = read_json_object(self.layout.update_status_path)
            allowed = {
                "status",
                "target_version",
                "downloaded_bytes",
                "expected_size",
                "checked_at",
                "error_code",
                "error_message",
            }
            for key in allowed:
                if key in status:
                    result[key] = status[key]
            downloaded = result.get("downloaded_bytes")
            expected = result.get("expected_size")
            if (
                isinstance(downloaded, int)
                and not isinstance(downloaded, bool)
                and isinstance(expected, int)
                and not isinstance(expected, bool)
                and expected > 0
            ):
                result["progress_percent"] = max(
                    0,
                    min(100, int(downloaded * 100 / expected)),
                )
        return result

    def trigger_update_check(self) -> dict[str, Any]:
        return {"ok": True, "started": bool(self.update_trigger())}
