import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "wechat_cli" / "web" / "static"


class WebLicenseUiTests(unittest.TestCase):
    def test_navigation_and_screen_include_license_update_management(self):
        html = (STATIC / "index.html").read_text(encoding="utf-8")

        self.assertIn('data-target="license"', html)
        self.assertIn('id="license"', html)
        self.assertIn('id="license-state"', html)
        self.assertIn('id="license-devices"', html)
        self.assertIn('id="update-state"', html)
        self.assertIn('id="manual-update-check"', html)
        self.assertIn('id="diagnostics-generate"', html)
        self.assertNotIn('id="full-license-key"', html)
        self.assertNotIn('id="device-token"', html)

    def test_javascript_loads_masked_license_devices_and_update_apis(self):
        script = (STATIC / "app.js").read_text(encoding="utf-8")

        for endpoint in (
            "/api/license",
            "/api/license/devices",
            "/api/update-status",
            "/api/license/devices/unbind",
            "/api/license/devices/rename",
            "/api/update/check",
        ):
            self.assertIn(endpoint, script)
        self.assertIn("crypto.randomUUID", script)
        self.assertIn("confirm(", script)
        self.assertNotIn("device_token", script)
        self.assertNotIn("license_key", script)

    def test_styles_cover_license_cards_devices_and_progress(self):
        css = (STATIC / "app.css").read_text(encoding="utf-8")

        for selector in (
            ".license-grid",
            ".license-card",
            ".device-list",
            ".device-row",
            ".update-progress",
            ".diagnostics-consent",
        ):
            self.assertIn(selector, css)


if __name__ == "__main__":
    unittest.main()
