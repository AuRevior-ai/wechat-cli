import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "services" / "license-update-worker" / "deployment-policy.json"


class WorkerDeploymentPolicyTests(unittest.TestCase):
    def test_non_secret_deployment_policy_source_exists(self):
        self.assertTrue(POLICY.is_file())

    def test_policy_declares_environment_names_bindings_and_secret_names_only(self):
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        self.assertEqual(1, policy.get("schema_version"))
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
        serialized = json.dumps(policy, sort_keys=True).lower()
        self.assertNotIn("github_pat_", serialized)
        self.assertNotIn("private key-----", serialized)
        self.assertNotIn("secret_value", serialized)


if __name__ == "__main__":
    unittest.main()
