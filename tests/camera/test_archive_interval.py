"""Continuous archive windows over native whole-day CGI searches."""

import xml.etree.ElementTree as ET
from io import BytesIO
from unittest.mock import Mock

import pytest

from quii_helper import (
    AutonomousConfig,
    Camera,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.camera import api
from quii_helper.camera.device_cgi import service as cgi
from quii_helper.device.cgi.models import (
    DeviceRecordMessageInfo,
    DeviceRecordSessionInfo,
)
from quii_helper.device.http import transport

WINDOW = dict(
    start_time="2026-11-27t12:00:00z", end_time="2026-11-27t13:00:00z"
)


def entry(start, end="", file_type="video"):
    return CameraDeviceRecordFileInfo(
        file_name="native-file",
        start_time=start,
        end_time=end,
        file_type=file_type,
        raw={"native": "preserved"},
    )


@pytest.fixture
def archive(monkeypatch):
    camera = Camera(
        config=AutonomousConfig(
            connection_mode="lan", device_host="192.0.2.10", auth_code="test"
        )
    )
    camera.connector = Mock()
    read = Mock(
        return_value=CameraDeviceRecordListInfo(error=0, completed=True)
    )
    monkeypatch.setattr(api, "fetch_record_list_info", read)
    yield camera, read
    assert camera.connector.mock_calls == []


@pytest.mark.parametrize(
    "separator,suffix",
    [
        (" ", ""),
        ("t", "z"),
        ("T", ""),
        ("T", "Z"),
    ],
)
def test_formats_preserve_device_clock_and_one_search(
    archive, separator, suffix
):
    camera, read = archive
    result = camera.list_record_files(
        start_time=f"2026-11-27{separator}12:00:00{suffix}",
        end_time=f"2026-11-28{separator}00:00:00{suffix}",
        channel_id=2,
        file_type="picture",
        occur_type="manual",
        stream="sub",
        max_pages=7,
        port=443,
        scheme="https",
        auth_code="override",
        verify_tls=True,
    )
    assert result.completed
    read.assert_called_once()
    assert read.call_args.kwargs == dict(
        start_time="2026-11-27t00:00:00z",
        end_time="2026-11-28t23:59:59z",
        channel_id=2,
        file_type="picture",
        occur_type="manual",
        stream="sub",
        max_pages=7,
    )
    endpoint = read.call_args.args[0]
    assert (
        endpoint.host,
        endpoint.port,
        endpoint.scheme,
        endpoint.auth_code,
        endpoint.verify_tls,
    ) == (
        "192.0.2.10",
        443,
        "https",
        "override",
        True,
    )


@pytest.mark.parametrize(
    "start,end",
    [
        ("2028-02-29t23:59:59z", "2028-03-01t00:00:00z"),
        ("2026-12-31t23:59:59z", "2027-01-01t00:00:00z"),
        ("0001-01-01t00:00:00z", "9999-12-31t23:59:59z"),
    ],
)
def test_calendar_boundaries_do_not_overflow_or_shift(archive, start, end):
    camera, read = archive
    camera.list_record_files(start_time=start, end_time=end)
    assert read.call_args.kwargs["start_time"] == start[:10] + "t00:00:00z"
    assert read.call_args.kwargs["end_time"] == end[:10] + "t23:59:59z"


@pytest.mark.parametrize("field", ["start_time", "end_time"])
@pytest.mark.parametrize(
    "value",
    [
        None,
        42,
        "",
        "private-invalid-value",
        "2026-02-29t12:00:00z",
        "2026-11-27t24:00:00z",
        "2026-11-27T12:00:00+03:00",
        "2026-11-27t12:00:00.000z",
        "2026-11-27t12:00:00z ",
        "2026-1-2 3:4:5",
    ],
)
def test_invalid_bounds_fail_before_endpoint_resolution(
    archive, monkeypatch, field, value
):
    camera, read = archive
    endpoint = Mock(side_effect=AssertionError("must not resolve credentials"))
    monkeypatch.setattr(camera, "_resolve_local_cgi_endpoint", endpoint)
    bounds = {**WINDOW, field: value}
    with pytest.raises(ConfigurationError) as raised:
        camera.list_record_files(**bounds)
    assert "private-invalid-value" not in str(raised.value)
    endpoint.assert_not_called()
    read.assert_not_called()


@pytest.mark.parametrize(
    "end", ["2026-11-27t12:00:00z", "2026-11-26t23:59:59z"]
)
def test_empty_or_reversed_interval_is_rejected(archive, end):
    camera, read = archive
    with pytest.raises(
        ConfigurationError, match="start_time must be before end_time"
    ):
        camera.list_record_files(**{**WINDOW, "end_time": end})
    read.assert_not_called()


@pytest.mark.parametrize(
    "start,end,file_type,included",
    [
        ("11:59:59", "11:59:59", "video", False),
        ("11:59:59", "12:00:00", "video", True),
        ("11:59:59", "12:30:00", "video", True),
        ("11:00:00", "14:00:00", "video", True),
        ("12:00:00", "12:00:00", "video", True),
        ("12:30:00", "14:00:00", "video", True),
        ("13:00:00", "14:00:00", "video", True),
        ("13:00:01", "14:00:00", "video", False),
        ("11:59:59", "14:00:00", "picture", False),
        ("12:00:00", "", "picture", True),
        ("13:00:00", "invalid-unused-end", "picture", True),
        ("13:00:01", "", "picture", False),
        ("12:30:00", "", "video", True),
        ("13:00:01", "", "video", False),
    ],
)
def test_inclusive_overlap_and_picture_point_semantics(
    archive, start, end, file_type, included
):
    camera, read = archive
    row = entry(
        "2026-11-27t" + start + "z",
        "2026-11-27t" + end + "z" if ":" in end else end,
        file_type,
    )
    original = CameraDeviceRecordListInfo(
        error=0, records=[row], completed=True
    )
    read.return_value = original
    result = camera.list_record_files(**WINDOW)
    assert result.records == ([row] if included else [])
    assert original.records == [
        row
    ]  # Do not rewrite native pages or caller data.


def test_midnight_window_preserves_order_identity_and_native_diagnostics(
    archive,
):
    camera, read = archive
    outside = entry("2026-11-28t01:00:00z", "2026-11-28t01:01:00z")
    video = entry("2026-11-27t23:58:00z", "2026-11-28t00:01:00z")
    picture = entry("2026-11-28t00:00:00z", file_type="picture")
    native_page = DeviceRecordMessageInfo(
        error=0, result=0, records=[outside, video, picture]
    )
    session = DeviceRecordSessionInfo(error=0, session_id="native-session")
    original = CameraDeviceRecordListInfo(
        error=0,
        session_id=session.session_id,
        records=native_page.records,
        pages=[native_page],
        session=session,
        completed=True,
    )
    read.return_value = original
    result = camera.list_record_files(
        start_time="2026-11-27t23:59:00z",
        end_time="2026-11-28t00:00:00z",
        file_type="video",
    )
    assert result.records == [video, picture]
    assert result.records[0] is video and result.records[1] is picture
    assert (
        result.session is session and result.session_id == session.session_id
    )
    assert result.pages is original.pages and result.pages[0].records == [
        outside,
        video,
        picture,
    ]
    assert original.records == [outside, video, picture]


@pytest.mark.parametrize(
    "row",
    [
        entry(""),
        entry("private-bad-time"),
        entry("2026-11-27t12:30:00z", "bad-end"),
        entry("2026-11-27t12:30:00z", "2026-11-27t12:29:59z"),
        entry("2026-11-27t11:59:59z"),
    ],
)
def test_ambiguous_or_invalid_metadata_is_not_silently_dropped(archive, row):
    camera, read = archive
    read.return_value = CameraDeviceRecordListInfo(
        error=0, records=[row], completed=True
    )
    with pytest.raises(QuiiConnectionError, match="cannot filter") as raised:
        camera.list_record_files(**WINDOW)
    assert "private-bad-time" not in str(raised.value)


def test_device_error_preserves_native_failure_even_with_unusable_metadata(
    archive,
):
    camera, read = archive
    original = CameraDeviceRecordListInfo(
        error=-8, completed=False, records=[entry("")]
    )
    read.return_value = original
    assert camera.list_record_files(**WINDOW, file_type="video") is original


def test_partial_page_is_still_incomplete_even_if_filter_removes_every_record(
    archive, monkeypatch
):
    camera, _ = archive
    monkeypatch.setattr(
        api, "fetch_record_list_info", cgi.fetch_record_list_info
    )
    session = Mock(
        return_value=DeviceRecordSessionInfo(
            error=0, session_id="native-session"
        )
    )
    outside = entry("2026-11-27t14:00:00z", "2026-11-27t14:01:00z")
    message = Mock(
        return_value=DeviceRecordMessageInfo(
            error=0, result=1, records=[outside]
        )
    )
    monkeypatch.setattr(cgi, "fetch_record_session_info", session)
    monkeypatch.setattr(cgi, "fetch_record_message_info", message)
    result = camera.list_record_files(**WINDOW, file_type="video", max_pages=1)
    assert result.error == 0 and not result.completed and result.records == []
    assert result.pages[0].records == [outside] and result.pages[0].result == 1
    assert message.call_count == 1


def test_real_cgi_path_avoids_daily_filter_and_discards_unrequested_hours(
    monkeypatch,
):
    camera = Camera(
        config=AutonomousConfig(
            connection_mode="lan", device_host="192.0.2.10", auth_code="test"
        )
    )
    commands = []

    def respond(request, **kwargs):
        assert request.full_url == "http://192.0.2.10:80/tdkcgi"
        root = ET.fromstring(request.data)
        command = root.findtext("./body/command")
        commands.append(command)
        if command == "get.record.session":
            search = root.find("./body/content/record")
            assert search.findtext("starttime") == "2026-11-27t00:00:00z"
            assert search.findtext("endtime") == "2026-11-28t23:59:59z"
            content = "<record><id>native-session</id></record>"
        else:
            assert command == "get.record.message"
            content = "<record><page>0</page><datalist>"
            for hour in ("2026-11-27t12:00:00z", "2026-11-28t12:00:00z"):
                content += f"<data><filetype>picture</filetype><filename>native-{hour}</filename><starttime>{hour}</starttime></data>"
            content += "</datalist></record>"
        return BytesIO(
            (
                "<envelope><body><error>0</error><content>"
                + content
                + "</content></body></envelope>"
            ).encode()
        )

    monkeypatch.setattr(
        transport.urllib.request.OpenerDirector,
        "open",
        Mock(side_effect=respond),
    )
    result = camera.list_record_files(
        start_time="2026-11-27t00:00:00z",
        end_time="2026-11-28t00:00:00z",
        file_type="picture",
    )
    assert result.completed and len(result.records) == 1
    assert len(result.pages[0].records) == 2
    assert commands == ["get.record.session", "get.record.message"]
