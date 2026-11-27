"""Logical all belongs to Camera, not to CLI or watcher-specific workarounds."""

from dataclasses import replace
from typing import get_type_hints
from unittest.mock import Mock

import pytest

from quii_helper import (
    AutonomousConfig,
    Camera,
    CameraDeviceRecordFileInfo,
    CameraDeviceRecordListInfo,
    QuiiConnectionError,
)
from quii_helper.camera import api
from quii_helper.camera.device_cgi import service as cgi
from quii_helper.device.cgi.models import (
    DeviceRecordMessageInfo,
    DeviceRecordSessionInfo,
)

WINDOW = dict(
    start_time="2026-11-27t12:00:00z", end_time="2026-11-27t13:00:00z"
)


def record(kind="video", **kwargs):
    return CameraDeviceRecordFileInfo(
        file_name="same-native-name",
        file_type=kind,
        channel_id="2",
        start_time="2026-11-27t12:01:00z",
        end_time="2026-11-27t12:02:00z",
        **kwargs,
    )


def result(kind, *records, error=0, completed=True):
    session = DeviceRecordSessionInfo(error=0, session_id=kind + "-session")
    page = DeviceRecordMessageInfo(
        error=error, result=0 if completed else 1, records=list(records)
    )
    return CameraDeviceRecordListInfo(
        error=error,
        session_id=session.session_id,
        session=session,
        pages=[page],
        records=list(records),
        completed=completed,
    )


@pytest.fixture
def archive(monkeypatch):
    camera = Camera(
        config=AutonomousConfig(
            connection_mode="lan", device_host="192.0.2.10", auth_code="test"
        )
    )
    camera.connector = Mock()
    native = Mock()
    monkeypatch.setattr(api, "fetch_record_list_info", native)
    yield camera, native
    assert camera.connector.mock_calls == []


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("with_picture", [False, True])
def test_default_all_works_when_native_all_is_successfully_empty(
    archive, explicit, with_picture
):
    camera, native = archive
    video, photo = record(), record("picture", picture_index="0007")

    def respond(endpoint, **kwargs):
        kind = kwargs["file_type"]
        if kind == "video":
            return result(kind, video)
        if kind == "picture" and with_picture:
            return result(kind, photo)
        return result(kind)  # The observed device behavior for literal all.

    native.side_effect = respond
    combined = camera.list_record_files(
        **WINDOW, **({"file_type": "all"} if explicit else {})
    )
    assert combined.error == 0 and combined.completed
    assert combined.records == [video] + ([photo] if with_picture else [])
    assert [call.kwargs["file_type"] for call in native.call_args_list] == [
        "video",
        "picture",
    ]
    assert combined.session_id == "" and combined.session is None
    assert list(combined.searches) == ["video", "picture"]
    assert combined.searches["video"].session_id == "video-session"


def test_combined_results_preserve_filtered_children_raw_pages_and_identity(
    archive,
):
    camera, native = archive
    video = record(file_size=42, raw={"idx": "unchanged"})
    changed_video = replace(video, file_size=99)
    photo = record("picture", picture_index="0007")
    next_photo = replace(photo, picture_index="0008")
    other_channel = replace(photo, channel_id="1")
    outside = replace(
        video,
        start_time="2026-11-27t14:00:00z",
        end_time="2026-11-27t14:01:00z",
    )
    videos = result("video", outside, video, changed_video)
    pictures = result(
        "picture", photo, video, photo, next_photo, other_channel
    )
    native.side_effect = [videos, pictures]
    combined = camera.list_record_files(
        **WINDOW,
        max_pages=7,
        channel_id=2,
        occur_type="manual",
        stream="sub",
        scheme="https",
        port=443,
    )
    assert combined.records == [video, photo, next_photo, other_channel]
    assert combined.records[0] is video and video.file_size == 42
    assert combined.records[1].picture_index == "0007"
    assert combined.searches["video"].records == [video, changed_video]
    assert combined.searches["picture"] is pictures
    assert combined.pages == videos.pages + pictures.pages
    assert (
        combined.pages[0] is videos.pages[0]
        and combined.pages[0].records[0] is outside
    )
    assert videos.records == [outside, video, changed_video]
    for call in native.call_args_list:
        assert call.kwargs == dict(
            start_time="2026-11-27t00:00:00z",
            end_time="2026-11-27t23:59:59z",
            channel_id=2,
            file_type=call.kwargs["file_type"],
            occur_type="manual",
            stream="sub",
            max_pages=7,
        )
        assert call.args[0].port == 443 and call.args[0].scheme == "https"


