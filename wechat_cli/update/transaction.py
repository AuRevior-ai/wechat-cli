"""Crash-recoverable version switch transaction state machine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from .layout import InstallLayout
from .state import atomic_write_json, load_pending_update, read_json_object
from .versioning import SemanticVersion


class TransactionState(str, Enum):
    PREPARED = "prepared"
    SWITCHING = "switching"
    STARTING = "starting"
    HEALTH_CHECKING = "health_checking"
    COMMITTED = "committed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"


_ALLOWED_TRANSITIONS = {
    TransactionState.PREPARED: {TransactionState.SWITCHING},
    TransactionState.SWITCHING: {
        TransactionState.STARTING,
        TransactionState.ROLLING_BACK,
    },
    TransactionState.STARTING: {
        TransactionState.HEALTH_CHECKING,
        TransactionState.ROLLING_BACK,
    },
    TransactionState.HEALTH_CHECKING: {
        TransactionState.COMMITTED,
        TransactionState.ROLLING_BACK,
    },
    TransactionState.ROLLING_BACK: {TransactionState.ROLLED_BACK},
    TransactionState.COMMITTED: set(),
    TransactionState.ROLLED_BACK: set(),
}


def _timestamp(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("transaction timestamp must include a timezone")
    return value


@dataclass(frozen=True)
class UpdateTransaction:
    transaction_id: str
    release_id: str
    from_version: str
    from_previous_version: str | None
    from_manifest_sha256: str
    to_version: str
    to_manifest_sha256: str
    state: TransactionState
    started_at: str
    updated_at: str
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.transaction_id or not self.release_id:
            raise ValueError("transaction and release IDs are required")
        SemanticVersion.parse(self.from_version)
        SemanticVersion.parse(self.to_version)
        if self.from_previous_version is not None:
            SemanticVersion.parse(self.from_previous_version)
        for digest in (self.from_manifest_sha256, self.to_manifest_sha256):
            if len(digest) != 64:
                raise ValueError("transaction manifest hashes must be SHA-256 values")
            int(digest, 16)
        _timestamp(self.started_at)
        _timestamp(self.updated_at)

    def to_mapping(self) -> dict[str, Any]:
        return {
            "transaction_id": self.transaction_id,
            "release_id": self.release_id,
            "from_version": self.from_version,
            "from_previous_version": self.from_previous_version,
            "from_manifest_sha256": self.from_manifest_sha256.lower(),
            "to_version": self.to_version,
            "to_manifest_sha256": self.to_manifest_sha256.lower(),
            "state": self.state.value,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "UpdateTransaction":
        try:
            previous = data.get("from_previous_version")
            failure_reason = data.get("failure_reason")
            if previous is not None and not isinstance(previous, str):
                raise ValueError("from_previous_version must be null or text")
            if failure_reason is not None and not isinstance(failure_reason, str):
                raise ValueError("failure_reason must be null or text")
            return cls(
                transaction_id=str(data["transaction_id"]),
                release_id=str(data["release_id"]),
                from_version=str(data["from_version"]),
                from_previous_version=previous,
                from_manifest_sha256=str(data["from_manifest_sha256"]),
                to_version=str(data["to_version"]),
                to_manifest_sha256=str(data["to_manifest_sha256"]),
                state=TransactionState(data["state"]),
                started_at=str(data["started_at"]),
                updated_at=str(data["updated_at"]),
                failure_reason=failure_reason,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RuntimeError("update transaction state is invalid") from exc


class FailedVersionRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path

    @staticmethod
    def _key(version: str, manifest_sha256: str) -> str:
        SemanticVersion.parse(version)
        if len(manifest_sha256) != 64:
            raise ValueError("manifest_sha256 must contain 64 characters")
        int(manifest_sha256, 16)
        return f"{version}|{manifest_sha256.lower()}"

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"failures": {}}
        data = read_json_object(self.path)
        failures = data.get("failures")
        if not isinstance(failures, dict):
            raise RuntimeError("failed version registry is invalid")
        return {"failures": failures}

    def is_failed(self, version: str, manifest_sha256: str) -> bool:
        return self._key(version, manifest_sha256) in self._load()["failures"]

    def failed_versions(self) -> list[str]:
        versions = {
            entry.get("version")
            for entry in self._load()["failures"].values()
            if isinstance(entry, Mapping) and isinstance(entry.get("version"), str)
        }
        valid: list[str] = []
        for version in versions:
            try:
                SemanticVersion.parse(version)
            except ValueError:
                continue
            valid.append(version)
        return sorted(valid, key=SemanticVersion.parse)

    def failed_releases(self) -> list[dict[str, str]]:
        exact: dict[str, dict[str, str]] = {}
        for entry in self._load()["failures"].values():
            if not isinstance(entry, Mapping):
                continue
            version = entry.get("version")
            manifest_sha256 = entry.get("manifest_sha256")
            if not isinstance(version, str) or not isinstance(manifest_sha256, str):
                continue
            try:
                key = self._key(version, manifest_sha256)
            except (ValueError, TypeError):
                continue
            exact[key] = {
                "version": version,
                "manifest_sha256": manifest_sha256.lower(),
            }
        return sorted(
            exact.values(),
            key=lambda item: (SemanticVersion.parse(item["version"]), item["manifest_sha256"]),
        )

    def mark_failed(
        self,
        *,
        version: str,
        manifest_sha256: str,
        failed_at: str,
        reason: str,
    ) -> None:
        _timestamp(failed_at)
        if not reason:
            raise ValueError("failure reason is required")
        data = self._load()
        data["failures"][self._key(version, manifest_sha256)] = {
            "version": version,
            "manifest_sha256": manifest_sha256.lower(),
            "failed_at": failed_at,
            "reason": reason,
        }
        atomic_write_json(self.path, data)


class UpdateTransactionEngine:
    def __init__(self, layout: InstallLayout) -> None:
        self.layout = layout
        self.failed_versions = FailedVersionRegistry(layout.failed_versions_path)

    def load(self) -> UpdateTransaction | None:
        if not self.layout.transaction_path.exists():
            return None
        return UpdateTransaction.from_mapping(read_json_object(self.layout.transaction_path))

    def _save(self, transaction: UpdateTransaction) -> UpdateTransaction:
        atomic_write_json(self.layout.transaction_path, transaction.to_mapping())
        return transaction

    def _transition(
        self,
        transaction: UpdateTransaction,
        state: TransactionState,
        *,
        updated_at: str | None = None,
        failure_reason: str | None = None,
    ) -> UpdateTransaction:
        if state not in _ALLOWED_TRANSITIONS[transaction.state]:
            raise RuntimeError(
                f"invalid update transaction transition: {transaction.state.value} -> {state.value}"
            )
        return self._save(
            replace(
                transaction,
                state=state,
                updated_at=updated_at or transaction.updated_at,
                failure_reason=failure_reason,
            )
        )

    def begin(self, *, transaction_id: str, started_at: str) -> UpdateTransaction:
        pending = load_pending_update(self.layout.pending_update_path)
        if pending is None:
            raise RuntimeError("no pending update is ready to install")
        if self.failed_versions.is_failed(pending.version, pending.manifest_sha256):
            raise RuntimeError("pending update is already marked as failed")
        target = self.layout.version_path(pending.version)
        if not target.is_dir():
            raise RuntimeError("pending update version directory is missing")
        current = self.layout.load_current()
        transaction = UpdateTransaction(
            transaction_id=transaction_id,
            release_id=pending.release_id,
            from_version=current.current_version,
            from_previous_version=current.previous_version,
            from_manifest_sha256=current.manifest_sha256,
            to_version=pending.version,
            to_manifest_sha256=pending.manifest_sha256,
            state=TransactionState.PREPARED,
            started_at=started_at,
            updated_at=started_at,
        )
        return self._save(transaction)

    def apply_pointer_switch(
        self,
        transaction: UpdateTransaction,
        *,
        activated_at: str,
    ) -> UpdateTransaction:
        transaction = self._transition(
            transaction,
            TransactionState.SWITCHING,
            updated_at=activated_at,
        )
        self.layout.activate_version(
            transaction.to_version,
            manifest_sha256=transaction.to_manifest_sha256,
            activated_at=activated_at,
        )
        return self._transition(
            transaction,
            TransactionState.STARTING,
            updated_at=activated_at,
        )

    def mark_health_checking(
        self,
        transaction: UpdateTransaction,
        *,
        updated_at: str | None = None,
    ) -> UpdateTransaction:
        return self._transition(
            transaction,
            TransactionState.HEALTH_CHECKING,
            updated_at=updated_at,
        )

    def commit(
        self,
        transaction: UpdateTransaction,
        *,
        committed_at: str | None = None,
    ) -> UpdateTransaction:
        transaction = self._transition(
            transaction,
            TransactionState.COMMITTED,
            updated_at=committed_at,
        )
        try:
            self.layout.pending_update_path.unlink()
        except FileNotFoundError:
            pass
        self.layout.prune_versions(self.layout.load_current())
        return transaction

    def rollback(
        self,
        transaction: UpdateTransaction,
        *,
        failed_at: str,
        reason: str,
    ) -> UpdateTransaction:
        if transaction.state == TransactionState.ROLLING_BACK:
            rolling_back = transaction
        else:
            rolling_back = self._transition(
                transaction,
                TransactionState.ROLLING_BACK,
                updated_at=failed_at,
                failure_reason=reason,
            )
        self.layout.restore_version(
            rolling_back.from_version,
            previous_version=rolling_back.from_previous_version,
            manifest_sha256=rolling_back.from_manifest_sha256,
            activated_at=failed_at,
        )
        self.failed_versions.mark_failed(
            version=rolling_back.to_version,
            manifest_sha256=rolling_back.to_manifest_sha256,
            failed_at=failed_at,
            reason=reason,
        )
        return self._transition(
            rolling_back,
            TransactionState.ROLLED_BACK,
            updated_at=failed_at,
            failure_reason=reason,
        )

    def recover_interrupted(
        self,
        *,
        failed_at: str,
        reason: str,
    ) -> UpdateTransaction | None:
        transaction = self.load()
        if transaction is None:
            return None
        if transaction.state in {
            TransactionState.COMMITTED,
            TransactionState.ROLLED_BACK,
            TransactionState.PREPARED,
        }:
            return transaction
        return self.rollback(transaction, failed_at=failed_at, reason=reason)
