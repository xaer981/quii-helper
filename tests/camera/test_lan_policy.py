"""LAN defaults must not accidentally reach cloud or use invalid credentials."""

from unittest.mock import Mock

import pytest

from quii_helper import (
    AutonomousConfig,
    Camera,
    ConfigurationError,
    load_config,
)
from quii_helper.camera.connection.session import CameraConnector
from quii_helper.config.settings_loader import SettingsLoader
from quii_helper.support.redaction import (
    redact_json_text,
    redact_mapping,
    redact_xml_text,
)


def test_lan_is_default_even_when_cloud_credentials_are_present():
    camera = Camera(
        config=AutonomousConfig(cloud_account="test", cloud_password="test")
    )
    assert camera.config.connection_mode == "lan"
    assert camera.config.stream_port == 34567


def test_lan_config_keywords_env_and_secret_representations():
    env = {
        "CAMERA_CONNECTION_MODE": "lan",
        "CAMERA_DEVICE_HOST": "127.0.0.1",
        "CAMERA_STREAM_PORT": "34568",
        "STREAM_KEY": "S" * 32,
        "AUTH_CODE": "auth",
    }
    settings = SettingsLoader(env=env).load()
    config = load_config(env=env, load_env_file=False)
    camera = Camera(config, stream_port=34569, stream_key="T" * 32)
    assert config.stream_port == 34568
    assert camera.config.stream_port == 34569
    assert camera.config.stream_key == "T" * 32
    assert "S" * 32 not in repr(settings) + repr(config)
    assert "T" * 32 not in repr(camera.config)
    assert "S" * 32 not in str(redact_mapping(env))
    assert "S" * 32 not in redact_json_text(
        '{"stream_key": "' + "S" * 32 + '"}'
    )
    assert "S" * 32 not in redact_xml_text(
        "<stream_key>" + "S" * 32 + "</stream_key>"
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"connection_mode": "auto"},
        {"connection_mode": "local"},
        {"stream_port": 0},
        {"stream_port": 65536},
        {"stream_port": True},
    ],
)
def test_invalid_connection_options_are_rejected(kwargs):
    with pytest.raises(ConfigurationError):
        Camera(config=AutonomousConfig(), **kwargs)


@pytest.mark.parametrize(
    "operation",
    [
        "get_device_info",
        "get_device_shadow_info",
        "get_iot_command_support",
        "get_call_events",
        "fetch_stream_credentials",
    ],
)
def test_cloud_apis_refuse_before_any_connector_or_cloud_call(
    monkeypatch, operation
):
    camera = Camera(config=AutonomousConfig())
    camera.connector = Mock()
    cloud = Mock(side_effect=AssertionError("cloud call"))
    monkeypatch.setattr("quii_helper.camera.api.fetch_call_events", cloud)
    with pytest.raises(ConfigurationError, match="cloud access is disabled"):
        getattr(camera, operation)()
    assert camera.connector.mock_calls == []
    cloud.assert_not_called()


@pytest.mark.parametrize(
    "operation", ["capture", "snapshot", "save_video", "record", "serve_rtsp"]
)
def test_invalid_lan_media_configuration_fails_before_io(
    monkeypatch, operation
):
    camera = Camera(config=AutonomousConfig())
    cloud = Mock(side_effect=AssertionError("cloud call"))
    monkeypatch.setattr(camera.connector, "fetch_credentials", cloud)
    server = Mock(side_effect=AssertionError("listener started"))
    monkeypatch.setattr(
        "quii_helper.streaming.rtsp.server.socket.socket", server
    )
    with pytest.raises(ConfigurationError, match="explicit device_host"):
        getattr(camera, operation)(
            **(
                {"duration_seconds": 1}
                if operation in {"save_video", "record"}
                else {}
            )
        )
    cloud.assert_not_called()
    server.assert_not_called()


def test_connector_routes_lan_session_without_fetching_credentials(
    monkeypatch,
):
    connector = CameraConnector(AutonomousConfig())
    cloud = Mock(side_effect=AssertionError("cloud call"))
    session_cls = Mock()
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials",
        cloud,
    )
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.LanTcpSession", session_cls
    )
    assert connector.connect() is session_cls.return_value.open.return_value
    session_cls.assert_called_once_with(connector.config)
    cloud.assert_not_called()
    with pytest.raises(ConfigurationError):
        connector.fetch_credentials()
    cloud.assert_not_called()


def test_cloud_connector_still_fetches_credentials_when_explicitly_selected(
    monkeypatch,
):
    connector = CameraConnector(AutonomousConfig(connection_mode="cloud"))
    cloud = Mock()
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials",
        cloud,
    )
    assert connector.fetch_credentials() is cloud.return_value
    cloud.assert_called_once_with(
        connector.config, cookie_jar=connector.cookie_jar
    )


@pytest.mark.parametrize(
    "values",
    [{"CAMERA_CONNECTION_MODE": "auto"}, {"CAMERA_STREAM_PORT": "65536"}],
)
def test_invalid_loaded_connection_policy_is_rejected(values):
    with pytest.raises(ConfigurationError):
        SettingsLoader(env=values).load()


def test_lan_rejects_cloud_credentials_without_constructing_session(
    monkeypatch,
):
    connector = CameraConnector(AutonomousConfig())
    session_cls = Mock(side_effect=AssertionError("unexpected session"))
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.LanTcpSession", session_cls
    )
    with pytest.raises(
        ConfigurationError, match="do not accept cloud credentials"
    ):
        connector.open_preview(credentials=object())
    session_cls.assert_not_called()


def test_lan_door_auto_never_looks_up_capability_in_cloud(monkeypatch):
    camera = Camera(
        config=AutonomousConfig(
            device_host="127.0.0.1",
            auth_code="synthetic",
            unlock_password="synthetic-unlock",
        )
    )
    cloud = Mock(side_effect=AssertionError("cloud call"))
    send = Mock(side_effect=AssertionError("door command"))
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.fetch_runtime_credentials",
        cloud,
    )
    monkeypatch.setattr("quii_helper.device.control.request_cgi", send)
    with pytest.raises(ConfigurationError):
        camera.open_door(password_mode="auto")
    cloud.assert_not_called()
    send.assert_not_called()
