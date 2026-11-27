"""Exercise installed archive listing with fake devices and no network I/O."""

import json
import os
import shlex
import ssl
import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from quii_helper import (
    Camera,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    CameraStreamCredentials,
    cli,
)
from quii_helper.camera import api
from quii_helper.cli import archive
from quii_helper.device.http import transport

HOST = "192.0.2.10"
AUTH = "synthetic-private-auth"
KEY = "K" * 32
ARGS = [
    "archive",
    "list",
    "--from",
    "2026-11-27 00:00:00",
    "--to",
    "2026-11-27 23:59:59",
]


def record(name="one", **kwargs):
    return CameraDeviceRecordFileInfo(
        file_name=name,
        file_type="video",
        channel_id="1",
        start_time="2026-11-27t12:00:00z",
        **kwargs,
    )


def page(*records, **kwargs):
    return CameraDeviceRecordListInfo(
        error=0, completed=True, records=list(records), **kwargs
    )


def forbidden(*args, **kwargs):
    raise AssertionError(
        "archive CLI attempted real network or unrelated operations"
    )


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setenv("CAMERA_DEVICE_HOST", HOST)
    monkeypatch.setenv("AUTH_CODE", AUTH)
    guards = []
    for name in (
        "socket.getaddrinfo",
        "socket.create_connection",
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "socket.socket.sendto",
        "subprocess.Popen",
        "quii_helper.Camera.fetch_stream_credentials",
        "quii_helper.Camera.get_device_info",
        "quii_helper.Camera.open_door",
        "quii_helper.Camera.serve_rtsp",
        "quii_helper.Camera.download_record",
        "quii_helper.Camera.watch_archive_events",
        "quii_helper.cloud.services.discovery.query_service_addresses",
    ):
        guard = Mock(side_effect=forbidden)
        monkeypatch.setattr(name, guard)
        guards.append(guard)
    yield
    for guard in guards:
        guard.assert_not_called()


@pytest.fixture
def read():
    with patch.object(
        Camera, "list_record_files", autospec=True, return_value=page()
    ) as mock:
        yield mock


@pytest.mark.parametrize(
    "args", [["--help"], ["archive", "--help"], ["archive", "list", "--help"]]
)
def test_help_is_offline_and_does_not_read_settings_or_credentials(
    args, monkeypatch, capsys
):
    monkeypatch.setattr(cli.SettingsLoader, "load", forbidden)
    monkeypatch.setattr(CameraStreamCredentials, "load", forbidden)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 0
    assert "archive" in capsys.readouterr().out
    assert not list(Path.cwd().iterdir())


@pytest.mark.parametrize(
    "args",
    [
        ["archive"],
        ["archive", "list"],
        ARGS + ["--channel", "0"],
        ARGS + ["--channel", "65536"],
        ARGS + ["--max-pages", "0"],
        ARGS + ["--cgi-port", "65536"],
        ARGS + ["--type", "photo"],
        ARGS + ["--occur-type", ""],
        ARGS + ["--occur-type", "event\n"],
        ARGS + ["--scheme", "ftp"],
        ARGS + ["--from", "2026-02-30 00:00:00"],
        ARGS + ["--from", "2026-1-27 00:00:00"],
        ARGS + ["--from", "2026-11-27T00:00:00Z"],
        ARGS + ["--to", "2026-11-27 00:00:00"],
        ARGS + ["--to", "2026-11-26 00:00:00"],
    ],
)
def test_bad_arguments_stop_before_settings_or_io(args, monkeypatch):
    monkeypatch.setattr(cli.SettingsLoader, "load", forbidden)
    with pytest.raises(SystemExit) as exc:
        cli.main(args)
    assert exc.value.code == 2
    assert not list(Path.cwd().iterdir())


