import importlib.util
import tomllib
import unittest
from pathlib import Path

from wechat_cli.version import APP_VERSION, PRODUCT, UPDATE_SCHEMA_VERSION


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

        self.assertEqual(project_version, APP_VERSION)

    def test_packager_uses_checked_shared_version(self):
        package = load_package_script()

        self.assertEqual(APP_VERSION, package.read_version())

    def test_product_and_schema_contract_are_stable(self):
        self.assertEqual("wechat-cli-web", PRODUCT)
        self.assertEqual(1, UPDATE_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
