import importlib.util
import os
import runpy
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.version import (
    APP_VERSION,
    BUILD_ID,
    LAUNCHER_VERSION,
    PRODUCT,
    UPDATE_SCHEMA_VERSION,
    production_build_id,
)


ROOT = Path(__file__).resolve().parents[1]


def load_package_script():
    path = ROOT / "scripts" / "package_windows_app.py"
    spec = importlib.util.spec_from_file_location("package_windows_app_version_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_build_script():
    path = ROOT / "npm" / "scripts" / "build.py"
    spec = importlib.util.spec_from_file_location("npm_build_version_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VersionMetadataTests(unittest.TestCase):
    def test_runtime_and_project_versions_match(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project_version = tomllib.load(stream)["project"]["version"]

        self.assertEqual("0.6.0", APP_VERSION)
        self.assertEqual("0.6.0", project_version)
        self.assertEqual(project_version, APP_VERSION)
        self.assertEqual("0.2.0", LAUNCHER_VERSION)

    def test_pywebview_is_pinned_to_board5_accepted_version(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            dependencies = tomllib.load(stream)["project"]["dependencies"]

        self.assertIn("pywebview==6.2.1", dependencies)
        self.assertFalse(any(item.startswith("pywebview>=") for item in dependencies))

    def test_default_build_id_is_not_a_historical_staging_identity(self):
        self.assertEqual("dev", BUILD_ID)

    def test_production_build_id_is_deterministic_from_full_lowercase_sha(self):
        source_sha = "0123456789abcdef0123456789abcdef01234567"
        self.assertEqual("prod-060-0123456789ab", production_build_id(source_sha))

    def test_production_build_id_rejects_untrusted_commit_strings(self):
        invalid = [
            "short",
            "A" * 40,
            "g" * 40,
            "0" * 39,
            "0" * 41,
            "0" * 39 + "\n",
        ]
        for source_sha in invalid:
            with self.subTest(source_sha=repr(source_sha)):
                with self.assertRaises(ValueError):
                    production_build_id(source_sha)

    def test_build_id_environment_override_is_preserved(self):
        version_path = ROOT / "wechat_cli" / "version.py"
        with patch.dict(os.environ, {"WECHAT_CLI_BUILD_ID": "override-build"}):
            loaded = runpy.run_path(str(version_path))

        self.assertEqual("override-build", loaded["BUILD_ID"])

    def test_packager_uses_checked_shared_version(self):
        package = load_package_script()

        self.assertEqual(APP_VERSION, package.read_version())

    def test_build_script_derives_production_environment_from_full_source_sha(self):
        build = load_build_script()
        source_sha = "abcdef0123456789abcdef0123456789abcdef01"
        environment = build.production_build_environment(source_sha, base_environment={"KEEP": "1"})
        self.assertEqual("1", environment["KEEP"])
        self.assertEqual("prod-060-abcdef012345", environment["WECHAT_CLI_BUILD_ID"])
        self.assertEqual(source_sha, environment["WECHAT_CLI_SOURCE_SHA"])

    def test_build_script_rejects_invalid_production_source_sha(self):
        build = load_build_script()
        with self.assertRaises(ValueError):
            build.production_build_environment("feature-branch")

    def test_product_and_schema_contract_are_stable(self):
        self.assertEqual("wechat-cli-web", PRODUCT)
        self.assertEqual(1, UPDATE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