def test_lists_without_stream_key_cloud_or_assets_and_preserves_config(
    read, capsys
):
    read.return_value = page(record(file_size=123, occur_type="manual"))
    before = dict(os.environ)
    assert cli.main(ARGS + ["--type", "video"]) == 0
    read.assert_called_once()
    camera = read.call_args.args[0]
    assert camera.config.connection_mode == "lan"
    assert camera.config.auth_code == AUTH
    assert not camera.config.stream_key and not camera.config.cloud_account
    assert read.call_args.kwargs == {
        "start_time": "2026-11-27t00:00:00z",
        "end_time": "2026-11-27t23:59:59z",
        "channel_id": 1,
        "file_type": "video",
        "occur_type": "all",
        "stream": "all",
        "max_pages": 32,
        "scheme": "http",
        "port": 80,
        "debug": False,
    }
    captured = capsys.readouterr()
    assert "SIZE_KiB" in captured.out and "manual" in captured.out
    assert "123" in captured.out and "Records: 1" in captured.out
    assert "without TLS" in captured.err
    assert HOST not in captured.out + captured.err
    assert AUTH not in captured.out + captured.err
    assert dict(os.environ) == before and not list(Path.cwd().iterdir())


def test_all_delegates_once_and_preserves_deduplication_and_indices(
    read, capsys
):
    video = record("a", file_size=42)
    photo = replace(video, file_type="picture", picture_index="0007")
    read.return_value = page(video, video, photo, photo)
    assert cli.main(ARGS + ["--json"]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert [call.kwargs["file_type"] for call in read.call_args_list] == [
        "all",
    ]
    assert [r["file_type"] for r in result["records"]] == ["video", "picture"]
    assert result["records"][1]["picture_index"] == "0007"
    assert result["records"][0]["file_size_kib"] == 42
    assert result["version"] == 1
    assert result["device"] == {"host": HOST, "device_id": ""}
    assert result["query"]["start_time"] == "2026-11-27 00:00:00"


@pytest.mark.parametrize("position", [0, 1])
@pytest.mark.parametrize("status", ["error", "incomplete", "exception"])
def test_either_search_failure_never_emits_or_saves_partial_success(
    monkeypatch, capsys, position, status
):
    responses = [page(record("video")), page(record("picture"))]
    responses[position] = {
        "error": CameraDeviceRecordListInfo(error=-8, completed=True),
        "incomplete": CameraDeviceRecordListInfo(error=0, completed=False),
        "exception": OSError("synthetic-private-error"),
    }[status]
    read = Mock(side_effect=responses)
    monkeypatch.setattr(api, "fetch_record_list_info", read)
    assert cli.main(ARGS + ["--json", "--output", "lists/records.json"]) == 1
    captured = capsys.readouterr()
    assert not captured.out and "synthetic-private" not in captured.err
    assert not Path("lists").exists()
    assert read.call_count == position + 1


def test_export_whitelists_metadata_and_does_not_serialize_secrets_raw_or_url(
    read, capsys
):
    read.return_value = page(
        record(
            "native-file",
            record_id="native-id",
            picture_index="0012",
            frame_rate=20,
            url="https://private.example/?password=private-token",
            raw={
                "password": "private-token",
                "xml": "private-xml",
                "auth": AUTH,
            },
        )
    )
    read.return_value.searches["video"] = page(
        record(
            "private-subquery",
            url="https://private.example/?auth=private-token",
        )
    )
    assert (
        cli.main(
            ARGS
            + ["--type", "video", "--json", "--output", "lists/records.json"]
        )
        == 0
    )
    captured = capsys.readouterr()
    data = Path("lists/records.json").read_bytes()
    assert json.loads(data) == json.loads(captured.out)
    assert data.endswith(b"\n")
    assert set(json.loads(data)["records"][0]) == set(
        archive.ArchiveRecord.__annotations__
    )
    for value in [
        AUTH,
        KEY,
        "private-token",
        "private-xml",
        "private.example",
    ]:
        assert value not in data.decode() + captured.out + captured.err
    assert "saved" in captured.err
    assert [p.name for p in Path("lists").iterdir()] == ["records.json"]
    if os.name != "nt":
        assert Path("lists/records.json").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    "name", ["records.json", ".env", ".env.local.json", "records.txt"]
)
def test_bad_or_existing_output_stops_before_settings_and_reads(
    read, monkeypatch, capsys, name
):
    Path(name).write_bytes(b"existing-private-file")
    monkeypatch.setattr(cli.SettingsLoader, "load", forbidden)
    assert cli.main(ARGS + ["--output", name]) == 1
    read.assert_not_called()
    assert Path(name).read_bytes() == b"existing-private-file"
    assert not capsys.readouterr().out


