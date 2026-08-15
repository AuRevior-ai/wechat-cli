import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "scripts" / "verify_local_update_artifacts.py"
    spec = importlib.util.spec_from_file_location("verify_local_update_artifacts_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_update_zip(path: Path) -> None:
    manifest = {
        "product": "wechat-cli-web",
        "version": "0.6.0",
        "platform": "windows",
        "architecture": "x86_64",
        "entrypoint": "wechat-cli.exe",
        "build_id": "dev",
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("wechat-cli.exe", b"fake-executable")
        archive.writestr(
            "app-manifest.json",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )


class UpdateOnlyArtifactVerificationTests(unittest.TestCase):
    def test_verifier_prefers_its_repository_source_outside_repo_cwd(self):
        verifier_path = ROOT / "scripts" / "verify_local_update_artifacts.py"
        code = (
            "import importlib.util,pathlib,sys;"
            f"path=pathlib.Path({str(verifier_path)!r});"
            "spec=importlib.util.spec_from_file_location('isolated_verifier',path);"
            "module=importlib.util.module_from_spec(spec);"
            "spec.loader.exec_module(module);"
            "version=sys.modules['wechat_cli.version'];"
            "print(module.APP_VERSION);"
            "print(pathlib.Path(version.__file__).resolve())"
        )
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=tmp,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                check=False,
            )

        self.assertEqual(0, completed.returncode, completed.stdout)
        lines = completed.stdout.strip().splitlines()
        self.assertEqual("0.6.0", lines[0])
        self.assertEqual(
            (ROOT / "wechat_cli" / "version.py").resolve(),
            Path(lines[1]).resolve(),
        )

    def test_verify_update_only_does_not_require_bootstrap_artifacts(self):
        verifier = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            update_zip = Path(tmp) / "wechat-cli-app-0.6.0-win-x64.zip"
            write_update_zip(update_zip)

            with patch.object(
                verifier,
                "_execute_version",
                return_value="wechat-cli, version 0.6.0",
            ):
                result = verifier.verify_update_only(update_zip=update_zip)

        self.assertTrue(result["ok"])
        self.assertEqual("wechat-cli-web", result["product"])
        self.assertEqual("0.6.0", result["version"])
        self.assertEqual("0.2.0", result["launcher_version"])
        self.assertTrue(result["manifest_signature_verified"])
        self.assertTrue(result["safe_extraction_verified"])
        self.assertEqual("wechat-cli, version 0.6.0", result["extracted_application_version"])
        self.assertNotIn("bootstrap_zip_sha256", result)

    def test_update_only_cli_routes_without_bootstrap_defaults(self):
        verifier = load_module()
        update_zip = Path("dist/wechat-cli-app-0.6.0-win-x64.zip")
        expected = {
            "ok": True,
            "product": "wechat-cli-web",
            "version": "0.6.0",
        }

        with patch.object(
            verifier,
            "verify_update_only",
            return_value=expected,
        ) as verify_update_only, patch.object(
            verifier,
            "verify",
            side_effect=AssertionError("bootstrap verification path used"),
        ):
            verifier.main(["--update-only", "--update-zip", str(update_zip)])

        verify_update_only.assert_called_once_with(update_zip=update_zip.resolve())


if __name__ == "__main__":
    unittest.main()
