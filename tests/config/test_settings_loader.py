from pathlib import Path

import pytest

from quii_helper.config import AutonomousConfig, load_config
from quii_helper.config.settings_loader import (
    SettingsLoader,
    has_default_settings_cache,
    reset_default_settings_cache,
)


class SettingsLoaderTests:
    def setup_method(self) -> None:
        reset_default_settings_cache()

    def teardown_method(self) -> None:
        reset_default_settings_cache()

    def test_loads_values_from_supplied_env_without_process_env(self) -> None:
        settings = SettingsLoader(
            project_root=Path("project"),
            env={
                "CLOUD_ACCOUNT": "account",
                "CLOUD_PASSWORD": "password",
                "DEVICE_ID": "device",
                "CAMERA_DEVICE_HOST": "192.0.2.10",
                "AUTH_CODE": "auth-code",
                "CLOUD_CLIENT_UUID": "client",
                "LOG_LEVEL": "debug",
                "CLOUD_AUTH_VERSION": "v1",
                "CLOUD_AUTH_URL": "https://auth",
                "CLOUD_SERVICE_URL": "https://service",
                "CAMERA_OEM": "OEM",
                "CAMERA_APP_ID": "10",
                "CAMERA_CLIENT_TYPE": "20",
                "IP_REGION_ID": "30",
                "CAMERA_CHANNEL": "2",
                "CAMERA_STREAM": "1",
                "TLS_VERIFY": "false",
            },
            load_env_file=False,
        ).load()

        assert "account" == settings.cloud_account
        assert "password" == settings.cloud_password
        assert "device" == settings.device_id
        assert "192.0.2.10" == settings.camera_device_host
        assert "auth-code" == settings.auth_code
        assert "client" == settings.cloud_client_uuid
        assert "debug" == settings.log_level
        assert "v1" == settings.cloud_auth_version
        assert "https://auth" == settings.cloud_auth_url
        assert "https://service" == settings.cloud_service_url
        assert "OEM" == settings.camera_oem
        assert 10 == settings.camera_app_id
        assert 20 == settings.camera_client_type
        assert 30 == settings.ip_region_id
        assert 2 == settings.camera_channel
        assert 1 == settings.camera_stream
        assert not settings.tls_verify

    def test_loads_legacy_aliases(self) -> None:
        settings = SettingsLoader(
            project_root=Path("project"),
            env={
                "CLOUD_USERNAME": "account",
                "CLOUD_OEM": "OEM",
                "CLOUD_APP_ID": "11",
                "CLOUD_CLIENT_TYPE": "21",
                "VIDEO_PANEL": "3",
                "QUII_STREAM": "2",
            },
            load_env_file=False,
        ).load()

        assert "account" == settings.cloud_account
        assert "OEM" == settings.camera_oem
        assert 11 == settings.camera_app_id
        assert 21 == settings.camera_client_type
        assert 3 == settings.camera_channel
        assert 2 == settings.camera_stream

    def test_prefers_canonical_account_over_legacy_username(self) -> None:
        settings = SettingsLoader(
            project_root=Path("project"),
            env={
                "CLOUD_ACCOUNT": "account",
                "CLOUD_USERNAME": "legacy",
            },
            load_env_file=False,
        ).load()

        assert "account" == settings.cloud_account

    def test_rejects_invalid_integer_env_value(self) -> None:
        loader = SettingsLoader(
            project_root=Path("project"),
            env={"CAMERA_APP_ID": "bad"},
            load_env_file=False,
        )

        with pytest.raises(ValueError, match="CAMERA_APP_ID must be"):
            loader.load()

    def test_rejects_invalid_bool_env_value(self) -> None:
        loader = SettingsLoader(
            project_root=Path("project"),
            env={"TLS_VERIFY": "maybe"},
            load_env_file=False,
        )

        with pytest.raises(ValueError, match="TLS_VERIFY must be"):
            loader.load()

    def test_autonomous_config_class_import_does_not_load_default_settings(
        self,
    ) -> None:
        assert not has_default_settings_cache()

        _config_type = AutonomousConfig

        assert AutonomousConfig is _config_type
        assert not has_default_settings_cache()

    def test_autonomous_config_instance_keeps_convenient_env_defaults(
        self,
    ) -> None:
        assert not has_default_settings_cache()

        AutonomousConfig()

        assert has_default_settings_cache()

    def test_load_config_uses_supplied_env_without_default_cache(self) -> None:
        config = load_config(
            project_root=Path("project"),
            env={
                "CLOUD_ACCOUNT": "account",
                "CLOUD_PASSWORD": "password",
                "DEVICE_ID": "device",
                "CAMERA_DEVICE_HOST": "192.0.2.10",
                "AUTH_CODE": "auth-code",
                "CLOUD_CLIENT_UUID": "client",
                "CLOUD_AUTH_URL": "https://auth",
                "CLOUD_SERVICE_URL": "https://service",
                "CAMERA_OEM": "OEM",
                "CAMERA_APP_ID": "10",
                "CAMERA_CLIENT_TYPE": "20",
                "IP_REGION_ID": "30",
            },
            load_env_file=False,
        )

        assert "account" == config.cloud_account
        assert "password" == config.cloud_password
        assert "device" == config.device_id
        assert "192.0.2.10" == config.device_host
        assert "auth-code" == config.auth_code
        assert "client" == config.client_id
        assert "https://auth" == config.auth_url
        assert "https://service" == config.service_url
        assert "OEM" == config.oem
        assert 10 == config.app_id
        assert 20 == config.client_type
        assert 30 == config.ip_region_id
        assert config.tls_verify
        assert not has_default_settings_cache()
