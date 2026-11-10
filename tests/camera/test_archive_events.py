import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timezone
from http.client import IncompleteRead
from io import BytesIO
from unittest.mock import Mock
from urllib.error import URLError

import pytest

from quii_helper import (
    AutonomousConfig,
    Camera,
    CameraArchiveEvent,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    CameraStreamCredentials,
    ConfigurationError,
    QuiiConnectionError,
)
from quii_helper.camera import api
from quii_helper.camera.device_cgi import service as cgi
from quii_helper.camera.events import archive
from quii_helper.device.cgi.models import (
    DeviceRecordMessageInfo,
    DeviceRecordSessionInfo,
)
from quii_helper.device.http import transport

WINDOW = dict(start_time="2026-11-10 12:00:00", end_time="2026-11-10 12:10:00")
CGI_WINDOW = dict(
    start_time="2026-11-10t12:00:00z", end_time="2026-11-10t12:10:00z"
)
VIDEO_WINDOW = dict(**WINDOW, file_type="video")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def sleep(self, delay: float) -> None:
        assert delay > 0
        self.sleeps.append(delay)
        self.now += delay


def record(name: str, **kwargs) -> CameraDeviceRecordFileInfo:
    return CameraDeviceRecordFileInfo(
        file_name=name,
        file_type="video",
        channel_id="1",
        start_time="2026-11-10 12:01:00",
        **kwargs,
    )


def page(*records: CameraDeviceRecordFileInfo) -> CameraDeviceRecordListInfo:
    return CameraDeviceRecordListInfo(
        error=0, completed=True, records=list(records)
    )


@pytest.fixture
def watcher(monkeypatch):
    clock = FakeClock()
    monkeypatch.setattr(archive, "monotonic", lambda: clock.now)
    monkeypatch.setattr(archive, "sleep", clock.sleep)
    camera = Camera(
        config=AutonomousConfig(
            connection_mode="lan", device_host="192.0.2.10", auth_code="test"
        )
    )
    camera.connector = Mock()
    read = Mock(return_value=page())
    monkeypatch.setattr(camera, "list_record_files", read)
    monkeypatch.setattr(
        api, "fetch_call_events", Mock(side_effect=AssertionError("no cloud"))
    )
    return camera, read, clock


def test_baseline_photos_videos_and_deduplication(watcher) -> None:
    camera, read, _ = watcher
    baseline = record("baseline")
    video = record("new-video", occur_type="manual")
    picture = replace(video, file_type="picture", picture_index="0007")
    next_picture = replace(picture, picture_index="0008")
    changed = replace(
        video, end_time="later", file_size=999, occur_type="event"
    )
    read.side_effect = [
        page(baseline),
        page(),
        page(video, video, baseline),
        page(picture),
        page(changed),
        page(picture, next_picture),
        page(),
        page(),
    ]

    events = list(camera.watch_archive_events(**WINDOW, duration_seconds=20))

    assert [event.record for event in events] == [video, picture, next_picture]
    assert all(event.kind == "archive_record_added" for event in events)
    assert all(event.observed_at.tzinfo is timezone.utc for event in events)
    assert all(event.record.start_time == video.start_time for event in events)
    assert events[0].observed_at == events[1].observed_at
    assert read.call_count == 8
    assert camera.connector.mock_calls == []
    for index, call in enumerate(read.call_args_list):
        assert call.kwargs == dict(
            **CGI_WINDOW,
            channel_id=1,
            file_type="video" if index % 2 == 0 else "picture",
            occur_type="all",
            stream="all",
            max_pages=32,
            port=80,
            scheme="http",
            auth_code=None,
            verify_tls=None,
            debug=False,
        )


