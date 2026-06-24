import unittest
from types import SimpleNamespace

from quii_helper.config.validation import (
    is_missing_config_value,
    missing_camera_app_fields,
)


class ConfigValidationStateTests(unittest.TestCase):
    def test_is_missing_config_value_preserves_existing_rules(self) -> None:
        self.assertTrue(is_missing_config_value(None))
        self.assertTrue(is_missing_config_value(""))
        self.assertTrue(is_missing_config_value("   "))
        self.assertTrue(is_missing_config_value(0))
        self.assertFalse(is_missing_config_value("value"))
        self.assertFalse(is_missing_config_value(1))
        self.assertFalse(is_missing_config_value(object()))

    def test_missing_camera_app_fields_preserves_field_order_and_env_names(
        self,
    ) -> None:
        config = SimpleNamespace(
            service_url="",
            auth_url="https://auth",
            oem="OEM",
            app_id=0,
            client_type=1,
            client_id="client",
            ip_region_id=None,
        )

        self.assertEqual(
            [
                "service_url (CLOUD_SERVICE_URL)",
                "app_id (CAMERA_APP_ID)",
                "ip_region_id (IP_REGION_ID)",
            ],
            missing_camera_app_fields(config),
        )

    def test_missing_camera_app_fields_returns_empty_for_complete_config(
        self,
    ) -> None:
        config = SimpleNamespace(
            service_url="https://service",
            auth_url="https://auth",
            oem="OEM",
            app_id=1,
            client_type=1,
            client_id="client",
            ip_region_id=1,
        )

        self.assertEqual([], missing_camera_app_fields(config))


if __name__ == "__main__":
    unittest.main()