@pytest.mark.parametrize("name", [".env.json", "records.txt", "folder.json"])
def test_invalid_missing_output_or_directory_stops_before_reads(read, name):
    if name == "folder.json":
        Path(name).mkdir()
    assert cli.main(ARGS + ["--output", name]) == 1
    read.assert_not_called()


@pytest.mark.skipif(os.name != "nt", reason="Windows filename semantics")
@pytest.mark.parametrize(
    "name",
    [
        ".env.json ",
        "records.json.",
        "other:stream.json",
        "CON.json",
        "NUL.json",
    ],
)
def test_windows_output_aliases_and_devices_are_rejected_before_reads(
    read, name
):
    assert cli.main(ARGS + ["--output", name]) == 1
    read.assert_not_called()


@pytest.mark.parametrize("character", [*'<>:"|?*', "\x00", "\x1f"])
@pytest.mark.parametrize("location", ["filename", "parent"])
def test_windows_invalid_output_components_stop_before_settings_and_reads(
    read, monkeypatch, capsys, character, location
):
    monkeypatch.setattr(
        archive, "sys", SimpleNamespace(platform="win32", stderr=sys.stderr)
    )
    load = Mock(side_effect=forbidden)
    monkeypatch.setattr(cli.SettingsLoader, "load", load)
    name = (
        f"records{character}.json"
        if location == "filename"
        else f"folder{character}/records.json"
    )
    assert cli.main(ARGS + ["--output", name]) == 1
    load.assert_not_called()
    read.assert_not_called()
    captured = capsys.readouterr()
    assert not captured.out and "Output" in captured.err
    assert not list(Path.cwd().iterdir())


@pytest.mark.parametrize(
    "name",
    [
        "folder./records.json",
        "folder /records.json",
        "NUL/records.json",
        "COM1.json/records.json",
        "CONIN$.json",
        "CONOUT$/records.json",
        "COM\xb9.json",
        "LPT\xb2/records.json",
        "CON .json",
    ],
)
def test_windows_unsafe_output_parts_stop_before_settings_and_reads(
    read, monkeypatch, name
):
    monkeypatch.setattr(
        archive, "sys", SimpleNamespace(platform="win32", stderr=sys.stderr)
    )
    load = Mock(side_effect=forbidden)
    monkeypatch.setattr(cli.SettingsLoader, "load", load)
    assert cli.main(ARGS + ["--output", name]) == 1
    load.assert_not_called()
    read.assert_not_called()
    assert not list(Path.cwd().iterdir())


@pytest.mark.parametrize("name", ["record 1.2.json", "nested/../records.json"])
def test_windows_valid_output_preserves_absolute_and_parent_relative_paths(
    read, monkeypatch, name
):
    monkeypatch.setattr(
        archive, "sys", SimpleNamespace(platform="win32", stderr=sys.stderr)
    )
    Path("nested").mkdir()
    for target in (Path(name), Path("absolute.json").absolute()):
        assert cli.main(ARGS + ["--output", str(target)]) == 0
        assert json.loads(target.read_text())["records"] == []


def test_racing_output_is_not_replaced_and_temporary_is_removed(
    read, monkeypatch, capsys
):
    def competing_writer(source, target):
        Path(target).write_bytes(b"other-writer")
        raise FileExistsError("private-output-path")

    monkeypatch.setattr(archive.os, "link", competing_writer)
    assert cli.main(ARGS + ["--output", "records.json", "--json"]) == 1
    assert Path("records.json").read_bytes() == b"other-writer"
    captured = capsys.readouterr()
    assert not captured.out and "private-output-path" not in captured.err
    assert [p.name for p in Path.cwd().iterdir()] == ["records.json"]


def test_link_failure_fails_safely_without_an_unsafe_fallback(
    read, monkeypatch
):
    monkeypatch.setattr(
        archive.os, "link", Mock(side_effect=OSError("unsupported"))
    )
    assert cli.main(ARGS + ["--output", "records.json"]) == 1
    assert not list(Path.cwd().iterdir())


