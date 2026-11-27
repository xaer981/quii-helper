"""Test archive download selection and local output without real network I/O."""

import json
import os
import shlex
import ssl
import sys
from dataclasses import replace
from functools import partial
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import URLError
from urllib.request import OpenerDirector

import pytest

from quii_helper import (
    Camera,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    CameraStreamCredentials,
    MediaRenderError,
    QuiiConnectionError,
    cli,
)
from quii_helper.camera import api
from quii_helper.cli import archive, archive_download
from quii_helper.protocols.tcp.archive.download import download_record_bytes
from tests.protocols.tcp.test_archive_download import JPEG, cpacket, peer
from tests.protocols.tcp.test_lan_session import KEY, command, media

HOST = "192.0.2.10"
NAME = "1_2026-11-27-12-0-0_2026-11-27-12-0-1_0_0_0_0_1_0_0"
TIME = "2026-11-27t12:00:00z"
LIST = [
    "archive",
    "list",
    "--from",
    "2026-11-27 00:00:00",
    "--to",
    "2026-11-27 23:59:59",
    "--output",
    "records.json",
]
DOWNLOAD = [
    "archive",
    "download",
    "--from-list",
    "records.json",
    "--index",
    "2",
    "--output",
    "media/clip.mp4",
]
INTERACTIVE = ["archive", "download", "--date", "2026-11-27"]


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "environ", {})
    monkeypatch.setenv("CAMERA_DEVICE_HOST", HOST)
    monkeypatch.setenv("STREAM_KEY", "A" * 32)
    monkeypatch.setenv("AUTH_CODE", "synthetic-config-auth")
    guard = Mock(side_effect=AssertionError("unexpected external action"))
    for name in (
        "socket.getaddrinfo",
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "socket.socket.sendto",
        "quii_helper.Camera.fetch_stream_credentials",
        "quii_helper.Camera.open_door",
        "quii_helper.Camera.serve_rtsp",
    ):
        monkeypatch.setattr(name, guard)
    yield
    guard.assert_not_called()


@pytest.fixture
def entries():
    return [
        CameraDeviceRecordFileInfo(
            file_name=NAME,
            file_type="picture",
            start_time=TIME,
            picture_index="12",
            channel_id="1",
            url="http://private.invalid/file",
        ),
        CameraDeviceRecordFileInfo(
            file_name=NAME,
            file_type="video",
            start_time=TIME,
            frame_rate=15,
            channel_id="1",
            file_size=1024,
        ),
    ]


@pytest.fixture
def exported(entries):
    with patch.object(
        Camera,
        "list_record_files",
        autospec=True,
        return_value=CameraDeviceRecordListInfo(
            error=0,
            completed=True,
            records=entries,
        ),
    ) as listing:
        assert cli.main(LIST) == 0
        listing.assert_called_once()
    return Path("records.json")


def test_download_uses_saved_order_and_configured_tcp_not_cgi(
    exported, capsys
):
    command = DOWNLOAD + ["--timeout", "5.5", "--max-bytes", "4096"]
    with (
        patch.object(Camera, "list_record_files") as listing,
        patch.object(
            Camera, "download_record", autospec=True, return_value=b"mp4"
        ) as fetch,
    ):
        assert cli.main(command) == 0
    listing.assert_not_called()
    fetch.assert_called_once()
    camera, entry = fetch.call_args.args
    assert camera.config.device_host == HOST
    assert camera.config.stream_port == 34567
    assert camera.config.connection_mode == "lan"
    assert entry.file_type == "video" and entry.frame_rate == 15
    assert entry.file_name == NAME and entry.start_time == TIME
    assert not entry.url and not entry.raw and entry.file_size is None
    assert fetch.call_args.kwargs == {"timeout": 5.5, "max_bytes": 4096}
    target = Path("media/clip.mp4")
    assert target.read_bytes() == b"mp4"
    if os.name == "posix":
        assert target.stat().st_mode & 0o777 == 0o600
    stdout = capsys.readouterr().out
    assert "Archive download saved (3 bytes)" in stdout
    assert "synthetic-config-auth" not in stdout


