import unittest
from unittest.mock import patch

from wechat_cli import keys


class KeyScannerDispatchTests(unittest.TestCase):
    def test_forwards_custom_logger_to_windows_scanner(self):
        logger = object()
        with patch.object(
            keys.platform, "system", return_value="Windows"
        ), patch(
            "wechat_cli.keys.scanner_windows.extract_keys",
            return_value={"salt": "key"},
        ) as scanner:
            result = keys.extract_keys(
                "db", "all_keys.json", pid=123, print_fn=logger
            )

        scanner.assert_called_once_with(
            "db", "all_keys.json", pid=123, print_fn=logger
        )
        self.assertEqual(result, {"salt": "key"})


if __name__ == "__main__":
    unittest.main()
