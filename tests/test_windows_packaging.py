import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from wechat_cli.version import APP_VERSION


ROOT = Path(__file__).resolve().parents[1]


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowsPackagingTests(unittest.TestCase):
    def test_package_script_help_works_under_direct_execution(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "package_windows_app.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--launcher-config", result.stdout)
        self.assertIn("--update-only", result.stdout)

    def test_package_script_production_path_resolves_project_imports_under_direct_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher_config = root / "launcher-config.json"
            trust_profile = root / "invalid-trust-profile.json"
            output_dir = root / "output"
            launcher_config.write_text("{}", encoding="utf-8")
            trust_profile.write_text("{}", encoding="utf-8")
            output_dir.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "package_windows_app.py"),
                    "--production-installer",
                    "--launcher-config",
                    str(launcher_config),
                    "--launcher-trust-profile",
                    str(trust_profile),
                    "--output-dir",
                    str(output_dir),
                    "--source-sha",
                    "a" * 40,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("unsupported deployment trust profile schema", result.stderr)
        self.assertNotIn("ModuleNotFoundError", result.stderr)

    def test_release_metadata_and_windows_guide_credit_author(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        guide = (
            ROOT / "packaging" / "windows" / "README-APP.md"
        ).read_text(encoding="utf-8")

        self.assertIn('version = "0.6.1.dev1"', pyproject)
        self.assertIn('authors = [{ name = "Au Revior" }]', pyproject)
        self.assertIn("作者：Au Revior", guide)
        self.assertIn("关于与支持", guide)

    def test_pyinstaller_command_bundles_web_static_files(self):
        build = load_module("npm_build", ROOT / "npm" / "scripts" / "build.py")

        cmd = build.make_pyinstaller_command("win32-x64", "app")
        joined = "\n".join(cmd)

        self.assertIn("--add-data", cmd)
        self.assertIn("wechat_cli/web/static", joined.replace("\\", "/"))
        self.assertIn("entry.py", joined.replace("\\", "/"))
        self.assertNotIn("--windowed", cmd)

    def test_installer_pyinstaller_command_requires_explicit_payload(self):
        build = load_module(
            "npm_build_installer_requires_payload",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with self.assertRaisesRegex(ValueError, "payload"):
            build.make_pyinstaller_command("win32-x64", "installer")

    def test_installer_pyinstaller_command_embeds_bootstrap_payload(self):
        build = load_module(
            "npm_build_installer_payload",
            ROOT / "npm" / "scripts" / "build.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            payload = Path(tmp) / "bootstrap-payload"
            payload.mkdir()
            (payload / "install.ps1").write_text("# installer", encoding="utf-8")
            cmd = build.make_pyinstaller_command(
                "win32-x64",
                "installer",
                installer_payload_path=payload,
            )

        joined = "\n".join(cmd).replace("\\", "/")
        self.assertIn("wechat-cli-installer", cmd)
        self.assertIn("packaging/windows/installer_entry.py", joined)
        self.assertIn(str(payload).replace("\\", "/"), joined)
        self.assertIn("bootstrap_payload", joined)
        self.assertNotIn("--collect-all", cmd)
        self.assertNotIn("webview", cmd)

    def test_launcher_pyinstaller_command_requires_explicit_trust_profile(self):
        build = load_module(
            "npm_build_launcher_requires_profile",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with self.assertRaisesRegex(ValueError, "trust profile"):
            build.make_pyinstaller_command("win32-x64", "launcher")

    def test_launcher_pyinstaller_command_rejects_invalid_trust_profile(self):
        build = load_module(
            "npm_build_launcher_invalid_profile",
            ROOT / "npm" / "scripts" / "build.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "deployment-trust-profile.json"
            profile.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "trust profile"):
                build.make_pyinstaller_command(
                    "win32-x64",
                    "launcher",
                    trust_profile_path=profile,
                )

    def test_launcher_pyinstaller_command_rejects_invalid_private_production_trust_identity(self):
        build = load_module(
            "npm_build_launcher_private_prod_profile",
            ROOT / "npm" / "scripts" / "build.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "deployment-trust-profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "distribution_profile": "private_controlled",
                        "environment": "production",
                        "api_base_url": "https://api.example.test",
                        "expected_channel": "stable",
                        "fingerprint_salt": "fresh-production-fingerprint-salt",
                        "release_public_keys": {"release-key-staging-01": "release-key"},
                        "lease_public_keys": {"lease-key-production-01": "lease-key"},
                        "windows_publisher_policy": "",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "trust profile"):
                build.make_pyinstaller_command(
                    "win32-x64",
                    "launcher",
                    trust_profile_path=profile,
                )

    def test_launcher_pyinstaller_command_bundles_local_ui_and_webview(self):
        build = load_module("npm_build_launcher", ROOT / "npm" / "scripts" / "build.py")

        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "deployment-trust-profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "environment": "staging",
                        "api_base_url": "https://staging-api.example.test",
                        "expected_channel": "beta",
                        "fingerprint_salt": "build-test-salt",
                        "release_public_keys": {"release-test": "release-key"},
                        "lease_public_keys": {"lease-test": "lease-key"},
                        "windows_publisher_policy": "CN=Board6 Test Publisher",
                    }
                ),
                encoding="utf-8",
            )
            cmd = build.make_pyinstaller_command(
                "win32-x64",
                "launcher",
                trust_profile_path=profile,
            )
        joined = "\n".join(cmd).replace("\\", "/")

        self.assertIn("--windowed", cmd)
        self.assertIn("--collect-all", cmd)
        self.assertIn("webview", cmd)
        self.assertIn("wechat_cli/launcher/ui", joined)
        self.assertIn("deployment-trust-profile.json", joined)
        self.assertIn("wechat_cli/launcher", joined)
        self.assertIn("launcher_entry.py", joined)
        self.assertIn("wechat-cli-launcher", cmd)

    def test_launcher_build_stages_production_profile_under_runtime_filename(self):
        build = load_module(
            "npm_build_launcher_canonical_profile_name",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "production-trust-profile.json"
            profile.write_text("production-profile-bytes", encoding="utf-8")
            platforms = root / "platforms"
            captured = {}

            def make_command(platform, target, **kwargs):
                staged = Path(kwargs["trust_profile_path"])
                captured["name"] = staged.name
                captured["content"] = staged.read_text(encoding="utf-8")
                return ["fake-pyinstaller"]

            def check_call(_cmd, **_kwargs):
                output = platforms / "win32-x64" / "bin"
                output.mkdir(parents=True, exist_ok=True)
                (output / "wechat-cli-launcher.exe").write_bytes(b"launcher")

            with patch.object(build, "PLATFORMS_DIR", platforms), patch.object(
                build, "make_pyinstaller_command", side_effect=make_command
            ), patch.object(
                build, "ensure_target_dependencies"
            ), patch.object(
                build.subprocess, "check_call", side_effect=check_call
            ):
                self.assertTrue(
                    build.build_platform(
                        "win32-x64",
                        targets=["launcher"],
                        trust_profile_path=profile,
                    )
                )

        self.assertEqual("deployment-trust-profile.json", captured["name"])
        self.assertEqual("production-profile-bytes", captured["content"])

    def test_launcher_build_fails_fast_when_pywebview_is_missing(self):
        build = load_module(
            "npm_build_missing_webview",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with patch.object(build.importlib.util, "find_spec", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "pywebview"):
                build.ensure_target_dependencies("launcher")

    def test_application_build_does_not_require_pywebview(self):
        build = load_module(
            "npm_build_app_dependencies",
            ROOT / "npm" / "scripts" / "build.py",
        )

        def finder(module):
            return None if module == "webview" else object()

        build.ensure_target_dependencies("app", module_finder=finder)

    def test_windows_build_preflights_all_targets_before_running_pyinstaller(self):
        build = load_module(
            "npm_build_preflight",
            ROOT / "npm" / "scripts" / "build.py",
        )

        def dependency_check(target):
            if target == "launcher":
                raise RuntimeError("missing pywebview")

        with patch.object(
            build,
            "ensure_target_dependencies",
            side_effect=dependency_check,
        ) as dependency_mock, patch.object(build.subprocess, "check_call") as check_call:
            self.assertFalse(build.build_platform("win32-x64"))

        self.assertEqual(
            [item.args[0] for item in dependency_mock.call_args_list],
            ["app", "launcher"],
        )
        check_call.assert_not_called()

    def test_build_platform_accepts_explicit_installer_payload(self):
        build = load_module(
            "npm_build_platform_installer_contract",
            ROOT / "npm" / "scripts" / "build.py",
        )
        self.assertIn(
            "installer_payload_path",
            inspect.signature(build.build_platform).parameters,
        )

    def test_build_platform_accepts_explicit_launcher_trust_profile(self):
        build = load_module(
            "npm_build_platform_profile_contract",
            ROOT / "npm" / "scripts" / "build.py",
        )

        self.assertIn("trust_profile_path", inspect.signature(build.build_platform).parameters)

    def test_windows_app_only_build_preflights_and_builds_only_app(self):
        build = load_module(
            "npm_build_app_only",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            binary = output_root / "win32-x64" / "bin" / "wechat-cli.exe"

            def create_binary(*_args, **_kwargs):
                binary.write_bytes(b"app")

            with patch.object(build, "PLATFORMS_DIR", output_root), patch.object(
                build, "ensure_target_dependencies"
            ) as dependency_check, patch.object(
                build.subprocess, "check_call", side_effect=create_binary
            ) as check_call:
                self.assertTrue(build.build_platform("win32-x64", targets=["app"]))

        dependency_check.assert_called_once_with("app")
        self.assertEqual(1, check_call.call_count)
        joined = " ".join(check_call.call_args.args[0])
        self.assertIn("wechat-cli", joined)
        self.assertNotIn("wechat-cli-launcher", joined)

    def test_windows_build_with_source_sha_passes_deterministic_production_metadata(self):
        build = load_module(
            "npm_build_source_sha",
            ROOT / "npm" / "scripts" / "build.py",
        )
        source_sha = "abcdef0123456789abcdef0123456789abcdef01"
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            binary = output_root / "win32-x64" / "bin" / "wechat-cli.exe"

            def create_binary(*_args, **_kwargs):
                binary.write_bytes(b"app")

            with patch.object(build, "PLATFORMS_DIR", output_root), patch.object(
                build, "ensure_target_dependencies"
            ), patch.object(
                build.subprocess, "check_call", side_effect=create_binary
            ) as check_call:
                self.assertTrue(
                    build.build_platform(
                        "win32-x64",
                        targets=["app"],
                        source_sha=source_sha,
                    )
                )

        environment = check_call.call_args.kwargs["env"]
        self.assertEqual("prod-060-abcdef012345", environment["WECHAT_CLI_BUILD_ID"])
        self.assertEqual(source_sha, environment["WECHAT_CLI_SOURCE_SHA"])
        command = check_call.call_args.args[0]
        self.assertIn("--runtime-hook", command)

    def test_windows_installer_only_build_forwards_payload_and_checks_output(self):
        build = load_module(
            "npm_build_installer_only",
            ROOT / "npm" / "scripts" / "build.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_root = root / "platforms"
            payload = root / "payload"
            payload.mkdir()
            (payload / "install.ps1").write_text("# installer", encoding="utf-8")
            binary = output_root / "win32-x64" / "bin" / "wechat-cli-installer.exe"

            def create_binary(*_args, **_kwargs):
                binary.write_bytes(b"installer")

            with patch.object(build, "PLATFORMS_DIR", output_root), patch.object(
                build, "ensure_target_dependencies"
            ) as dependency_check, patch.object(
                build.subprocess, "check_call", side_effect=create_binary
            ) as check_call:
                try:
                    built = build.build_platform(
                        "win32-x64",
                        targets=["installer"],
                        installer_payload_path=payload,
                    )
                except Exception as exc:
                    self.fail(f"installer target was rejected: {exc}")
                self.assertTrue(built)

        dependency_check.assert_called_once_with("installer")
        joined = " ".join(check_call.call_args.args[0]).replace("\\", "/")
        self.assertIn("wechat-cli-installer", joined)
        self.assertIn(str(payload).replace("\\", "/"), joined)

    def test_windows_build_rejects_unknown_target_selection(self):
        build = load_module(
            "npm_build_unknown_target",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with self.assertRaisesRegex(ValueError, "Unknown or empty build target"):
            build.build_platform("win32-x64", targets=["unknown"])

    def test_build_cli_passes_explicit_app_target(self):
        build = load_module(
            "npm_build_cli_target",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with patch.object(
            build.sys, "argv", ["build.py", "win32-x64", "--target", "app"]
        ), patch.object(build, "ensure_pyinstaller"), patch.object(
            build, "build_platform", return_value=True
        ) as build_platform:
            build.main()

        build_platform.assert_called_once_with("win32-x64", targets=["app"])

    def test_build_cli_forwards_explicit_installer_payload(self):
        build = load_module(
            "npm_build_cli_installer_payload",
            ROOT / "npm" / "scripts" / "build.py",
        )
        payload = "C:/external/bootstrap-payload"

        with patch.object(
            build.sys,
            "argv",
            [
                "build.py",
                "win32-x64",
                "--target",
                "installer",
                "--installer-payload",
                payload,
            ],
        ), patch.object(build, "ensure_pyinstaller"), patch.object(
            build, "build_platform", return_value=True
        ) as build_platform:
            try:
                build.main()
            except SystemExit as exc:
                self.fail(f"installer payload CLI was rejected: {exc}")

        build_platform.assert_called_once_with(
            "win32-x64",
            targets=["installer"],
            installer_payload_path=payload,
        )

    def test_build_cli_forwards_explicit_launcher_trust_profile(self):
        build = load_module(
            "npm_build_cli_trust_profile",
            ROOT / "npm" / "scripts" / "build.py",
        )
        profile = "C:/external/deployment-trust-profile.json"

        with patch.object(
            build.sys,
            "argv",
            [
                "build.py",
                "win32-x64",
                "--target",
                "launcher",
                "--trust-profile",
                profile,
            ],
        ), patch.object(build, "ensure_pyinstaller"), patch.object(
            build, "build_platform", return_value=True
        ) as build_platform:
            try:
                build.main()
            except SystemExit as exc:
                self.fail(f"launcher trust-profile CLI was rejected: {exc}")

        build_platform.assert_called_once_with(
            "win32-x64",
            targets=["launcher"],
            trust_profile_path=profile,
        )

    def test_build_cli_rejects_unknown_target_before_build_setup(self):
        build = load_module(
            "npm_build_cli_unknown_target",
            ROOT / "npm" / "scripts" / "build.py",
        )

        with patch.object(
            build.sys, "argv", ["build.py", "win32-x64", "--target", "unknown"]
        ), patch.object(build, "ensure_pyinstaller") as ensure_pyinstaller:
            with self.assertRaises(SystemExit):
                build.main()

        ensure_pyinstaller.assert_not_called()

    def test_pyinstaller_command_omits_missing_legacy_sqlcipher_imports(self):
        build = load_module("npm_build", ROOT / "npm" / "scripts" / "build.py")

        cmd = build.make_pyinstaller_command("win32-x64", "app")

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
        normalized = [item.replace("\\", "/") for item in manifest]
        self.assertIn("launcher/wechat-cli-launcher.exe", normalized)
        self.assertIn("launcher/launcher-config.json", normalized)
        self.assertTrue(
            any(
                item.startswith("versions/") and item.endswith("/wechat-cli.exe")
                for item in normalized
            )
        )
        self.assertTrue(
            any(
                item.startswith("versions/") and item.endswith("/app-manifest.json")
                for item in normalized
            )
        )
        self.assertNotIn("app/wechat-cli.exe", normalized)

    def test_update_only_package_contains_only_app_and_manifest(self):
        package = load_module(
            "package_windows_update_only",
            ROOT / "scripts" / "package_windows_app.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            app_binary = root / "wechat-cli.exe"
            app_binary.write_bytes(b"app-binary")
            bootstrap_dir = dist / "wechat-cli-web-bootstrap-win32-x64-0.5.1"
            bootstrap_dir.mkdir()
            bootstrap_marker = bootstrap_dir / "keep.txt"
            bootstrap_marker.write_text("keep", encoding="utf-8")
            bootstrap_zip = dist / "wechat-cli-web-bootstrap-win32-x64-0.5.1.zip"
            bootstrap_zip.write_bytes(b"keep-bootstrap")

            with patch.object(package, "DIST_DIR", dist), patch.object(
                package, "_binary_path", return_value=app_binary
            ) as binary_path:
                update_zip = package.create_update_only_package(skip_build=True)

            self.assertEqual(f"wechat-cli-app-{APP_VERSION}-win-x64.zip", update_zip.name)
            binary_path.assert_called_once_with("wechat-cli.exe")
            self.assertEqual("keep", bootstrap_marker.read_text(encoding="utf-8"))
            self.assertEqual(b"keep-bootstrap", bootstrap_zip.read_bytes())
            with zipfile.ZipFile(update_zip) as archive:
                self.assertEqual(
                    {"wechat-cli.exe", "app-manifest.json"},
                    set(archive.namelist()),
                )
                manifest = json.loads(archive.read("app-manifest.json"))

        self.assertEqual(
            {
                "product": "wechat-cli-web",
                "version": APP_VERSION,
                "platform": "windows",
                "architecture": "x86_64",
                "entrypoint": "wechat-cli.exe",
                "build_id": "dev",
            },
            manifest,
        )

    def test_update_only_rejects_existing_archive_without_touching_binary(self):
        package = load_module(
            "package_windows_update_existing",
            ROOT / "scripts" / "package_windows_app.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            target = dist / f"wechat-cli-app-{APP_VERSION}-win-x64.zip"
            target.write_bytes(b"existing")
            with patch.object(package, "DIST_DIR", dist), patch.object(
                package, "_binary_path"
            ) as binary_path:
                with self.assertRaises(FileExistsError):
                    package.create_update_only_package(skip_build=True)

            self.assertEqual(b"existing", target.read_bytes())
            binary_path.assert_not_called()

    def test_package_build_binary_accepts_installer_payload_path(self):
        package = load_module(
            "package_windows_build_installer_contract",
            ROOT / "scripts" / "package_windows_app.py",
        )
        self.assertIn(
            "installer_payload_path",
            inspect.signature(package.build_binary).parameters,
        )

    def test_package_build_binary_accepts_trust_profile_path(self):
        package = load_module(
            "package_windows_build_profile_contract",
            ROOT / "scripts" / "package_windows_app.py",
        )

        self.assertIn("trust_profile_path", inspect.signature(package.build_binary).parameters)

    def test_package_build_binary_forwards_profile_to_launcher_build(self):
        package = load_module(
            "package_windows_build_profile_forwarding",
            ROOT / "scripts" / "package_windows_app.py",
        )
        profile = Path("C:/external/deployment-trust-profile.json")

        with patch.object(package.subprocess, "check_call") as check_call:
            package.build_binary(targets=["launcher"], trust_profile_path=profile)

        command = check_call.call_args.args[0]
        self.assertIn("--trust-profile", command)
        self.assertEqual(str(profile), command[command.index("--trust-profile") + 1])

    def test_package_build_binary_forwards_exact_source_sha(self):
        package = load_module(
            "package_windows_build_source_sha_forwarding",
            ROOT / "scripts" / "package_windows_app.py",
        )
        source_sha = "a" * 40

        with patch.object(package.subprocess, "check_call") as check_call:
            package.build_binary(targets=["app"], source_sha=source_sha)

        command = check_call.call_args.args[0]
        self.assertIn("--source-sha", command)
        self.assertEqual(source_sha, command[command.index("--source-sha") + 1])

    def test_update_only_builds_only_application_target(self):
        package = load_module(
            "package_windows_update_build",
            ROOT / "scripts" / "package_windows_app.py",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            app_binary = root / "wechat-cli.exe"
            app_binary.write_bytes(b"app-binary")
            with patch.object(package, "DIST_DIR", dist), patch.object(
                package, "build_binary"
            ) as build_binary, patch.object(
                package, "_binary_path", return_value=app_binary
            ):
                package.create_update_only_package(skip_build=False)

        build_binary.assert_called_once_with(targets=["app"])

    def test_production_installer_path_requires_explicit_signing_provider_contract(self):
        package = load_module(
            "package_windows_production_installer_contract",
            ROOT / "scripts" / "package_windows_app.py",
        )
        creator = getattr(package, "create_production_installer", None)
        self.assertTrue(callable(creator))
        parameters = inspect.signature(creator).parameters
        self.assertIn("signing_provider", parameters)
        self.assertIn("trust_profile_path", parameters)

    def test_production_installer_uses_production_payload_and_signs_final_exe(self):
        package = load_module(
            "package_windows_production_installer_pipeline",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            package_dir = root / "compatibility-package"
            package_dir.mkdir()
            (package_dir / "bootstrap-package.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "product": "wechat-cli-web",
                        "version": "0.5.1",
                        "production_capable": False,
                        "distribution_tier": "compatibility",
                    }
                ),
                encoding="utf-8",
            )
            legacy_zip = root / "legacy.zip"
            update_zip = root / "update.zip"
            profile = root / "deployment-trust-profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "environment": "staging",
                        "api_base_url": "https://staging-api.example.test",
                        "expected_channel": "beta",
                        "fingerprint_salt": "installer-test-salt",
                        "release_public_keys": {"release": "test"},
                        "lease_public_keys": {"lease": "test"},
                        "windows_publisher_policy": "CN=Board6 Test Publisher",
                    }
                ),
                encoding="utf-8",
            )
            installer_source = root / "wechat-cli-installer.exe"
            events = []
            captured = {}

            class Provider:
                def sign(self, path):
                    events.append(("sign", path.name))

            def verifier(path, policy):
                events.append(("verify", path.name))
                self.assertEqual("CN=Board6 Test Publisher", policy.expected_subject)

            def build_installer(**kwargs):
                payload = Path(kwargs["installer_payload_path"])
                captured["metadata"] = json.loads(
                    (payload / "bootstrap-package.json").read_text(encoding="utf-8")
                )
                events.append(("build", "installer"))
                installer_source.write_bytes(b"signed-installer-source")

            with patch.object(package, "DIST_DIR", dist), patch.object(
                package,
                "create_signed_package",
                return_value=(package_dir, legacy_zip, update_zip),
            ), patch.object(
                package, "build_binary", side_effect=build_installer
            ), patch.object(
                package,
                "_binary_path",
                return_value=installer_source,
            ):
                try:
                    result = package.create_production_installer(
                        launcher_config_path=root / "launcher-config.json",
                        trust_profile_path=profile,
                        signing_provider=Provider(),
                        authenticode_verifier=verifier,
                    )
                except Exception as exc:
                    self.fail(f"production installer orchestration failed: {exc}")

            final_installer, returned_legacy, returned_update = result
            self.assertTrue(final_installer.is_file())
            self.assertEqual(b"signed-installer-source", final_installer.read_bytes())
            self.assertEqual(legacy_zip, returned_legacy)
            self.assertEqual(update_zip, returned_update)
            self.assertTrue(captured["metadata"]["production_capable"])
            self.assertEqual(
                "production-installer", captured["metadata"]["distribution_tier"]
            )
            self.assertEqual(
                [
                    ("build", "installer"),
                    ("sign", "wechat-cli-installer.exe"),
                    ("verify", "wechat-cli-installer.exe"),
                ],
                events,
            )

    def test_private_controlled_production_installer_does_not_require_authenticode(self):
        package = load_module(
            "package_windows_private_production_installer",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            dist.mkdir()
            package_dir = root / "private-package"
            package_dir.mkdir()
            (package_dir / "bootstrap-package.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "product": "wechat-cli-web",
                        "version": "0.6.0",
                        "production_capable": False,
                        "distribution_tier": "compatibility",
                    }
                ),
                encoding="utf-8",
            )
            legacy_zip = root / "legacy.zip"
            update_zip = root / "update.zip"
            profile = root / "deployment-trust-profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "distribution_profile": "private_controlled",
                        "environment": "production",
                        "api_base_url": "https://wechat-cli-api.aurevior-devspace.com",
                        "expected_channel": "stable",
                        "fingerprint_salt": "fresh-production-fingerprint-salt",
                        "release_public_keys": {"release-key-production-01": "release-key"},
                        "lease_public_keys": {"lease-key-production-01": "lease-key"},
                        "windows_publisher_policy": "",
                    }
                ),
                encoding="utf-8",
            )
            installer_source = root / "wechat-cli-installer.exe"
            events = []
            captured = {}

            def build_installer(**kwargs):
                payload = Path(kwargs["installer_payload_path"])
                captured["metadata"] = json.loads(
                    (payload / "bootstrap-package.json").read_text(encoding="utf-8")
                )
                events.append(("build", "installer"))
                installer_source.write_bytes(b"unsigned-private-installer")

            with patch.object(package, "DIST_DIR", dist), patch.object(
                package,
                "create_package",
                return_value=(package_dir, legacy_zip, update_zip),
            ) as create_package, patch.object(
                package, "build_binary", side_effect=build_installer
            ), patch.object(
                package, "_binary_path", return_value=installer_source
            ), patch.dict(
                sys.modules, {"scripts.sign_windows_artifacts": None}
            ):
                output_dir = root / "external-output"
                source_sha = "b" * 40
                result = package.create_production_installer(
                    launcher_config_path=root / "launcher-config.json",
                    trust_profile_path=profile,
                    signing_provider=None,
                    authenticode_verifier=lambda *_args: self.fail(
                        "private_controlled installer must not run Authenticode verification"
                    ),
                    output_dir=output_dir,
                    source_sha=source_sha,
                )

            final_installer, returned_legacy, returned_update = result
            create_package.assert_called_once()
            create_package_kwargs = dict(create_package.call_args.kwargs)
            actual_output_dir = Path(create_package_kwargs.pop("output_dir"))
            self.assertTrue(actual_output_dir.samefile(output_dir))
            self.assertEqual(
                {
                    "launcher_config_path": root / "launcher-config.json",
                    "trust_profile_path": profile,
                    "skip_build": False,
                    "build_id": "prod-060-bbbbbbbbbbbb",
                    "source_sha": source_sha,
                    "allow_overwrite": False,
                },
                create_package_kwargs,
            )
            self.assertEqual(b"unsigned-private-installer", final_installer.read_bytes())
            self.assertEqual(legacy_zip, returned_legacy)
            self.assertEqual(update_zip, returned_update)
            self.assertTrue(captured["metadata"]["production_capable"])
            self.assertEqual("production-installer", captured["metadata"]["distribution_tier"])
            self.assertEqual("stable", captured["metadata"]["channel"])
            self.assertEqual([("build", "installer")], events)
            self.assertTrue(final_installer.parent.samefile(output_dir))

    def test_private_production_installer_cli_uses_external_output_and_exact_source_sha(self):
        package = load_module(
            "package_windows_private_production_installer_cli",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            launcher_config = root / "launcher-config.json"
            trust_profile = root / "production-trust-profile.json"
            output_dir = root / "production-output"
            source_sha = "c" * 40
            expected = (
                output_dir / "wechat-cli-installer-0.6.0-win-x64.exe",
                output_dir / "wechat-cli-web-bootstrap-win32-x64-0.6.0.zip",
                output_dir / "wechat-cli-app-0.6.0-win-x64.zip",
            )
            with patch.object(
                package, "create_production_installer", return_value=expected
            ) as create_installer:
                package.main(
                    [
                        "--production-installer",
                        "--launcher-config",
                        str(launcher_config),
                        "--launcher-trust-profile",
                        str(trust_profile),
                        "--output-dir",
                        str(output_dir),
                        "--source-sha",
                        source_sha,
                    ]
                )

        create_installer.assert_called_once_with(
            launcher_config_path=launcher_config,
            trust_profile_path=trust_profile,
            signing_provider=None,
            output_dir=output_dir,
            source_sha=source_sha,
        )

    def test_signed_package_path_requires_explicit_signing_provider_contract(self):
        package = load_module(
            "package_windows_signed_contract",
            ROOT / "scripts" / "package_windows_app.py",
        )
        signed = getattr(package, "create_signed_package", None)
        self.assertTrue(callable(signed))
        parameters = inspect.signature(signed).parameters
        self.assertIn("signing_provider", parameters)
        self.assertIn("trust_profile_path", parameters)

    def test_signed_package_orders_build_sign_verify_before_packaging(self):
        package = load_module(
            "package_windows_signed_order",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = root / "deployment-trust-profile.json"
            profile.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "environment": "staging",
                        "api_base_url": "https://staging-api.example.test",
                        "expected_channel": "beta",
                        "fingerprint_salt": "test-salt",
                        "release_public_keys": {"release": "test"},
                        "lease_public_keys": {"lease": "test"},
                        "windows_publisher_policy": "CN=Board6 Test Publisher",
                    }
                ),
                encoding="utf-8",
            )
            app = root / "wechat-cli.exe"
            launcher = root / "wechat-cli-launcher.exe"
            app.write_bytes(b"app")
            launcher.write_bytes(b"launcher")
            events = []

            class Provider:
                def sign(self, path):
                    events.append(("sign", path.name))

            def verifier(path, policy):
                events.append(("verify", path.name))
                self.assertEqual("CN=Board6 Test Publisher", policy.expected_subject)

            def binary_path(name, **_kwargs):
                return app if name == "wechat-cli.exe" else launcher

            expected = (root / "package", root / "bootstrap.zip", root / "update.zip")
            with patch.object(
                package,
                "build_binary",
                side_effect=lambda **_kwargs: events.append(("build", None)),
            ), patch.object(
                package, "_binary_path", side_effect=binary_path
            ), patch.object(
                package,
                "create_package",
                side_effect=lambda **_kwargs: events.append(("package", None)) or expected,
            ):
                try:
                    result = package.create_signed_package(
                        launcher_config_path=root / "launcher-config.json",
                        trust_profile_path=profile,
                        signing_provider=Provider(),
                        authenticode_verifier=verifier,
                    )
                except Exception as exc:
                    self.fail(f"signed package orchestration failed: {exc}")

        self.assertEqual(expected, result)
        self.assertEqual(
            [
                ("build", None),
                ("sign", "wechat-cli.exe"),
                ("verify", "wechat-cli.exe"),
                ("sign", "wechat-cli-launcher.exe"),
                ("verify", "wechat-cli-launcher.exe"),
                ("package", None),
            ],
            events,
        )

    def test_full_package_accepts_explicit_launcher_trust_profile(self):
        package = load_module(
            "package_windows_full_profile_contract",
            ROOT / "scripts" / "package_windows_app.py",
        )

        self.assertIn("trust_profile_path", inspect.signature(package.create_package).parameters)

    def test_full_package_forwards_trust_profile_when_building_launcher(self):
        package = load_module(
            "package_windows_full_profile_forwarding",
            ROOT / "scripts" / "package_windows_app.py",
        )
        profile = Path("C:/external/deployment-trust-profile.json")

        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            with patch.object(package, "DIST_DIR", dist), patch.object(
                package, "build_binary"
            ) as build_binary, patch.object(
                package, "read_version", return_value="0.5.1"
            ), patch.object(
                package, "copy_package_files"
            ), patch.object(
                package.shutil,
                "make_archive",
                return_value=str(dist / "wechat-cli-bootstrap-0.5.1.zip"),
            ), patch.object(
                package,
                "create_update_package",
                return_value=dist / "wechat-cli-app-0.5.1-win-x64.zip",
            ):
                package.create_package(
                    launcher_config_path=Path("C:/external/launcher-config.json"),
                    trust_profile_path=profile,
                    skip_build=False,
                )

        build_binary.assert_called_once_with(trust_profile_path=profile)

    def test_update_only_package_writes_to_explicit_output_dir(self):
        package = load_module(
            "package_windows_update_output_dir",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dist = root / "dist"
            output_dir = root / "external"
            app_binary = root / "wechat-cli.exe"
            app_binary.write_bytes(b"app-binary")
            with patch.object(package, "DIST_DIR", dist), patch.object(
                package, "read_version", return_value="0.6.0"
            ), patch.object(
                package, "_binary_path", return_value=app_binary
            ), patch.object(package, "build_binary") as build_binary:
                update_zip = package.create_update_only_package(
                    skip_build=True,
                    output_dir=output_dir,
                    version="0.6.0",
                    build_id="prod-060-20335fa7df13",
                )

            self.assertEqual("wechat-cli-app-0.6.0-win-x64.zip", update_zip.name)
            self.assertTrue(update_zip.is_file())
            self.assertTrue(update_zip.samefile(output_dir / update_zip.name))
            self.assertFalse(dist.exists())
            with zipfile.ZipFile(update_zip, "r") as archive:
                manifest = json.loads(archive.read("app-manifest.json").decode("utf-8"))
            self.assertEqual("0.6.0", manifest["version"])
            self.assertEqual("prod-060-20335fa7df13", manifest["build_id"])
            build_binary.assert_not_called()

    def test_update_only_cli_does_not_require_launcher_config(self):
        package = load_module(
            "package_windows_update_cli",
            ROOT / "scripts" / "package_windows_app.py",
        )

        with patch.object(
            package,
            "create_update_only_package",
            return_value=Path("dist/wechat-cli-app-0.5.1-win-x64.zip"),
        ) as create_update, patch.object(
            package, "create_package", side_effect=AssertionError("bootstrap path used")
        ):
            package.main(["--update-only", "--skip-build"])

        create_update.assert_called_once_with(
            skip_build=True,
            output_dir=None,
            version=None,
            build_id=None,
        )

    def test_update_only_cli_forwards_explicit_output_dir(self):
        package = load_module(
            "package_windows_update_output_cli",
            ROOT / "scripts" / "package_windows_app.py",
        )
        output_dir = Path("C:/external/production-release")
        with patch.object(
            package,
            "create_update_only_package",
            return_value=output_dir / "wechat-cli-app-0.6.0-win-x64.zip",
        ) as create_update:
            package.main(
                [
                    "--update-only",
                    "--skip-build",
                    "--output-dir",
                    str(output_dir),
                    "--version",
                    "0.6.0",
                    "--build-id",
                    "prod-060-20335fa7df13",
                ]
            )

        create_update.assert_called_once_with(
            skip_build=True,
            output_dir=output_dir,
            version="0.6.0",
            build_id="prod-060-20335fa7df13",
        )

    def test_update_only_rejects_explicit_version_mismatch(self):
        package = load_module(
            "package_windows_update_version_guard",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with patch.object(package, "read_version", return_value="0.6.0"):
            with self.assertRaisesRegex(ValueError, "must match source version"):
                package.create_update_only_package(
                    skip_build=True,
                    version="0.6.1",
                )

    def _write_bootstrap_only_inputs(self, root: Path):
        source_root = root / "source"
        source_root.mkdir()
        binary_root = root / "bin"
        binary_root.mkdir()
        (binary_root / "wechat-cli.exe").write_bytes(b"app")
        (binary_root / "wechat-cli-launcher.exe").write_bytes(b"launcher")
        config = root / "launcher-config.json"
        config.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "port": 18787,
                }
            ),
            encoding="utf-8",
        )
        return source_root, binary_root, config

    def test_packager_rejects_trust_fields_in_external_launcher_config(self):
        package = load_module(
            "package_windows_operational_config_boundary",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _source_root, _binary_root, config = self._write_bootstrap_only_inputs(root)
            value = json.loads(config.read_text(encoding="utf-8"))
            value["api_base_url"] = "https://override.example.test"
            config.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "operational"):
                package._validate_launcher_config(config)

    def test_bootstrap_only_writes_only_bootstrap_to_external_output(self):
        package = load_module(
            "package_windows_bootstrap_only",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root, binary_root, config = self._write_bootstrap_only_inputs(root)
            output_root = root / "external"
            with patch.object(package, "WINDOWS_PACKAGE_FILES", ()), patch.object(
                package, "create_update_package"
            ) as update:
                package_dir, bootstrap_zip = package.create_bootstrap_package(
                    launcher_config_path=config,
                    source_root=source_root,
                    binary_root=binary_root,
                    output_dir=output_root,
                    version="0.5.1",
                    build_id="board6-bootstrap-test",
                )

            self.assertTrue(package_dir.is_dir())
            self.assertTrue(bootstrap_zip.is_file())
            self.assertEqual([], list(output_root.glob("wechat-cli-app-*.zip")))
            update.assert_not_called()
            manifest = json.loads(
                (package_dir / "versions" / "0.5.1" / "app-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual("board6-bootstrap-test", manifest["build_id"])
            bootstrap_metadata = json.loads(
                (package_dir / "bootstrap-package.json").read_text(encoding="utf-8")
            )
            self.assertIn("production_capable", bootstrap_metadata)
            self.assertIn("distribution_tier", bootstrap_metadata)
            self.assertFalse(bootstrap_metadata.get("production_capable"))
            self.assertEqual("compatibility", bootstrap_metadata.get("distribution_tier"))

    def test_bootstrap_only_rejects_repository_outputs(self):
        package = load_module(
            "package_windows_bootstrap_guards",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root, binary_root, config = self._write_bootstrap_only_inputs(root)
            for output_dir in (ROOT, ROOT / "dist", ROOT / "foo"):
                with self.subTest(output_dir=output_dir):
                    with self.assertRaisesRegex(ValueError, "outside the repository"):
                        package.create_bootstrap_package(
                            launcher_config_path=config,
                            source_root=source_root,
                            binary_root=binary_root,
                            output_dir=output_dir,
                            version="0.5.1",
                            build_id="board6-bootstrap-test",
                        )

    def test_full_package_cli_forwards_launcher_trust_profile(self):
        package = load_module(
            "package_windows_full_profile_cli",
            ROOT / "scripts" / "package_windows_app.py",
        )
        config = Path("C:/external/launcher-config.json")
        profile = Path("C:/external/deployment-trust-profile.json")
        expected = (
            Path("dist/bootstrap-dir"),
            Path("dist/bootstrap.zip"),
            Path("dist/update.zip"),
        )
        with patch.object(package, "create_package", return_value=expected) as create_package:
            try:
                package.main(
                    [
                        "--launcher-config",
                        str(config),
                        "--launcher-trust-profile",
                        str(profile),
                    ]
                )
            except SystemExit as exc:
                self.fail(f"full package trust-profile CLI was rejected: {exc}")

        create_package.assert_called_once_with(
            launcher_config_path=config,
            trust_profile_path=profile,
            skip_build=False,
        )

    def test_full_package_cli_requires_trust_profile_when_building(self):
        package = load_module(
            "package_windows_full_profile_required",
            ROOT / "scripts" / "package_windows_app.py",
        )
        expected = (
            Path("dist/bootstrap-dir"),
            Path("dist/bootstrap.zip"),
            Path("dist/update.zip"),
        )
        with patch.object(package, "create_package", return_value=expected) as create_package:
            with self.assertRaises(SystemExit):
                package.main(
                    [
                        "--launcher-config",
                        "C:/external/launcher-config.json",
                    ]
                )

        create_package.assert_not_called()

    def test_bootstrap_only_cli_passes_explicit_external_inputs_without_building(self):
        package = load_module(
            "package_windows_bootstrap_cli",
            ROOT / "scripts" / "package_windows_app.py",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_root, binary_root, config = self._write_bootstrap_only_inputs(root)
            output_root = root / "external"
            expected_dir = output_root / "wechat-cli-web-bootstrap-win32-x64-0.5.1"
            expected_zip = Path(str(expected_dir) + ".zip")
            with patch.object(
                package,
                "create_bootstrap_package",
                return_value=(expected_dir, expected_zip),
            ) as create_bootstrap, patch.object(package, "build_binary") as build_binary:
                package.main(
                    [
                        "--bootstrap-only",
                        "--launcher-config",
                        str(config),
                        "--source-root",
                        str(source_root),
                        "--binary-root",
                        str(binary_root),
                        "--output-dir",
                        str(output_root),
                        "--version",
                        "0.5.1",
                        "--build-id",
                        "board6-bootstrap-test",
                    ]
                )

            create_bootstrap.assert_called_once_with(
                launcher_config_path=config,
                source_root=source_root,
                binary_root=binary_root,
                output_dir=output_root,
                version="0.5.1",
                build_id="board6-bootstrap-test",
            )
            build_binary.assert_not_called()

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

    def test_installer_uses_versioned_layout_and_atomic_current_pointer(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn('$VersionsDir = Join-Path $InstallDir "versions"', script)
        self.assertIn('$CurrentStatePath = Join-Path $StateDir "current.json"', script)
        self.assertIn("function Write-JsonAtomic", script)
        self.assertIn("current_version = $Version", script)
        self.assertIn("previous_version = $PreviousVersion", script)
        self.assertIn("Move-Item -Path $StagedVersionDir", script)
        self.assertNotIn("mklink", script.lower())

    def test_installer_bootstraps_official_webview2_runtime_when_missing(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("Get-WebView2RuntimeVersion", script)
        self.assertIn("https://go.microsoft.com/fwlink/p/?LinkId=2124703", script)
        self.assertIn('"/silent", "/install"', script)
        self.assertIn("WebView2 installer completed but the Runtime is still not detected", script)

    def test_installer_preserves_and_versions_the_legacy_app(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn('$LegacyAppDir = Join-Path $InstallDir "app"', script)
        self.assertIn('$LegacyVersion = [string]$PackageMetadata.legacy_version', script)
        self.assertIn('$LegacyVersionDir = Join-Path $VersionsDir $LegacyVersion', script)
        self.assertIn("Copy-WithRetry -Recurse -Path (Join-Path $LegacyAppDir \"*\")", script)
        self.assertIn("build_id = \"legacy-bootstrap\"", script)
        self.assertIn("$PreviousVersion = $LegacyVersion", script)
        self.assertIn("Existing legacy app was preserved", script)
        self.assertNotIn("Remove-Item -Force -Recurse $LegacyAppDir", script)

    def test_installer_accepts_embedded_production_channel_when_operational_config_omits_channel(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn('$SourceConfigData = Get-Content -Raw -Encoding UTF8 $SourceConfig | ConvertFrom-Json', script)
        self.assertIn('if ($SourceConfigData.PSObject.Properties.Name -contains "channel")', script)
        self.assertIn('elseif ($PackageMetadata.PSObject.Properties.Name -contains "channel")', script)
        self.assertIn('$Channel = [string]$PackageMetadata.channel', script)
        self.assertIn('if ($Channel -notin @("stable", "beta"))', script)

    def test_installer_supports_isolated_no_start_no_shortcuts_mode(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn("[switch]$NoStart", script)
        self.assertIn("[switch]$NoShortcuts", script)
        self.assertIn("[switch]$SkipWebView2Check", script)
        self.assertIn("[switch]$SkipProcessStop", script)
        self.assertIn("Isolation switches require -NoStart and -NoShortcuts", script)
        self.assertIn("if (-not $SkipWebView2Check)", script)
        self.assertIn("if (-not $SkipProcessStop)", script)
        self.assertIn("if (-not $NoShortcuts)", script)
        self.assertIn("-TargetPath $LauncherExePath", script)

    def test_installer_records_and_rolls_back_install_transaction(self):
        script = (ROOT / "packaging" / "windows" / "install.ps1").read_text(encoding="utf-8")

        self.assertIn('$InstallTransactionPath = Join-Path $StateDir "install-transaction.json"', script)
        self.assertIn('-Stage "preparing"', script)
        self.assertIn('-Stage "switched"', script)
        self.assertIn('-Stage "committed"', script)
        self.assertIn("Restore-InstallState", script)
        self.assertIn("Launcher did not complete successfully", script)

    def test_bootstrap_metadata_declares_supported_legacy_version(self):
        package_source = (ROOT / "scripts" / "package_windows_app.py").read_text(encoding="utf-8")

        self.assertIn('LEGACY_BOOTSTRAP_VERSION = "0.4.2"', package_source)
        self.assertIn('"legacy_version": LEGACY_BOOTSTRAP_VERSION', package_source)

    def test_repair_and_uninstall_entrypoints_are_packaged(self):
        package = load_module(
            "package_windows_repair",
            ROOT / "scripts" / "package_windows_app.py",
        )
        manifest = package.build_manifest()

        self.assertIn("repair-wechat-cli-web.bat", manifest)
        self.assertIn("uninstall-wechat-cli-web.bat", manifest)
        self.assertIn("uninstall.ps1", manifest)
        repair = (
            ROOT / "packaging" / "windows" / "repair-wechat-cli-web.bat"
        ).read_text(encoding="utf-8")
        uninstall = (
            ROOT / "packaging" / "windows" / "uninstall.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("--repair", repair)
        self.assertIn("[switch]$NoShortcuts", uninstall)
        self.assertIn("if (-not $NoShortcuts)", uninstall)
        self.assertIn('Join-Path $HOME ".wechat-cli"', uninstall)
        self.assertIn("User data was intentionally preserved", uninstall)


if __name__ == "__main__":
    unittest.main()
