"""Test the doctor command without network, subprocesses or real credentials."""

import json
import os
from pathlib import Path

import pytest

from quii_helper import cli

KEY = "K" * 32
AUTH = "synthetic-private-auth"
HOST = "192.0.2.10"
LAN_ENV = f"CAMERA_DEVICE_HOST={HOST}\nSTREAM_KEY={KEY}\nAUTH_CODE={AUTH}\n"


def unexpected_io(*args, **kwargs):
    raise AssertionError("doctor attempted a network or process operation")


@pytest.fixture(autouse=True)
def isolate_doctor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setattr(cli, "which", lambda name: None)
    monkeypatch.setattr(cli, "find_spec", lambda name: None)
    for target in (
        "socket.create_connection",
        "socket.getaddrinfo",
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "socket.socket.sendto",
        "subprocess.Popen",
    ):
        monkeypatch.setattr(target, unexpected_io)


@pytest.mark.parametrize("args", [["--help"], ["doctor", "--help"]])
def test_help_does_not_load_settings(args, monkeypatch, capsys):
    monkeypatch.setattr(cli.SettingsLoader, "load", unexpected_io)
    with pytest.raises(SystemExit) as caught:
        cli.main(args)
    assert caught.value.code == 0
    assert "doctor" in capsys.readouterr().out
    assert list(Path.cwd().iterdir()) == []


def test_doctor_reports_missing_configuration_without_creating_files(capsys):
    assert cli.main(["doctor"]) == 1
    assert "CAMERA_DEVICE_HOST (not set)" in capsys.readouterr().out
    assert list(Path.cwd().iterdir()) == []


def test_doctor_uses_existing_config_precedence_and_keeps_values_private(
    monkeypatch, capsys
):
    path = Path(".env")
    data = LAN_ENV.replace(HOST, "synthetic-private-invalid-host")
    path.write_text(data, encoding="utf-8")
    monkeypatch.setenv("CAMERA_DEVICE_HOST", HOST)
    environment = dict(os.environ)
    assert cli.main(["doctor"]) == 0
    captured = capsys.readouterr()
    assert "LAN configuration: OK (offline only)" in captured.out
    assert "FFmpeg: not found" in captured.out
    assert "miniaudio: module not found" in captured.out
    for value in (KEY, AUTH, HOST, "synthetic-private-invalid-host"):
        assert value not in captured.out + captured.err
    assert path.read_text(encoding="utf-8") == data
    assert os.environ == environment
    assert list(Path.cwd().iterdir()) == [path.resolve()]


@pytest.mark.parametrize(
    "setting, field, hint",
    [
        (
            "CAMERA_DEVICE_HOST=synthetic-private-value",
            "CAMERA_DEVICE_HOST",
            "numeric IP",
        ),
        (
            "QUII_STREAM=synthetic-private-value",
            "QUII_STREAM",
            "Use high, low",
        ),
        ("QUII_STREAM=257", "QUII_STREAM", "1 to 256"),
        ("CAMERA_STREAM_PORT=65536", "CAMERA_STREAM_PORT", "1 to 65535"),
        (
            "CAMERA_STREAM_PORT=synthetic-private-value",
            "CAMERA_STREAM_PORT",
            "Enter an integer",
        ),
        ("VIDEO_PANEL=65536", "VIDEO_PANEL", "1 to 65535"),
        (
            "QUII_CHANNEL=synthetic-private-value",
            "QUII_CHANNEL",
            "Enter an integer",
        ),
        (
            "CAMERA_CONNECTION_MODE=cloud",
            "CAMERA_CONNECTION_MODE",
            "Set it to lan",
        ),
        (
            "CAMERA_CONNECTION_MODE=synthetic-private-value",
            "CAMERA_CONNECTION_MODE",
            "Set it to lan",
        ),
        ("STREAM_KEY=synthetic-private-value", "STREAM_KEY", "32 UTF-8 bytes"),
        (
            "CLOUD_TLS_VERIFY=synthetic-private-value",
            "CLOUD_TLS_VERIFY",
            "Use true or false",
        ),
    ],
)
def test_invalid_lan_settings_fail_without_echoing_input(
    setting, field, hint, capsys
):
    Path(".env").write_text(LAN_ENV + setting + "\n", encoding="utf-8")
    assert cli.main(["doctor"]) == 1
    captured = capsys.readouterr()
    assert "LAN configuration: FAIL" in captured.out
    assert f"{field} (.env):" in captured.out
    assert hint in captured.out
    for value in (KEY, AUTH, HOST, "synthetic-private-value"):
        assert value not in captured.out + captured.err


