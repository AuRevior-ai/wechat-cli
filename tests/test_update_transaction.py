import tempfile
import unittest
from pathlib import Path

from wechat_cli.update.layout import CurrentVersion, InstallLayout
from wechat_cli.update.state import PendingUpdate, save_pending_update
from wechat_cli.update.transaction import (
    TransactionState,
    UpdateTransactionEngine,
)


class UpdateTransactionTests(unittest.TestCase):
    def make_layout(self, root: Path) -> InstallLayout:
        layout = InstallLayout(root / "WeChatCliWeb")
        layout.ensure_directories()
        for version in ("0.4.2", "0.5.0"):
            directory = layout.version_path(version)
            directory.mkdir()
            (directory / "wechat-cli.exe").write_text(version, encoding="utf-8")
        layout.save_current(
            CurrentVersion(
                current_version="0.4.2",
                previous_version=None,
                channel="stable",
                activated_at="2026-08-04T14:00:00Z",
                manifest_sha256="11" * 32,
            )
        )
        save_pending_update(
            layout.pending_update_path,
            PendingUpdate(
                release_id="rel_050",
                version="0.5.0",
                prepared_path="versions\\0.5.0",
                manifest_sha256="22" * 32,
                prepared_at="2026-08-04T14:30:00Z",
                install_on_next_start=True,
            ),
        )
        return layout

    def test_successful_switch_moves_through_transaction_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            engine = UpdateTransactionEngine(layout)

            transaction = engine.begin(
                transaction_id="txn_success",
                started_at="2026-08-04T15:00:00Z",
            )
            self.assertEqual(TransactionState.PREPARED, transaction.state)

            transaction = engine.apply_pointer_switch(
                transaction,
                activated_at="2026-08-04T15:00:01Z",
            )
            self.assertEqual(TransactionState.STARTING, transaction.state)
            self.assertEqual("0.5.0", layout.load_current().current_version)

            transaction = engine.mark_health_checking(transaction)
            self.assertEqual(TransactionState.HEALTH_CHECKING, transaction.state)

            transaction = engine.commit(transaction)
            self.assertEqual(TransactionState.COMMITTED, transaction.state)
            self.assertFalse(layout.pending_update_path.exists())
            self.assertEqual(transaction, engine.load())

    def test_recovery_rolls_back_switch_that_was_not_committed(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            engine = UpdateTransactionEngine(layout)
            transaction = engine.begin(
                transaction_id="txn_interrupted",
                started_at="2026-08-04T15:00:00Z",
            )
            transaction = engine.apply_pointer_switch(
                transaction,
                activated_at="2026-08-04T15:00:01Z",
            )
            transaction = engine.mark_health_checking(transaction)

            recovered = UpdateTransactionEngine(layout).recover_interrupted(
                failed_at="2026-08-04T15:01:00Z",
                reason="health_check_timeout",
            )

            self.assertEqual(TransactionState.ROLLED_BACK, recovered.state)
            self.assertEqual("0.4.2", layout.load_current().current_version)
            self.assertTrue(
                engine.failed_versions.is_failed("0.5.0", "22" * 32)
            )

    def test_explicit_rollback_marks_failed_version_and_keeps_pending_for_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            engine = UpdateTransactionEngine(layout)
            transaction = engine.begin(
                transaction_id="txn_failure",
                started_at="2026-08-04T15:00:00Z",
            )
            transaction = engine.apply_pointer_switch(
                transaction,
                activated_at="2026-08-04T15:00:01Z",
            )

            rolled_back = engine.rollback(
                transaction,
                failed_at="2026-08-04T15:00:30Z",
                reason="process_exited",
            )

            self.assertEqual(TransactionState.ROLLED_BACK, rolled_back.state)
            self.assertTrue(layout.pending_update_path.exists())
            self.assertTrue(engine.failed_versions.is_failed("0.5.0", "22" * 32))

    def test_committed_transaction_is_not_rolled_back_during_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            engine = UpdateTransactionEngine(layout)
            transaction = engine.begin(
                transaction_id="txn_committed",
                started_at="2026-08-04T15:00:00Z",
            )
            transaction = engine.apply_pointer_switch(
                transaction,
                activated_at="2026-08-04T15:00:01Z",
            )
            transaction = engine.commit(engine.mark_health_checking(transaction))

            recovered = UpdateTransactionEngine(layout).recover_interrupted(
                failed_at="2026-08-04T15:02:00Z",
                reason="should_not_apply",
            )

            self.assertEqual(TransactionState.COMMITTED, recovered.state)
            self.assertEqual("0.5.0", layout.load_current().current_version)

    def test_failed_registry_serializes_exact_release_identities(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            registry = UpdateTransactionEngine(layout).failed_versions
            registry.mark_failed(
                version="0.5.1",
                manifest_sha256="BB" * 32,
                failed_at="2026-08-04T14:50:00Z",
                reason="second_failure",
            )
            registry.mark_failed(
                version="0.5.0",
                manifest_sha256="AA" * 32,
                failed_at="2026-08-04T14:40:00Z",
                reason="first_failure",
            )

            self.assertTrue(
                callable(getattr(registry, "failed_releases", None)),
                "FailedVersionRegistry must expose failed_releases()",
            )
            self.assertEqual(
                [
                    {"version": "0.5.0", "manifest_sha256": "aa" * 32},
                    {"version": "0.5.1", "manifest_sha256": "bb" * 32},
                ],
                registry.failed_releases(),
            )

    def test_begin_rejects_known_failed_version_with_same_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            layout = self.make_layout(Path(tmp))
            engine = UpdateTransactionEngine(layout)
            engine.failed_versions.mark_failed(
                version="0.5.0",
                manifest_sha256="22" * 32,
                failed_at="2026-08-04T14:50:00Z",
                reason="prior_failure",
            )

            with self.assertRaises(RuntimeError):
                engine.begin(
                    transaction_id="txn_repeat",
                    started_at="2026-08-04T15:00:00Z",
                )


if __name__ == "__main__":
    unittest.main()
