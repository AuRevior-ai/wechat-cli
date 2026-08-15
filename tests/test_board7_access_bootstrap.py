import json
import unittest


class Board7AccessBootstrapTests(unittest.TestCase):
    def test_g3_plan_freezes_exact_access_boundaries(self):
        from scripts.board7_access_bootstrap import build_g3_plan

        plan = build_g3_plan("operator@example.com")

        self.assertEqual("2040a134dbf533fd538deae668556226", plan["account_id"])
        self.assertEqual(
            "wechat-cli-production-human-admin",
            plan["human_app"]["name"],
        )
        self.assertEqual(
            "wechat-cli-admin.aurevior-devspace.com/v1/admin/*",
            plan["human_app"]["domain"],
        )
        self.assertEqual("self_hosted", plan["human_app"]["type"])
        self.assertEqual("30m", plan["human_app"]["session_duration"])
        self.assertIs(plan["human_app"]["app_launcher_visible"], False)
        self.assertIs(plan["human_app"]["allow_authenticate_via_warp"], False)

        self.assertEqual("allow", plan["human_policy"]["decision"])
        self.assertEqual(
            [{"email": {"email": "operator@example.com"}}],
            plan["human_policy"]["include"],
        )

        self.assertEqual(
            "wechat-cli-production-release-automation",
            plan["automation_app"]["name"],
        )
        self.assertEqual(
            "wechat-cli-admin.aurevior-devspace.com/v1/automation/*",
            plan["automation_app"]["domain"],
        )
        self.assertEqual("self_hosted", plan["automation_app"]["type"])
        self.assertIs(plan["automation_app"]["service_auth_401_redirect"], True)
        self.assertNotIn("automation_policy", plan)
        self.assertNotIn("service_token", plan)

    def test_g3_plan_rejects_non_email_identity(self):
        from scripts.board7_access_bootstrap import build_g3_plan

        for value in ("", "operator", "operator@", "@example.com", "operator example.com"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                build_g3_plan(value)

    def test_g3_execute_refuses_exact_name_or_domain_collision_before_writes(self):
        from scripts.board7_access_bootstrap import AccessProvisionError, execute_g3

        collisions = [
            {
                "id": "existing-id",
                "name": "wechat-cli-production-human-admin",
                "domain": "other.example.com",
            },
            {
                "id": "existing-id",
                "name": "other-app",
                "domain": "wechat-cli-admin.aurevior-devspace.com/v1/automation/*",
            },
        ]
        for existing in collisions:
            calls = []

            def requester(method, path, *, token, body=None):
                calls.append((method, path, body))
                if method == "GET":
                    return {"success": True, "result": [existing]}
                raise AssertionError("write must not occur after collision")

            with self.subTest(existing=existing), self.assertRaises(AccessProvisionError):
                execute_g3(
                    api_token="secret-token",
                    human_email="operator@example.com",
                    requester=requester,
                )
            self.assertEqual(1, len(calls))
            self.assertEqual("GET", calls[0][0])

    def test_g3_execute_creates_only_human_app_policy_and_automation_app(self):
        from scripts.board7_access_bootstrap import execute_g3

        calls = []
        responses = [
            {"success": True, "result": []},
            {
                "success": True,
                "result": {
                    "id": "human-app-id",
                    "aud": "human-aud",
                    "name": "wechat-cli-production-human-admin",
                    "domain": "wechat-cli-admin.aurevior-devspace.com/v1/admin/*",
                    "type": "self_hosted",
                },
            },
            {"success": True, "result": {"id": "human-policy-id"}},
            {
                "success": True,
                "result": {
                    "id": "automation-app-id",
                    "aud": "automation-aud",
                    "name": "wechat-cli-production-release-automation",
                    "domain": "wechat-cli-admin.aurevior-devspace.com/v1/automation/*",
                    "type": "self_hosted",
                },
            },
        ]

        def requester(method, path, *, token, body=None):
            calls.append((method, path, token, body))
            return responses[len(calls) - 1]

        result = execute_g3(
            api_token="secret-token",
            human_email="operator@example.com",
            requester=requester,
        )

        self.assertEqual(
            ["GET", "POST", "POST", "POST"],
            [call[0] for call in calls],
        )
        self.assertEqual(
            "/accounts/2040a134dbf533fd538deae668556226/access/apps",
            calls[0][1],
        )
        self.assertEqual(calls[0][1], calls[1][1])
        self.assertEqual(
            "/accounts/2040a134dbf533fd538deae668556226/access/apps/human-app-id/policies",
            calls[2][1],
        )
        self.assertEqual(calls[0][1], calls[3][1])
        serialized_calls = json.dumps(calls)
        self.assertNotIn("service_tokens", serialized_calls)
        self.assertNotIn("any_valid_service_token", serialized_calls)
        self.assertNotIn("non_identity", serialized_calls)

        self.assertEqual(
            {
                "human_app_id": "human-app-id",
                "human_audience": "human-aud",
                "human_policy_id": "human-policy-id",
                "automation_app_id": "automation-app-id",
                "automation_audience": "automation-aud",
                "automation_policy_state": "deny_by_default_until_g4",
            },
            result,
        )
        serialized_result = json.dumps(result)
        self.assertNotIn("secret-token", serialized_result)
        self.assertNotIn("operator@example.com", serialized_result)

    def test_g3_execute_rejects_drifted_create_response(self):
        from scripts.board7_access_bootstrap import AccessProvisionError, execute_g3

        responses = [
            {"success": True, "result": []},
            {
                "success": True,
                "result": {
                    "id": "human-app-id",
                    "aud": "human-aud",
                    "name": "wrong-name",
                    "domain": "wechat-cli-admin.aurevior-devspace.com/v1/admin/*",
                    "type": "self_hosted",
                },
            },
        ]
        calls = []

        def requester(method, path, *, token, body=None):
            calls.append((method, path, body))
            return responses[len(calls) - 1]

        with self.assertRaises(AccessProvisionError):
            execute_g3(
                api_token="secret-token",
                human_email="operator@example.com",
                requester=requester,
            )
        self.assertEqual(2, len(calls))


if __name__ == "__main__":
    unittest.main()
