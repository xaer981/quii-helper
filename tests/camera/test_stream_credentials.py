"""Cloud bootstrap and secret persistence using synthetic responses only."""

import importlib
import json
import os
import stat
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, Mock

import pytest

from quii_helper import (
    AutonomousConfig,
    Camera,
    CameraStreamCredentials,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.cloud.http import transport
from tests.cloud.test_http_transport import _Response

KEY = "K" * 32
AUTH = "synthetic-device-auth"


def credentials():
    return CameraStreamCredentials("synthetic-device", KEY, AUTH)


def cloud_config(**overrides):
    values = dict(
        connection_mode="cloud",
        cloud_account="synthetic-account",
        cloud_password="synthetic-cloud-password",
        device_id="synthetic-device",
        auth_url="https://auth.example/UserAuth",
        service_url="https://service.example",
        oem="OEM",
        app_id=1,
        client_type=2,
        ip_region_id=3,
        client_id="synthetic-client",
    )
    values.update(overrides)
    return AutonomousConfig(**values)


@pytest.fixture
def cloud(monkeypatch):
    seen = []
    reply = {
        "key": KEY,
        "auth": AUTH,
        "device": "synthetic-device",
        "result": 0,
    }

    def build(*, verify_tls, cookie_jar):
        class Opener:
            def open(self, request, timeout):
                root = ET.fromstring(request.data)
                command = root.findtext("header/command")
                seen.append((command, root, verify_tls, cookie_jar))
                if command == "login":
                    data = (
                        "<envelope><header><result>0</result>"
                        "<session>synthetic-session</session></header><content/>"
                        "</envelope>"
                    )
                else:
                    assert command == "get-device-token"
                    data = (
                        f"<envelope><header><result>{reply['result']}</result>"
                        "</header><content>"
                        f"<deviceid>{reply['device']}</deviceid>"
                        f"<dataEncodeKey>{reply['key']}</dataEncodeKey>"
                        f"<authCode>{reply['auth']}</authCode>"
                        "<dynamicPassword>synthetic-dynamic-password</dynamicPassword>"
                        "</content></envelope>"
                    )
                return _Response(data.encode("utf-8"), {})

        return Opener()

    monkeypatch.setattr(transport, "build_cloud_opener", build)
    forbidden = Mock(
        side_effect=AssertionError("preview/device/discovery I/O")
    )
    monkeypatch.setattr("quii_helper.camera.api.request_open_door", forbidden)
    monkeypatch.setattr(
        "quii_helper.camera.connection.session.open_direct_preview", forbidden
    )
    monkeypatch.setattr(
        "quii_helper.cloud.services.discovery.query_service_addresses",
        forbidden,
    )
    monkeypatch.setattr(
        "quii_helper.protocols.ust.crypto_tables._read_p2p_crypto_tables",
        forbidden,
    )
    yield seen, reply
    forbidden.assert_not_called()


@pytest.mark.parametrize("tls_verify", [True, False])
def test_bootstrap_uses_login_and_device_token_only_and_refreshes_each_time(
    tmp_path, cloud, tls_verify
):
    seen, _ = cloud
    statuses = []
    camera = Camera(
        cloud_config(tls_verify=tls_verify), status=statuses.append
    )
    original_config = repr(camera.config)
    first = camera.fetch_stream_credentials()
    second = camera.fetch_stream_credentials()
    assert first == second == credentials()
    assert [call[0] for call in seen] == ["login", "get-device-token"] * 2
    assert all(call[2] is tls_verify for call in seen)
    assert all(call[3] is camera.connector.cookie_jar for call in seen)
    assert seen[1][1].findtext("content/device-id") == first.device_id
    assert seen[1][1].findtext("header/session") == "synthetic-session"
    assert repr(camera.config) == original_config
    path = first.save(tmp_path / "stream_credentials.json")
    saved = CameraStreamCredentials.load(path)
    lan = Camera(
        config=AutonomousConfig(device_host="127.0.0.1"),
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    assert lan.config.connection_mode == "lan"
    assert lan.config.stream_key == KEY
    assert len(seen) == 4
    assert KEY not in repr(saved) + str(statuses)
    assert AUTH not in repr(saved) + str(statuses)


def test_lan_refuses_bootstrap_before_network_or_status_callback():
    status = Mock()
    camera = Camera(AutonomousConfig(), status=status)
    camera.connector.fetch_credentials = Mock(
        side_effect=AssertionError("cloud")
    )
    with pytest.raises(ConfigurationError, match="cloud access is disabled"):
        camera.fetch_stream_credentials()
    camera.connector.fetch_credentials.assert_not_called()
    status.assert_not_called()


@pytest.mark.parametrize(
    "update",
    [
        {"key": ""},
        {"key": "too-short"},
        {"auth": ""},
        {"device": "another-device"},
    ],
)
def test_invalid_cloud_credentials_do_not_fall_back_to_env_or_change_config(
    cloud, update
):
    _, reply = cloud
    reply.update(update)
    camera = Camera(cloud_config(stream_key="X" * 32, auth_code="old-auth"))
    with pytest.raises(QuiiConnectionError) as error:
        camera.fetch_stream_credentials()
    assert camera.config.stream_key == "X" * 32
    assert camera.config.auth_code == "old-auth"
    assert KEY not in str(error.value) and AUTH not in str(error.value)


def test_rejected_cloud_query_reports_error_without_returning_credentials(
    cloud,
):
    _, reply = cloud
    reply["result"] = 1012
    with pytest.raises(QuiiConnectionError, match="1012"):
        Camera(cloud_config()).fetch_stream_credentials()


def test_save_load_only_minimal_fields_and_preserve_old_file_on_replace_error(
    tmp_path, monkeypatch
):
    saved = credentials()
    path = saved.save(tmp_path / "private" / "stream_credentials.json")
    contents = path.read_bytes()
    assert json.loads(contents) == {
        "version": 1,
        "device_id": saved.device_id,
        "stream_key": KEY,
        "auth_code": AUTH,
    }
    assert CameraStreamCredentials.load(path) == saved
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    monkeypatch.setattr(
        "quii_helper.camera.connection.credentials.os.replace",
        Mock(side_effect=PermissionError("synthetic publication failure")),
    )
    with pytest.raises(PermissionError):
        CameraStreamCredentials(saved.device_id, "N" * 32, AUTH).save(path)
    assert path.read_bytes() == contents
    assert list(path.parent.iterdir()) == [path]


def test_save_replaces_existing_key_and_tightens_unix_permissions(tmp_path):
    path = tmp_path / "stream_credentials.json"
    path.write_text("old-key")
    if os.name == "posix":
        path.chmod(0o644)
    credentials().save(path)
    assert CameraStreamCredentials.load(path) == credentials()
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_write_error_preserves_previous_file_and_removes_temporary(
    tmp_path, monkeypatch
):
    path = credentials().save(tmp_path / "stream_credentials.json")
    previous = path.read_bytes()
    monkeypatch.setattr(
        "quii_helper.camera.connection.credentials.os.fsync",
        Mock(side_effect=OSError("synthetic write failure")),
    )
    with pytest.raises(OSError):
        credentials().save(path)
    assert path.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "data",
    [
        b"{broken",
        b"\xff",
        b"[]",
        b"null",
        b"x" * 4097,
        b"[" * 1500 + b"]" * 1500,
    ],
)
def test_load_rejects_invalid_or_oversized_json_without_echoing_it(
    tmp_path, data
):
    path = tmp_path / "bad.json"
    path.write_bytes(data)
    with pytest.raises(ConfigurationError):
        CameraStreamCredentials.load(path)


@pytest.mark.parametrize(
    "update",
    [
        {"version": 2},
        {"version": True},
        {"version": 1.0},
        {"cloud_password": "forbidden-extra"},
        {"stream_key": None},
        {"stream_key": []},
        {"stream_key": "\ud800" * 32},
        {"stream_key": "short"},
        {"auth_code": ""},
        {"auth_code": 123},
        {"auth_code": "\ud800"},
        {"auth_code": "A" * 64 + "&"},
        {"device_id": ""},
        {"device_id": None},
    ],
)
def test_load_validates_schema_and_values_without_disclosing_secrets(
    tmp_path, update
):
    values = {
        "version": 1,
        "device_id": "device",
        "stream_key": KEY,
        "auth_code": AUTH,
    }
    values.update(update)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ConfigurationError) as error:
        CameraStreamCredentials.load(path)
    assert KEY not in str(error.value) and AUTH not in str(error.value)