def test_saved_picture_download_reaches_real_api_with_scripted_transport(
    exported, monkeypatch
):
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    monkeypatch.setenv("STREAM_KEY", KEY)
    monkeypatch.setattr(
        api,
        "download_record_bytes",
        partial(download_record_bytes, transport_factory=factory),
    )
    argv = DOWNLOAD[:-3] + ["1", "--output", "photo.jpg"]
    assert cli.main(argv) == 0
    factory.assert_called_once_with(HOST, 34567)
    assert sock.closed
    assert Path("photo.jpg").read_bytes() == JPEG


def test_invalid_native_selector_is_rejected_before_transport(
    exported, monkeypatch
):
    snapshot = json.loads(exported.read_text(encoding="utf-8"))
    snapshot["records"][0]["picture_index"] = ""
    exported.write_text(json.dumps(snapshot), encoding="utf-8")
    factory = Mock(side_effect=AssertionError("transport created"))
    monkeypatch.setattr(
        api,
        "download_record_bytes",
        partial(download_record_bytes, transport_factory=factory),
    )
    argv = DOWNLOAD[:-3] + ["1", "--output", "photo.jpg"]
    assert cli.main(argv) == 1
    factory.assert_not_called()
    assert not Path("photo.jpg").exists()


def test_picture_uses_native_index_and_explicit_saved_key_auth(
    exported, monkeypatch
):
    snapshot = json.loads(exported.read_text(encoding="utf-8"))
    snapshot["device"]["device_id"] = "test-device"
    snapshot["records"][0]["url"] = "http://private.invalid/ignored"
    exported.write_text(json.dumps(snapshot), encoding="utf-8")
    credentials = CameraStreamCredentials(
        "test-device", "B" * 32, "saved-auth"
    )
    credentials.save("saved.json")
    monkeypatch.delenv("STREAM_KEY")
    command = DOWNLOAD[:-3] + [
        "1",
        "--output",
        "photo.jpeg",
        "--credentials",
        "saved.json",
    ]
    with patch.object(
        Camera,
        "download_record",
        autospec=True,
        return_value=b"jpeg",
    ) as fetch:
        assert cli.main(command) == 0
    camera, entry = fetch.call_args.args
    assert camera.config.stream_key == "B" * 32
    assert camera.config.auth_code == "saved-auth"
    assert camera.config.device_id == "test-device"
    assert entry.picture_index == "12" and entry.file_type == "picture"
    assert entry.url == ""
    assert Path("photo.jpeg").read_bytes() == b"jpeg"


@pytest.mark.parametrize(
    "option,value",
    [
        ("--index", "0"),
        ("--max-bytes", "0"),
        ("--timeout", "nan"),
        ("--timeout", "inf"),
        ("--timeout", "-1"),
    ],
)
def test_invalid_limits_rejected_before_touching_files(option, value):
    with pytest.raises(SystemExit) as failure:
        cli.main(DOWNLOAD + [option, value])
    assert failure.value.code == 2
    assert not Path("media").exists()


