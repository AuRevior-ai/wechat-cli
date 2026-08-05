import tempfile
import unittest
from pathlib import Path

from wechat_cli.release.github import (
    GitHubReleaseClient,
    GitHubReleaseError,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, headers, body, content_type):
        self.calls.append((method, url, dict(headers), body, content_type))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class GitHubReleaseClientTests(unittest.TestCase):
    def test_creates_draft_release_with_current_api_headers(self):
        transport = FakeTransport(
            [
                (
                    201,
                    {
                        "id": 123,
                        "tag_name": "v0.5.1",
                        "draft": True,
                        "upload_url": "https://uploads.github.com/repos/example/releases/releases/123/assets{?name,label}",
                    },
                )
            ]
        )
        client = GitHubReleaseClient(
            repository="example/releases",
            token="github_pat_secret",
            transport=transport,
        )

        release = client.create_release(
            tag_name="v0.5.1",
            name="WeChat CLI Web 0.5.1",
            body="Private authorized update",
            target_commitish="main",
            draft=True,
            prerelease=False,
        )

        method, url, headers, payload, content_type = transport.calls[0]
        self.assertEqual("POST", method)
        self.assertEqual(
            "https://api.github.com/repos/example/releases/releases",
            url,
        )
        self.assertEqual("Bearer github_pat_secret", headers["Authorization"])
        self.assertEqual("2026-03-10", headers["X-GitHub-Api-Version"])
        self.assertEqual("application/vnd.github+json", headers["Accept"])
        self.assertEqual("application/json", content_type)
        self.assertTrue(payload["draft"])
        self.assertFalse(payload["generate_release_notes"])
        self.assertEqual(123, release.release_id)
        self.assertNotIn("github_pat_secret", repr(client))

    def test_upload_asset_uses_upload_host_and_encoded_name(self):
        content = b"package bytes"
        transport = FakeTransport(
            [
                (
                    201,
                    {
                        "id": 456,
                        "name": "wechat cli 0.5.1.zip",
                        "state": "uploaded",
                        "size": len(content),
                    },
                )
            ]
        )
        client = GitHubReleaseClient(
            repository="example/releases",
            token="github_pat_secret",
            transport=transport,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wechat cli 0.5.1.zip"
            path.write_bytes(content)

            asset = client.upload_asset(
                "https://uploads.github.com/repos/example/releases/releases/123/assets{?name,label}",
                path,
                content_type="application/zip",
            )

        method, url, headers, body, content_type = transport.calls[0]
        self.assertEqual("POST", method)
        self.assertEqual(
            "https://uploads.github.com/repos/example/releases/releases/123/assets?name=wechat+cli+0.5.1.zip",
            url,
        )
        self.assertEqual(content, body)
        self.assertEqual("application/zip", content_type)
        self.assertEqual("Bearer github_pat_secret", headers["Authorization"])
        self.assertEqual(456, asset.asset_id)

    def test_rejects_untrusted_upload_url(self):
        client = GitHubReleaseClient(
            repository="example/releases",
            token="github_pat_secret",
            transport=FakeTransport([]),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.zip"
            path.write_bytes(b"asset")

            with self.assertRaises(ValueError):
                client.upload_asset(
                    "https://malicious.example/upload{?name,label}",
                    path,
                    content_type="application/zip",
                )

    def test_rejects_asset_size_mismatch(self):
        transport = FakeTransport(
            [(201, {"id": 456, "name": "asset.zip", "state": "uploaded", "size": 1})]
        )
        client = GitHubReleaseClient(
            repository="example/releases",
            token="github_pat_secret",
            transport=transport,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "asset.zip"
            path.write_bytes(b"longer")

            with self.assertRaises(GitHubReleaseError) as caught:
                client.upload_asset(
                    "https://uploads.github.com/repos/example/releases/releases/123/assets{?name,label}",
                    path,
                    content_type="application/zip",
                )

        self.assertEqual("GITHUB_ASSET_SIZE_MISMATCH", caught.exception.code)

    def test_api_error_preserves_request_id_without_token(self):
        transport = FakeTransport(
            [
                (
                    422,
                    {
                        "message": "Validation Failed",
                        "documentation_url": "https://docs.github.com/rest/releases/releases#create-a-release",
                        "request_id": "github-request-01",
                    },
                )
            ]
        )
        client = GitHubReleaseClient(
            repository="example/releases",
            token="github_pat_secret",
            transport=transport,
        )

        with self.assertRaises(GitHubReleaseError) as caught:
            client.create_release(
                tag_name="v0.5.1",
                name="0.5.1",
                body="",
                target_commitish="main",
            )

        self.assertEqual("GITHUB_API_ERROR", caught.exception.code)
        self.assertEqual(422, caught.exception.status)
        self.assertNotIn("github_pat_secret", str(caught.exception))

    def test_delete_release_and_asset_use_expected_paths(self):
        transport = FakeTransport([(204, {}), (204, {})])
        client = GitHubReleaseClient(
            repository="example/releases",
            token="github_pat_secret",
            transport=transport,
        )

        client.delete_asset(456)
        client.delete_release(123)

        self.assertEqual(
            [
                (
                    "DELETE",
                    "https://api.github.com/repos/example/releases/releases/assets/456",
                ),
                (
                    "DELETE",
                    "https://api.github.com/repos/example/releases/releases/123",
                ),
            ],
            [(method, url) for method, url, *_rest in transport.calls],
        )


if __name__ == "__main__":
    unittest.main()