def test_save_rejects_oversized_credentials_before_creating_directories(
    tmp_path,
):
    target = tmp_path / "missing" / "stream_credentials.json"
    with pytest.raises(ConfigurationError, match="size limit"):
        CameraStreamCredentials("D" * 4096, KEY, AUTH).save(target)
    assert not target.parent.exists()


def test_load_missing_file_is_not_a_cloud_refresh(tmp_path):
    with pytest.raises(FileNotFoundError):
        CameraStreamCredentials.load(tmp_path / "missing.json")


@pytest.mark.parametrize("interrupted", [False, True])
def test_bootstrap_example_saves_before_lan_rtsp_without_opening_door(
    tmp_path, monkeypatch, capsys, interrupted
):
    module = importlib.import_module("examples.cloud_key_rtsp")
    cloud_camera, lan_camera = Mock(), Mock()
    cloud_camera.data_dir = tmp_path
    secret = credentials()
    cloud_camera.fetch_stream_credentials.return_value = secret
    camera_cls = Mock(side_effect=[cloud_camera, lan_camera])
    monkeypatch.setattr(module, "Camera", camera_cls)
    monkeypatch.setattr(module, "load_config", lambda: config)
    monkeypatch.setattr(module, "configure_logging", Mock())
    config = AutonomousConfig(device_host="127.0.0.1")
    context = lan_camera.serve_rtsp.return_value
    context.__enter__ = Mock()
    context.__exit__ = Mock()
    if interrupted:
        context.__enter__.return_value.wait.side_effect = KeyboardInterrupt

    def serve(**kwargs):
        assert (
            CameraStreamCredentials.load(tmp_path / "stream_credentials.json")
            == secret
        )
        assert cloud_camera.fetch_stream_credentials.call_count == 1
        return context

    lan_camera.serve_rtsp.side_effect = serve
    module.main()
    assert camera_cls.call_args_list[0].kwargs["connection_mode"] == "cloud"
    assert camera_cls.call_args_list[1].kwargs["connection_mode"] == "lan"
    assert camera_cls.call_args_list[1].kwargs["device_id"] == secret.device_id
    assert camera_cls.call_args_list[1].kwargs["stream_key"] == KEY
    context.__enter__.return_value.wait.assert_called_once_with()
    context.__exit__.assert_called_once()
    cloud_camera.open_door.assert_not_called()
    lan_camera.open_door.assert_not_called()
    lan_camera.fetch_stream_credentials.assert_not_called()
    output = capsys.readouterr().out
    assert KEY not in output and AUTH not in output


