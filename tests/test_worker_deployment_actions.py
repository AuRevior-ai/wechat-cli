import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.deploy_worker import deploy_production_worker
from tests import test_worker_deployment_preflight as _preflight_module

POLICY = _preflight_module.POLICY


class WorkerDeploymentActionTests(unittest.TestCase):
    def helper(self):
        return _preflight_module.WorkerDeploymentPreflightTests()

    def test_cli_routes_explicit_production_deploy_with_required_source_sha(self):
        from scripts import deploy_worker

        with patch.object(deploy_worker, "deploy_production_worker") as production, patch.object(
            deploy_worker, "deploy_staging_worker"
        ) as staging:
            result = deploy_worker.main(
                [
                    "deploy",
                    "--environment",
                    "production",
                    "--source-sha",
                    "a" * 40,
                    "--api-origin",
                    "https://api.example.test",
                ]
            )

        self.assertEqual(0, result)
        production.assert_called_once()
        self.assertEqual("production", production.call_args.kwargs["environment"])
        self.assertEqual("a" * 40, production.call_args.kwargs["source_sha"])
        staging.assert_not_called()

    def test_cli_refuses_production_deploy_without_source_sha(self):
        from scripts import deploy_worker

        with patch.object(deploy_worker, "deploy_production_worker") as production:
            with self.assertRaises(SystemExit):
                deploy_worker.main(["deploy", "--environment", "production"])
        production.assert_not_called()

    def test_production_action_refuses_wrong_environment_and_bad_source_sha_before_runner(self):
        calls = []
        for environment, source_sha in [
            ("staging", "a" * 40),
            ("production", "short"),
            ("production", "A" * 40),
        ]:
            with self.subTest(environment=environment, source_sha=source_sha):
                with self.assertRaises(ValueError):
                    deploy_production_worker(
                        "missing.json",
                        environment=environment,
                        source_sha=source_sha,
                        runner=lambda *args, **kwargs: calls.append((args, kwargs)),
                    )
        self.assertEqual([], calls)

    def test_production_action_runs_preflight_before_exact_wrangler_command(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = helper._write_config(root, helper._config())
            profile_path = helper._write_profile(root)
            calls = []
            emitted = []

            def runner(command, **kwargs):
                calls.append((command, kwargs))
                return subprocess.CompletedProcess(command, 0)

            result = deploy_production_worker(
                config_path,
                environment="production",
                source_sha="a" * 40,
                policy_path=POLICY,
                trust_profile_path=profile_path,
                api_origin="https://api.example.test",
                declared_secret_names=helper._production_secret_names(),
                runner=runner,
                emit=emitted.append,
            )

        self.assertEqual("production", result.environment)
        self.assertEqual(1, len(calls))
        command, kwargs = calls[0]
        self.assertEqual(
            [
                shutil.which("npx"),
                "wrangler",
                "deploy",
                "--env",
                "production",
                "--config",
                str(config_path.resolve()),
            ],
            command,
        )
        self.assertEqual(config_path.resolve().parent, kwargs["cwd"])
        self.assertIs(kwargs["check"], True)
        payload = json.loads(emitted[0])
        self.assertEqual("a" * 40, payload["source_sha"])
        self.assertEqual(
            {
                "environment",
                "worker_name",
                "d1_database_name",
                "r2_bucket_names",
                "required_secret_names",
                "source_sha",
            },
            set(payload),
        )
        self.assertNotIn("database_id", payload)
        self.assertNotIn("api_origin", payload)
        self.assertNotIn("secret_value", payload)

    def test_production_action_rejects_repository_secrets_file_before_runner(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = helper._write_config(root, helper._config())
            profile_path = helper._write_profile(root)
            repository_secret = Path(__file__).resolve()
            calls = []
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                deploy_production_worker(
                    config_path,
                    environment="production",
                    source_sha="b" * 40,
                    policy_path=POLICY,
                    trust_profile_path=profile_path,
                    api_origin="https://api.example.test",
                    declared_secret_names=helper._production_secret_names(),
                    secrets_file=repository_secret,
                    runner=lambda *args, **kwargs: calls.append((args, kwargs)),
                )
            self.assertEqual([], calls)

    def test_production_action_accepts_external_secrets_file_without_reading_it(self):
        helper = self.helper()
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as secrets_tmp:
            root = Path(tmp)
            config_path = helper._write_config(root, helper._config())
            profile_path = helper._write_profile(root)
            secrets_file = Path(secrets_tmp) / "production.env"
            marker = "DO_NOT_READ_THIS_VALUE"
            secrets_file.write_text(f"LEASE_SIGNING_PRIVATE_KEY={marker}", encoding="utf-8")
            calls = []
            emitted = []
            deploy_production_worker(
                config_path,
                environment="production",
                source_sha="c" * 40,
                policy_path=POLICY,
                trust_profile_path=profile_path,
                api_origin="https://api.example.test",
                declared_secret_names=helper._production_secret_names(),
                secrets_file=secrets_file,
                runner=lambda command, **kwargs: calls.append((command, kwargs)),
                emit=emitted.append,
            )
        command = calls[0][0]
        self.assertEqual(
            str(secrets_file.resolve()),
            command[command.index("--secrets-file") + 1],
        )
        self.assertNotIn(marker, "\n".join(emitted))
        self.assertNotIn(marker, " ".join(command))


if __name__ == "__main__":
    unittest.main()
