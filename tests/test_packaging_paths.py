from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.packaging_paths import PackagingPathError, assert_outside_repository


ROOT = Path(__file__).resolve().parents[1]


class PackagingPathTests(unittest.TestCase):
    def test_repository_root_is_rejected(self):
        with self.assertRaises(PackagingPathError):
            assert_outside_repository(ROOT, repository_root=ROOT)

    def test_repository_child_is_rejected(self):
        with self.assertRaises(PackagingPathError):
            assert_outside_repository(ROOT / "dist", repository_root=ROOT)

    def test_normalized_repository_path_is_rejected(self):
        with self.assertRaises(PackagingPathError):
            assert_outside_repository(
                ROOT / "dist" / ".." / "artifacts",
                repository_root=ROOT,
            )

    def test_external_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "artifacts"
            self.assertEqual(
                target.resolve(),
                assert_outside_repository(target, repository_root=ROOT),
            )


if __name__ == "__main__":
    unittest.main()