@pytest.mark.parametrize("stage", ["cloud", "save"])
def test_bootstrap_failure_never_starts_lan_or_reuses_an_old_key(
    tmp_path, monkeypatch, stage
):
    module = importlib.import_module("examples.cloud_key_rtsp")
    original = credentials().save(tmp_path / "stream_credentials.json")
    previous = original.read_bytes()
    cloud_camera = Mock()
    cloud_camera.data_dir = tmp_path
    error = OSError("synthetic bootstrap failure")
    if stage == "cloud":
        cloud_camera.fetch_stream_credentials.side_effect = error
    else:
        cloud_camera.fetch_stream_credentials.return_value.save.side_effect = (
            error
        )
    camera_cls = Mock(return_value=cloud_camera)
    monkeypatch.setattr(module, "Camera", camera_cls)
    monkeypatch.setattr(module, "load_config", lambda: AutonomousConfig())
    monkeypatch.setattr(module, "configure_logging", Mock())
    with pytest.raises(OSError) as caught:
        module.main()
    assert caught.value is error
    assert camera_cls.call_count == 1
    cloud_camera.serve_rtsp.assert_not_called()
    cloud_camera.open_door.assert_not_called()
    assert original.read_bytes() == previous


@pytest.mark.parametrize("outcome", ["normal", "interrupt", "failure"])
def test_saved_key_example_forces_lan_without_bootstrap_or_door(
    tmp_path, monkeypatch, capsys, outcome
):
    module = importlib.import_module("examples.lan_rtsp")
    monkeypatch.chdir(tmp_path)
    saved = credentials()
    saved.save(tmp_path / "data" / "stream_credentials.json")
    config = cloud_config(device_host="127.0.0.1", channel=3, stream=1)
    monkeypatch.setattr(module, "load_config", lambda: config)
    monkeypatch.setattr(module, "configure_logging", Mock())
    camera_cls = MagicMock(spec=Camera)
    monkeypatch.setattr(module, "Camera", camera_cls)
    camera = camera_cls.return_value
    context = camera.serve_rtsp.return_value
    stream = context.__enter__.return_value
    if outcome == "interrupt":
        stream.wait.side_effect = KeyboardInterrupt
    elif outcome == "failure":
        error = QuiiConnectionError("synthetic receive failure")
        stream.wait.side_effect = error
    if outcome == "failure":
        with pytest.raises(QuiiConnectionError) as caught:
            module.main()
        assert caught.value is error
    else:
        module.main()

    camera_cls.assert_called_once_with(
        config=config,
        connection_mode="lan",
        device_id=saved.device_id,
        stream_key=saved.stream_key,
        auth_code=saved.auth_code,
    )
    assert config.connection_mode == "cloud"
    camera.serve_rtsp.assert_called_once_with(port=8554)
    stream.wait.assert_called_once_with()
    context.__exit__.assert_called_once()
    camera.fetch_stream_credentials.assert_not_called()
    camera.get_device_info.assert_not_called()
    camera.open_door.assert_not_called()
    assert (
        CameraStreamCredentials.load("data/stream_credentials.json") == saved
    )
    output = capsys.readouterr().out
    assert KEY not in output and AUTH not in output


@pytest.mark.parametrize("cache_state", ["missing", "invalid"])
def test_saved_key_example_never_bootstraps_when_cache_cannot_be_loaded(
    tmp_path, monkeypatch, cache_state
):
    module = importlib.import_module("examples.lan_rtsp")
    monkeypatch.chdir(tmp_path)
    if cache_state == "invalid":
        path = tmp_path / "data" / "stream_credentials.json"
        path.parent.mkdir()
        path.write_text("{}", encoding="utf-8")
    camera_cls = Mock(side_effect=AssertionError("camera must not start"))
    monkeypatch.setattr(module, "Camera", camera_cls)
    monkeypatch.setattr(module, "load_config", cloud_config)
    monkeypatch.setattr(module, "configure_logging", Mock())
    expected = (
        FileNotFoundError if cache_state == "missing" else ConfigurationError
    )
    with pytest.raises(expected):
        module.main()
    camera_cls.assert_not_called()
