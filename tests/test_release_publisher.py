import inspect
import tempfile
import unittest
from pathlib import Path

from wechat_cli.release.builder import SignedRelease
from wechat_cli.release.github import GitHubAsset, GitHubRelease
from wechat_cli.release.publisher import publish_signed_release


class FakeGitHub:
    def __init__(self, events, *, fail_upload_index=None, fail_publish=False):
        self.repository = "example/releases"
        self.events = events
        self.fail_upload_index = fail_upload_index
        self.fail_publish = fail_publish
        self.upload_count = 0

    def create_release(self, **kwargs):
        self.events.append(("github.create_draft", kwargs))
        return GitHubRelease(
            release_id=123,
            tag_name=kwargs["tag_name"],
            upload_url="https://uploads.github.com/repos/example/releases/releases/123/assets{?name,label}",
            draft=kwargs["draft"],
        )

    def upload_asset(self, upload_url, path, *, content_type):
        self.upload_count += 1
        source = Path(path)
        self.events.append(
            (
                "github.upload_asset",
                {
                    "upload_url": upload_url,
                    "path": source,
                    "content_type": content_type,
                },
            )
        )
        if self.fail_upload_index == self.upload_count:
            raise RuntimeError("upload failed")
        return GitHubAsset(
            asset_id=400 + self.upload_count,
            name=source.name,
            size=source.stat().st_size,
            state="uploaded",
        )

    def publish_release(self, release_id, *, prerelease, make_latest):
        self.events.append(
            (
                "github.publish_release",
                {
                    "release_id": release_id,
                    "prerelease": prerelease,
                    "make_latest": make_latest,
                },
            )
        )
        if self.fail_publish:
            raise RuntimeError("publish failed")
        return GitHubRelease(
            release_id=release_id,
            tag_name="v0.5.1",
            upload_url="https://uploads.github.com/repos/example/releases/releases/123/assets{?name,label}",
            draft=False,
        )

    def delete_asset(self, asset_id):
        self.events.append(("github.delete_asset", {"asset_id": asset_id}))

    def delete_release(self, release_id):
        self.events.append(("github.delete_release", {"release_id": release_id}))


class FakeAdmin:
    def __init__(self, events, *, fail_register=False, fail_readiness=False):
        self.events = events
        self.fail_register = fail_register
        self.fail_readiness = fail_readiness

    def upload_release_package(
        self,
        release_id,
        *,
        channel,
        package_path,
        package_sha256,
        operation_nonce,
    ):
        source = Path(package_path)
        self.events.append(
            (
                "admin.r2_ready",
                {
                    "release_id": release_id,
                    "channel": channel,
                    "package_path": source,
                    "package_sha256": package_sha256,
                    "operation_nonce": operation_nonce,
                },
            )
        )
        if self.fail_readiness:
            raise RuntimeError("r2 readiness failed")
        return {
            "release_id": release_id,
            "distribution_backend": "r2",
            "distribution_object_key": f"releases/{channel}/{release_id}/{package_sha256}.zip",
            "package_sha256": package_sha256,
            "package_size": source.stat().st_size,
            "ready": True,
        }

    def register_release(self, payload):
        self.events.append(("admin.register_release", dict(payload)))
        if self.fail_register:
            raise RuntimeError("worker registration failed")
        return {
            "release_id": payload["release_id"],
            "enabled": False,
            "paused": True,
        }

    def update_release(self, release_id, **kwargs):
        self.events.append(
            ("admin.update_release", {"release_id": release_id, **kwargs})
        )
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

    def publish(self, signed, github, admin, **kwargs):
        self.assertIn(
            "upload_operation_nonce",
            inspect.signature(publish_signed_release).parameters,
        )
        return publish_signed_release(
            signed,
            github_client=github,
            admin_client=admin,
            repository="example/releases",
            target_commitish="main",
            release_name="WeChat CLI Web 0.5.1",
            release_body="Private update",
            operation_nonce="nonce_release_01",
            upload_operation_nonce="nonce_upload_01",
            **kwargs,
        )

    def test_r2_readiness_precedes_immutable_github_publication_and_registration(self):
        events = []
        github = FakeGitHub(events)
        admin = FakeAdmin(events)
        with tempfile.TemporaryDirectory() as tmp:
            signed = self.make_signed(Path(tmp))
            result = self.publish(signed, github, admin)

        names = [name for name, _payload in events]
        self.assertLess(names.index("admin.r2_ready"), names.index("github.publish_release"))
        self.assertLess(
            names.index("github.publish_release"), names.index("admin.register_release")
        )
        publish_payload = next(
            payload for name, payload in events if name == "github.publish_release"
        )
        self.assertFalse(publish_payload["make_latest"])
        registration = next(
            payload for name, payload in events if name == "admin.register_release"
        )
        self.assertEqual("r2", registration["distribution_backend"])
        self.assertEqual(
            f"releases/stable/rel_051/{signed.package_sha256}.zip",
            registration["distribution_object_key"],
        )
        self.assertFalse(result.enabled)
        self.assertTrue(result.paused)
        self.assertNotIn("admin.update_release", names)

    def test_enable_is_never_coupled_to_publish_or_registration(self):
        events = []
        github = FakeGitHub(events)
        admin = FakeAdmin(events)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                self.publish(
                    self.make_signed(Path(tmp)),
                    github,
                    admin,
                    enable=True,
                    enable_operation_nonce="nonce_enable_01",
                )
        self.assertEqual([], events)

    def test_asset_upload_failure_rolls_back_only_the_unpublished_draft(self):
        events = []
        github = FakeGitHub(events, fail_upload_index=2)
        admin = FakeAdmin(events)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                self.publish(self.make_signed(Path(tmp)), github, admin)

        names = [name for name, _payload in events]
        self.assertNotIn("admin.r2_ready", names)
        self.assertNotIn("github.publish_release", names)
        self.assertIn("github.delete_asset", names)
        self.assertIn("github.delete_release", names)

    def test_r2_readiness_failure_never_publishes_github_provenance(self):
        events = []
        github = FakeGitHub(events)
        admin = FakeAdmin(events, fail_readiness=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                self.publish(self.make_signed(Path(tmp)), github, admin)

        names = [name for name, _payload in events]
        self.assertIn("admin.r2_ready", names)
        self.assertNotIn("github.publish_release", names)
        self.assertNotIn("admin.register_release", names)
        self.assertIn("github.delete_release", names)

    def test_registration_failure_after_publish_preserves_immutable_provenance(self):
        events = []
        github = FakeGitHub(events)
        admin = FakeAdmin(events, fail_register=True)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                self.publish(self.make_signed(Path(tmp)), github, admin)

        names = [name for name, _payload in events]
        self.assertIn("admin.r2_ready", names)
        self.assertIn("github.publish_release", names)
        self.assertIn("admin.register_release", names)
        self.assertNotIn("github.delete_asset", names)
        self.assertNotIn("github.delete_release", names)


if __name__ == "__main__":
    unittest.main()