def test_empty_baseline_and_lazy_start_and_close(watcher) -> None:
    camera, read, clock = watcher
    read.side_effect = [
        page(),
        page(record("new")),
        page(record("never-read")),
    ]
    events = camera.watch_archive_events(**VIDEO_WINDOW, duration_seconds=20)
    read.assert_not_called()
    clock.now = 1000  # The budget starts on iteration, not construction.
    assert next(events).record.file_name == "new"
    events.close()
    assert read.call_count == 2
    assert clock.sleeps == [5]


@pytest.mark.parametrize("phase", ["baseline", "later"])
@pytest.mark.parametrize("failed_type", ["video", "picture"])
@pytest.mark.parametrize(
    "failure", ["device", "incomplete", "transport", "interrupt"]
)
def test_all_requires_both_complete_types_before_emitting(
    watcher, phase, failed_type, failure
) -> None:
    camera, read, _ = watcher
    partial = record("not-an-event")
    failed = {
        "device": replace(page(partial), error=-1),
        "incomplete": replace(page(partial), completed=False),
        "transport": OSError("read failed"),
        "interrupt": KeyboardInterrupt(),
    }[failure]
    prefix = [page(), page()] if phase == "later" else []
    batch = [failed] if failed_type == "video" else [page(partial), failed]
    read.side_effect = prefix + batch
    events = camera.watch_archive_events(**WINDOW)
    expected = (
        KeyboardInterrupt if failure == "interrupt" else QuiiConnectionError
    )
    with pytest.raises(expected):
        next(events)
    assert [call.kwargs["file_type"] for call in read.call_args_list] == (
        (["video", "picture"] if phase == "later" else [])
        + (["video"] if failed_type == "video" else ["video", "picture"])
    )


@pytest.mark.parametrize("limit", [1, 2])
def test_all_shares_identity_limit_across_types(watcher, limit) -> None:
    camera, read, _ = watcher
    video = record("video")
    picture = replace(record("picture"), file_type="picture")
    read.side_effect = [
        page(video),
        page(picture),
        page(video, record("later-video")),
        page(picture),
    ]
    with pytest.raises(QuiiConnectionError, match="max_seen_records"):
        next(camera.watch_archive_events(**WINDOW, max_seen_records=limit))
    assert read.call_count == (2 if limit == 1 else 4)


def test_all_deduplicates_overlapping_native_type_results(watcher) -> None:
    camera, read, _ = watcher
    video = record("shared-name")
    picture = replace(video, file_type="picture", picture_index="0007")
    read.side_effect = [
        page(),
        page(),
        page(video, picture),
        page(video, picture),
        page(video, picture),
        page(video, picture),
    ]
    events = list(camera.watch_archive_events(**WINDOW, duration_seconds=11))
    assert [event.record for event in events] == [video, picture]
    assert events[0].observed_at == events[1].observed_at
    assert read.call_count == 6


@pytest.mark.parametrize(
    "duration, starts, sleeps",
    [
        (5, [("video", 0), ("picture", 4)], []),
        (
            20,
            [("video", 0), ("picture", 4), ("video", 13), ("picture", 17)],
            [5],
        ),
    ],
)
def test_all_query_budget_covers_the_complete_batch(
    watcher, duration, starts, sleeps
) -> None:
    camera, read, clock = watcher
    actual = []

    def query(**kwargs):
        actual.append((kwargs["file_type"], clock.now))
        clock.now += 4
        return page()

    read.side_effect = query
    assert (
        list(camera.watch_archive_events(**WINDOW, duration_seconds=duration))
        == []
    )
    assert actual == starts
    assert clock.sleeps == sleeps


def test_direct_archive_all_remains_one_native_search(
    watcher, monkeypatch
) -> None:
    camera, _, _ = watcher
    monkeypatch.delattr(camera, "list_record_files")
    result = page()
    fetch = Mock(return_value=result)
    monkeypatch.setattr(api, "fetch_record_list_info", fetch)
    assert camera.list_record_files(**CGI_WINDOW, file_type="all") is result
    fetch.assert_called_once()
    assert fetch.call_args.kwargs["file_type"] == "all"
    assert fetch.call_args.kwargs["start_time"] == CGI_WINDOW["start_time"]
    assert fetch.call_args.kwargs["end_time"] == CGI_WINDOW["end_time"]


