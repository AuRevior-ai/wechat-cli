import importlib.util
import inspect
import json
import shutil
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
                    "routes": [
                        {
                            "pattern": "staging-admin.example.test",
                            "custom_domain": True,
                        }
                    ],
                    "vars": {
                        "ENVIRONMENT": "staging",
                        "ACCESS_JWT_ISSUER": "https://team.cloudflareaccess.com",
                        "ACCESS_JWKS_URL": "https://team.cloudflareaccess.com/cdn-cgi/access/certs",
                        "ACCESS_AUDIENCES": "staging-audience",
                        "ACCESS_IDENTITY_CLAIM": "email",
                        "ACCESS_ADMIN_ORIGIN": "https://staging-admin.example.test",
                        **selectors,
                    },
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
                    "routes": [
                        {"pattern": "api.example.test", "custom_domain": True},
                        {"pattern": "admin.example.test", "custom_domain": True},
                    ],
                    "vars": {
                        "ENVIRONMENT": "production",
                        "PUBLIC_API_ORIGIN": "https://api.example.test",
                        "ACCESS_ADMIN_ORIGIN": "https://admin.example.test",
                        "ACCESS_JWT_ISSUER": "https://team.cloudflareaccess.com",
                        "ACCESS_JWKS_URL": "https://team.cloudflareaccess.com/cdn-cgi/access/certs",
                        "ACCESS_HUMAN_AUDIENCES": "human-production-audience",
                        "ACCESS_HUMAN_IDENTITY_CLAIM": "email",
                        "ACCESS_AUTOMATION_AUDIENCES": "automation-production-audience",
                        "ACCESS_AUTOMATION_IDENTITY_CLAIM": "common_name",
                        "ACCESS_AUTOMATION_IDENTITIES": "release-automation-client",
                        **selectors,
                    },
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
        if environment == "production":
            profile = {
                "schema_version": 2,
                "distribution_profile": "private_controlled",
                "environment": "production",
                "api_base_url": api_origin,
                "expected_channel": "stable",
                "fingerprint_salt": "fresh-production-fingerprint-salt",
                "release_public_keys": {"release-key-production-01": "release-public-key"},
                "lease_public_keys": {"lease-key-production-01": "lease-public-key"},
                "windows_publisher_policy": "",
            }
        else:
            profile = {
                "schema_version": 1,
                "environment": environment,
                "api_base_url": api_origin,
                "expected_channel": "beta",
                "fingerprint_salt": f"{environment}-fingerprint-salt",
                "release_public_keys": {"release-test": "release-public-key"},
                "lease_public_keys": {"lease-test": "lease-public-key"},
                "windows_publisher_policy": "CN=Board6 Test",
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

    def test_deployment_preflight_exports_local_and_staging_deploy_contract(self):
        from scripts import deploy_worker

        self.assertTrue(callable(getattr(deploy_worker, "preflight_worker_deployment", None)))
        self.assertTrue(callable(getattr(deploy_worker, "deploy_staging_worker", None)))

    def test_staging_deploy_refuses_non_staging_before_runner(self):
        from scripts import deploy_worker

        deploy_staging_worker = getattr(deploy_worker, "deploy_staging_worker", None)
        self.assertTrue(callable(deploy_staging_worker), "deploy_staging_worker contract missing")
        calls = []
        with self.assertRaisesRegex(ValueError, "staging"):
            deploy_staging_worker(
                WRANGLER,
                environment="production",
                runner=lambda *args, **kwargs: calls.append((args, kwargs)),
            )
        self.assertEqual([], calls)

    def test_staging_deploy_runs_preflight_before_exact_wrangler_command(self):
        from scripts import deploy_worker

        deploy_staging_worker = getattr(deploy_worker, "deploy_staging_worker", None)
        self.assertTrue(callable(deploy_staging_worker), "deploy_staging_worker contract missing")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root, environment="staging")
            secret_names = self._production_secret_names() | {
                "ADMIN_TOKEN_PEPPER",
                "GITHUB_RELEASE_READ_TOKEN",
            }
            calls = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0)

            result = deploy_staging_worker(
                config_path,
                environment="staging",
                policy_path=POLICY,
                trust_profile_path=profile_path,
                api_origin="https://staging-api.example.test",
                declared_secret_names=secret_names,
                runner=runner,
            )

        self.assertEqual("staging", result.environment)
        self.assertEqual(1, len(calls))
        command, kwargs = calls[0]
        self.assertEqual(
            [
                shutil.which("npx"),
                "wrangler",
                "deploy",
                "--env",
                "staging",
                "--config",
                str(config_path.resolve()),
            ],
            command,
        )
        self.assertEqual(config_path.resolve().parent, kwargs["cwd"])
        self.assertIs(kwargs["check"], True)

    def test_staging_deploy_accepts_external_secrets_file_without_reading_it(self):
        from scripts import deploy_worker

        deploy_staging_worker = getattr(deploy_worker, "deploy_staging_worker", None)
        self.assertTrue(callable(deploy_staging_worker), "deploy_staging_worker contract missing")
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as secrets_tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root, environment="staging")
            secrets_file = Path(secrets_tmp) / "lease.env"
            secrets_file.write_text("LEASE_SIGNING_PRIVATE_KEY=not-read-by-wrapper", encoding="utf-8")
            secret_names = self._production_secret_names() | {
                "ADMIN_TOKEN_PEPPER",
                "GITHUB_RELEASE_READ_TOKEN",
            }
            calls = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0)

            deploy_staging_worker(
                config_path,
                environment="staging",
                policy_path=POLICY,
                trust_profile_path=profile_path,
                api_origin="https://staging-api.example.test",
                declared_secret_names=secret_names,
                secrets_file=secrets_file,
                runner=runner,
            )

        command, _kwargs = calls[0]
        self.assertEqual("--secrets-file", command[-2])
        self.assertEqual(str(secrets_file.resolve()), command[-1])
        self.assertNotIn("not-read-by-wrapper", repr(calls))

    def test_staging_deploy_rejects_repository_secrets_file_before_runner(self):
        from scripts import deploy_worker

        deploy_staging_worker = getattr(deploy_worker, "deploy_staging_worker", None)
        self.assertTrue(callable(deploy_staging_worker), "deploy_staging_worker contract missing")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root, environment="staging")
            secret_names = self._production_secret_names() | {
                "ADMIN_TOKEN_PEPPER",
                "GITHUB_RELEASE_READ_TOKEN",
            }
            calls = []
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                deploy_staging_worker(
                    config_path,
                    environment="staging",
                    policy_path=POLICY,
                    trust_profile_path=profile_path,
                    api_origin="https://staging-api.example.test",
                    declared_secret_names=secret_names,
                    secrets_file=WRANGLER,
                    runner=lambda *args, **kwargs: calls.append((args, kwargs)),
                )
        self.assertEqual([], calls)

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

    def test_preflight_rejects_missing_or_inconsistent_staging_access_boundary(self):
        from scripts.deploy_worker import preflight_worker_deployment

        cases = [
            ("missing issuer", lambda staging: staging["vars"].pop("ACCESS_JWT_ISSUER"), "access"),
            (
                "jwks origin mismatch",
                lambda staging: staging["vars"].update(
                    ACCESS_JWKS_URL="https://other.cloudflareaccess.com/cdn-cgi/access/certs"
                ),
                "jwks",
            ),
            (
                "wrong identity claim",
                lambda staging: staging["vars"].update(ACCESS_IDENTITY_CLAIM="sub"),
                "identity",
            ),
            (
                "workers.dev admin origin",
                lambda staging: staging["vars"].update(
                    ACCESS_ADMIN_ORIGIN="https://worker.workers.dev"
                ),
                "origin",
            ),
            (
                "custom domain mismatch",
                lambda staging: staging.update(
                    routes=[{"pattern": "other.example.test", "custom_domain": True}]
                ),
                "route",
            ),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = self._config()
                mutate(config["env"]["staging"])
                config_path = self._write_config(root, config)
                profile_path = self._write_profile(root, environment="staging")
                try:
                    preflight_worker_deployment(
                        config_path,
                        environment="staging",
                        trust_profile_path=profile_path,
                        api_origin="https://staging-api.example.test",
                        declared_secret_names=self._production_secret_names()
                        | {"ADMIN_TOKEN_PEPPER", "GITHUB_RELEASE_READ_TOKEN"},
                    )
                except Exception as exc:
                    self.assertIsInstance(exc, ValueError)
                    self.assertIn(expected, str(exc).lower())
                else:
                    self.fail("unsafe staging Access boundary must fail closed")

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

        cases = [
            (
                True,
                [
                    {"pattern": "api.example.test", "custom_domain": True},
                    {"pattern": "admin.example.test", "custom_domain": True},
                ],
                "workers_dev",
            ),
            (False, [], "route"),
        ]
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

    def test_preflight_rejects_incomplete_or_confused_production_access_contract(self):
        from scripts.deploy_worker import preflight_worker_deployment

        cases = [
            (
                "missing public API origin",
                lambda production: production["vars"].pop("PUBLIC_API_ORIGIN"),
                "PUBLIC_API_ORIGIN",
            ),
            (
                "admin route missing",
                lambda production: production.update(
                    routes=[{"pattern": "api.example.test", "custom_domain": True}]
                ),
                "route",
            ),
            (
                "same api and admin origin",
                lambda production: production["vars"].update(
                    ACCESS_ADMIN_ORIGIN="https://api.example.test"
                ),
                "distinct",
            ),
            (
                "same human and machine audience",
                lambda production: production["vars"].update(
                    ACCESS_AUTOMATION_AUDIENCES="human-production-audience"
                ),
                "audience",
            ),
            (
                "legacy audience only",
                lambda production: (
                    production["vars"].pop("ACCESS_HUMAN_AUDIENCES"),
                    production["vars"].update(ACCESS_AUDIENCES="human-production-audience"),
                ),
                "ACCESS_HUMAN_AUDIENCES",
            ),
            (
                "issuer jwks origin mismatch",
                lambda production: production["vars"].update(
                    ACCESS_JWKS_URL="https://other.cloudflareaccess.com/cdn-cgi/access/certs"
                ),
                "JWKS",
            ),
            (
                "staging hostname in production",
                lambda production: production["vars"].update(
                    ACCESS_ADMIN_ORIGIN="https://wechat-cli-admin-staging.aurevior-devspace.com"
                ),
                "staging",
            ),
        ]
        for label, mutate, expected in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = self._config()
                mutate(config["env"]["production"])
                config_path = self._write_config(root, config)
                profile_path = self._write_profile(root)
                with self.assertRaises(ValueError) as caught:
                    preflight_worker_deployment(
                        config_path,
                        environment="production",
                        trust_profile_path=profile_path,
                        api_origin="https://api.example.test",
                        declared_secret_names=self._production_secret_names(),
                    )
                self.assertIn(expected.lower(), str(caught.exception).lower())

    def test_preflight_rejects_unresolved_production_origin_symbol_before_deploy(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config()
            config["env"]["production"]["vars"]["PUBLIC_API_ORIGIN"] = (
                "REPLACE_WITH_PRODUCTION_API_ORIGIN"
            )
            config_path = self._write_config(root, config)
            profile_path = self._write_profile(root)
            with self.assertRaisesRegex(ValueError, "placeholder"):
                preflight_worker_deployment(
                    config_path,
                    environment="production",
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=self._production_secret_names(),
                )

    def test_production_secret_inventory_excludes_runtime_github_and_legacy_admin(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            result = preflight_worker_deployment(
                config_path,
                environment="production",
                trust_profile_path=profile_path,
                api_origin="https://api.example.test",
                declared_secret_names=self._production_secret_names(),
            )
        required = set(result.required_secret_names)
        self.assertEqual(self._production_secret_names(), required)
        self.assertNotIn("GITHUB_RELEASE_READ_TOKEN", required)
        self.assertNotIn("ADMIN_TOKEN_PEPPER", required)

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

    def test_preflight_rejects_non_board7_private_production_trust_contract(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self._write_config(root, self._config())
            profile_path = self._write_profile(root)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile["release_public_keys"] = {"release-key-staging-01": "release-public-key"}
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "release key"):
                preflight_worker_deployment(
                    config_path,
                    environment="production",
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=self._production_secret_names(),
                )

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

    def test_staging_preflight_does_not_require_production_provisioning(self):
        from scripts.deploy_worker import preflight_worker_deployment

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = self._config()
            config["env"]["production"]["d1_databases"][0]["database_id"] = (
                "REPLACE_WITH_PRODUCTION_D1_ID"
            )
            config["env"]["production"]["routes"] = []
            config_path = self._write_config(root, config)
            profile_path = self._write_profile(root, environment="staging")
            secret_names = self._production_secret_names() | {
                "ADMIN_TOKEN_PEPPER",
                "GITHUB_RELEASE_READ_TOKEN",
            }
            try:
                result = preflight_worker_deployment(
                    config_path,
                    environment="staging",
                    trust_profile_path=profile_path,
                    api_origin="https://staging-api.example.test",
                    declared_secret_names=secret_names,
                )
            except Exception as exc:
                self.fail(f"staging preflight incorrectly required production provisioning: {exc}")

        self.assertEqual("staging", result.environment)

    def test_current_production_source_remains_fail_closed_while_identity_placeholders_exist(self):
        from scripts.deploy_worker import preflight_worker_deployment

        config = json.loads(WRANGLER.read_text(encoding="utf-8"))
        production_vars = config["env"]["production"]["vars"]
        unresolved = {
            name: value
            for name, value in production_vars.items()
            if isinstance(value, str) and "REPLACE_WITH_PRODUCTION" in value
        }
        self.assertTrue(unresolved, "G3/G4 source must name unresolved identity placeholders explicitly")
        with self.assertRaises(ValueError):
            preflight_worker_deployment(WRANGLER, environment="production")

    def test_cli_help_exposes_explicit_staging_and_guarded_production_deploy_action(self):
        root_help = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "deploy_worker.py"), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        deploy_help = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "deploy_worker.py"),
                "deploy",
                "--help",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(0, root_help.returncode, root_help.stderr)
        self.assertIn("deploy", root_help.stdout.lower())
        self.assertEqual(0, deploy_help.returncode, deploy_help.stderr)
        self.assertIn("--environment {staging,production}", deploy_help.stdout)
        self.assertIn("--source-sha", deploy_help.stdout)
        self.assertIn("--trust-profile", deploy_help.stdout)
        self.assertIn("--secret-name", deploy_help.stdout)

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

    def test_production_source_disables_workers_dev_and_freezes_exact_custom_domains(self):
        config = json.loads(WRANGLER.read_text(encoding="utf-8"))
        production = config["env"]["production"]
        self.assertIs(production.get("workers_dev"), False)
        self.assertEqual(
            [
                {
                    "pattern": "wechat-cli-api.aurevior-devspace.com",
                    "custom_domain": True,
                },
                {
                    "pattern": "wechat-cli-admin.aurevior-devspace.com",
                    "custom_domain": True,
                },
            ],
            production.get("routes"),
        )


if __name__ == "__main__":
    unittest.main()