@pytest.mark.parametrize("name", ["CAMERA_DEVICE_HOST", "AUTH_CODE"])
def test_missing_cgi_input_names_the_field_without_reading(
    read, monkeypatch, capsys, name
):
    monkeypatch.delenv(name)
    assert cli.main(ARGS) == 1
    read.assert_not_called()
    assert name in capsys.readouterr().err


@pytest.mark.parametrize(
    "host",
    [
        "https://private.example",
        "private.example:443",
        "private@example.com",
        "host/path",
        "bad host",
        "host?secret",
        "[::1",
    ],
)
def test_bad_host_is_rejected_without_printing_its_value(
    read, monkeypatch, capsys, host
):
    monkeypatch.setenv("CAMERA_DEVICE_HOST", host)
    assert cli.main(ARGS) == 1
    read.assert_not_called()
    assert host not in capsys.readouterr().err


def test_cloud_mode_is_rejected_before_queries(read, monkeypatch, capsys):
    monkeypatch.setenv("CAMERA_CONNECTION_MODE", "cloud")
    assert cli.main(ARGS) == 1
    read.assert_not_called()
    assert "CAMERA_CONNECTION_MODE" in capsys.readouterr().err


def test_saved_json_is_read_only_when_explicit_and_does_not_require_env_auth(
    read, monkeypatch
):
    path = CameraStreamCredentials("test-device", KEY, AUTH).save(
        "credentials.json"
    )
    monkeypatch.delenv("AUTH_CODE")
    assert cli.main(ARGS) == 1
    read.assert_not_called()
    assert cli.main(ARGS + ["--credentials", str(path)]) == 0
    assert read.call_args.args[0].config.device_id == "test-device"
    assert read.call_args.args[0].config.auth_code == AUTH
    assert not read.call_args.args[0].config.stream_key


def test_mismatching_device_id_and_saved_json_stop_before_reads(
    read, monkeypatch, capsys
):
    path = CameraStreamCredentials("test-device", KEY, AUTH).save(
        "credentials.json"
    )
    monkeypatch.setenv("DEVICE_ID", "other-private-device")
    assert cli.main(ARGS + ["--credentials", str(path)]) == 1
    read.assert_not_called()
    assert "other-private-device" not in capsys.readouterr().err


@pytest.mark.parametrize(
    "failure",
    [
        KeyboardInterrupt(),
        ssl.SSLCertVerificationError("private-certificate"),
        OSError("private-host"),
    ],
)
def test_interrupt_and_tls_failure_do_not_retry_or_fall_back(
    read, failure, capsys
):
    read.side_effect = failure
    assert cli.main(ARGS + ["--scheme", "https", "--json"]) == (
        130 if isinstance(failure, KeyboardInterrupt) else 1
    )
    read.assert_called_once()
    assert read.call_args.kwargs["port"] == 443
    captured = capsys.readouterr()
    assert not captured.out and "private-" not in captured.err


def test_explicit_https_port_and_filters_are_forwarded(
    read, monkeypatch, capsys
):
    monkeypatch.setenv("TLS_VERIFY", "false")
    assert (
        cli.main(
            ARGS
            + [
                "--scheme",
                "https",
                "--cgi-port",
                "8443",
                "--type",
                "picture",
                "--channel",
                "2",
                "--occur-type",
                "manual",
                "--stream",
                "sub",
                "--max-pages",
                "5",
            ]
        )
        == 0
    )
    assert read.call_args.kwargs["port"] == 8443
    assert read.call_args.kwargs["channel_id"] == 2
    assert read.call_args.kwargs["occur_type"] == "manual"
    assert read.call_args.kwargs["stream"] == "sub"
    assert read.call_args.kwargs["max_pages"] == 5
    assert read.call_args.args[0].config.tls_verify is False
    assert "verification is disabled" in capsys.readouterr().err


