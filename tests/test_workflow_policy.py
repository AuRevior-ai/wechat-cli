import re
import unittest
from pathlib import Path

from scripts.verify_canonical_main import verify_canonical_main
from scripts.verify_workflow_policy import verify_workflow_policy


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class CanonicalMainVerificationTests(unittest.TestCase):
    def test_exact_canonical_main_identity_is_required(self):
        sha = "a" * 40
        self.assertEqual(
            sha,
            verify_canonical_main(
                requested_sha=sha,
                checked_out_sha=sha,
                observed_main_sha=sha,
            ),
        )

    def test_mismatch_or_untrusted_sha_fails_closed(self):
        sha = "a" * 40
        cases = [
            {"requested_sha": "b" * 40, "checked_out_sha": sha, "observed_main_sha": sha},
            {"requested_sha": sha, "checked_out_sha": "b" * 40, "observed_main_sha": sha},
            {"requested_sha": sha, "checked_out_sha": sha, "observed_main_sha": "b" * 40},
            {"requested_sha": "short", "checked_out_sha": "short", "observed_main_sha": "short"},
            {"requested_sha": "A" * 40, "checked_out_sha": "A" * 40, "observed_main_sha": "A" * 40},
        ]
        for case in cases:
            with self.subTest(case=case):
                with self.assertRaises(ValueError):
                    verify_canonical_main(**case)


class WorkflowPolicyTests(unittest.TestCase):
    def test_required_workflow_sources_exist_and_pass_policy(self):
        result = verify_workflow_policy(ROOT)
        self.assertEqual(
            {"ci.yml", "deploy-production-worker.yml", "publish-production-release.yml"},
            set(result),
        )
        self.assertTrue(all(result.values()))

    def test_all_external_actions_are_full_sha_pinned(self):
        verify_workflow_policy(ROOT)
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            for reference in re.findall(r"^\s*-?\s*uses:\s*([^\s#]+)", text, flags=re.MULTILINE):
                self.assertIn("@", reference, (path.name, reference))
                action, ref = reference.rsplit("@", 1)
                self.assertIn("/", action)
                self.assertRegex(ref, FULL_SHA, (path.name, reference))

    def test_ci_has_no_production_credentials_and_minimal_permissions(self):
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn("fetch-depth: 2", text)
        self.assertNotIn("${{ secrets.", text)
        for forbidden in (
            "CLOUDFLARE_API_TOKEN",
            "PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY",
            "PRODUCTION_ACCESS_CLIENT_SECRET",
            "RELEASE_PUBLISHER_APP_PRIVATE_KEY",
        ):
            self.assertNotIn(forbidden, text)

    def test_ci_checks_out_exact_source_head_for_push_and_pull_request(self):
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertIn(
            "ref: ${{ github.event.pull_request.head.sha || github.sha }}",
            text,
        )
        self.assertIn("run: git diff --check HEAD^", text)

    def test_privileged_workflows_are_manual_concurrent_and_canonical_main_only(self):
        for filename, group in (
            ("deploy-production-worker.yml", "production-worker"),
            ("publish-production-release.yml", "production-release"),
        ):
            text = (WORKFLOWS / filename).read_text(encoding="utf-8")
            self.assertIn("workflow_dispatch:", text)
            self.assertNotIn("pull_request_target:", text)
            self.assertNotRegex(text, r"(?m)^\s{2}(push|pull_request):")
            self.assertIn(f"group: {group}", text)
            self.assertIn("scripts/verify_canonical_main.py", text)
            self.assertIn("environment: production", text)

    def test_deploy_workflow_materializes_atomic_worker_secret_bundle(self):
        text = (WORKFLOWS / "deploy-production-worker.yml").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            1, text.count("${{ secrets.PRODUCTION_WORKER_SECRETS_JSON }}")
        )
        self.assertIn("worker-secrets.production.json", text)
        self.assertIn("--secrets-file $secretsFile", text)
        self.assertIn("Remove-Item -LiteralPath $secretsFile", text)
        self.assertNotIn("wrangler secret put", text.lower())

    def test_publish_workflow_has_no_release_state_or_license_mutation(self):
        text = (WORKFLOWS / "publish-production-release.yml").read_text(
            encoding="utf-8"
        ).lower()
        for forbidden in (
            "releases enable",
            "releases resume",
            "rollout_percentage",
            "rollout-percentage",
            "license create",
            "licenses create",
            "/v1/admin/releases/",
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("disabled registration", text)
        self.assertIn("r2 readiness", text)
        self.assertIn("immutable github provenance", text)
        self.assertIn("verify_local_update_artifacts.py", text)
        self.assertIn("--provenance-target-sha", text)
        self.assertIn("read-only reconcile", text)
        self.assertIn("/v1/automation/releases", text)

    def test_release_signing_key_is_scoped_to_one_signing_step_and_no_action_follows_it(self):
        text = (WORKFLOWS / "publish-production-release.yml").read_text(
            encoding="utf-8"
        )
        marker = "PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY"
        self.assertEqual(1, text.count(marker))
        marker_index = text.index(marker)
        self.assertNotIn("uses:", text[marker_index:])


if __name__ == "__main__":
    unittest.main()
