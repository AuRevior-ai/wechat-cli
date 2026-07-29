import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsPackagingTests(unittest.TestCase):
    def test_pyinstaller_command_bundles_web_static_files(self):
        build = load_module("npm_build", ROOT / "npm" / "scripts" / "build.py")

        cmd = build.make_pyinstaller_command("win32-x64")
        joined = "\n".join(cmd)

        self.assertIn("--add-data", cmd)
        self.assertIn("wechat_cli/web/static", joined.replace("\\", "/"))

    def test_pyinstaller_command_omits_missing_legacy_sqlcipher_imports(self):
        build = load_module("npm_build", ROOT / "npm" / "scripts" / "build.py")

        cmd = build.make_pyinstaller_command("win32-x64")

        self.assertNotIn("pysqlcipher3", cmd)
        self.assertNotIn("sqlcipher3", cmd)
        self.assertNotIn("Cryptodome", cmd)

    def test_package_manifest_contains_one_click_entrypoints(self):
        package = load_module("package_windows_app", ROOT / "scripts" / "package_windows_app.py")

        manifest = package.build_manifest()

        self.assertIn("install.ps1", manifest)
        self.assertIn("start-wechat-cli-web.bat", manifest)
        self.assertIn("README-APP.md", manifest)
        self.assertIn("THIRD_PARTY_NOTICES.md", manifest)
        self.assertIn("app/wechat-cli.exe", [item.replace("\\", "/") for item in manifest])

    def test_installer_stops_running_installed_exe_before_copying(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("Stop-InstalledWeChatCliWeb", script)
        self.assertIn("Get-CimInstance Win32_Process", script)
        self.assertIn("Stop-Process -Id", script)
        self.assertLess(
            script.index("Stop-InstalledWeChatCliWeb -TargetExePath"),
            script.index("Copy-WithRetry -Recurse"),
        )

    def test_installer_stops_legacy_portable_web_server_on_default_port(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("$MatchesDefaultWebServer", script)
        self.assertIn("'(^|\\s)web(\\s|$)'", script)
        self.assertIn("'--port(?:\\s+|=)8787(?:\\s|$)'", script)
        self.assertIn(
            "$MatchesExe -or $MatchesInstallDir -or $MatchesDefaultWebServer",
            script,
        )

    def test_installer_closes_launcher_parent_of_stopped_portable_server(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("$StoppedServerParentIds", script)
        self.assertIn("$StoppedServerParentIds -contains $_.ProcessId", script)

    def test_installer_retries_copy_after_stopping_old_server(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("function Copy-WithRetry", script)
        self.assertIn("Start-Sleep -Milliseconds", script)
        self.assertIn("Copy-Item -Force -Recurse", script)
        self.assertIn("Please close any remaining WeChat CLI Web command windows", script)

    def test_installer_closes_old_launcher_window(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("Closing old WeChat CLI Web launcher window", script)
        self.assertIn("name = 'cmd.exe'", script)


if __name__ == "__main__":
    unittest.main()
