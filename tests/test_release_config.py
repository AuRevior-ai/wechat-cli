import tempfile
import unittest
from pathlib import Path

from wechat_cli.release.config import ReleaseConfig, ReleaseConfigStorage
from wechat_cli.update.errors import ErrorCode, UpdateError
from wechat_cli.windows.dpapi import TestOnlyDataProtector


class ReleaseConfigTests(unittest.TestCase):
    def setUp(self):
        self.protector = TestOnlyDataProtector(
            b"release-config-tests",
            allow_insecure_test_use=True,
        )

    def make_key(self, root: Path):
        path = root / "release-key.pem"
        path.write_text("private key placeholder", encoding="utf-8")
        return path

    def test_validates_repository_target_and_absolute_key_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            key = self.make_key(Path(tmp)).resolve()
            config = ReleaseConfig(
                repository="example/wechat-cli-releases",
                target_commitish="main",
                github_token="github_pat_secret_value",
                signing_key_path=str(key),
                signing_key_id="release-key-demo-01",
            )

        self.assertEqual("example/wechat-cli-releases", config.repository)
        self.assertEqual(str(key), config.signing_key_path)
        self.assertNotIn("github_pat_secret_value", repr(config))

    def test_rejects_invalid_repository_relative_or_missing_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = self.make_key(root)
            cases = [
                {"repository": "missing-slash", "signing_key_path": str(key.resolve())},
                {"repository": "example/repo", "signing_key_path": "relative.pem"},
                {"repository": "example/repo", "signing_key_path": str(root / "missing.pem")},
            ]
            for override in cases:
                with self.subTest(override=override):
                    with self.assertRaises(ValueError):
                        ReleaseConfig(
                            repository=override["repository"],
                            target_commitish="main",
                            github_token="github_pat_secret_value",
                            signing_key_path=override["signing_key_path"],
                            signing_key_id="release-key-demo-01",
                        )

    def test_encrypted_storage_round_trip_contains_no_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            key = self.make_key(root).resolve()
            config = ReleaseConfig(
                repository="example/wechat-cli-releases",
                target_commitish="main",
                github_token="github_pat_secret_value",
                signing_key_path=str(key),
                signing_key_id="release-key-demo-01",
            )
            path = root / "release-config.dat"
            storage = ReleaseConfigStorage(path, self.protector)

            storage.save(config)
            raw = path.read_bytes()
            loaded = storage.load()

        self.assertEqual(config, loaded)
        self.assertNotIn(b"github_pat_secret_value", raw)
        self.assertNotIn(b"example/wechat-cli-releases", raw)

    def test_missing_and_corrupt_config(self):
        other = TestOnlyDataProtector(
            b"other-release-config-tests",
            allow_insecure_test_use=True,
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "release-config.dat"
            storage = ReleaseConfigStorage(path, self.protector)
            self.assertIsNone(storage.load())
            key = self.make_key(root).resolve()
            storage.save(
                ReleaseConfig(
                    repository="example/wechat-cli-releases",
                    target_commitish="main",
                    github_token="github_pat_secret_value",
                    signing_key_path=str(key),
                    signing_key_id="release-key-demo-01",
                )
            )
            with self.assertRaises(UpdateError) as caught:
                ReleaseConfigStorage(path, other).load()

        self.assertEqual(ErrorCode.LOCAL_STATE_CORRUPT, caught.exception.code)


if __name__ == "__main__":
    unittest.main()