def test_process_error_identifies_override_without_printing_either_value(
    monkeypatch, capsys
):
    Path(".env").write_text(LAN_ENV, encoding="utf-8")
    monkeypatch.setenv("CAMERA_DEVICE_HOST", "synthetic-private-invalid-host")
    assert cli.main(["doctor"]) == 1
    captured = capsys.readouterr()
    assert (
        "CAMERA_DEVICE_HOST (process environment; overrides .env"
        in captured.out
    )
    assert "numeric IP" in captured.out
    assert HOST not in captured.out + captured.err
    assert "synthetic-private-invalid-host" not in captured.out + captured.err


def test_empty_process_setting_identifies_why_file_value_is_ignored(
    monkeypatch, capsys
):
    Path(".env").write_text(LAN_ENV, encoding="utf-8")
    monkeypatch.setenv("AUTH_CODE", "")
    assert cli.main(["doctor"]) == 1
    captured = capsys.readouterr()
    assert "AUTH_CODE (process environment; overrides .env" in captured.out
    assert "--credentials FILE" in captured.out
    assert AUTH not in captured.out + captured.err


def test_saved_credentials_are_only_read_when_requested(capsys):
    Path(".env").write_text(
        f"CAMERA_DEVICE_HOST={HOST}\nSTREAM_KEY=invalid\n", encoding="utf-8"
    )
    path = cli.CameraStreamCredentials("synthetic-device", KEY, AUTH).save(
        "data/stream_credentials.json"
    )
    before = path.read_bytes()
    assert cli.main(["doctor"]) == 1
    assert "--credentials FILE" in capsys.readouterr().out
    assert cli.main(["doctor", "--credentials", str(path)]) == 0
    captured = capsys.readouterr()
    assert "LAN configuration: OK" in captured.out
    for value in (KEY, AUTH, str(path), "synthetic-device"):
        assert value not in captured.out + captured.err
    assert path.read_bytes() == before


@pytest.mark.parametrize("exists", [False, True])
def test_bad_saved_credentials_do_not_fall_back_to_env(exists, capsys):
    Path(".env").write_text(LAN_ENV, encoding="utf-8")
    path = Path("synthetic-private-path.json")
    if exists:
        path.write_text('{"stream_key": "synthetic-private-json"', "utf-8")
    assert cli.main(["doctor", "--credentials", str(path)]) == 1
    captured = capsys.readouterr()
    assert (
        "Invalid saved JSON" if exists else "Cannot open saved JSON"
    ) in captured.out
    assert "synthetic-private-" not in captured.out + captured.err


@pytest.mark.parametrize(
    "field, value, hint",
    [
        ("stream_key", "synthetic-private-key", "32 UTF-8 bytes"),
        (
            "auth_code",
            "synthetic-private-auth&invalid".ljust(64, "x"),
            "paired with the stream key",
        ),
    ],
)
def test_bad_saved_credential_field_names_json_source(
    field, value, hint, capsys
):
    Path(".env").write_text(LAN_ENV, encoding="utf-8")
    path = Path("synthetic-private-path.json")
    saved = {
        "version": 1,
        "device_id": "synthetic-private-device",
        "stream_key": KEY,
        "auth_code": AUTH,
    }
    saved[field] = value
    path.write_text(json.dumps(saved), encoding="utf-8")
    assert cli.main(["doctor", "--credentials", str(path)]) == 1
    captured = capsys.readouterr()
    assert f"{field} (saved JSON):" in captured.out
    assert hint in captured.out
    assert "synthetic-private-" not in captured.out + captured.err
    assert KEY not in captured.out + captured.err


def test_optional_dependencies_are_reported_without_paths(monkeypatch, capsys):
    Path(".env").write_text(LAN_ENV, encoding="utf-8")
    monkeypatch.setattr(cli, "which", lambda name: "synthetic-private-ffmpeg")
    monkeypatch.setattr(cli, "find_spec", lambda name: object())
    assert cli.main(["doctor"]) == 0
    captured = capsys.readouterr()
    assert "FFmpeg: found on PATH" in captured.out
    assert "miniaudio: module found" in captured.out
    assert "synthetic-private-ffmpeg" not in captured.out + captured.err
