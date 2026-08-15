import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import production_release_workflow


class ProductionReleaseWorkflowScriptTests(unittest.TestCase):
    def test_publish_requires_machine_credentials_and_full_source_sha_before_clients(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(
            production_release_workflow, "load_prepared_release"
        ) as loader:
            with self.assertRaises(ValueError):
                production_release_workflow.publish_prepared_release(
                    package_path=Path("package.zip"),
                    manifest_path=Path("manifest.json"),
                    signature_path=Path("manifest.sig"),
                    metadata_path=Path("metadata.json"),
                    trust_profile_path=Path("profile.json"),
                    api_origin="https://api.prod.example.test",
                    admin_origin="https://admin.prod.example.test",
                    repository="example/releases",
                    source_sha="short",
                    provenance_target_sha="b" * 40,
                    release_name="0.6.0",
                    release_body="notes",
                )
            loader.assert_not_called()

    def test_publish_uses_exact_machine_headers_and_never_requires_signing_private_key(self):
        signed = type(
            "Signed",
            (),
            {
                "release_id": "rel_prod_060",
                "version": "0.6.0",
                "channel": "stable",
            },
        )()
        github = object()
        automation = object()
        captured = {}

        class FakeAutomationClient:
            def __init__(self, *, json_transport, upload_transport, header_provider):
                captured["json_transport"] = json_transport
                captured["upload_transport"] = upload_transport
                captured["headers"] = dict(header_provider())

        with patch.dict(
            os.environ,
            {
                "WECHAT_CLI_GITHUB_APP_TOKEN": "github-installation-token",
                "WECHAT_CLI_ACCESS_CLIENT_ID": "service-client-id",
                "WECHAT_CLI_ACCESS_CLIENT_SECRET": "service-client-secret",
            },
            clear=True,
        ), patch.object(
            production_release_workflow,
            "load_prepared_release",
            return_value=signed,
        ), patch.object(
            production_release_workflow,
            "GitHubReleaseClient",
            return_value=github,
        ) as github_client, patch.object(
            production_release_workflow,
            "ReleaseAutomationClient",
            FakeAutomationClient,
        ), patch.object(
            production_release_workflow,
            "publish_signed_release",
            return_value=type(
                "Published",
                (),
                {
                    "release_id": "rel_prod_060",
                    "version": "0.6.0",
                    "github_release_id": 123,
                    "enabled": False,
                    "paused": True,
                },
            )(),
        ) as publish:
            result = production_release_workflow.publish_prepared_release(
                package_path=Path("package.zip"),
                manifest_path=Path("manifest.json"),
                signature_path=Path("manifest.sig"),
                metadata_path=Path("metadata.json"),
                trust_profile_path=Path("profile.json"),
                api_origin="https://api.prod.example.test",
                admin_origin="https://admin.prod.example.test",
                repository="example/releases",
                source_sha="a" * 40,
                provenance_target_sha="b" * 40,
                release_name="WeChat CLI 0.6.0",
                release_body="Private production baseline",
            )

        github_client.assert_called_once_with(
            repository="example/releases",
            token="github-installation-token",
        )
        self.assertEqual(
            {
                "CF-Access-Client-Id": "service-client-id",
                "CF-Access-Client-Secret": "service-client-secret",
            },
            captured["headers"],
        )
        publish.assert_called_once()
        self.assertEqual("b" * 40, publish.call_args.kwargs["target_commitish"])
        self.assertIn("Source commit: " + "a" * 40, publish.call_args.kwargs["release_body"])
        self.assertIn(
            "Release provenance commit: " + "b" * 40,
            publish.call_args.kwargs["release_body"],
        )
        self.assertEqual(0, publish.call_args.kwargs["rollout_percentage"])
        self.assertIn("Private production baseline", publish.call_args.kwargs["release_body"])
        self.assertEqual("a" * 40, result["source_sha"])
        self.assertEqual("b" * 40, result["provenance_target_sha"])
        self.assertFalse(result["enabled"])
        self.assertTrue(result["paused"])
        self.assertNotIn("token", repr(result).lower())
        self.assertNotIn("secret", repr(result).lower())


if __name__ == "__main__":
    unittest.main()