@pytest.mark.parametrize(
    "video_empty,picture_empty", [(True, True), (True, False), (False, True)]
)
def test_empty_search_is_not_a_failure(archive, video_empty, picture_empty):
    camera, native = archive
    videos = [] if video_empty else [record()]
    photos = [] if picture_empty else [record("picture")]
    native.side_effect = [result("video", *videos), result("picture", *photos)]
    combined = camera.list_record_files(**WINDOW)
    assert combined.completed and combined.error == 0
    assert combined.records == videos + photos
    assert native.call_count == 2


@pytest.mark.parametrize("position", [0, 1])
@pytest.mark.parametrize("failure", ["device", "incomplete"])
def test_failure_retains_diagnostics_but_never_partial_aggregate(
    archive, position, failure
):
    camera, native = archive
    searches = [
        result("video", record()),
        result("picture", record("picture")),
    ]
    searches[position] = replace(
        searches[position],
        error=-8 if failure == "device" else 0,
        completed=False,
    )
    native.side_effect = searches
    combined = camera.list_record_files(**WINDOW)
    assert combined.error == (-8 if failure == "device" else 0)
    assert not combined.completed and combined.records == []
    assert native.call_count == position + 1
    assert list(combined.searches) == ["video", "picture"][: position + 1]
    assert (
        combined.searches[["video", "picture"][position]] is searches[position]
    )
    assert combined.pages == [
        p for search in searches[: position + 1] for p in search.pages
    ]
    assert combined.session is None and combined.session_id == ""


@pytest.mark.parametrize("position", [0, 1])
@pytest.mark.parametrize(
    "failure",
    [
        OSError("private-error"),
        KeyboardInterrupt(),
        QuiiConnectionError("metadata failure"),
    ],
)
def test_exception_or_cancellation_propagates_without_retry(
    archive, position, failure
):
    camera, native = archive
    searches = [
        result("video", record()),
        result("picture", record("picture")),
    ]
    searches[position] = failure
    native.side_effect = searches
    with pytest.raises(type(failure)) as caught:
        camera.list_record_files(**WINDOW)
    assert caught.value is failure
    assert native.call_count == position + 1


@pytest.mark.parametrize("kind", ["video", "picture", "custom-native-filter"])
def test_explicit_selector_retains_single_native_session(archive, kind):
    camera, native = archive
    original = result(
        kind, record("picture" if kind == "picture" else "video")
    )
    native.return_value = original
    assert camera.list_record_files(**WINDOW, file_type=kind) is original
    assert original.searches == {}
    native.assert_called_once()
    assert native.call_args.kwargs["file_type"] == kind


@pytest.mark.parametrize("page_status", [0, 1])
def test_page_cap_applies_to_each_native_search(
    archive, monkeypatch, page_status
):
    camera, _ = archive
    monkeypatch.setattr(
        api, "fetch_record_list_info", cgi.fetch_record_list_info
    )
    session = Mock(
        side_effect=[
            DeviceRecordSessionInfo(error=0, session_id="video"),
            DeviceRecordSessionInfo(error=0, session_id="picture"),
        ]
    )
    message = Mock(
        side_effect=[
            DeviceRecordMessageInfo(error=0, result=0, records=[record()]),
            DeviceRecordMessageInfo(
                error=0, result=page_status, records=[record("picture")]
            ),
        ]
    )
    monkeypatch.setattr(cgi, "fetch_record_session_info", session)
    monkeypatch.setattr(cgi, "fetch_record_message_info", message)
    combined = camera.list_record_files(**WINDOW, max_pages=1)
    assert combined.completed == (page_status == 0)
    assert len(combined.records) == (2 if page_status == 0 else 0)
    assert [call.kwargs["file_type"] for call in session.call_args_list] == [
        "video",
        "picture",
    ]
    assert [call.kwargs["session_id"] for call in message.call_args_list] == [
        "video",
        "picture",
    ]


def test_missing_identity_is_not_silently_deduplicated(archive):
    camera, native = archive
    native.side_effect = [
        result("video", replace(record(), file_name="")),
        result("picture"),
    ]
    with pytest.raises(QuiiConnectionError, match="no usable filename"):
        camera.list_record_files(**WINDOW)


def test_new_diagnostics_field_preserves_old_positional_constructor():
    session = DeviceRecordSessionInfo(error=0, session_id="native")
    original = CameraDeviceRecordListInfo(0, "native", [], [], True, session)
    other = CameraDeviceRecordListInfo(error=0)
    assert original.searches == {} and original.searches is not other.searches
    assert original.session is session and original.session_id == "native"
    assert (
        get_type_hints(CameraDeviceRecordListInfo)["searches"]
        == dict[str, CameraDeviceRecordListInfo]
    )
