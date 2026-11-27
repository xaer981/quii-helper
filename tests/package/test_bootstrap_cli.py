"""Bootstrap CLI checks with synthetic credentials and no real networking."""

import os
import ssl
import sys
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError

import pytest

from quii_helper import Camera, CameraStreamCredentials, cli
from tests.camera.test_stream_credentials import AUTH, KEY, cloud

CLOUD_ENV = {
    "CLOUD_ACCOUNT": "synthetic-private-account",
    "CLOUD_PASSWORD": "synthetic-private-password",
    "DEVICE_ID": "synthetic-device",
    "CLOUD_CLIENT_UUID": "synthetic-private-client",
    "CLOUD_AUTH_URL": "https://auth.example/UserAuth",
    "CLOUD_SERVICE_URL": "https://service.example",
    "CAMERA_OEM": "synthetic-private-oem",
    "CAMERA_APP_ID": "1",
    "CAMERA_CLIENT_TYPE": "2",
    "IP_REGION_ID": "3",
}


def forbidden(*args, **kwargs):
    raise AssertionError("bootstrap attempted preview, door or real I/O")


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {})
    for name, value in CLOUD_ENV.items():
        monkeypatch.setenv(name, value)
    for target in (
        "socket.getaddrinfo",
        "socket.create_connection",
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "socket.socket.sendto",
        "subprocess.Popen",
        "quii_helper.Camera.serve_rtsp",
        "quii_helper.Camera.open_door",
        "quii_helper.cloud.services.discovery.query_service_addresses",
    ):
        monkeypatch.setattr(target, forbidden)


@pytest.fixture
def fetch():
    saved = CameraStreamCredentials("synthetic-device", KEY, AUTH)
    with patch.object(
        Camera, "fetch_stream_credentials", autospec=True, return_value=saved
    ) as mocked:
        yield mocked


@pytest.mark.parametrize("args", [["--help"], ["bootstrap", "--help"]])
def test_help_does_not_load_settings_or_create_files(
    args, monkeypatch, capsys
):
    monkeypatch.setattr(cli.SettingsLoader, "load", forbidden)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 0
    assert "bootstrap" in capsys.readouterr().out
    assert list(Path.cwd().iterdir()) == []


@pytest.mark.parametrize("custom", [False, True])
@pytest.mark.parametrize("mode", ["lan", "cloud"])
def test_fetches_once_in_explicit_cloud_mode_without_lan_inputs(
    fetch, custom, mode, monkeypatch, capsys
):
    monkeypatch.setenv("CAMERA_CONNECTION_MODE", mode)
    monkeypatch.setenv("CAMERA_DEVICE_HOST", "synthetic-private-unused-host")
    monkeypatch.setenv("STREAM_KEY", "synthetic-private-unused-key")
    target = Path(
        "synthetic-private-output.json"
        if custom
        else "data/stream_credentials.json"
    )
    args = ["bootstrap", "--output", str(target)] if custom else ["bootstrap"]
    environment = dict(os.environ)
    assert cli.main(args) == 0
    fetch.assert_called_once()
    config = fetch.call_args.args[0].config
    assert config.connection_mode == "cloud"
    assert config.tls_verify is True
    assert CameraStreamCredentials.load(target) == fetch.return_value
    assert os.environ == environment
    captured = capsys.readouterr()
    assert "Streaming credentials saved" in captured.out
    assert not captured.err
    for value in (*CLOUD_ENV.values(), KEY, AUTH, str(target)):
        if value not in {"1", "2", "3"}:
            assert value not in captured.out + captured.err


