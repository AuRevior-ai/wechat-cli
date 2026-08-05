"""Launcher startup orchestration for authorization, update switch, and rollback."""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from ..license.client import LicenseRejected, LicenseServiceUnavailable
from ..license.device_identity import DeviceIdentity
from ..license.lease import OfflineLease, TrustedTimeState, verify_signed_lease
from ..license.models import ActivationResult, ClientLicenseState, ValidationResult
from ..license.session import create_launch_session
from ..license.storage import LicenseStateStorage, LocalLicenseState
from ..update.crypto import TrustedEd25519Keys
from ..update.errors import ErrorCode, UpdateError
from ..update.layout import InstallLayout
from ..update.state import load_pending_update
from ..update.transaction import (
    TransactionState,
    UpdateTransaction,
    UpdateTransactionEngine,
)
from ..version import APP_VERSION, LAUNCHER_VERSION


class LicenseValidator(Protocol):
    def activate(
        self,
        *,
        license_key: str,
        device_id: str,
        device_fingerprint: str,
        device_name: str,
        app_version: str,
        launcher_version: str,
    ) -> ActivationResult: ...

    def validate(
        self,
        *,
        device_token: str,
        app_version: str,
        launcher_version: str,
    ) -> ValidationResult: ...


class ApplicationRuntime(Protocol):
    def start(self, version: str, session_path: Path): ...

    def wait_healthy(self, version: str): ...

    def stop(self, process) -> None: ...


class LauncherStatus(str, Enum):
    ACTIVATION_REQUIRED = "activation_required"
    BLOCKED = "blocked"
    STARTED = "started"
    UPDATED = "updated"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass(frozen=True)
class LauncherResult:
    status: LauncherStatus
    version: str | None = None
    license_state: ClientLicenseState | None = None
    reason: str | None = None
    process: object | None = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class _Authorization:
    state: ClientLicenseState
    local_state: LocalLicenseState
    reason: str | None = None

    @property
    def allowed(self) -> bool:
        return self.state in {
            ClientLicenseState.ONLINE_VALID,
            ClientLicenseState.OFFLINE_VALID,
            ClientLicenseState.OFFLINE_EXPIRING,
        }