def test_controls_in_device_metadata_cannot_inject_terminal_lines(
    read, capsys
):
    read.return_value = page(record("a\n\x1b[31m\tname"))
    assert cli.main(ARGS + ["--type", "video"]) == 0
    captured = capsys.readouterr()
    assert "\\n\\u001b[31m\\tname" in captured.out
    assert "\x1b" not in captured.out
    assert len(captured.out.splitlines()) == 3


def test_record_limit_never_emits_or_saves_partial_results(
    read, monkeypatch, capsys
):
    monkeypatch.setattr(archive, "MAX_RECORDS", 1)
    read.return_value = page(record("one"), record("two"))
    assert cli.main(ARGS + ["--output", "records.json"]) == 1
    assert not Path("records.json").exists()
    assert not capsys.readouterr().out


def test_empty_complete_list_is_valid_json(read, capsys):
    assert cli.main(ARGS + ["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["records"] == []


@pytest.mark.parametrize(
    "setting", ["CAMERA_CHANNEL", "VIDEO_PANEL", "QUII_CHANNEL"]
)
@pytest.mark.parametrize("override", [None, "3"])
def test_channel_respects_config_and_explicit_override(
    read, monkeypatch, capsys, setting, override
):
    monkeypatch.setenv(setting, "2")
    args = ARGS + ["--type", "video", "--json"]
    if override is not None:
        args += ["--channel", override]
    assert cli.main(args) == 0
    expected = int(override or "2")
    assert read.call_args.kwargs["channel_id"] == expected
    assert (
        json.loads(capsys.readouterr().out)["query"]["channel_id"] == expected
    )


def test_firmware_specific_occurrence_is_forwarded_without_call_inference(
    read,
):
    assert (
        cli.main(ARGS + ["--type", "video", "--occur-type", "alarm-input"])
        == 0
    )
    assert read.call_args.kwargs["occur_type"] == "alarm-input"


@pytest.mark.parametrize("channel", ["0", "-1", "65536"])
def test_invalid_configured_channel_stops_before_queries_but_flag_can_override(
    read, monkeypatch, capsys, channel
):
    monkeypatch.setenv("CAMERA_CHANNEL", channel)
    assert cli.main(ARGS) == 1
    read.assert_not_called()
    assert "CAMERA_CHANNEL" in capsys.readouterr().err
    assert cli.main(ARGS + ["--channel", "2"]) == 0
    assert read.call_args.kwargs["channel_id"] == 2


@pytest.mark.parametrize("reply_page", [0, 1])
@pytest.mark.parametrize("end", ["2026-11-27 23:59:59", "2026-11-28 00:00:00"])
def test_cli_builds_real_cgi_xml_and_parses_nested_archive_metadata(
    monkeypatch, capsys, reply_page, end
):
    searches = []
    commands = []

    def respond(request, **kwargs):
        assert request.full_url == f"http://{HOST}:80/tdkcgi"
        root = ET.fromstring(request.data)
        command = root.findtext("./body/command")
        commands.append(command)
        assert root.findtext("./header/username") == "adminapp2"
        assert root.findtext("./header/passwordencode") == "1"
        if command == "get.record.session":
            search = root.find("./body/content/record")
            assert search is not None
            searches.append({item.tag: item.text for item in search})
            content = f"<record><id>search-{len(searches)}</id></record>"
        else:
            assert command == "get.record.message"
            assert (
                root.findtext("./body/content/record/id")
                == f"search-{len(searches)}"
            )
            content = (
                f"<record><page>{reply_page}</page><datalist><data>"
                f"<filename>native-{len(searches)}</filename>"
                f"<filetype>{searches[-1]['filetype']}</filetype>"
                "<starttime>2026-11-27t12:00:00z</starttime><filesize>42</filesize>"
                "<address><idx>0007</idx><idc>2</idc><ids>2</ids><idf>15</idf></address>"
                "<url>https://private.example/?auth=private-token</url>"
                "</data></datalist></record>"
            )
        return BytesIO(
            (
                "<envelope><body><error>0</error><content>"
                + content
                + "</content></body></envelope>"
            ).encode()
        )

    network = Mock(side_effect=respond)
    monkeypatch.setattr(transport.urllib.request, "urlopen", network)
    args = ARGS + [
        "--json",
        "--channel",
        "2",
        "--max-pages",
        "1",
        "--stream",
        "sub",
        "--occur-type",
        "manual",
        "--output",
        "records.json",
    ]
    args[args.index("--to") + 1] = end
    assert cli.main(args) == (0 if reply_page == 0 else 1)
    captured = capsys.readouterr()
    assert searches == [
        {
            "filetype": file_type,
            "occurtype": "manual",
            "channel": "2",
            "starttime": "2026-11-27t00:00:00z",
            "endtime": end[:10] + "t23:59:59z",
            "stream": "sub",
        }
        for file_type in (
            ("video", "picture") if reply_page == 0 else ("video",)
        )
    ]
    assert commands == ["get.record.session", "get.record.message"] * len(
        searches
    )
    if reply_page == 0:
        result = json.loads(captured.out)
        assert result["query"]["end_time"] == end
        assert len(result["records"]) == 2
        for row in result["records"]:
            assert row["picture_index"] == "0007"
            assert row["channel_id"] == "2" and row["stream"] == "sub"
            assert row["frame_rate"] == 15 and row["file_size_kib"] == 42
        assert json.loads(Path("records.json").read_text()) == result
    else:
        assert not captured.out and not Path("records.json").exists()
    assert "private-token" not in captured.out + captured.err


@pytest.mark.parametrize("content", [None, "not json", "{}"])
def test_missing_or_malformed_credentials_fail_without_queries(
    read, capsys, content
):
    if content is not None:
        Path("credentials.json").write_text(content, encoding="utf-8")
    assert cli.main(ARGS + ["--credentials", "credentials.json"]) == 1
    read.assert_not_called()
    assert "Cannot read saved JSON" in capsys.readouterr().err


def test_full_env_validation_is_retained_without_exposing_values(read, capsys):
    Path(".env").write_text(
        "CAMERA_APP_ID=private-invalid-integer\n", encoding="utf-8"
    )
    assert cli.main(ARGS) == 1
    read.assert_not_called()
    captured = capsys.readouterr()
    assert "CAMERA_APP_ID" in captured.err
    assert "private-invalid-integer" not in captured.err


@pytest.mark.parametrize("dangling", [False, True])
def test_output_symlinks_are_rejected_before_reads(read, dangling):
    destination = Path("original.json")
    if not dangling:
        destination.write_bytes(b"original")
    target = Path("records.json")
    try:
        target.symlink_to(destination)
    except OSError:
        pytest.skip("symlinks require privileges on this Windows host")
    assert cli.main(ARGS + ["--output", str(target)]) == 1
    read.assert_not_called()
    assert target.is_symlink()
    assert (
        destination.read_bytes() == b"original"
        if not dangling
        else not destination.exists()
    )


def test_output_parent_file_is_rejected_before_reads(read):
    Path("parent").write_bytes(b"original")
    assert cli.main(ARGS + ["--output", "parent/records.json"]) == 1
    read.assert_not_called()
    assert Path("parent").read_bytes() == b"original"


def test_interrupt_while_saving_cleans_temporary_file(read, monkeypatch):
    monkeypatch.setattr(
        archive.os, "link", Mock(side_effect=KeyboardInterrupt)
    )
    assert cli.main(ARGS + ["--output", "records.json"]) == 130
    assert not list(Path.cwd().iterdir())


def test_documented_list_commands_work_with_only_local_cgi_settings(
    read, capsys
):
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/archive-cli.md").read_text(encoding="utf-8")
    commands = [
        line
        for line in text.splitlines()
        if line.startswith("quii-helper archive list ")
    ]
    assert len(commands) == 2
    for command in commands:
        assert cli.main(shlex.split(command)[1:]) == 0
    captured = capsys.readouterr()
    assert "Records: 0" in captured.out
    assert (
        json.loads(Path("records.json").read_text())["query"]["file_type"]
        == "video"
    )
    assert [call.kwargs["file_type"] for call in read.call_args_list] == [
        "video",
        "picture",
    ]
    assert "not included in PyPI" in text
    assert "[Archive CLI](archive-cli.md)" in (
        root / "docs/README.md"
    ).read_text(encoding="utf-8")
