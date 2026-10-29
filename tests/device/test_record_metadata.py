"""Archive fields verified against the vHome/vEye record-list parsers."""

import pytest

from quii_helper.device.cgi.models import (
    DeviceCgiResponse,
    DeviceRecordFileInfo,
)
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_record_alarm_info,
    parse_record_message_info,
)


@pytest.mark.parametrize(
    "parse", [parse_record_message_info, parse_record_alarm_info]
)
@pytest.mark.parametrize("index", ["0", "00017", "4294967295"])
@pytest.mark.parametrize(
    "ids,stream", [("1", "main"), ("2", "sub"), ("9", "")]
)
def test_native_picture_selectors_are_not_record_ids(
    parse, index, ids, stream
):
    raw = {
        "id": "record-id",
        "filename": "native-file-name",
        "filetype": "picture",
        "idx": index,
        "ids": ids,
        "idf": "25",
        "filesize": "12",
    }
    response = DeviceCgiResponse("get.record.message", 0, {"record": raw}, "")
    record = parse(response).records[0]
    assert record.record_id == "record-id"
    assert record.picture_index == index
    assert record.frame_rate == 25
    assert record.stream == stream
    assert (
        record.file_size == 12
    )  # Preserve existing CGI units, not JPEG bytes.
    assert record.raw == raw


@pytest.mark.parametrize("key", ["stream", "streamtype", "stream_type"])
def test_explicit_stream_still_takes_precedence_over_ids(key):
    response = DeviceCgiResponse(
        "get.record.message", 0, {"record": {key: "custom", "ids": "2"}}, ""
    )
    assert parse_record_message_info(response).records[0].stream == "custom"


@pytest.mark.parametrize("idf", [None, "", "not-an-integer"])
def test_missing_picture_metadata_is_not_guessed(idf):
    response = DeviceCgiResponse(
        "get.record.message", 0, {"record": {"idf": idf}}, ""
    )
    record = parse_record_message_info(response).records[0]
    assert record.picture_index == ""
    assert record.frame_rate is None
    assert record.stream == ""


def test_new_fields_do_not_change_old_positional_constructor():
    raw = {"idx": "4"}
    record = DeviceRecordFileInfo(
        "id",
        "name",
        "picture",
        "event",
        "1",
        "start",
        "end",
        "sub",
        12,
        "url",
        raw,
    )
    assert record.raw is raw
    assert record.picture_index == "" and record.frame_rate is None


@pytest.mark.parametrize("page", [0, "0", "1", "2"])
def test_native_page_is_used_as_archive_completion_status(page):
    response = DeviceCgiResponse("get.record.message", 0, {"page": page}, "")
    assert parse_record_message_info(response).result == int(page)


def test_explicit_zero_result_takes_precedence_over_other_statuses():
    response = DeviceCgiResponse(
        "get.record.message", 0, {"result": 0, "status": 8, "page": 1}, ""
    )
    assert parse_record_message_info(response).result == 0


@pytest.mark.parametrize("blank", [None, ""])
def test_blank_result_keeps_legacy_status_fallback(blank):
    response = DeviceCgiResponse(
        "get.record.message", 0, {"result": blank, "status": "2"}, ""
    )
    assert parse_record_message_info(response).result == 2


@pytest.mark.parametrize(
    "parse", [parse_record_message_info, parse_record_alarm_info]
)
@pytest.mark.parametrize(
    "contents", ["<datalist></datalist><page>0</page>", "<page>0</page>"]
)
def test_real_empty_record_wrapper_is_not_a_phantom_file(parse, contents):
    response = parse_cgi_response(
        "get.record.message",
        f"<envelope><body><error>0</error><content><record>{contents}</record></content></body></envelope>",
    )
    result = parse(response)
    assert result.error == 0
    assert result.result == 0
    assert result.records == []


@pytest.mark.parametrize(
    "parse", [parse_record_message_info, parse_record_alarm_info]
)
def test_nested_record_page_and_real_files_are_parsed(parse):
    response = parse_cgi_response(
        "get.record.message",
        """<envelope><body><error>0</error><content><record>
        <datalist><data><filename>picture-name</filename><filetype>picture</filetype><idx>0</idx></data>
        <data><filename>video-name</filename><filetype>video</filetype><ids>1</ids><idf>25</idf></data></datalist>
        <page>1</page></record></content></body></envelope>""",
    )
    result = parse(response)
    assert result.result == 1
    assert [row.file_name for row in result.records] == [
        "picture-name",
        "video-name",
    ]
    assert result.records[0].picture_index == "0"
    assert result.records[1].frame_rate == 25
    assert result.records[1].stream == "main"


def test_nested_single_file_and_root_status_precedence():
    response = DeviceCgiResponse(
        "get.record.message",
        0,
        {
            "result": 0,
            "record": {
                "page": "1",
                "datalist": {
                    "data": {"filetype": "video", "filename": "name"}
                },
            },
        },
        "",
    )
    result = parse_record_message_info(response)
    assert result.result == 0
    assert len(result.records) == 1 and result.records[0].file_name == "name"


@pytest.mark.parametrize(
    "container",
    [
        {"record": ""},
        {"record": None},
        {"record": {}},
        {"record": [None, "", {}]},
        {"record": {"datalist": {"data": ""}, "page": "0"}},
        {"record": {"datalist": {"data": [None, "", {}]}, "page": "0"}},
    ],
)
def test_empty_or_scalar_record_nodes_do_not_become_files(container):
    response = DeviceCgiResponse("get.record.message", 0, container, "")
    assert parse_record_message_info(response).records == []