def _format_time(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("launcher time must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("server time must include a timezone")
    return parsed.astimezone(timezone.utc)


_REJECTION_STATES = {
    ErrorCode.LICENSE_REVOKED: ClientLicenseState.LICENSE_REVOKED,
    ErrorCode.LICENSE_SUSPENDED: ClientLicenseState.LICENSE_SUSPENDED,
    ErrorCode.DEVICE_UNBOUND: ClientLicenseState.DEVICE_UNBOUND,
    ErrorCode.DEVICE_DISABLED: ClientLicenseState.DEVICE_DISABLED,
    ErrorCode.INVALID_DEVICE_TOKEN: ClientLicenseState.UNACTIVATED,
    ErrorCode.LICENSE_NOT_FOUND: ClientLicenseState.UNACTIVATED,
}


class LauncherService:
    def __init__(
        self,
        *,
        layout: InstallLayout,
        state_storage: LicenseStateStorage,
        license_client: LicenseValidator,
        lease_keys: TrustedEd25519Keys,
        runtime: ApplicationRuntime,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.layout = layout
        self.state_storage = state_storage
        self.license_client = license_client
        self.lease_keys = lease_keys
        self.runtime = runtime
        self.now = now
        self.transactions = UpdateTransactionEngine(layout)

    def activate(
        self,
        *,
        license_key: str,
        identity: DeviceIdentity,
    ) -> LocalLicenseState:
        """Activate one device, verify the signed lease, and persist secrets."""
        if not isinstance(license_key, str) or not license_key.strip():
            raise ValueError("license_key is required")
        if not isinstance(identity, DeviceIdentity):
            raise TypeError("identity must be a DeviceIdentity")
        result = self.license_client.activate(
            license_key=license_key,
            device_id=identity.device_id,
            device_fingerprint=identity.fingerprint,
            device_name=identity.display_name,
            app_version=self.layout.load_current().current_version,
            launcher_version=LAUNCHER_VERSION,
        )
        if result.device_id != identity.device_id:
            raise UpdateError(
                ErrorCode.OFFLINE_LEASE_DENIED,
                "activation response is bound to another device",
            )
        lease = verify_signed_lease(
            result.lease_content,
            result.lease_signature,
            self.lease_keys,
            expected_device_id=identity.device_id,
            expected_license_id=result.license_id,
        )
        current_time = self.now()
        if current_time.tzinfo is None:
            raise ValueError("launcher clock must return a timezone-aware datetime")
        state = LocalLicenseState(
            license_id=result.license_id,
            license_key=license_key,
            device_id=result.device_id,
            device_token=result.device_token,
            lease_content=result.lease_content,
            lease_signature=result.lease_signature,
            local_launch_key=secrets.token_bytes(32),
            trusted_time=TrustedTimeState(
                last_server_time=lease.issued_at,
                last_wall_clock=_format_time(current_time),
            ),
        )
        self.state_storage.save(state)
        return state

    def _verify_stored_offline_lease(
        self,
        state: LocalLicenseState,
        current_time: datetime,
    ) -> _Authorization:
        try:
            state.trusted_time.assert_not_rolled_back(current_time)
            lease = verify_signed_lease(
                state.lease_content,
                state.lease_signature,
                self.lease_keys,
                expected_device_id=state.device_id,
                expected_license_id=state.license_id,
            )
            client_state = lease.client_state_at(current_time)
        except (UpdateError, ValueError) as exc:
            return _Authorization(
                ClientLicenseState.LOCAL_STATE_CORRUPT,
                state,
                str(exc),
            )
        return _Authorization(client_state, state, "license service unavailable")

    def _authorize(
        self,
        state: LocalLicenseState,
        current_time: datetime,
    ) -> _Authorization:
        try:
            validation = self.license_client.validate(
                device_token=state.device_token,
                app_version=self.layout.load_current().current_version,
                launcher_version=LAUNCHER_VERSION,
            )
        except LicenseRejected as exc:
            return _Authorization(
                _REJECTION_STATES.get(exc.code, ClientLicenseState.UNACTIVATED),
                state,
                exc.message,
            )
        except LicenseServiceUnavailable:
            return self._verify_stored_offline_lease(state, current_time)

        if validation.license_id != state.license_id or validation.device_id != state.device_id:
            return _Authorization(
                ClientLicenseState.LOCAL_STATE_CORRUPT,
                state,
                "validation response identity mismatch",
            )
        try:
            verify_signed_lease(
                validation.lease_content,
                validation.lease_signature,
                self.lease_keys,
                expected_device_id=state.device_id,
                expected_license_id=state.license_id,
            )
            trusted_time = state.trusted_time.updated(
                server_time=_parse_time(validation.server_time),
                wall_clock=current_time,
            )
        except (UpdateError, ValueError) as exc:
            return _Authorization(
                ClientLicenseState.LOCAL_STATE_CORRUPT,
                state,
                str(exc),
            )
        refreshed = replace(
            state,
            lease_content=validation.lease_content,
            lease_signature=validation.lease_signature,
            trusted_time=trusted_time,
        )
        self.state_storage.save(refreshed)
        return _Authorization(ClientLicenseState.ONLINE_VALID, refreshed)

    def _recover_previous_interrupted_transaction(self, current_time: datetime) -> None:
        transaction = self.transactions.load()
        if transaction is None:
            return
        if transaction.state in {
            TransactionState.SWITCHING,
            TransactionState.STARTING,
            TransactionState.HEALTH_CHECKING,
            TransactionState.ROLLING_BACK,
        }:
            self.transactions.recover_interrupted(
                failed_at=_format_time(current_time),
                reason="launcher_recovered_interrupted_update",
            )

    def _begin_pending_update(
        self,
        current_time: datetime,
    ) -> UpdateTransaction | None:
        pending = load_pending_update(self.layout.pending_update_path)
        if pending is None:
            return None
        if self.transactions.failed_versions.is_failed(
            pending.version,
            pending.manifest_sha256,
        ):
            return None
        transaction = self.transactions.begin(
            transaction_id="txn_" + secrets.token_urlsafe(18),
            started_at=_format_time(current_time),
        )
        return self.transactions.apply_pointer_switch(
            transaction,
            activated_at=_format_time(current_time),
        )

    def _rollback_if_needed(
        self,
        transaction: UpdateTransaction | None,
        *,
        current_time: datetime,
        reason: str,
    ) -> None:
        if transaction is None:
            return
        self.transactions.rollback(
            transaction,
            failed_at=_format_time(current_time),
            reason=reason,
        )

    def _session_for(
        self,
        state: LocalLicenseState,
        version: str,
        current_time: datetime,
    ) -> Path:
        return create_launch_session(
            runtime_dir=self.layout.runtime_dir,
            local_launch_key=state.local_launch_key,
            app_version=version,
            device_id=state.device_id,
            lease_content=state.lease_content,
            now=current_time,
        )

    def start(self) -> LauncherResult:
        current_time = self.now()
        if current_time.tzinfo is None:
            raise ValueError("launcher clock must return a timezone-aware datetime")
        self.layout.ensure_directories()
        self._recover_previous_interrupted_transaction(current_time)
        transaction = self._begin_pending_update(current_time)

        try:
            state = self.state_storage.load()
        except UpdateError as exc:
            self._rollback_if_needed(
                transaction,
                current_time=current_time,
                reason="local_state_corrupt",
            )
            return LauncherResult(
                LauncherStatus.BLOCKED,
                version=self.layout.load_current().current_version,
                license_state=ClientLicenseState.LOCAL_STATE_CORRUPT,
                reason=exc.message,
            )
        if state is None:
            self._rollback_if_needed(
                transaction,
                current_time=current_time,
                reason="license_activation_required",
            )
            return LauncherResult(
                LauncherStatus.ACTIVATION_REQUIRED,
                version=self.layout.load_current().current_version,
                license_state=ClientLicenseState.UNACTIVATED,
                reason="local license state is missing",
            )

        authorization = self._authorize(state, current_time)
        if not authorization.allowed:
            self._rollback_if_needed(
                transaction,
                current_time=current_time,
                reason=authorization.state.value,
            )
            return LauncherResult(
                LauncherStatus.BLOCKED,
                version=self.layout.load_current().current_version,
                license_state=authorization.state,
                reason=authorization.reason,
            )

        active = self.layout.load_current()
        session_path = self._session_for(
            authorization.local_state,
            active.current_version,
            current_time,
        )
        process = None
        try:
            process = self.runtime.start(active.current_version, session_path)
            if transaction is not None:
                transaction = self.transactions.mark_health_checking(
                    transaction,
                    updated_at=_format_time(current_time),
                )
            self.runtime.wait_healthy(active.current_version)
        except Exception as exc:
            if process is not None:
                try:
                    self.runtime.stop(process)
                except Exception:
                    pass
            if transaction is None:
                return LauncherResult(
                    LauncherStatus.FAILED,
                    version=active.current_version,
                    license_state=authorization.state,
                    reason=str(exc),
                )
            rolled_back = self.transactions.rollback(
                transaction,
                failed_at=_format_time(current_time),
                reason=str(exc) or "new_version_health_failed",
            )
            restored = self.layout.load_current()
            rollback_session = self._session_for(
                authorization.local_state,
                restored.current_version,
                current_time,
            )
            rollback_process = None
            try:
                rollback_process = self.runtime.start(
                    restored.current_version,
                    rollback_session,
                )
                self.runtime.wait_healthy(restored.current_version)
            except Exception as rollback_error:
                if rollback_process is not None:
                    try:
                        self.runtime.stop(rollback_process)
                    except Exception:
                        pass
                return LauncherResult(
                    LauncherStatus.FAILED,
                    version=restored.current_version,
                    license_state=authorization.state,
                    reason=f"update failed and rollback was unhealthy: {rollback_error}",
                )
            return LauncherResult(
                LauncherStatus.ROLLED_BACK,
                version=restored.current_version,
                license_state=authorization.state,
                reason=rolled_back.failure_reason,
                process=rollback_process,
            )

        if transaction is not None:
            self.transactions.commit(
                transaction,
                committed_at=_format_time(current_time),
            )
            return LauncherResult(
                LauncherStatus.UPDATED,
                version=active.current_version,
                license_state=authorization.state,
                process=process,
            )
        return LauncherResult(
            LauncherStatus.STARTED,
            version=active.current_version,
            license_state=authorization.state,
            process=process,
        )
