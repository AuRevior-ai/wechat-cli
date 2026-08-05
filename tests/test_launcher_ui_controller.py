import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from wechat_cli.launcher.service import LauncherResult, LauncherStatus
from wechat_cli.launcher.ui_controller import LauncherUiController
from wechat_cli.license.device_identity import DeviceIdentity
from wechat_cli.license.models import ClientLicenseState
from wechat_cli.update.layout import InstallLayout


@dataclass
class StoredState:
    device_id: str = "dev_existing"
    license_key: str = "WCL-EXISTING-R4DN"


class FakeStorage:
    def __init__(self, state=None):
        self.state = state

    def load(self):
        return self.state


class FakeIdentityProvider:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return DeviceIdentity(
            device_id=kwargs.get("existing_device_id") or "dev_new",
            fingerprint="ab" * 32,
            display_name="DEFAULT-PC",
        )


class FakeService:
    def __init__(self, start_result=None, activation_error=None):
        self.start_result = start_result or LauncherResult(
            LauncherStatus.STARTED,
            version="0.4.2",
            license_state=ClientLicenseState.ONLINE_VALID,
        )
        self.activation_error = activation_error
        self.activation_calls = []
        self.start_calls = 0

    def activate(self, **kwargs):
        self.activation_calls.append(kwargs)
        if self.activation_error:
            raise self.activation_error
        return StoredState(
            device_id=kwargs["identity"].device_id,
            license_key=kwargs["license_key"],
        )

    def start(self):
        self.start_calls += 1
        return self.start_result


class LauncherUiControllerTests(unittest.TestCase):
    def make_layout(self, root):
        layout = InstallLayout(Path(root) / "WeChatCliWeb")
        layout.ensure_directories()
        return layout

    def test_initial_activation_state_is_masked(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = LauncherUiController(
                service=FakeService(),
                storage=FakeStorage(StoredState()),
                identity_provider=FakeIdentityProvider(),
                fingerprint_salt="salt-v1",
                layout=self.make_layout(tmp),
                initial_result=LauncherResult(
                    LauncherStatus.ACTIVATION_REQUIRED,
                    version="0.4.2",
                    license_state=ClientLicenseState.UNACTIVATED,
                ),
            )

            state = controller.get_ui_state()

        self.assertEqual("activation_required", state["status"])
        self.assertEqual("R4DN", state["license_hint"])
        self.assertNotIn("license_key", state)

    def test_activation_uses_existing_device_id_and_selected_name_then_starts(self):
        identity = FakeIdentityProvider()
        service = FakeService()
        success = []
        with tempfile.TemporaryDirectory() as tmp:
            controller = LauncherUiController(
                service=service,
                storage=FakeStorage(StoredState()),
                identity_provider=identity,
                fingerprint_salt="salt-v1",
                layout=self.make_layout(tmp),
                initial_result=LauncherResult(
                    LauncherStatus.ACTIVATION_REQUIRED,
                    version="0.4.2",
                ),
                success_handler=success.append,
            )

            state = controller.activate_license("WCL-NEW-KEY", "SURTR-PC")

        self.assertEqual("dev_existing", identity.calls[0]["existing_device_id"])
        call = service.activation_calls[0]
        self.assertEqual("WCL-NEW-KEY", call["license_key"])
        self.assertEqual("SURTR-PC", call["identity"].display_name)
        self.assertEqual(1, service.start_calls)
        self.assertEqual("ready", state["status"])
        self.assertEqual(1, len(success))
        self.assertNotIn("WCL-NEW-KEY", repr(state))

    def test_activation_failure_returns_stable_masked_error_state(self):
        service = FakeService(activation_error=RuntimeError("server refused WCL-SECRET"))
        with tempfile.TemporaryDirectory() as tmp:
            controller = LauncherUiController(
                service=service,
                storage=FakeStorage(),
                identity_provider=FakeIdentityProvider(),
                fingerprint_salt="salt-v1",
                layout=self.make_layout(tmp),
                initial_result=LauncherResult(LauncherStatus.ACTIVATION_REQUIRED),
            )

            state = controller.activate_license("WCL-SECRET", "PC")

        self.assertEqual("activation_required", state["status"])
        self.assertEqual("LIC-ACTIVATE-FAILED", state["error_code"])
        self.assertNotIn("WCL-SECRET", state["error_message"])

    def test_retry_maps_blocked_license_state(self):
        service = FakeService(
            start_result=LauncherResult(
                LauncherStatus.BLOCKED,
                version="0.4.2",
                license_state=ClientLicenseState.LICENSE_REVOKED,
                reason="revoked",
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            controller = LauncherUiController(
                service=service,
                storage=FakeStorage(StoredState()),
                identity_provider=FakeIdentityProvider(),
                fingerprint_salt="salt-v1",
                layout=self.make_layout(tmp),
                initial_result=service.start_result,
            )

            state = controller.retry_validation()

        self.assertEqual("blocked", state["status"])
        self.assertEqual("LIC-LICENSE-REVOKED", state["error_code"])
        self.assertFalse(state["can_retry_validation"])


if __name__ == "__main__":
    unittest.main()
