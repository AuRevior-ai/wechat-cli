import os
import unittest
import uuid

from wechat_cli.launcher.locks import LauncherInstanceLock, default_launcher_mutex_name


class LauncherLockNameTests(unittest.TestCase):
    def test_default_name_is_stable_and_contains_no_raw_sid(self):
        name = default_launcher_mutex_name("S-1-5-21-123456-secret")

        self.assertTrue(name.startswith("Local\\WeChatCliLauncher-"))
        self.assertNotIn("S-1-5-21", name)
        self.assertEqual(name, default_launcher_mutex_name("S-1-5-21-123456-secret"))


@unittest.skipUnless(os.name == "nt", "named mutex test requires Windows")
class WindowsLauncherInstanceLockTests(unittest.TestCase):
    def test_second_lock_is_rejected_until_first_is_released(self):
        name = "Local\\WeChatCliLauncher-Test-" + uuid.uuid4().hex
        first = LauncherInstanceLock(name)
        second = LauncherInstanceLock(name)
        third = LauncherInstanceLock(name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.release()
            self.assertTrue(third.acquire())
        finally:
            first.release()
            second.release()
            third.release()

    def test_context_manager_raises_when_another_instance_exists(self):
        name = "Local\\WeChatCliLauncher-Test-" + uuid.uuid4().hex
        first = LauncherInstanceLock(name)
        second = LauncherInstanceLock(name)
        try:
            self.assertTrue(first.acquire())
            with self.assertRaises(RuntimeError):
                with second:
                    pass
        finally:
            first.release()
            second.release()


if __name__ == "__main__":
    unittest.main()
