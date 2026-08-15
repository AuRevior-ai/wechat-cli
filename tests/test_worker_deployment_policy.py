import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "services" / "license-update-worker" / "deployment-policy.json"
WRANGLER = ROOT / "services" / "license-update-worker" / "wrangler.jsonc"


class WorkerDeploymentPolicyTests(unittest.TestCase):
    def test_non_secret_deployment_policy_source_exists(self):
        self.assertTrue(POLICY.is_file())

    def test_policy_declares_environment_names_bindings_and_secret_names_only(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(2, policy.get("schema_version"))
        environments = policy.get("environments")
        self.assertIsInstance(environments, dict)
        self.assertEqual(
            "wechat-cli-license-update-local",
            environments["local"]["worker_name"],
        )
        self.assertEqual(
            "wechat-cli-license-update-staging",
            environments["staging"]["worker_name"],
        )
        self.assertEqual(
            "wechat-cli-license-update",
            environments["production"]["worker_name"],
        )
        self.assertIs(environments["production"]["workers_dev"], False)
        self.assertTrue(environments["production"]["require_custom_route"])
        self.assertEqual(["DB"], policy["required_bindings"]["d1"])
        self.assertEqual(
            ["DIAGNOSTICS", "RELEASES"],
            policy["required_bindings"]["r2"],
        )
        contract = policy["production_contract"]
        self.assertEqual("PUBLIC_API_ORIGIN", contract["public_api_origin_var"])
        self.assertEqual("ACCESS_ADMIN_ORIGIN", contract["admin_origin_var"])
        self.assertEqual("ACCESS_HUMAN_AUDIENCES", contract["human_audiences_var"])
        self.assertEqual(
            "ACCESS_AUTOMATION_AUDIENCES",
            contract["automation_audiences_var"],
        )
        self.assertEqual(2, contract["required_custom_domain_count"])
        serialized = json.dumps(policy, sort_keys=True).lower()
        self.assertNotIn("github_pat_", serialized)
        self.assertNotIn("private key-----", serialized)
        self.assertNotIn("secret_value", serialized)

    def test_staging_source_binds_exact_access_verifier_and_admin_custom_domain(self):
        config = json.loads(WRANGLER.read_text(encoding="utf-8"))
        self.assertNotIn("global_fetch_strictly_public", config.get("compatibility_flags", []))
        staging = config["env"]["staging"]
        vars_value = staging["vars"]
        self.assertEqual(
            "https://floral-glitter-1ede.cloudflareaccess.com",
            vars_value.get("ACCESS_JWT_ISSUER"),
        )
        self.assertEqual(
            "https://floral-glitter-1ede.cloudflareaccess.com/cdn-cgi/access/certs",
            vars_value.get("ACCESS_JWKS_URL"),
        )
        self.assertEqual(
            "12ce8ebd33213a9c532ba90144d8bf0dc5df851c289071be5484d9cc751eb6fb",
            vars_value.get("ACCESS_AUDIENCES"),
        )
        self.assertEqual("email", vars_value.get("ACCESS_IDENTITY_CLAIM"))
        self.assertEqual(
            "https://wechat-cli-admin-staging.aurevior-devspace.com",
            vars_value.get("ACCESS_ADMIN_ORIGIN"),
        )
        self.assertEqual(
            [
                {
                    "pattern": "wechat-cli-admin-staging.aurevior-devspace.com",
                    "custom_domain": True,
                }
            ],
            staging.get("routes"),
        )


if __name__ == "__main__":
    unittest.main()
