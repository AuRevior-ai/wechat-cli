import unittest

from wechat_cli.update.versioning import SemanticVersion, is_newer_version


class SemanticVersionTests(unittest.TestCase):
    def test_numeric_components_are_compared_numerically(self):
        self.assertGreater(SemanticVersion.parse("0.10.0"), SemanticVersion.parse("0.9.9"))

    def test_release_is_newer_than_prerelease(self):
        self.assertGreater(SemanticVersion.parse("1.0.0"), SemanticVersion.parse("1.0.0-rc.2"))

    def test_prerelease_identifiers_follow_semver_precedence(self):
        ordered = [
            "1.0.0-alpha",
            "1.0.0-alpha.1",
            "1.0.0-alpha.beta",
            "1.0.0-beta",
            "1.0.0-beta.2",
            "1.0.0-beta.11",
            "1.0.0-rc.1",
            "1.0.0",
        ]
        parsed = [SemanticVersion.parse(value) for value in ordered]
        self.assertEqual(parsed, sorted(parsed))

    def test_build_metadata_does_not_change_precedence(self):
        self.assertEqual(
            SemanticVersion.parse("1.2.3+build.1"),
            SemanticVersion.parse("1.2.3+build.99"),
        )

    def test_invalid_versions_are_rejected(self):
        for value in ("1", "1.2", "01.2.3", "1.02.3", "1.2.03", "1.2.3-01", "v1.2.3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    SemanticVersion.parse(value)

    def test_is_newer_version_uses_semantic_ordering(self):
        self.assertTrue(is_newer_version("0.10.0", "0.9.9"))
        self.assertFalse(is_newer_version("0.9.9", "0.10.0"))
        self.assertFalse(is_newer_version("1.0.0+one", "1.0.0+two"))


if __name__ == "__main__":
    unittest.main()