@pytest.mark.parametrize(
    "problem",
    [
        "version",
        "host",
        "device_id",
        "malformed",
        "oversize",
        "bad_record",
        "extension",
        "missing_key",
        "cloud_mode",
        "index_range",
        "existing",
    ],
)
def test_preflight_failures_do_not_call_download(
    exported, monkeypatch, capsys, problem
):
    changes = {
        "version": ("version", True),
        "host": ("device", {"host": "192.0.2.11", "device_id": ""}),
        "device_id": ("device", {"host": HOST, "device_id": "unconfigured"}),
        "bad_record": ("records", [None, {"file_name": 123}]),
        "index_range": ("records", []),
    }
    command = DOWNLOAD.copy()
    if problem in changes:
        snapshot = json.loads(exported.read_text(encoding="utf-8"))
        key, value = changes[problem]
        snapshot[key] = value
        exported.write_text(json.dumps(snapshot), encoding="utf-8")
    elif problem == "malformed":
        exported.write_text("not JSON private-marker", encoding="utf-8")
    elif problem == "oversize":
        monkeypatch.setattr(archive_download, "MAX_LIST_BYTES", 4)
    elif problem == "extension":
        command[-1] = "media/photo.jpg"
    elif problem == "missing_key":
        monkeypatch.delenv("STREAM_KEY")
    elif problem == "cloud_mode":
        monkeypatch.setenv("CAMERA_CONNECTION_MODE", "cloud")
    elif problem == "existing":
        Path("media").mkdir()
        Path(command[-1]).write_bytes(b"original")
    with patch.object(Camera, "download_record") as fetch:
        assert cli.main(command) == 1
    fetch.assert_not_called()
    assert "private-marker" not in capsys.readouterr().err
    if problem == "existing":
        assert Path(command[-1]).read_bytes() == b"original"
    else:
        assert not Path("media").exists()


@pytest.mark.parametrize(
    "error,code",
    [
        (QuiiConnectionError("private-error"), 1),
        (MediaRenderError("private-error"), 1),
        (KeyboardInterrupt(), 130),
    ],
)
def test_transfer_failure_or_cancellation_leaves_no_file(
    exported, capsys, error, code
):
    capsys.readouterr()
    with patch.object(Camera, "download_record", side_effect=error) as fetch:
        assert cli.main(DOWNLOAD) == code
    fetch.assert_called_once()
    assert not Path("media").exists()
    captured = capsys.readouterr()
    assert not captured.out and "private-error" not in captured.err


def test_racing_output_is_not_replaced_and_temp_is_removed(
    exported, monkeypatch, capsys
):
    original_link = os.link

    def racing_link(temporary, target):
        target.write_bytes(b"other writer")
        original_link(temporary, target)

    monkeypatch.setattr(archive.os, "link", racing_link)
    with patch.object(Camera, "download_record", return_value=b"mp4"):
        assert cli.main(DOWNLOAD) == 1
    assert list(Path("media").iterdir()) == [Path("media/clip.mp4")]
    assert Path("media/clip.mp4").read_bytes() == b"other writer"
    assert "was not replaced" in capsys.readouterr().err


def test_help_and_documented_command(exported, monkeypatch, capsys):
    doc = Path(__file__).resolve().parents[2] / "docs" / "archive-cli.md"
    command = next(
        line
        for line in doc.read_text(encoding="utf-8").splitlines()
        if line.startswith("quii-helper archive download ")
        and "--from-list" in line
    )
    with patch.object(Camera, "download_record", return_value=b"mp4"):
        assert cli.main(shlex.split(command)[1:]) == 0
    monkeypatch.setattr(
        cli.SettingsLoader, "load", Mock(side_effect=AssertionError)
    )
    with pytest.raises(SystemExit) as result:
        cli.main(["archive", "download", "--help"])
    assert result.value.code == 0
    assert "--from-list" in capsys.readouterr().out


def _terminal(monkeypatch, responses):
    stdin = StringIO(responses)
    monkeypatch.setattr(stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys, "stdin", stdin)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: True)


@pytest.mark.parametrize(
    "failure, diagnostic",
    [
        (
            URLError(ssl.SSLCertVerificationError("private certificate")),
            "TLS certificate verification failed",
        ),
        (
            URLError(OSError("private network detail")),
            "LAN archive search failed",
        ),
    ],
)
def test_cgi_errors_are_reported_before_download(
    monkeypatch, capsys, failure, diagnostic
):
    _terminal(monkeypatch, "")
    opener = Mock(side_effect=failure)
    monkeypatch.setattr(OpenerDirector, "open", opener)
    with patch.object(Camera, "download_record") as fetch:
        assert cli.main(INTERACTIVE + ["--scheme", "https"]) == 1
    opener.assert_called_once()
    fetch.assert_not_called()
    captured = capsys.readouterr()
    assert diagnostic in captured.err
    assert not captured.out and "Choose a record" not in captured.err
    assert "Cannot save" not in captured.err and "private" not in captured.err


