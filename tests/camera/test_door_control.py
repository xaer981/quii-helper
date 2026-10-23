import base64
from typing import get_type_hints
from unittest.mock import MagicMock

import pytest

from quii_helper import (
    Camera,
    CameraDeviceInfo,
    CameraDoorOpenResult,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.camera import api as camera_api
from quii_helper.camera.metadata import camera_device_info_from_credentials
from quii_helper.config import RuntimeCredentials, load_config
from quii_helper.device import control


def _camera(**overrides: str) -> Camera:
    env = {
        "CAMERA_DEVICE_HOST": "192.0.2.10",
        "AUTH_CODE": "test-cgi-auth",
        "UNLOCK_PASSWORD": "test-door-password",
        "CAMERA_CHANNEL": "2",
        "TLS_VERIFY": "false",
    }
    env.update(overrides)
    return Camera(config=load_config(env=env, load_env_file=False))


def _credentials(support: bool | None) -> RuntimeCredentials:
    basedata = (
        base64.b64encode(
            b"\x01\x0e\x00\x00\x00" + bytes([support]) + bytes(10)
        ).decode()
        if support is not None
        else ""
    )
    return RuntimeCredentials(
        session_id="test-session",
        dynamic_password="test-dynamic-password",
        data_encode_key="test-data-key",
        auth_code="test-cgi-auth",
        transparent_basedata=basedata,
        raw={},
    )


def _info(camera: Camera, support: bool | None) -> CameraDeviceInfo:
    return camera_device_info_from_credentials(
        camera.config, _credentials(support)
    )


def test_open_door_uses_env_configuration_without_cloud_or_preview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = _camera()
    sender = MagicMock(return_value=CameraDoorOpenResult(0, 2, 1))
    monkeypatch.setattr(camera_api, "request_open_door", sender)
    monkeypatch.setattr(
        camera.connector,
        "fetch_credentials",
        MagicMock(side_effect=AssertionError("unexpected cloud login")),
    )
    monkeypatch.setattr(
        camera.connector,
        "open_preview",
        MagicMock(side_effect=AssertionError("unexpected preview session")),
    )

    result = camera.open_door(password_mode="sha256")

    assert result.accepted
    sender.assert_called_once_with(
        host="192.0.2.10",
        auth_code="test-cgi-auth",
        unlock_password="test-door-password",
        password_mode="sha256",
        supports_sha256_password=None,
        channel=2,
        lock_number=1,
        port=80,
        scheme="http",
        verify_tls=False,
        debug=False,
    )
    assert get_type_hints(Camera.open_door)["return"] is CameraDoorOpenResult


def test_constructor_and_per_call_overrides_preserve_base_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base = _camera().config
    camera = Camera(config=base, unlock_password="constructor-password")
    assert camera.config.unlock_password == "constructor-password"
    assert base.unlock_password == "test-door-password"
    sender = MagicMock(return_value=CameraDoorOpenResult(0, 3, 2))
    monkeypatch.setattr(camera_api, "request_open_door", sender)

    camera.open_door(
        channel=3,
        lock_number=2,
        unlock_password="call-password",
        password_mode="plain",
        auth_code="call-auth",
        port=8443,
        scheme="https",
        verify_tls=True,
        debug=True,
    )

    sender.assert_called_once_with(
        host="192.0.2.10",
        auth_code="call-auth",
        unlock_password="call-password",
        password_mode="plain",
        supports_sha256_password=None,
        channel=3,
        lock_number=2,
        port=8443,
        scheme="https",
        verify_tls=True,
        debug=True,
    )
    assert camera.config.channel == 2
    assert camera.config.unlock_password == "constructor-password"


@pytest.mark.parametrize("support", [True, False])
def test_auto_mode_reads_capability_before_command(
    monkeypatch: pytest.MonkeyPatch, support: bool
) -> None:
    camera = _camera()
    calls = []

    def get_info() -> CameraDeviceInfo:
        calls.append("metadata")
        return _info(camera, support)

    def send(**kwargs: object) -> CameraDoorOpenResult:
        calls.append("command")
        assert kwargs["password_mode"] == "auto"
        assert kwargs["supports_sha256_password"] is support
        return CameraDoorOpenResult(0, 2, 1)

    monkeypatch.setattr(camera, "get_device_info", get_info)
    monkeypatch.setattr(camera_api, "request_open_door", send)

    assert camera.open_door().accepted
    assert calls == ["metadata", "command"]


@pytest.mark.parametrize("support", [True, False])
def test_auto_mode_reuses_metadata_from_previous_read(
    monkeypatch: pytest.MonkeyPatch, support: bool
) -> None:
    camera = _camera(CAMERA_CONNECTION_MODE="cloud")
    fetch = MagicMock(return_value=_credentials(support))
    device_list = MagicMock(return_value=[])
    sender = MagicMock(return_value=CameraDoorOpenResult(0, 2, 1))
    monkeypatch.setattr(camera.connector, "fetch_credentials", fetch)
    monkeypatch.setattr(camera_api, "fetch_cloud_device_list", device_list)
    monkeypatch.setattr(camera_api, "request_open_door", sender)

    assert camera.get_device_info().supports_sha256_password is support
    camera.open_door()

    fetch.assert_called_once()
    device_list.assert_called_once()
    assert sender.call_args.kwargs["supports_sha256_password"] is support


def test_auto_mode_can_use_cached_runtime_capability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    camera = _camera()
    camera._runtime_credentials = _credentials(False)
    sender = MagicMock(return_value=CameraDoorOpenResult(0, 2, 1))
    lookup = MagicMock(side_effect=AssertionError("unexpected cloud lookup"))
    monkeypatch.setattr(camera, "get_device_info", lookup)
    monkeypatch.setattr(camera_api, "request_open_door", sender)

    camera.open_door()

    lookup.assert_not_called()
    assert sender.call_args.kwargs["supports_sha256_password"] is False


@pytest.mark.parametrize("lookup_fails", [True, False])
def test_unknown_capability_requires_explicit_mode_without_sending(
    monkeypatch: pytest.MonkeyPatch, lookup_fails: bool
) -> None:
    camera = _camera()
    lookup = MagicMock(return_value=_info(camera, None))
    if lookup_fails:
        lookup.side_effect = QuiiConnectionError("test cloud unavailable")
    sender = MagicMock(side_effect=AssertionError("unexpected device command"))
    monkeypatch.setattr(camera, "get_device_info", lookup)
    monkeypatch.setattr(control, "request_cgi", sender)

    with pytest.raises(ConfigurationError, match="password_mode='plain'"):
        camera.open_door()

    lookup.assert_called_once()
    sender.assert_not_called()


@pytest.mark.parametrize("mode", ["plain", "sha256"])
def test_explicit_mode_skips_metadata_lookup(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    camera = _camera()
    lookup = MagicMock(side_effect=AssertionError("unexpected cloud lookup"))
    sender = MagicMock(return_value=CameraDoorOpenResult(0, 2, 1))
    monkeypatch.setattr(camera, "get_device_info", lookup)
    monkeypatch.setattr(camera_api, "request_open_door", sender)

    camera.open_door(password_mode=mode)

    lookup.assert_not_called()
    assert sender.call_args.kwargs["password_mode"] == mode


@pytest.mark.parametrize(
    "field", ["CAMERA_DEVICE_HOST", "AUTH_CODE", "UNLOCK_PASSWORD"]
)
def test_missing_setting_never_sends(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    camera = _camera(**{field: ""})
    sender = MagicMock(side_effect=AssertionError("unexpected device request"))
    monkeypatch.setattr(control, "request_cgi", sender)

    with pytest.raises(ConfigurationError, match=field):
        camera.open_door()

    sender.assert_not_called()
