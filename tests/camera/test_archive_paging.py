"""Exercise public archive aggregation with the observed nested CGI shape."""

from unittest.mock import Mock

import pytest

from quii_helper.camera.device_cgi import service
from quii_helper.device.cgi.models import (
    DeviceCgiResponse,
    DeviceRecordSessionInfo,
)
from quii_helper.device.cgi.parser import parse_record_message_info


@pytest.mark.parametrize(
    "raw_pages,limit,names,completed",
    [
        ([{"datalist": "", "page": "0"}], 3, [], True),
        (
            [
                {
                    "datalist": {
                        "data": {
                            "filename": "one",
                            "filetype": "picture",
                            "idx": "0",
                        }
                    },
                    "page": "1",
                },
                {"datalist": "", "page": "0"},
            ],
            3,
            ["one"],
            True,
        ),
        (
            [{"datalist": "", "page": "1"}, {"datalist": "", "page": "1"}],
            2,
            [],
            False,
        ),
    ],
)
def test_nested_pages_complete_or_stop_at_cap_without_phantom_records(
    monkeypatch, raw_pages, limit, names, completed
):
    session = Mock(
        return_value=DeviceRecordSessionInfo(
            error=0, session_id="synthetic-search"
        )
    )
    pages = Mock(
        side_effect=[
            parse_record_message_info(
                DeviceCgiResponse("get.record.message", 0, {"record": raw}, "")
            )
            for raw in raw_pages
        ]
    )
    monkeypatch.setattr(service, "fetch_record_session_info", session)
    monkeypatch.setattr(service, "fetch_record_message_info", pages)
    result = service.fetch_record_list_info(
        service.DeviceCgiEndpoint(host="127.0.0.1", auth_code="synthetic"),
        start_time="2026-10-29t00:00:00z",
        end_time="2026-10-29t23:59:59z",
        max_pages=limit,
    )
    assert result.completed == completed
    assert [row.file_name for row in result.records] == names
    assert pages.call_count == len(raw_pages)
    assert result.error == 0
