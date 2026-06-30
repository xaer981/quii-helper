import pytest

from quii_helper.cloud.config.runtime import (
    resolve_runtime_config,
    validate_runtime_config,
)
from quii_helper.config import AutonomousConfig
from quii_helper.support.errors import ConfigurationError


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
        "tls_verify": None,
    }
    values.update(overrides)
    return resolve_runtime_config(config, **values)


class CloudRuntimeConfigTests:
    def test_resolve_runtime_config_accepts_device_id_shorthand(self) -> None:
        resolved = _resolve("device-1")

        assert "device-1" == resolved.device_id

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

        assert "device-2" == resolved.device_id
        assert "account-2" == resolved.cloud_account
        assert "password-2" == resolved.cloud_password
        assert "client-2" == resolved.client_id
        assert "https://auth.example" == resolved.auth_url
        assert "https://service.example" == resolved.service_url
        assert "OEM2" == resolved.oem
        assert 22 == resolved.app_id
        assert 33 == resolved.client_type
        assert 44 == resolved.ip_region_id

    def test_resolve_runtime_config_rejects_conflicting_account_aliases(
        self,
    ) -> None:
        with pytest.raises(
            ConfigurationError,
            match="pass either cloud_username or cloud_account",
        ):
            _resolve(cloud_username="a", cloud_account="b")

    def test_validate_runtime_config_reports_missing_credentials(self) -> None:
        config = AutonomousConfig(
            device_id="",
            cloud_account="",
            cloud_password="",
        )

        with pytest.raises(
            ConfigurationError,
            match="device_id, cloud_account, cloud_password",
        ):
            validate_runtime_config(config)
