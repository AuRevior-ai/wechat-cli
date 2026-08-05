import json
import tempfile
import unittest
from pathlib import Path

from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.update.state import (
    PendingUpdate,
    atomic_write_json,
    load_pending_update,
    read_json_object,
    save_pending_update,
)


class AtomicJsonStateTests(unittest.TestCase):
    def test_atomic_write_json_replaces_existing_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state" / "current.json"
            atomic_write_json(path, {"version": "0.4.2"})
            atomic_write_json(path, {"version": "0.5.0"})

            self.assertEqual({"version": "0.5.0"}, json.loads(path.read_text("utf-8")))
            self.assertEqual([], list(path.parent.glob("*.tmp")))

    def test_read_json_object_rejects_truncated_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text('{"version":', encoding="utf-8")

            with self.assertRaises(UpdateError) as caught:
                read_json_object(path)

        self.assertEqual(ErrorCode.LOCAL_STATE_CORRUPT, caught.exception.code)

    def test_read_json_object_rejects_non_object_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("[]", encoding="utf-8")

            with self.assertRaises(UpdateError) as caught:
                read_json_object(path)

        self.assertEqual(ErrorCode.LOCAL_STATE_CORRUPT, caught.exception.code)


class PendingUpdateTests(unittest.TestCase):
    def test_round_trips_pending_update(self):
        pending = PendingUpdate(
            release_id="rel_test_050",
            version="0.5.0",
            prepared_path="versions\\0.5.0",
            manifest_sha256="ab" * 32,
            prepared_at="2026-08-04T15:00:00Z",
            install_on_next_start=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-update.json"

            save_pending_update(path, pending)
            loaded = load_pending_update(path)

        self.assertEqual(pending, loaded)

    def test_missing_pending_update_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(load_pending_update(Path(tmp) / "missing.json"))

    def test_rejects_invalid_pending_manifest_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "pending-update.json"
            atomic_write_json(
                path,
                {
                    "release_id": "rel",
                    "version": "0.5.0",
                    "prepared_path": "versions\\0.5.0",
                    "manifest_sha256": "bad",
                    "prepared_at": "2026-08-04T15:00:00Z",
                    "install_on_next_start": True,
                },
            )

            with self.assertRaises(UpdateError) as caught:
                load_pending_update(path)

        self.assertEqual(ErrorCode.LOCAL_STATE_CORRUPT, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