@pytest.mark.parametrize("phase", ["baseline", "later"])
@pytest.mark.parametrize("failure", ["device", "incomplete", "transport"])
def test_failed_queries_are_not_empty_results(watcher, phase, failure) -> None:
    camera, read, clock = watcher
    result = {
        "device": replace(page(), error=-1),
        "incomplete": replace(page(), completed=False),
        "transport": QuiiConnectionError("transport error"),
    }[failure]
    read.side_effect = ([page()] if phase == "later" else []) + [result]
    with pytest.raises(QuiiConnectionError):
        list(camera.watch_archive_events(**VIDEO_WINDOW))
    assert read.call_count == (2 if phase == "later" else 1)
    assert len(clock.sleeps) == (1 if phase == "later" else 0)


@pytest.mark.parametrize(
    "error",
    [
        OSError("private-network-detail"),
        URLError("private-network-detail"),
        TimeoutError("private-network-detail"),
        ET.ParseError("private-xml-detail"),
        RuntimeError("response body not found"),
        ValueError("CGI response body not found"),
        IncompleteRead(b"private-partial-body"),
    ],
)
def test_standard_cgi_errors_become_connection_errors(watcher, error) -> None:
    camera, read, _ = watcher
    read.side_effect = error
    with pytest.raises(
        QuiiConnectionError, match="could not read local archive"
    ) as caught:
        next(camera.watch_archive_events(**WINDOW))
    assert caught.value.__cause__ is error
    assert "private" not in str(caught.value)
    read.assert_called_once()


def test_configuration_error_is_not_masked_or_retried(watcher) -> None:
    camera, read, _ = watcher
    error = ConfigurationError("missing local settings")
    read.side_effect = error
    with pytest.raises(ConfigurationError) as caught:
        next(camera.watch_archive_events(**WINDOW))
    assert caught.value is error
    read.assert_called_once()


@pytest.mark.parametrize("phase", ["baseline", "later"])
@pytest.mark.parametrize("failure", ["identity", "capacity"])
def test_invalid_batch_emits_nothing(watcher, phase, failure) -> None:
    camera, read, _ = watcher
    records = [
        record("valid"),
        record("" if failure == "identity" else "other"),
    ]
    read.side_effect = ([page()] if phase == "later" else []) + [
        page(*records)
    ]
    with pytest.raises(QuiiConnectionError):
        next(camera.watch_archive_events(**VIDEO_WINDOW, max_seen_records=1))


def test_memory_limit_includes_baseline_and_never_evicts(watcher) -> None:
    camera, read, _ = watcher
    first = record("baseline")
    second = record("second")
    read.side_effect = [
        page(first),
        page(first, second),
        page(record("third")),
    ]
    events = camera.watch_archive_events(**VIDEO_WINDOW, max_seen_records=2)
    assert next(events).record is second
    with pytest.raises(QuiiConnectionError, match="max_seen_records"):
        next(events)


@pytest.mark.parametrize(
    "seconds", [0, -1, True, "5", float("inf"), float("nan"), 10**400]
)
@pytest.mark.parametrize("option", ["interval_seconds", "duration_seconds"])
def test_invalid_timing_is_rejected_before_io(
    watcher, option, seconds
) -> None:
    camera, read, _ = watcher
    with pytest.raises(ConfigurationError, match=option):
        camera.watch_archive_events(**WINDOW, **{option: seconds})
    read.assert_not_called()


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "2"])
@pytest.mark.parametrize("option", ["max_seen_records", "max_pages"])
def test_invalid_limits_are_rejected_before_io(watcher, option, value) -> None:
    camera, read, _ = watcher
    with pytest.raises(ConfigurationError, match=option):
        camera.watch_archive_events(**WINDOW, **{option: value})
    read.assert_not_called()


