from pathlib import Path

import pytest
from dotenv import dotenv_values

from quii_helper import Camera
from quii_helper.config import AutonomousConfig, load_config
from quii_helper.config.settings_loader import (
    SettingsLoader,
    has_default_settings_cache,
    reset_default_settings_cache,
)


class SettingsLoaderTests:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("high", 1),
            ("main", 1),
            (" HD ", 1),
            ("clear", 1),
            ("low", 2),
            ("sub", 2),
            ("sd", 2),
            ("smooth", 2),
            ("1", 1),
            ("2", 2),
            ("3", 3),
        ],
    )
    def test_stream_names_and_numeric_ids(self, value, expected) -> None:
        config = load_config(env={"CAMERA_STREAM": value})
        assert config.stream == expected
        assert isinstance(config.stream, int)

    @pytest.mark.parametrize("value", ["0", "-1", "unknown", "1.5"])
    def test_invalid_stream_is_reported_as_configuration_error(
        self, value
    ) -> None:
        from quii_helper import ConfigurationError

        with pytest.raises(ConfigurationError, match="CAMERA_STREAM"):
            load_config(env={"CAMERA_STREAM": value})

    @pytest.mark.parametrize(
        "env,expected",
        [
            ({}, 2),
            ({"CAMERA_STREAM": "  "}, 2),
            ({"QUII_STREAM": "high"}, 1),
            ({"CAMERA_STREAM": "low", "QUII_STREAM": "high"}, 2),
            ({"CAMERA_STREAM": "", "QUII_STREAM": "high"}, 1),
        ],
    )
    def test_stream_default_and_legacy_alias_precedence(
        self, env, expected
    ) -> None:
        assert load_config(env=env).stream == expected

    def test_named_stream_file_process_and_camera_precedence(
        self, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.delenv("CAMERA_STREAM", raising=False)
        monkeypatch.delenv("QUII_STREAM", raising=False)
        path = tmp_path / ".env"
        path.write_text("CAMERA_STREAM=low\n", encoding="utf-8")
        assert load_config(project_root=tmp_path).stream == 2
        monkeypatch.setenv("CAMERA_STREAM", "high")
        config = load_config(project_root=tmp_path)
        assert config.stream == 1
        assert Camera(config=config).config.stream == 1
        assert Camera(config=config, stream_quality="low").config.stream == 2
        assert Camera(config=config, stream=3).config.stream == 3
        assert config.stream == 1
        assert path.read_text(encoding="utf-8") == "CAMERA_STREAM=low\n"

    def setup_method(self) -> None:
        reset_default_settings_cache()

    def teardown_method(self) -> None:
        reset_default_settings_cache()

    def test_env_template_leaves_door_control_unconfigured(self) -> None:
        template = Path(__file__).resolve().parents[2] / ".env.example"
        values = dotenv_values(template, interpolate=False)
        assert values["UNLOCK_PASSWORD"] == ""
        assert values["CAMERA_STREAM"] == "low"

    def test_loaded_settings_repr_hides_authentication_values(self) -> None:
        values = {
            "CLOUD_PASSWORD": "test-cloud-secret",
            "AUTH_CODE": "test-auth-secret",
            "DEVICE_PASSWORD": "test-device-secret",
            "UNLOCK_PASSWORD": "test-unlock-secret",
        }
        settings = SettingsLoader(env=values).load()
        assert all(value not in repr(settings) for value in values.values())
        assert settings.cloud_password == values["CLOUD_PASSWORD"]
        assert settings.auth_code == values["AUTH_CODE"]

    def test_loads_unlock_password_from_dotenv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("UNLOCK_PASSWORD", raising=False)
        (tmp_path / ".env").write_text(
            'UNLOCK_PASSWORD="test-door-password"\n', encoding="utf-8"
        )

        config = load_config(project_root=tmp_path)

        assert config.unlock_password == "test-door-password"
        assert "test-door-password" not in repr(config)

    def test_loads_values_from_supplied_env_without_process_env(self) -> None:
        settings = SettingsLoader(
            project_root=Path("project"),
            env={
                "CLOUD_ACCOUNT": "account",
                "CLOUD_PASSWORD": "password",
                "DEVICE_ID": "device",
                "CAMERA_DEVICE_HOST": "192.0.2.10",
                "AUTH_CODE": "auth-code",
                "UNLOCK_PASSWORD": "door-password",
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
        assert "door-password" == settings.unlock_password
        assert "door-password" not in repr(settings)
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

    def test_autonomous_config_is_independent_of_process_defaults(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assert not has_default_settings_cache()

        monkeypatch.setenv("CAMERA_APP_ID", "not-an-integer")
        monkeypatch.setenv("CLOUD_ACCOUNT", "unrelated-account")
        config = AutonomousConfig()
        assert config.cloud_account == ""
        assert config.app_id == 0
        assert not has_default_settings_cache()

    def test_dotenv_loading_is_isolated_and_does_not_mutate_process_env(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import os

        monkeypatch.delenv("UNLOCK_PASSWORD", raising=False)
        for name in ("first", "second"):
            root = tmp_path / name
            root.mkdir()
            (root / ".env").write_text(
                f"UNLOCK_PASSWORD={name}\n", encoding="utf-8"
            )
        first = load_config(project_root=tmp_path / "first")
        second = load_config(project_root=tmp_path / "second")
        assert first.unlock_password == "first"
        assert second.unlock_password == "second"
        assert "UNLOCK_PASSWORD" not in os.environ
        assert not has_default_settings_cache()

    def test_process_env_overrides_dotenv_without_changing_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UNLOCK_PASSWORD", "process-value")
        path = tmp_path / ".env"
        path.write_text("UNLOCK_PASSWORD=file-value\n", encoding="utf-8")
        assert (
            load_config(project_root=tmp_path).unlock_password
            == "process-value"
        )
        assert (
            path.read_text(encoding="utf-8") == "UNLOCK_PASSWORD=file-value\n"
        )

    def test_explicit_env_ignores_dotenv_and_process_values(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CAMERA_APP_ID", "bad-process-value")
        (tmp_path / ".env").write_text(
            "CAMERA_APP_ID=bad-file-value\n", encoding="utf-8"
        )
        config = load_config(
            project_root=tmp_path, env={"CAMERA_APP_ID": "17"}
        )
        assert config.app_id == 17

    def test_assets_directory_and_auth_version_belong_to_config(
        self,
        tmp_path: Path,
    ) -> None:
        config = load_config(
            project_root=tmp_path,
            assets_dir="private-assets",
            env={"CLOUD_AUTH_VERSION": "v-test"},
        )
        assert config.assets_dir == tmp_path / "private-assets"
        assert config.ca_path == config.assets_dir / "ca.pem"
        assert config.cert_path == config.assets_dir / "client.pem"
        assert config.key_path == config.assets_dir / "client.txt"
        assert config.auth_version == "v-test"
        assert not config.assets_dir.exists()

    def test_load_config_uses_supplied_env_without_default_cache(self) -> None:
        config = load_config(
            project_root=Path("project"),
            env={
                "CLOUD_ACCOUNT": "account",
                "CLOUD_PASSWORD": "password",
                "DEVICE_ID": "device",
                "CAMERA_DEVICE_HOST": "192.0.2.10",
                "AUTH_CODE": "auth-code",
                "UNLOCK_PASSWORD": "door-password",
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
        assert "door-password" == config.unlock_password
        assert "door-password" not in repr(config)
        assert "client" == config.client_id
        assert "https://auth" == config.auth_url
        assert "https://service" == config.service_url
        assert "OEM" == config.oem
        assert 10 == config.app_id
        assert 20 == config.client_type
        assert 30 == config.ip_region_id
        assert config.tls_verify
        assert not has_default_settings_cache()
