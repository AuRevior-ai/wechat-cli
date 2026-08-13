import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRANGLER = ROOT / "services" / "license-update-worker" / "wrangler.jsonc"
POLICY = ROOT / "services" / "license-update-worker" / "deployment-policy.json"


class WorkerDeploymentPreflightTests(unittest.TestCase):
    def _config(self):
        selectors = {
            "LICENSE_KEY_PEPPER_CURRENT_VERSION": "1",
            "LICENSE_KEY_PEPPER_READABLE_VERSIONS": "1",
            "DEVICE_TOKEN_PEPPER_CURRENT_VERSION": "1",
            "DEVICE_TOKEN_PEPPER_READABLE_VERSIONS": "1",
            "ADMIN_SESSION_PEPPER_CURRENT_VERSION": "1",
            "ADMIN_SESSION_PEPPER_READABLE_VERSIONS": "1",
            "CONTACT_LOOKUP_PEPPER_CURRENT_VERSION": "1",
            "CONTACT_LOOKUP_PEPPER_READABLE_VERSIONS": "1",
            "DOWNLOAD_TICKET_SECRET_CURRENT_VERSION": "1",
            "DOWNLOAD_TICKET_SECRET_READABLE_VERSIONS": "1",
            "DIAGNOSTIC_UPLOAD_SECRET_CURRENT_VERSION": "1",
            "DIAGNOSTIC_UPLOAD_SECRET_READABLE_VERSIONS": "1",
            "RATE_LIMIT_PEPPER_CURRENT_VERSION": "1",
            "RATE_LIMIT_PEPPER_READABLE_VERSIONS": "1",
            "CONTACT_ENCRYPTION_KEY_VERSION": "1",
        }
        return {
            "name": "wechat-cli-license-update-local",
            "workers_dev": True,
            "vars": {"ENVIRONMENT": "local", **selectors},
            "d1_databases": [
                {"binding": "DB", "database_name": "db-local", "database_id": "db-local-id"}
            ],
            "r2_buckets": [
                {"binding": "DIAGNOSTICS", "bucket_name": "diag-local"},
                {"binding": "RELEASES", "bucket_name": "rel-local"},
            ],
            "env": {
                "staging": {
                    "name": "wechat-cli-license-update-staging",
                    "workers_dev": True,
                    "vars": {"ENVIRONMENT": "staging", **selectors},
                    "d1_databases": [
                        {"binding": "DB", "database_name": "db-staging", "database_id": "db-staging-id"}
                    ],
                    "r2_buckets": [
                        {"binding": "DIAGNOSTICS", "bucket_name": "diag-staging"},
                        {"binding": "RELEASES", "bucket_name": "rel-staging"},
                    ],
                },
                "production": {
                    "name": "wechat-cli-license-update",
                    "workers_dev": False,
                    "routes": ["api.example.test/*"],
                    "vars": {"ENVIRONMENT": "production", **selectors},
                    "d1_databases": [
                        {"binding": "DB", "database_name": "db-production", "database_id": "db-production-id"}
                    ],
                    "r2_buckets": [
                        {"binding": "DIAGNOSTICS", "bucket_name": "diag-production"},
                        {"binding": "RELEASES", "bucket_name": "rel-production"},
                    ],
                },
            },
        }

    def _write_config(self, root: Path, config):
        path = root / "wrangler.jsonc"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def _write_profile(self, root: Path, *, environment="production", api_origin=None):
        if api_origin is None:
            api_origin = {
                "local": "http://127.0.0.1:8788",
                "staging": "https://staging-api.example.test",
                "production": "https://api.example.test",
            }[environment]
        profile = {
            "schema_version": 1,
            "environment": environment,
            "api_base_url": api_origin,
            "expected_channel": "stable" if environment == "production" else "beta",
            "fingerprint_salt": f"{environment}-fingerprint-salt",
            "release_public_keys": {"release-test": "release-public-key"},
            "lease_public_keys": {"lease-test": "lease-public-key"},
            "windows_publisher_policy": (
                "CN=Expected Publisher" if environment == "production" else "CN=Board6 Test"
            ),
        }
        path = root / "deployment-trust-profile.json"
        path.write_text(json.dumps(profile), encoding="utf-8")
        return path

    def _production_secret_names(self):
        return {
            "LICENSE_KEY_PEPPER_V1",
            "DEVICE_TOKEN_PEPPER_V1",
            "ADMIN_SESSION_PEPPER_V1",
            "CONTACT_LOOKUP_PEPPER_V1",
            "DOWNLOAD_TICKET_SECRET_V1",
            "DIAGNOSTIC_UPLOAD_SECRET_V1",
            "RATE_LIMIT_PEPPER_V1",
            "CONTACT_ENCRYPTION_KEY_V1",
            "LEASE_SIGNING_PRIVATE_KEY",
        }

    def test_deployment_preflight_module_exists(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.deploy_worker"))

    def test_deployment_preflight_exports_local_only_contract(self):
        from scripts import deploy_worker

        self.assertTrue(callable(getattr(deploy_worker, "preflight_worker_deployment", None)))
        self.assertFalse(hasattr(deploy_worker, "deploy_worker"))

    def test_preflight_accepts_explicit_deployment_policy_source(self):
        from scripts.deploy_worker import preflight_worker_deployment

        self.assertIn("policy_path", inspect.signature(preflight_worker_deployment).parameters)

    def test_preflight_rejects_invalid_deployment_policy_source(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = root / "deployment-policy.json"
            policy.write_text("{}", encoding="utf-8")
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            try:
                preflight_worker_deployment(
                    config_path,
                    environment="production",
                    policy_path=policy,
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=self._production_secret_names(),
                )
            except Exception as exc:
                self.assertIsInstance(exc, ValueError)
                self.assertIn("policy", str(exc).lower())
            else:
                self.fail("invalid deployment policy must fail closed")

    def test_preflight_worker_identity_is_driven_by_policy_source(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = json.loads(POLICY.read_text(encoding="utf-8"))
            policy["environments"]["production"]["worker_name"] = "custom-production-worker"
            policy_path = root / "deployment-policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            config = self._config()
            config["env"]["production"]["name"] = "custom-production-worker"
            config_path = self._write_config(root, config)
            profile_path = self._write_profile(root)
            try:
                result = preflight_worker_deployment(
                    config_path,
                    environment="production",
                    policy_path=policy_path,
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=self._production_secret_names(),
                )
            except Exception as exc:
                self.fail(f"policy-owned Worker identity was rejected: {exc}")

        self.assertEqual("custom-production-worker", result.worker_name)

    def test_preflight_required_secret_names_are_driven_by_policy_source(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = json.loads(POLICY.read_text(encoding="utf-8"))
            policy["versioned_secret_prefixes"].remove("RATE_LIMIT_PEPPER")
            policy_path = root / "deployment-policy.json"
            policy_path.write_text(json.dumps(policy), encoding="utf-8")
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            declared = self._production_secret_names() - {"RATE_LIMIT_PEPPER_V1"}
            try:
                result = preflight_worker_deployment(
                    config_path,
                    environment="production",
                    policy_path=policy_path,
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=declared,
                )
            except Exception as exc:
                self.fail(f"policy-owned secret declarations were rejected: {exc}")

        self.assertNotIn("RATE_LIMIT_PEPPER_V1", result.required_secret_names)

    def test_preflight_requires_explicit_known_environment(self):
        from scripts.deploy_worker import preflight_worker_deployment

        for environment in ("", "default", "prod"):
            with self.subTest(environment=environment):
                try:
                    preflight_worker_deployment(
                        WRANGLER,
                        environment=environment,
                    )
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                else:
                    self.fail("unknown deployment environment must fail closed")

    def test_preflight_rejects_production_placeholder_d1(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config()
            config["env"]["production"]["d1_databases"][0]["database_id"] = "REPLACE_WITH_PRODUCTION_D1_ID"
            path = self._write_config(root, config)
            try:
                preflight_worker_deployment(path, environment="production")
            except Exception as exc:
                self.assertIsInstance(exc, ValueError)
                self.assertIn("placeholder", str(exc).lower())
            else:
                self.fail("production placeholder D1 must fail closed")

    def test_preflight_rejects_production_workers_dev_and_missing_route(self):
        from scripts.deploy_worker import preflight_worker_deployment

        cases = [(True, ["api.example.test/*"], "workers_dev"), (False, [], "route")]
        for workers_dev, routes, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = self._config()
                production = config["env"]["production"]
                production["workers_dev"] = workers_dev
                production["routes"] = routes
                path = self._write_config(root, config)
                try:
                    preflight_worker_deployment(path, environment="production")
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                    self.assertIn(expected, str(exc).lower())
                else:
                    self.fail("unsafe production ingress must fail closed")

    def test_preflight_rejects_staging_production_resource_collisions(self):
        from scripts.deploy_worker import preflight_worker_deployment

        cases = [
            ("d1", lambda config: config["env"]["production"]["d1_databases"][0].update(database_id="db-staging-id")),
            ("r2", lambda config: config["env"]["production"]["r2_buckets"][1].update(bucket_name="rel-staging")),
        ]
        for label, mutate in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = self._config()
                mutate(config)
                path = self._write_config(root, config)
                try:
                    preflight_worker_deployment(path, environment="production")
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                    self.assertIn("collision", str(exc).lower())
                else:
                    self.fail("staging/production resource collision must fail closed")

    def test_preflight_rejects_missing_required_bindings(self):
        from scripts.deploy_worker import preflight_worker_deployment

        cases = [
            ("db", lambda production: production.update(d1_databases=[])),
            ("r2", lambda production: production.update(r2_buckets=[])),
        ]
        for label, mutate in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = self._config()
                mutate(config["env"]["production"])
                path = self._write_config(root, config)
                try:
                    preflight_worker_deployment(path, environment="production")
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                else:
                    self.fail("missing deployment binding must fail closed")

    def test_preflight_rejects_trust_profile_environment_and_origin_mismatch(self):
        from scripts.deploy_worker import preflight_worker_deployment

        cases = [
            ("staging", "https://api.example.test", "environment"),
            ("production", "https://wrong.example.test", "origin"),
        ]
        for profile_environment, api_origin, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config_path = self._write_config(root, self._config())
                profile_path = self._write_profile(
                    root,
                    environment=profile_environment,
                    api_origin=(
                        "https://staging-api.example.test"
                        if profile_environment == "staging"
                        else "https://api.example.test"
                    ),
                )
                try:
                    preflight_worker_deployment(
                        config_path,
                        environment="production",
                        trust_profile_path=profile_path,
                        api_origin=api_origin,
                    )
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                    self.assertIn(expected, str(exc).lower())
                else:
                    self.fail("trust profile mismatch must fail closed")

    def test_preflight_rejects_production_route_origin_mismatch(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config()
            config["env"]["production"]["routes"] = ["other.example.test/*"]
            config_path = self._write_config(root, config)
            profile_path = self._write_profile(root)
            try:
                preflight_worker_deployment(
                    config_path,
                    environment="production",
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=self._production_secret_names(),
                )
            except Exception as exc:
                self.assertIsInstance(exc, ValueError)
                self.assertIn("route", str(exc).lower())
            else:
                self.fail("production route/origin mismatch must fail closed")

    def test_preflight_rejects_missing_required_secret_names_without_values(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            declared = self._production_secret_names() - {"RATE_LIMIT_PEPPER_V1"}
            try:
                preflight_worker_deployment(
                    config_path,
                    environment="production",
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=declared,
                )
            except Exception as exc:
                self.assertIsInstance(exc, ValueError)
                text = str(exc)
                self.assertIn("RATE_LIMIT_PEPPER_V1", text)
                self.assertNotIn("secret-value", text)
            else:
                self.fail("missing required secret name must fail closed")

    def test_valid_production_preflight_returns_safe_metadata_only(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            try:
                result = preflight_worker_deployment(
                    config_path,
                    environment="production",
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=self._production_secret_names(),
                )
            except Exception as exc:
                self.fail(f"valid production preflight was rejected: {exc}")

        safe = result.to_safe_mapping()
        self.assertEqual("production", safe["environment"])
        self.assertEqual("wechat-cli-license-update", safe["worker_name"])
        self.assertEqual("db-production", safe["d1_database_name"])
        self.assertEqual(["diag-production", "rel-production"], safe["r2_bucket_names"])
        self.assertEqual(
            sorted(self._production_secret_names()),
            safe["required_secret_names"],
        )
        serialized = json.dumps(safe, sort_keys=True)
        self.assertNotIn("database_id", serialized)
        self.assertNotIn("secret_value", serialized)
        self.assertNotIn("api_origin", serialized)

    def test_current_production_source_is_intentionally_not_ready(self):
        from scripts.deploy_worker import preflight_worker_deployment

        try:
            preflight_worker_deployment(WRANGLER, environment="production")
        except Exception as exc:
            self.assertIsInstance(exc, ValueError)
            self.assertIn("placeholder", str(exc).lower())
        else:
            self.fail("current production source must remain fail-closed")

    def test_preflight_cli_help_exposes_no_deploy_action(self):
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deploy_worker.py"),
                "preflight",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("--environment", result.stdout)
        self.assertIn("--trust-profile", result.stdout)
        self.assertIn("--secret-name", result.stdout)
        self.assertNotIn(" deploy ", result.stdout.lower())

    def test_preflight_cli_direct_execution_returns_safe_json_for_valid_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            command = [
                sys.executable,
                str(ROOT / "scripts" / "deploy_worker.py"),
                "preflight",
                "--config",
                str(config_path),
                "--environment",
                "production",
                "--trust-profile",
                str(profile_path),
                "--api-origin",
                "https://api.example.test",
            ]
            for name in sorted(self._production_secret_names()):
                command.extend(["--secret-name", name])
            result = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("production", payload["environment"])
        self.assertEqual("wechat-cli-license-update", payload["worker_name"])
        self.assertNotIn("database_id", payload)
        self.assertNotIn("api_origin", payload)

    def test_source_worker_names_separate_local_staging_and_production(self):
        config = json.loads(WRANGLER.read_text(encoding="utf-8"))
        self.assertEqual("wechat-cli-license-update-local", config["name"])
        self.assertEqual(
            "wechat-cli-license-update-staging",
            config["env"]["staging"]["name"],
        )
        self.assertEqual(
            "wechat-cli-license-update",
            config["env"]["production"]["name"],
        )
        self.assertEqual(3, len({
            config["name"],
            config["env"]["staging"]["name"],
            config["env"]["production"]["name"],
        }))

    def test_production_source_disables_workers_dev_and_leaves_route_unconfigured(self):
        config = json.loads(WRANGLER.read_text(encoding="utf-8"))
        production = config["env"]["production"]
        self.assertIs(production.get("workers_dev"), False)
        self.assertIn("routes", production)
        self.assertEqual([], production.get("routes"))


if __name__ == "__main__":
    unittest.main()