@pytest.mark.parametrize(
    "window",
    [
        {**WINDOW, "start_time": "private-invalid-time"},
        {**WINDOW, "end_time": None},
        dict(start_time=WINDOW["end_time"], end_time=WINDOW["start_time"]),
        dict(start_time=WINDOW["end_time"], end_time=WINDOW["end_time"]),
    ],
)
def test_invalid_window_is_rejected_before_io(watcher, window) -> None:
    camera, read, _ = watcher
    with pytest.raises(ConfigurationError) as caught:
        camera.watch_archive_events(**window)
    assert "private-invalid-time" not in str(caught.value)
    read.assert_not_called()


@pytest.mark.parametrize(
    "query_seconds, starts, sleeps",
    [(1.0, [0, 5, 10, 15], [4] * 4), (7.0, [0, 12], [5, 1]), (25.0, [0], [])],
)
def test_query_budget_no_overlap_or_catchup(
    watcher, query_seconds, starts, sleeps
) -> None:
    camera, read, clock = watcher
    actual = []

    def query(**kwargs):
        actual.append(clock.now)
        clock.now += query_seconds
        return page()

    read.side_effect = query
    assert (
        list(camera.watch_archive_events(**VIDEO_WINDOW, duration_seconds=20))
        == []
    )
    assert actual == starts
    assert clock.sleeps == sleeps


def test_slow_consumer_counts_towards_deadline(watcher) -> None:
    camera, read, clock = watcher
    read.side_effect = [page(), page(record("first"), record("second"))]
    events = camera.watch_archive_events(**VIDEO_WINDOW, duration_seconds=10)
    assert next(events).record.file_name == "first"
    clock.now += 50
    assert next(events).record.file_name == "second"  # Already fetched batch.
    assert list(events) == []
    assert read.call_count == 2


def test_event_repr_does_not_expose_private_metadata() -> None:
    entry = record(
        "private-filename", url="private-token", raw={"auth": "secret"}
    )
    event = CameraArchiveEvent(entry, datetime.now(timezone.utc))
    assert "private" not in repr(event)
    assert "secret" not in repr(event)


def test_fresh_session_and_native_completion_on_every_poll(
    watcher, monkeypatch
) -> None:
    camera, _, _ = watcher
    monkeypatch.delattr(camera, "list_record_files")
    session = Mock(
        side_effect=[
            DeviceRecordSessionInfo(error=0, session_id=str(number))
            for number in range(3)
        ]
    )
    message = Mock(return_value=DeviceRecordMessageInfo(error=0, result=0))
    monkeypatch.setattr(cgi, "fetch_record_session_info", session)
    monkeypatch.setattr(cgi, "fetch_record_message_info", message)
    assert (
        list(camera.watch_archive_events(**VIDEO_WINDOW, duration_seconds=11))
        == []
    )
    assert session.call_count == 3
    assert [call.kwargs for call in message.call_args_list] == [
        {"session_id": "0"},
        {"session_id": "1"},
        {"session_id": "2"},
    ]


def test_each_poll_reuses_existing_local_cgi_path(
    watcher, monkeypatch
) -> None:
    camera, read, clock = watcher
    monkeypatch.delattr(camera, "list_record_files")
    fetch = Mock(return_value=page())
    monkeypatch.setattr(api, "fetch_record_list_info", fetch)
    assert (
        list(
            camera.watch_archive_events(
                **WINDOW,
                duration_seconds=11,
                channel_id=2,
                file_type="picture",
                occur_type="manual",
                stream="sub",
                max_pages=3,
                port=443,
                scheme="https",
                auth_code="override-auth",
                verify_tls=True,
            )
        )
        == []
    )
    assert fetch.call_count == 3
    assert read.call_count == 0
    for call in fetch.call_args_list:
        endpoint = call.args[0]
        assert endpoint.host == "192.0.2.10"
        assert (endpoint.port, endpoint.scheme, endpoint.auth_code) == (
            443,
            "https",
            "override-auth",
        )
        assert endpoint.verify_tls is True
        assert call.kwargs == dict(
            **CGI_WINDOW,
            channel_id=2,
            file_type="picture",
            occur_type="manual",
            stream="sub",
            max_pages=3,
        )


