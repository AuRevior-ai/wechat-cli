import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER_ENTRY = ROOT / "packaging" / "windows" / "installer_entry.py"


def load_installer_module():
    spec = importlib.util.spec_from_file_location("board6_installer_entry", INSTALLER_ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsInstallerTests(unittest.TestCase):
    def test_installer_entry_source_exists(self):
        self.assertTrue(INSTALLER_ENTRY.is_file())

    def test_installer_entry_exports_runner_contract(self):
        module = load_installer_module()
        self.assertTrue(callable(getattr(module, "run_installer", None)))

    def test_installer_runs_embedded_transaction_script_without_shell(self):
        module = load_installer_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = root / "bootstrap_payload"
            payload.mkdir()
            script = payload / "install.ps1"
            script.write_text("# transaction-aware installer", encoding="utf-8")
            calls = []

            class Completed:
                returncode = 0

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return Completed()

            try:
                result = module.run_installer(
                    args=["-NoStart", "-NoShortcuts"],
                    base_dir=root,
                    runner=runner,
                )
            except Exception as exc:
                self.fail(f"embedded installer runner failed: {exc}")

        self.assertEqual(0, result)
        command, kwargs = calls[0]
        self.assertEqual("powershell.exe", command[0])
        self.assertIn(str(script), command)
        self.assertEqual(["-NoStart", "-NoShortcuts"], command[-2:])
        self.assertEqual(str(payload), kwargs["cwd"])
        self.assertFalse(kwargs["shell"])
        self.assertFalse(kwargs["check"])


if __name__ == "__main__":
    unittest.main()
