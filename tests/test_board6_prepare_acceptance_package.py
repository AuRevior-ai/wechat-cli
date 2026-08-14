import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class Board6AcceptancePackageTests(unittest.TestCase):
    def test_direct_script_help_starts_without_import_error(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "board6_prepare_acceptance_package.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--known-good-exe", result.stdout)

    def test_module_exports_scoped_contract(self):
        from scripts import board6_prepare_acceptance_package as module

        self.assertEqual("0.5.2-board6g5.1", module.CANDIDATE_VERSION)
        self.assertEqual("staging-051-20260808.1", module.CANDIDATE_BUILD_ID)
        self.assertTrue(callable(getattr(module, "prepare_acceptance_package", None)))

    def test_rejects_wrong_source_hash_version_build_and_repo_output(self):
        from scripts import board6_prepare_acceptance_package as module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "wechat-cli.exe"
            source.write_bytes(b"not-the-frozen-exe")
            output = root / "candidate.zip"
            with self.assertRaises(ValueError):
                module.prepare_acceptance_package(source, output)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "wechat-cli.exe"
            payload = b"frozen-placeholder"
            source.write_bytes(payload)
            with mock.patch.object(module, "FROZEN_EXE_SIZE", len(payload)), mock.patch.object(
                module,
                "FROZEN_EXE_SHA256",
                hashlib.sha256(payload).hexdigest(),
            ):
                with self.assertRaises(ValueError):
                    module.prepare_acceptance_package(
                        source,
                        root / "candidate.zip",
                        candidate_version="0.5.2-other.1",
                    )
                with self.assertRaises(ValueError):
                    module.prepare_acceptance_package(
                        source,
                        root / "candidate.zip",
                        build_id="other-build",
                    )
                with self.assertRaises(ValueError):
                    module.prepare_acceptance_package(
                        source,
                        module.ROOT / "candidate.zip",
                    )

    def test_builds_two_member_zip_with_frozen_exe_and_exact_manifest(self):
        from scripts import board6_prepare_acceptance_package as module

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "wechat-cli.exe"
            payload = b"frozen-exe-placeholder"
            source.write_bytes(payload)
            output = root / "external" / "candidate.zip"
            with mock.patch.object(module, "FROZEN_EXE_SIZE", len(payload)), mock.patch.object(
                module,
                "FROZEN_EXE_SHA256",
                hashlib.sha256(payload).hexdigest(),
            ), mock.patch.object(module, "assert_outside_repository", return_value=output):
                result = module.prepare_acceptance_package(source, output)

            self.assertEqual(output, result)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual({"wechat-cli.exe", "app-manifest.json"}, set(archive.namelist()))
                self.assertEqual(payload, archive.read("wechat-cli.exe"))
                manifest = json.loads(archive.read("app-manifest.json"))
            self.assertEqual("wechat-cli-web", manifest["product"])
            self.assertEqual(module.CANDIDATE_VERSION, manifest["version"])
            self.assertEqual(module.CANDIDATE_BUILD_ID, manifest["build_id"])
            self.assertEqual("windows", manifest["platform"])
            self.assertEqual("x86_64", manifest["architecture"])
            self.assertEqual("wechat-cli.exe", manifest["entrypoint"])


if __name__ == "__main__":
    unittest.main()