@pytest.mark.parametrize(
    "file_type, native_types",
    [
        ("video", ["video"]),
        ("picture", ["picture"]),
        ("all", ["video", "picture"]),
    ],
)
@pytest.mark.parametrize(
    "window, native_start, native_end",
    [
        (WINDOW, "2026-11-10t12:00:00z", "2026-11-10t12:10:00z"),
        (
            dict(
                start_time="2026-12-31 23:59:00",
                end_time="2027-01-01 00:03:00",
            ),
            "2026-12-31t23:59:00z",
            "2027-01-01t00:03:00z",
        ),
        (
            dict(
                start_time="2028-02-29 03:04:05",
                end_time="2028-02-29 03:09:10",
            ),
            "2028-02-29t03:04:05z",
            "2028-02-29t03:09:10z",
        ),
        (
            dict(start_time="2026-1-2 3:4:5", end_time="2026-1-2 3:9:10"),
            "2026-01-02t03:04:05z",
            "2026-01-02t03:09:10z",
        ),
    ],
)
def test_watcher_serializes_native_cgi_times_without_utc_conversion(
    watcher,
    monkeypatch,
    window,
    native_start,
    native_end,
    file_type,
    native_types,
) -> None:
    camera, _, _ = watcher
    monkeypatch.delattr(camera, "list_record_files")
    searches = []

    def respond(request, **kwargs):
        assert request.full_url == "http://192.0.2.10:80/tdkcgi"
        root = ET.fromstring(request.data)
        command = root.findtext("./body/command")
        if command == "get.record.session":
            record = root.find("./body/content/record")
            assert record is not None
            searches.append(
                (
                    record.findtext("starttime"),
                    record.findtext("endtime"),
                    record.findtext("filetype"),
                )
            )
            assert record.findtext("channel") == "2"
            content = f"<record><id>test-search-{len(searches)}</id></record>"
        else:
            assert command == "get.record.message"
            assert root.findtext("./body/content/record/id") == (
                f"test-search-{len(searches)}"
            )
            content = "<record><datalist/><page>0</page></record>"
        # Valid empty replies must not hide malformed outgoing search bounds.
        return BytesIO(
            (
                "<envelope><body><error>0</error><content>"
                + content
                + "</content></body></envelope>"
            ).encode()
        )

    network = Mock(side_effect=respond)
    monkeypatch.setattr(transport.urllib.request, "urlopen", network)
    assert (
        list(
            camera.watch_archive_events(
                **window,
                channel_id=2,
                file_type=file_type,
                duration_seconds=11,
            )
        )
        == []
    )
    assert network.call_count == 6 * len(native_types)
    assert (
        searches
        == [
            (native_start, native_end, native_type)
            for native_type in native_types
        ]
        * 3
    )


@pytest.fixture
def archive_example(monkeypatch):
    from examples import watch_archive_events as example

    camera = Mock(spec=Camera)
    monkeypatch.setattr(example, "Camera", Mock(return_value=camera))
    monkeypatch.setattr(
        example,
        "load_config",
        Mock(
            return_value=AutonomousConfig(
                connection_mode="cloud", auth_code="different-env-auth"
            )
        ),
    )
    saved = CameraStreamCredentials("saved-device", "K" * 32, "saved-auth")
    monkeypatch.setattr(
        example.CameraStreamCredentials, "load", Mock(return_value=saved)
    )
    monkeypatch.setattr(example, "configure_logging", Mock())
    monkeypatch.setattr(
        "builtins.input", Mock(return_value="2026-11-10 12:05:00")
    )
    return example, camera


