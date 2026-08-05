import tempfile
import unittest
from pathlib import Path

from wechat_cli.release.builder import SignedRelease
from wechat_cli.release.github import GitHubAsset, GitHubRelease
from wechat_cli.release.publisher import publish_signed_release


class FakeGitHub:
    def __init__(self, fail_upload_index=None):
        self.repository = "example/releases"
        self.calls = []
        self.fail_upload_index = fail_upload_index
        self.upload_count = 0

    def create_release(self, **kwargs):
        self.calls.append(("create_release", kwargs))
        return GitHubRelease(
            release_id=123,
            tag_name=kwargs["tag_name"],
            upload_url="https://uploads.github.com/repos/example/releases/releases/123/assets{?name,label}",
            draft=kwargs["draft"],
        )

    def upload_asset(self, upload_url, path, *, content_type):
        self.upload_count += 1
        self.calls.append(
            (
                "upload_asset",
                {
                    "upload_url": upload_url,
                    "path": Path(path),
                    "content_type": content_type,
                },
            )
        )
        if self.fail_upload_index == self.upload_count:
            raise RuntimeError("upload failed")
        source = Path(path)
        return GitHubAsset(
            asset_id=400 + self.upload_count,
            name=source.name,
            size=source.stat().st_size,
            state="uploaded",
        )

    def delete_asset(self, asset_id):
        self.calls.append(("delete_asset", {"asset_id": asset_id}))

    def delete_release(self, release_id):
        self.calls.append(("delete_release", {"release_id": release_id}))


class FakeAdmin:
    def __init__(self, fail_register=False, fail_enable=False):
        self.calls = []
        self.fail_register = fail_register
        self.fail_enable = fail_enable

    def register_release(self, payload):
        self.calls.append(("register_release", dict(payload)))
        if self.fail_register:
            raise RuntimeError("worker registration failed")
        return {
            "release_id": payload["release_id"],
            "enabled": False,
            "paused": True,
        }

    def update_release(self, release_id, **kwargs):
        self.calls.append(
            ("update_release", {"release_id": release_id, **kwargs})
        )
        if self.fail_enable:
            raise RuntimeError("worker enable failed")
        return {"ok": True, "release_id": release_id, **kwargs}


class ReleasePublisherTests(unittest.TestCase):
    def make_signed(self, root: Path):
        package = root / "wechat-cli-app-0.5.1-win-x64.zip"
        package.write_bytes(b"package bytes")
        return SignedRelease(
            package_path=package,
            manifest_bytes=b'{"version":"0.5.1"}',
            signature=b"s" * 64,
            manifest_sha256="11" * 32,
            package_sha256="22" * 32,
            package_size=package.stat().st_size,
            version="0.5.1",
            release_id="rel_051",
            channel="stable",
            signing_key_id="release-key-demo-01",
        )

    def test_uploads_package_manifest_signature_then_registers_disabled_release(self):
        github = FakeGitHub()
        admin = FakeAdmin()
        with tempfile.TemporaryDirectory() as tmp:
            signed = self.make_signed(Path(tmp))

            result = publish_signed_release(
                signed,
                github_client=github,
                admin_client=admin,
                repository="example/releases",
                target_commitish="main",
                release_name="WeChat CLI Web 0.5.1",
                release_body="Private update",
                operation_nonce="nonce_release_01",
            )

        upload_calls = [call for call in github.calls if call[0] == "upload_asset"]
        self.assertEqual(3, len(upload_calls))
        self.assertEqual(
            [
                "wechat-cli-app-0.5.1-win-x64.zip",
                "wechat-cli-update-manifest-0.5.1.json",
                "wechat-cli-update-manifest-0.5.1.sig",
            ],
            [call[1]["path"].name for call in upload_calls],
        )
        payload = admin.calls[0][1]
        self.assertEqual("example/releases", payload["github_repository"])
        self.assertEqual("123", payload["github_release_id"])
        self.assertEqual("401", payload["github_asset_id"])
        self.assertEqual(signed.package_path.name, payload["github_asset_name"])
        self.assertEqual("nonce_release_01", payload["operation_nonce"])
        self.assertFalse(result.enabled)
        self.assertTrue(result.paused)

    def test_enable_after_registration_is_explicit(self):
        github = FakeGitHub()
        admin = FakeAdmin()
        with tempfile.TemporaryDirectory() as tmp:
            result = publish_signed_release(
                self.make_signed(Path(tmp)),
                github_client=github,
                admin_client=admin,
                repository="example/releases",
                target_commitish="main",
                release_name="0.5.1",
                release_body="",
                operation_nonce="nonce_release_01",
                enable=True,
                enable_operation_nonce="nonce_enable_01",
            )

        self.assertTrue(result.enabled)
        self.assertFalse(result.paused)
        self.assertEqual("update_release", admin.calls[1][0])
        self.assertTrue(admin.calls[1][1]["enabled"])
        self.assertFalse(admin.calls[1][1]["paused"])

    def test_asset_upload_failure_rolls_back_uploaded_assets_and_draft_release(self):
        github = FakeGitHub(fail_upload_index=2)
        admin = FakeAdmin()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                publish_signed_release(
                    self.make_signed(Path(tmp)),
                    github_client=github,
                    admin_client=admin,
                    repository="example/releases",
                    target_commitish="main",
                    release_name="0.5.1",
                    release_body="",
                    operation_nonce="nonce_release_01",
                )

        self.assertIn(("delete_asset", {"asset_id": 401}), github.calls)
        self.assertIn(("delete_release", {"release_id": 123}), github.calls)
        self.assertEqual([], admin.calls)

    def test_enable_failure_preserves_registered_github_assets(self):
        github = FakeGitHub()
        admin = FakeAdmin(fail_enable=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                publish_signed_release(
                    self.make_signed(Path(tmp)),
                    github_client=github,
                    admin_client=admin,
                    repository="example/releases",
                    target_commitish="main",
                    release_name="0.5.1",
                    release_body="",
                    operation_nonce="nonce_release_01",
                    enable=True,
                    enable_operation_nonce="nonce_enable_01",
                )

        self.assertEqual(
            [],
            [call for call in github.calls if call[0].startswith("delete_")],
        )
        self.assertEqual("register_release", admin.calls[0][0])
        self.assertEqual("update_release", admin.calls[1][0])

    def test_worker_registration_failure_rolls_back_all_github_objects(self):
        github = FakeGitHub()
        admin = FakeAdmin(fail_register=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                publish_signed_release(
                    self.make_signed(Path(tmp)),
                    github_client=github,
                    admin_client=admin,
                    repository="example/releases",
                    target_commitish="main",
                    release_name="0.5.1",
                    release_body="",
                    operation_nonce="nonce_release_01",
                )

        deleted_assets = [
            call[1]["asset_id"]
            for call in github.calls
            if call[0] == "delete_asset"
        ]
        self.assertEqual([403, 402, 401], deleted_assets)
        self.assertIn(("delete_release", {"release_id": 123}), github.calls)


if __name__ == "__main__":
    unittest.main()