@pytest.mark.parametrize("key", ["invalid-synthetic-key", "\u00e9" * 32])
def test_invalid_stream_key_stops_before_cgi_search(monkeypatch, capsys, key):
    _terminal(monkeypatch, "")
    monkeypatch.setenv("STREAM_KEY", key)
    with (
        patch.object(Camera, "list_record_files") as search,
        patch.object(Camera, "download_record") as fetch,
    ):
        assert cli.main(INTERACTIVE) == 1
    search.assert_not_called()
    fetch.assert_not_called()
    error = capsys.readouterr().err
    assert "STREAM_KEY" in error and "32 UTF-8 bytes" in error
    assert key not in error and "Choose a record" not in error


def test_interactive_output_path_preserves_unicode(
    entries, monkeypatch, capsys
):
    _terminal(monkeypatch, "1\n")
    target = Path("\u0442\u0435\u0441\u0442.jpg")
    with (
        patch.object(
            Camera,
            "list_record_files",
            return_value=CameraDeviceRecordListInfo(
                error=0, completed=True, records=entries
            ),
        ),
        patch.object(Camera, "download_record", return_value=b"jpeg"),
    ):
        assert cli.main(INTERACTIVE + ["--output", str(target)]) == 0
    assert target.read_bytes() == b"jpeg"
    assert f"File: {target.absolute().as_posix()}" in capsys.readouterr().err


@pytest.mark.parametrize("stage", ["transfer", "write"])
def test_download_distinguishes_transfer_and_filesystem_errors(
    exported, capsys, stage
):
    failure = OSError("private path or network detail")
    with (
        patch.object(Camera, "download_record", return_value=b"mp4") as fetch,
        patch.object(archive_download, "_save_archive_file") as save,
    ):
        (fetch if stage == "transfer" else save).side_effect = failure
        assert cli.main(DOWNLOAD) == 1
    error = capsys.readouterr().err
    assert "private" not in error
    if stage == "transfer":
        save.assert_not_called()
        assert (
            "LAN archive transfer failed" in error
            and "Cannot save" not in error
        )
    else:
        save.assert_called_once()
        assert (
            "Cannot save archive media" in error
            and "transfer failed" not in error
        )


def test_interactive_uses_displayed_record_after_paging(
    entries, monkeypatch, capsys
):
    _terminal(monkeypatch, "2\nn\np\nn\n2\n\n")
    monkeypatch.setattr(archive_download, "PAGE_SIZE", 1)
    picture, video = entries
    video = replace(video, occur_type="[red]manual\x1b[2J")
    with (
        patch.object(
            Camera,
            "list_record_files",
            return_value=CameraDeviceRecordListInfo(
                error=0, completed=True, records=[picture, video]
            ),
        ) as listing,
        patch.object(Camera, "download_record", return_value=b"mp4") as fetch,
    ):
        assert (
            cli.main(INTERACTIVE + ["--channel", "2", "--scheme", "https"])
            == 0
        )
    listing.assert_called_once()
    assert listing.call_args.kwargs["start_time"] == "2026-11-27t00:00:00z"
    assert listing.call_args.kwargs["end_time"] == "2026-11-27t23:59:59z"
    assert listing.call_args.kwargs["channel_id"] == 2
    assert listing.call_args.kwargs["port"] == 443
    assert fetch.call_args.args[0] is video
    assert Path("archive-20261127-120000-2.mp4").read_bytes() == b"mp4"
    captured = capsys.readouterr()
    assert not captured.out
    assert "Enter a number shown on this page." in captured.err
    assert "\x1b[2J" not in captured.err
    assert "[red]manual" in captured.err
    assert not Path("records.json").exists()


