import importlib.util
import os
import runpy
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from wechat_cli.version import APP_VERSION, BUILD_ID, LAUNCHER_VERSION, PRODUCT, UPDATE_SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]


def load_package_script():
    path = ROOT / "scripts" / "package_windows_app.py"
    spec = importlib.util.spec_from_file_location("package_windows_app_version_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VersionMetadataTests(unittest.TestCase):
    def test_runtime_and_project_versions_match(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            project_version = tomllib.load(stream)["project"]["version"]

        self.assertEqual("0.5.1", APP_VERSION)
        self.assertEqual("0.5.1", project_version)
        self.assertEqual(project_version, APP_VERSION)
        self.assertEqual("0.1.0", LAUNCHER_VERSION)

    def test_pywebview_is_pinned_to_board5_accepted_version(self):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            dependencies = tomllib.load(stream)["project"]["dependencies"]

        self.assertIn("pywebview==6.2.1", dependencies)
        self.assertFalse(any(item.startswith("pywebview>=") for item in dependencies))

    def test_default_build_id_identifies_staging_051(self):
        self.assertEqual("staging-051-20260808.1", BUILD_ID)

    def test_build_id_environment_override_is_preserved(self):
        version_path = ROOT / "wechat_cli" / "version.py"
        with patch.dict(os.environ, {"WECHAT_CLI_BUILD_ID": "override-build"}):
            loaded = runpy.run_path(str(version_path))

        self.assertEqual("override-build", loaded["BUILD_ID"])

    def test_packager_uses_checked_shared_version(self):
        package = load_package_script()

        self.assertEqual(APP_VERSION, package.read_version())

    def test_product_and_schema_contract_are_stable(self):
        self.assertEqual("wechat-cli-web", PRODUCT)
        self.assertEqual(1, UPDATE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