def test_terminal_shows_copyable_unicode_path(fetch, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    target = Path("\u043a\u043b\u044e\u0447.json")
    assert cli.main(["bootstrap", "--output", str(target)]) == 0
    fetch.assert_called_once()
    assert f"File: {target.absolute().as_posix()}" in capsys.readouterr().out


@pytest.mark.parametrize("name", CLOUD_ENV)
def test_missing_cloud_setting_fails_before_fetch_or_output(
    name, fetch, monkeypatch, capsys
):
    monkeypatch.delenv(name)
    assert cli.main(["bootstrap"]) == 1
    assert f"{name} (not set)" in capsys.readouterr().err
    fetch.assert_not_called()
    assert not Path("data").exists()


@pytest.mark.parametrize(
    "name", ["CAMERA_APP_ID", "CAMERA_CLIENT_TYPE", "IP_REGION_ID"]
)
@pytest.mark.parametrize("value", ["0", "-1", "synthetic-private-invalid"])
def test_invalid_numeric_settings_are_private(
    name, value, fetch, monkeypatch, capsys
):
    monkeypatch.setenv(name, value)
    assert cli.main(["bootstrap"]) == 1
    captured = capsys.readouterr()
    assert name in captured.err
    assert "synthetic-private-" not in captured.out + captured.err
    fetch.assert_not_called()


@pytest.mark.parametrize(
    "primary,alias",
    [
        ("CLOUD_ACCOUNT", "CLOUD_USERNAME"),
        ("CAMERA_APP_ID", "CLOUD_APP_ID"),
        ("CAMERA_CLIENT_TYPE", "CLOUD_CLIENT_TYPE"),
        ("CAMERA_OEM", "CLOUD_OEM"),
    ],
)
def test_empty_process_override_names_alias_source_without_values(
    primary, alias, fetch, monkeypatch, capsys
):
    monkeypatch.delenv(primary)
    Path(".env").write_text(f"{alias}=synthetic-private-file-value\n", "utf-8")
    monkeypatch.setenv(
        alias,
        "0" if primary in {"CAMERA_APP_ID", "CAMERA_CLIENT_TYPE"} else " ",
    )
    assert cli.main(["bootstrap"]) == 1
    captured = capsys.readouterr()
    assert "process environment" in captured.err
    assert "synthetic-private-" not in captured.out + captured.err
    fetch.assert_not_called()


def test_existing_file_stops_before_settings_or_cloud(
    fetch, monkeypatch, capsys
):
    target = Path("private.json")
    target.write_bytes(b"existing-private-file")
    monkeypatch.setattr(cli.SettingsLoader, "load", forbidden)
    assert cli.main(["bootstrap", "--output", str(target)]) == 1
    assert target.read_bytes() == b"existing-private-file"
    assert "--overwrite" in capsys.readouterr().err
    fetch.assert_not_called()


def test_overwrite_is_explicit_and_does_not_change_env(fetch, capsys):
    target = Path("private.json")
    target.write_bytes(b"old-private-file")
    source = Path(".env")
    source.write_text("CAMERA_CONNECTION_MODE=lan\n", "utf-8")
    assert cli.main(["bootstrap", "--output", str(target), "--overwrite"]) == 0
    assert CameraStreamCredentials.load(target) == fetch.return_value
    assert source.read_text("utf-8") == "CAMERA_CONNECTION_MODE=lan\n"
    assert "old-private-file" not in capsys.readouterr().out


@pytest.mark.parametrize("name", [".env", ".env.local", ".ENV"])
def test_environment_file_cannot_be_the_output_even_with_overwrite(
    name, fetch, capsys
):
    target = Path(name)
    target.write_bytes(b"private-configuration")
    assert cli.main(["bootstrap", "--output", name, "--overwrite"]) == 1
    fetch.assert_not_called()
    assert target.read_bytes() == b"private-configuration"
    assert "configuration file" in capsys.readouterr().err


@pytest.mark.skipif(os.name != "nt", reason="Windows filename aliases")
@pytest.mark.parametrize(
    "name",
    [
        ".env ",
        ".ENV ",
        ".env .",
        ".env. ",
        ".env::$DATA",
        ".ENV::$DATA",
        ".env:stream",
        ".env :stream",
    ],
)
@pytest.mark.parametrize("exists", [False, True])
@pytest.mark.parametrize("overwrite", [False, True])
def test_windows_env_alias_is_rejected_before_settings_or_cloud(
    name, exists, overwrite, fetch, monkeypatch, capsys
):
    source = Path(".env")
    if exists:
        source.write_bytes(b"private-configuration")
    monkeypatch.setattr(cli.SettingsLoader, "load", forbidden)
    args = ["bootstrap", "--output", name] + (
        ["--overwrite"] if overwrite else []
    )
    assert cli.main(args) == 1
    fetch.assert_not_called()
    assert source.exists() is exists
    if exists:
        assert source.read_bytes() == b"private-configuration"
    assert list(Path.cwd().iterdir()) == (
        [source.absolute()] if exists else []
    )
    assert "configuration file" in capsys.readouterr().err


@pytest.mark.skipif(os.name == "nt", reason="Literal POSIX filenames")
@pytest.mark.parametrize("name", [".env ", ".env:notes.json"])
def test_posix_literal_filename_is_not_a_windows_env_alias(name, fetch):
    source = Path(".env")
    source.write_bytes(b"private-configuration")
    assert cli.main(["bootstrap", "--output", name]) == 0
    fetch.assert_called_once()
    assert CameraStreamCredentials.load(name) == fetch.return_value
    assert source.read_bytes() == b"private-configuration"


@pytest.mark.parametrize(
    "primary,alias",
    [
        ("CLOUD_ACCOUNT", "CLOUD_USERNAME"),
        ("CAMERA_OEM", "CLOUD_OEM"),
        ("CAMERA_APP_ID", "CLOUD_APP_ID"),
        ("CAMERA_CLIENT_TYPE", "CLOUD_CLIENT_TYPE"),
    ],
)
def test_existing_cloud_aliases_are_accepted(
    primary, alias, fetch, monkeypatch
):
    value = os.environ[primary]
    monkeypatch.delenv(primary)
    monkeypatch.setenv(alias, value)
    assert cli.main(["bootstrap"]) == 0
    fetch.assert_called_once()


def test_destination_created_during_fetch_is_not_overwritten(fetch, capsys):
    target = Path("race.json")

    def race(camera):
        target.write_bytes(b"racing-private-file")
        return fetch.return_value

    fetch.side_effect = race
    assert cli.main(["bootstrap", "--output", str(target)]) == 1
    assert target.read_bytes() == b"racing-private-file"
    assert list(Path.cwd().iterdir()) == [target.resolve()]
    assert "not replaced" in capsys.readouterr().err


@pytest.mark.parametrize("overwrite", [False, True])
@pytest.mark.parametrize(
    "failure",
    [
        URLError("synthetic-private-network"),
        RuntimeError("synthetic-private-response"),
        KeyboardInterrupt(),
    ],
)
def test_fetch_failure_keeps_previous_file_and_has_no_secret_traceback(
    overwrite, failure, fetch, capsys
):
    target = Path("private.json")
    if overwrite:
        target.write_bytes(b"old-private-file")
    fetch.side_effect = failure
    args = ["bootstrap", "--output", str(target)] + (
        ["--overwrite"] if overwrite else []
    )
    assert cli.main(args) == (
        130 if isinstance(failure, KeyboardInterrupt) else 1
    )
    assert (
        target.read_bytes() == b"old-private-file"
        if overwrite
        else not target.exists()
    )
    captured = capsys.readouterr()
    assert "synthetic-private-" not in captured.out + captured.err
    assert "Traceback" not in captured.err
    assert "Streaming credentials saved" not in captured.out


@pytest.mark.parametrize("wrapped", [False, True])
def test_tls_verification_failure_is_not_retried_insecurely(
    wrapped, fetch, capsys
):
    failure = ssl.SSLCertVerificationError(1, "synthetic-private-certificate")
    fetch.side_effect = URLError(failure) if wrapped else failure
    assert cli.main(["bootstrap"]) == 1
    fetch.assert_called_once()
    assert fetch.call_args.args[0].config.tls_verify is True
    captured = capsys.readouterr()
    assert "TLS certificate verification failed" in captured.err
    assert "synthetic-private-certificate" not in captured.err
    assert not Path("data/stream_credentials.json").exists()


def test_explicit_disabled_tls_is_honored_and_warns(
    fetch, monkeypatch, capsys
):
    monkeypatch.setenv("TLS_VERIFY", "false")
    assert cli.main(["bootstrap"]) == 0
    assert fetch.call_args.args[0].config.tls_verify is False
    assert (
        "TLS certificate verification is disabled" in capsys.readouterr().err
    )


@pytest.mark.parametrize("overwrite", [False, True])
def test_directory_target_fails_before_cloud(overwrite, fetch, capsys):
    Path("target").mkdir()
    args = ["bootstrap", "--output", "target"] + (
        ["--overwrite"] if overwrite else []
    )
    assert cli.main(args) == 1
    fetch.assert_not_called()
    assert "regular file" in capsys.readouterr().err


@pytest.mark.parametrize("dangling", [False, True])
@pytest.mark.parametrize("overwrite", [False, True])
def test_symlink_target_is_rejected_before_cloud(dangling, overwrite, fetch):
    source = Path("original.json")
    if not dangling:
        source.write_bytes(b"private-original")
    target = Path("symlink.json")
    try:
        target.symlink_to(source)
    except OSError:
        pytest.skip("symlink creation unavailable")
    args = ["bootstrap", "--output", str(target)] + (
        ["--overwrite"] if overwrite else []
    )
    assert cli.main(args) == 1
    fetch.assert_not_called()
    assert target.is_symlink()
    assert (
        not source.exists()
        if dangling
        else source.read_bytes() == b"private-original"
    )


def test_output_parent_failure_happens_before_cloud(fetch, capsys):
    Path("blocked").write_bytes(b"private-parent")
    assert cli.main(["bootstrap", "--output", "blocked/key.json"]) == 1
    fetch.assert_not_called()
    assert "private-parent" not in capsys.readouterr().err


def test_save_failure_keeps_old_file_and_cleans_temporary(
    fetch, monkeypatch, capsys
):
    target = Path("private.json")
    target.write_bytes(b"old-private-file")
    monkeypatch.setattr(
        "quii_helper.camera.connection.credentials.os.fsync",
        Mock(side_effect=OSError("synthetic-private-write")),
    )
    assert cli.main(["bootstrap", "--output", str(target), "--overwrite"]) == 1
    assert target.read_bytes() == b"old-private-file"
    assert list(Path.cwd().iterdir()) == [target.resolve()]
    captured = capsys.readouterr()
    assert "Cannot save streaming credentials" in captured.err
    assert "synthetic-private-write" not in captured.err


def test_bootstrap_uses_only_login_and_device_token(cloud, capsys):
    seen, _ = cloud
    assert cli.main(["bootstrap"]) == 0
    assert [command for command, *_ in seen] == ["login", "get-device-token"]
    assert all(verify_tls for _, _, verify_tls, _ in seen)
    assert (
        CameraStreamCredentials.load("data/stream_credentials.json").stream_key
        == KEY
    )
    before = len(seen)
    assert cli.main(["bootstrap"]) == 1
    assert len(seen) == before
    captured = capsys.readouterr()
    assert KEY not in captured.out + captured.err
    assert AUTH not in captured.out + captured.err