@pytest.mark.parametrize("responses", ["q\n", "", "1\nq\n"])
def test_cancel_or_eof_does_not_download(
    entries, monkeypatch, capsys, responses
):
    _terminal(monkeypatch, responses)
    with (
        patch.object(
            Camera,
            "list_record_files",
            return_value=CameraDeviceRecordListInfo(
                error=0, completed=True, records=entries
            ),
        ),
        patch.object(Camera, "download_record") as fetch,
    ):
        assert cli.main(INTERACTIVE) == 130
    fetch.assert_not_called()
    assert "cancelled" in capsys.readouterr().err
    assert not list(Path.cwd().iterdir())


def test_interactive_prompts_again_for_existing_or_wrong_output(
    entries, monkeypatch, capsys
):
    _terminal(monkeypatch, "1\n\nclip.mp4\nnew photo.jpg\n")
    old = Path("archive-20261127-120000-1.jpg")
    old.write_bytes(b"keep")
    with (
        patch.object(
            Camera,
            "list_record_files",
            return_value=CameraDeviceRecordListInfo(
                error=0, completed=True, records=entries
            ),
        ),
        patch.object(Camera, "download_record", return_value=b"jpeg") as fetch,
    ):
        assert cli.main(INTERACTIVE) == 0
    fetch.assert_called_once()
    assert old.read_bytes() == b"keep"
    assert Path("new photo.jpg").read_bytes() == b"jpeg"
    status = capsys.readouterr().err
    assert "already exists" in status and "extension must match" in status


def test_interactive_download_reaches_real_api_with_scripted_transport(
    entries, monkeypatch, capsys
):
    _terminal(monkeypatch, "1\n")
    sock, _, factory = peer([command(2), media(cpacket()), command(8)])
    monkeypatch.setenv("STREAM_KEY", KEY)
    monkeypatch.setattr(
        api,
        "download_record_bytes",
        partial(download_record_bytes, transport_factory=factory),
    )
    with patch.object(
        Camera,
        "list_record_files",
        return_value=CameraDeviceRecordListInfo(
            error=0, completed=True, records=[entries[0]]
        ),
    ) as listing:
        assert cli.main(INTERACTIVE + ["--output", "photo.jpg"]) == 0
    listing.assert_called_once()
    factory.assert_called_once_with(HOST, 34567)
    assert sock.closed and Path("photo.jpg").read_bytes() == JPEG
    assert "Save as" not in capsys.readouterr().err


@pytest.mark.parametrize("completed", [True, False])
def test_empty_or_incomplete_search_never_prompts(
    monkeypatch, capsys, completed
):
    _terminal(monkeypatch, "")
    with (
        patch.object(
            Camera,
            "list_record_files",
            return_value=CameraDeviceRecordListInfo(
                error=0, completed=completed, records=[]
            ),
        ),
        patch.object(Camera, "download_record") as fetch,
    ):
        assert cli.main(INTERACTIVE) == 1
    fetch.assert_not_called()
    error = capsys.readouterr().err
    assert "Choose a record" not in error
    assert ("No archive records" if completed else "incomplete") in error


@pytest.mark.parametrize(
    "command, diagnostic",
    [
        (INTERACTIVE, "selection requires a terminal"),
        (INTERACTIVE + ["--index", "2"], "--index requires --from-list"),
        (INTERACTIVE + ["--from", "2026-11-27 12:00:00"], "not both"),
        (DOWNLOAD + ["--type", "all"], "cannot be combined"),
        (DOWNLOAD[:-2], "requires both --index and --output"),
    ],
)
def test_invalid_or_noninteractive_selection_stops_before_settings(
    monkeypatch, capsys, command, diagnostic
):
    monkeypatch.setattr(sys, "stdin", StringIO())
    monkeypatch.setattr(
        cli.SettingsLoader, "load", Mock(side_effect=AssertionError)
    )
    with pytest.raises(SystemExit) as result:
        cli.main(command)
    assert result.value.code == 2
    assert diagnostic in capsys.readouterr().err