def test_example_reads_only_archive_and_omits_private_fields(
    archive_example, capsys
) -> None:
    example, camera = archive_example
    entry = record("private-name", url="private-token", occur_type="manual")
    camera.watch_archive_events.return_value = iter(
        [CameraArchiveEvent(entry, datetime.now(timezone.utc))]
    )
    example.main()
    assert [call[0] for call in camera.mock_calls] == ["watch_archive_events"]
    camera.watch_archive_events.assert_called_once_with(
        start_time="2026-11-10 12:00:00",
        end_time="2026-11-10 12:09:00",
        file_type="all",
        interval_seconds=5,
        duration_seconds=180,
    )
    example.CameraStreamCredentials.load.assert_called_once_with(
        "data/stream_credentials.json"
    )
    example.Camera.assert_called_once_with(
        config=example.load_config.return_value,
        connection_mode="lan",
        device_id="saved-device",
        auth_code="saved-auth",
    )
    output = capsys.readouterr().out
    assert "private" not in output
    assert "saved-auth" not in output
    assert "K" * 32 not in output
    assert "archive_record_added" in output
    assert output.endswith("Stopped.\n")


@pytest.mark.parametrize(
    "error", [KeyboardInterrupt(), QuiiConnectionError("read failed")]
)
def test_example_stops_on_interrupt_or_read_failure(
    archive_example, capsys, error
) -> None:
    example, camera = archive_example
    camera.watch_archive_events.side_effect = error
    if isinstance(error, KeyboardInterrupt):
        example.main()
        assert capsys.readouterr().out.endswith("Stopped.\n")
    else:
        with pytest.raises(QuiiConnectionError):
            example.main()
        assert (
            "This does not mean that no event occurred"
            in capsys.readouterr().out
        )
    assert camera.watch_archive_events.call_count == 1


def test_example_retries_invalid_clock_input(
    archive_example, monkeypatch, capsys
) -> None:
    example, camera = archive_example
    answers = iter(
        ["", "10.11.2026 12:05", "2026-02-30 12:00:00", "2026-11-10 12:05:00"]
    )
    camera.watch_archive_events.return_value = iter(())

    def read_time(prompt):
        camera.watch_archive_events.assert_not_called()
        return next(answers)

    reader = Mock(side_effect=read_time)
    monkeypatch.setattr("builtins.input", reader)
    example.main()

    assert reader.call_count == 4
    assert (
        capsys.readouterr().out.count("Invalid time. Use YYYY-MM-DD HH:MM:SS")
        == 3
    )
    camera.watch_archive_events.assert_called_once_with(
        start_time="2026-11-10 12:00:00",
        end_time="2026-11-10 12:09:00",
        file_type="all",
        interval_seconds=5,
        duration_seconds=180,
    )


@pytest.mark.parametrize("phase", ["prompt", "credentials"])
def test_example_cancels_before_polling(
    archive_example, monkeypatch, capsys, phase
) -> None:
    example, camera = archive_example
    if phase == "prompt":
        monkeypatch.setattr(
            "builtins.input", Mock(side_effect=KeyboardInterrupt)
        )
    else:
        example.CameraStreamCredentials.load.side_effect = KeyboardInterrupt
    example.main()
    camera.watch_archive_events.assert_not_called()
    assert capsys.readouterr().out.endswith("Stopped.\n")


@pytest.mark.parametrize(
    "error",
    [
        FileNotFoundError("missing file"),
        ConfigurationError("invalid credentials"),
    ],
)
def test_example_missing_or_invalid_file_never_fetches_credentials(
    archive_example, error
) -> None:
    example, camera = archive_example
    example.CameraStreamCredentials.load.side_effect = error
    with pytest.raises(type(error)):
        example.main()
    example.Camera.assert_not_called()
    camera.watch_archive_events.assert_not_called()
