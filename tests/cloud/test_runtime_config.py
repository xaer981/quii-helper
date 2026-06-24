import unittest

from quii_helper.cloud.config.runtime import (
    resolve_runtime_config,
    validate_runtime_config,
)
from quii_helper.config import AutonomousConfig


def _resolve(config=None, **overrides):
    values = {
        "device_id": None,
        "cloud_username": None,
        "cloud_account": None,
        "cloud_password": None,
        "client_id": None,
        "auth_url": None,
        "service_url": None,
        "oem": None,
        "app_id": None,
        "client_type": None,
        "ip_region_id": None,
    }
    values.update(overrides)
    return resolve_runtime_config(config, **values)


class CloudRuntimeConfigTests(unittest.TestCase):
    def test_resolve_runtime_config_accepts_device_id_shorthand(self) -> None:
        resolved = _resolve("device-1")

        self.assertEqual("device-1", resolved.device_id)

    def test_resolve_runtime_config_applies_explicit_overrides(self) -> None:
        base = AutonomousConfig(
            device_id="base-device",
            cloud_account="base-account",
            cloud_password="base-password",
        )

        resolved = _resolve(
            base,
            device_id="device-2",
            cloud_username="account-2",
            cloud_password="password-2",
            client_id="client-2",
            auth_url="https://auth.example",
            service_url="https://service.example",
            oem="OEM2",
            app_id=22,
            client_type=33,
            ip_region_id=44,
        )

        self.assertEqual("device-2", resolved.device_id)
        self.assertEqual("account-2", resolved.cloud_account)
        self.assertEqual("password-2", resolved.cloud_password)
        self.assertEqual("client-2", resolved.client_id)
        self.assertEqual("https://auth.example", resolved.auth_url)
        self.assertEqual("https://service.example", resolved.service_url)
        self.assertEqual("OEM2", resolved.oem)
        self.assertEqual(22, resolved.app_id)
        self.assertEqual(33, resolved.client_type)
        self.assertEqual(44, resolved.ip_region_id)

    def test_resolve_runtime_config_rejects_conflicting_account_aliases(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "pass either cloud_username or cloud_account",
        ):
            _resolve(cloud_username="a", cloud_account="b")

    def test_validate_runtime_config_reports_missing_credentials(self) -> None:
        config = AutonomousConfig(
            device_id="",
            cloud_account="",
            cloud_password="",
        )

        with self.assertRaisesRegex(
            ValueError,
            "device_id, cloud_account, cloud_password",
        ):
            validate_runtime_config(config)


if __name__ == "__main__":
    unittest.main()
