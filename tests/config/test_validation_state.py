from types import SimpleNamespace

from quii_helper.config.validation import (
    is_missing_config_value,
    missing_camera_app_fields,
)


class ConfigValidationStateTests:
    def test_is_missing_config_value_preserves_existing_rules(self) -> None:
        assert is_missing_config_value(None)
        assert is_missing_config_value("")
        assert is_missing_config_value("   ")
        assert is_missing_config_value(0)
        assert not is_missing_config_value("value")
        assert not is_missing_config_value(1)
        assert not is_missing_config_value(object())

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

        assert [
            "service_url (CLOUD_SERVICE_URL)",
            "app_id (CAMERA_APP_ID)",
            "ip_region_id (IP_REGION_ID)",
        ] == (missing_camera_app_fields(config))

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

        assert [] == missing_camera_app_fields(config)
