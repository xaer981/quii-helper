import gzip
import runpy
import urllib.error
import xml.etree.ElementTree as ET
from dataclasses import replace
from http.cookiejar import CookieJar
from unittest.mock import MagicMock, Mock

import pytest

from quii_helper import Camera, CameraCallEventPage
from quii_helper.cloud.alarms import service
from quii_helper.cloud.alarms.client import (
    build_alarm_login_query,
    build_call_event_query,
    parse_call_event_page,
    require_alarm_success,
)
from quii_helper.cloud.http import transport
from quii_helper.cloud.services.query_parser import (
    parse_service_query_response,
)
from quii_helper.config import (
    AutonomousConfig,
    ServiceEntry,
    ServiceQueryResponse,
)
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

QUERY = dict(page=0, page_size=15, max_id="0", start_time="", end_time="")


def _row(**overrides: str) -> ET.Element:
    row = ET.Element("data")
    values = {
        "id": "101",
        "alarmid": "alarm-1",
        "devid": "device-1",
        "chno": "1",
        "event": "19",
        "time": "2026-10-16 12:30:00",
        "alarmstate": "0",
        "msgstate": "1",
        "msgsavetype": "0",
    }
    values.update(overrides)
    for name, value in values.items():
        ET.SubElement(row, name).text = value
    return row


def _response(*rows: ET.Element) -> ET.Element:
    root = ET.fromstring(
        "<envelope><header><result>0</result></header><content>"
        "<maxid>101</maxid><totoalcnt>5</totoalcnt>"
        "<unreadcnt>2</unreadcnt><record/></content></envelope>"
    )
    record = root.find("content/record")
    assert record is not None
    record.extend(rows)
    return root


def _login_response(result: int = 0) -> ET.Element:
    return ET.fromstring(
        f"<envelope><header><result>{result}</result><session>"
        "<id>alarm-header-id</id><timeout>120</timeout></session>"
        "</header></envelope>"
    )


@pytest.fixture
def config() -> AutonomousConfig:
    return AutonomousConfig(
        device_id="device-1",
        cloud_account="test-account",
        cloud_password="test-password",
        auth_url="https://auth.example/UserLogin",
        service_url="https://service.example",
        oem="TEST",
        app_id=1,
        client_type=2,
        client_id="test-client",
        ip_region_id=3,
        tls_verify=False,
    )


@pytest.fixture
def cloud(monkeypatch: pytest.MonkeyPatch) -> dict[str, Mock]:
    mocks = {
        "query_service_addresses": Mock(
            return_value=ServiceQueryResponse(
                seq=1,
                timestamp=0,
                result=0,
                client_region_id=3,
                re_maxtime=0,
                ip_validity=0,
                servers=[
                    ServiceEntry(
                        server_type="alarmapp",
                        query_result=0,
                        region_id=3,
                        url="https://alarm.example/",
                        uri="/api/",
                    )
                ],
            )
        ),
        "login_cloud": Mock(
            return_value={
                "session_id": "test-session",
                "account_id": "account-1",
            }
        ),
        "request_userauth": Mock(
            side_effect=[
                (_login_response(), ""),
                (_response(_row()), ""),
            ]
        ),
    }
    for name, mock in mocks.items():
        monkeypatch.setattr(service, name, mock)
    return mocks


def test_request_matches_java_query_and_has_no_mutating_commands() -> None:
    query = build_call_event_query("session<&", "device<&", **QUERY)
    root = ET.fromstring(query)
    assert root.findtext("header/command") == "client-query-recordlist"
    assert root.findtext("header/flag") == "tdkcloud"
    assert root.findtext("header/seq") == "0"
    assert root.findtext("header/session") == "session<&"
    assert root.findtext("content/maxid") == "0"
    assert root.findtext("content/pageno") == "0"
    assert root.findtext("content/pagelinenum") == "15"
    assert root.findtext("content/filter/devid/id") == "device<&"
    assert root.findtext("content/filter/event/type") == "19"
    assert root.find("content/filter/peroid") is not None
    assert root.find("content/filter/period") is None
    assert set(child.tag for child in root) == {"header", "content"}
    assert b"client-login" not in query


def test_alarm_login_matches_native_fields_without_push_token(
    config: AutonomousConfig,
) -> None:
    config = replace(config, auth_url="https://auth.example:8443/auth/user")
    root = ET.fromstring(
        build_alarm_login_query(
            config,
            session_id="session<&",
            account_id="account<&",
        )
    )
    assert root.findtext("header/command") == "client-login"
    assert root.findtext("header/session") == "session<&"
    assert root.findtext("header/flag") == "tdkcloud"
    assert root.findtext("header/seq") == "0"
    assert root.findtext("content/account/id") == "account<&"
    assert root.findtext("content/account/authserver") == "auth.example"
    assert root.findtext("content/client/type") == "2"
    assert root.findtext("content/client/appid") == "1"
    assert root.findtext("content/client/oemid") == "TEST"
    assert root.findtext("content/client/tokentype") == "0"
    assert root.findtext("content/client/notifylang") == "en"
    client_id = root.findtext("content/client/id")
    assert client_id is not None and client_id.startswith("002-1-")
    assert client_id != f"002-1-{config.client_id}"
    assert root.find("content/client/token") is None
    assert root.find("content/hs") is None
    assert root.find("content/lt") is None
    assert root.find(".//password") is None


def test_reader_identity_is_stable_and_separate_for_each_account(
    config: AutonomousConfig,
) -> None:
    def reader_id(account: str) -> str | None:
        return ET.fromstring(
            build_alarm_login_query(
                config,
                session_id="session",
                account_id=account,
            )
        ).findtext("content/client/id")

    assert reader_id("account-1") == reader_id("account-1")
    assert reader_id("account-1") != reader_id("account-2")


@pytest.mark.parametrize("session,account", [("", "id"), ("session", "")])
def test_alarm_login_rejects_missing_identity(
    config: AutonomousConfig,
    session: str,
    account: str,
) -> None:
    with pytest.raises(QuiiConnectionError, match="session or account id"):
        build_alarm_login_query(config, session_id=session, account_id=account)


@pytest.mark.parametrize("url", ["not-a-url", "https://["])
def test_alarm_login_rejects_invalid_auth_host(
    config: AutonomousConfig,
    url: str,
) -> None:
    with pytest.raises(ConfigurationError):
        build_alarm_login_query(
            replace(config, auth_url=url),
            session_id="session",
            account_id="id",
        )


@pytest.mark.parametrize(
    "xml",
    [
        "<invalid/>",
        "<envelope/>",
        "<envelope><header><result>invalid</result></header></envelope>",
    ],
)
def test_alarm_login_requires_a_valid_acknowledgement(xml: str) -> None:
    with pytest.raises(QuiiConnectionError):
        require_alarm_success(
            ET.fromstring(xml), operation="alarm client-login"
        )


def test_parse_full_native_response_preserves_fields_and_hides_urls() -> None:
    row = _row(
        chname="Front door",
        alarminfo="Incoming call",
        alarmsource="panel",
        alarmsourcename="Entrance",
        recordresurl="https://media.example/video?token=private-resource",
        recordsubresurl="https://media.example/image?token=private-thumbnail",
    )
    ET.SubElement(row, "sensor").extend(
        ET.fromstring(
            "<sensor><id>sensor-1</id><ch>2</ch><name>Bell</name></sensor>"
        )
    )
    page = parse_call_event_page(_response(row), device_id="device-1")
    assert (page.max_id, page.total_count, page.unread_count) == ("101", 5, 2)
    event = page.events[0]
    assert (event.record_id, event.alarm_id) == ("101", "alarm-1")
    assert (event.device_id, event.channel) == ("device-1", 1)
    assert event.time == "2026-10-16 12:30:00"
    assert (
        event.alarm_state,
        event.message_state,
        event.message_save_type,
    ) == (0, 1, 0)
    assert (event.channel_name, event.alarm_info) == (
        "Front door",
        "Incoming call",
    )
    assert (event.source, event.source_name) == ("panel", "Entrance")
    assert (event.sensor_id, event.sensor_channel, event.sensor_name) == (
        "sensor-1",
        2,
        "Bell",
    )
    assert "private-resource" in event.record_url
    assert "private-thumbnail" in event.record_sub_url
    assert "private-resource" not in repr(page)
    assert "private-thumbnail" not in repr(page)


def test_ignore_handled_calls_other_alarms_and_other_devices() -> None:
    root = _response(
        _row(), _row(event="20"), _row(event="1"), _row(devid="other-device")
    )
    page = parse_call_event_page(root, device_id="device-1")
    assert [event.record_id for event in page.events] == ["101"]


def test_empty_record_is_a_valid_page() -> None:
    page = parse_call_event_page(_response(), device_id="device-1")
    assert page.events == []


@pytest.mark.parametrize(
    "xml",
    [
        "<error/>",
        "<envelope/>",
        "<envelope><header><result>invalid</result></header></envelope>",
        "<envelope><header><result>0</result></header><content/></envelope>",
        ET.tostring(_response(_row(chno="invalid")), encoding="unicode"),
        ET.tostring(_response(_row(alarmid="")), encoding="unicode"),
        ET.tostring(_response(), encoding="unicode").replace(
            "<totoalcnt>5</totoalcnt>", "<totoalcnt>-1</totoalcnt>"
        ),
    ],
)
def test_malformed_response_is_not_reported_as_empty_history(xml: str) -> None:
    with pytest.raises(QuiiConnectionError):
        parse_call_event_page(ET.fromstring(xml), device_id="device-1")


def test_session_error_is_described_by_its_native_name() -> None:
    root = ET.fromstring(
        "<envelope><header><result>1012</result></header></envelope>"
    )
    with pytest.raises(
        QuiiConnectionError, match="result=1012.*ALARM_RESULT_SESSION_ERROR"
    ):
        parse_call_event_page(root, device_id="device-1")


@pytest.mark.parametrize(
    "overrides",
    [
        {"page": -1},
        {"page": True},
        {"page_size": 0},
        {"page_size": 1.5},
        {"max_id": ""},
        {"max_id": "   "},
        {"max_id": None},
        {"start_time": "2026-10-16"},
        {"end_time": "2026-10-16 12:00:00Z"},
        {"start_time": "2026-02-30 00:00:00"},
        {
            "start_time": "2026-10-17 00:00:00",
            "end_time": "2026-10-16 00:00:00",
        },
    ],
)
def test_invalid_query_performs_no_network_io(
    config: AutonomousConfig, cloud: dict[str, Mock], overrides: dict
) -> None:
    with pytest.raises(ConfigurationError):
        service.fetch_call_events(config, **overrides)
    assert all(mock.call_count == 0 for mock in cloud.values())


def test_fetch_uses_separate_alarm_login_before_history_post(
    config: AutonomousConfig, cloud: dict[str, Mock]
) -> None:
    page = service.fetch_call_events(
        config,
        page=1,
        page_size=10,
        max_id="101",
        start_time="2026-10-16 00:00:00",
        end_time="2026-10-16 23:59:59",
    )
    assert len(page.events) == 1
    cloud["query_service_addresses"].assert_called_once_with(
        config, server_types=("alarmapp",)
    )
    assert cloud["login_cloud"].call_count == 1
    request = cloud["request_userauth"]
    assert request.call_count == 2
    alarm_login = ET.fromstring(request.call_args_list[0].args[0])
    assert alarm_login.findtext("header/command") == "client-login"
    assert alarm_login.findtext("content/account/id") == "account-1"
    assert alarm_login.find("content/client/token") is None
    jar = request.call_args.kwargs["cookie_jar"]
    assert isinstance(jar, CookieJar)
    assert jar is not cloud["login_cloud"].call_args.kwargs["cookie_jar"]
    assert request.call_args_list[0].kwargs["cookie_jar"] is jar
    assert request.call_args.kwargs == {
        "auth_url": "https://alarm.example/UserAlarm",
        "verify_tls": False,
        "cookie_jar": jar,
    }
    root = ET.fromstring(request.call_args.args[0])
    assert root.findtext("header/session") == "test-session"
    assert root.findtext("content/maxid") == "101"
    assert root.findtext("content/pageno") == "1"
    assert root.findtext("content/pagelinenum") == "10"
    assert (
        root.findtext("content/filter/peroid/start") == "2026-10-16 00:00:00"
    )
    assert root.findtext("content/filter/peroid/end") == "2026-10-16 23:59:59"


def test_native_pagination_anchor_is_kept_opaque(
    config: AutonomousConfig, cloud: dict[str, Mock]
) -> None:
    service.fetch_call_events(config, page=1, max_id="opaque:anchor<&")
    root = ET.fromstring(cloud["request_userauth"].call_args.args[0])
    assert root.findtext("content/maxid") == "opaque:anchor<&"


@pytest.mark.parametrize("query_result", [0, 1])
def test_discovery_accepts_reported_service_with_address(
    config: AutonomousConfig, cloud: dict[str, Mock], query_result: int
) -> None:
    cloud["query_service_addresses"].return_value = (
        parse_service_query_response(
            "<envelope><header><result>0</result></header><content><server>"
            f"<server-type>alarmapp</server-type><query-result>{query_result}"
            "</query-result><url>https://alarm.example</url><uri>/api</uri>"
            "</server></content></envelope>"
        )
    )
    page = service.fetch_call_events(config)
    assert len(page.events) == 1
    cloud["login_cloud"].assert_called_once()
    assert cloud["request_userauth"].call_args.kwargs["auth_url"] == (
        "https://alarm.example/UserAlarm"
    )


def test_call_history_decodes_gzip_at_the_original_alarm_endpoint(
    config: AutonomousConfig,
    cloud: dict[str, Mock],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cloud["query_service_addresses"].return_value.servers[
        0
    ].uri = "/wrong-route"
    response = MagicMock()
    response.read.return_value = gzip.compress(ET.tostring(_response(_row())))
    response.info.return_value = {"Content-Encoding": "gzip"}
    response.status = 200
    opener = MagicMock()
    opener.open.return_value.__enter__.return_value = response
    monkeypatch.setattr(
        transport, "build_cloud_opener", lambda **kwargs: opener
    )
    monkeypatch.setattr(
        service, "request_userauth", transport.request_userauth
    )

    page = service.fetch_call_events(config)

    assert [event.record_id for event in page.events] == ["101"]
    request = opener.open.call_args.args[0]
    assert request.full_url == "https://alarm.example/UserAlarm"
    assert ET.fromstring(request.data).findtext("header/command") == (
        "client-query-recordlist"
    )
    assert opener.open.call_count == 2


@pytest.mark.parametrize(
    "failure", ["global", "entry", "missing", "empty_url", "url"]
)
def test_discovery_failure_never_falls_back_to_another_host(
    config: AutonomousConfig, cloud: dict[str, Mock], failure: str
) -> None:
    response = cloud["query_service_addresses"].return_value
    if failure == "global":
        response.result = -1
        response.servers[0].query_result = 1
    elif failure == "entry":
        response.servers[0].query_result = -1
    elif failure == "missing":
        response.servers.clear()
    elif failure == "empty_url":
        response.servers[0].query_result = 1
        response.servers[0].url = ""
    else:
        response.servers[0].url = "file:///private"
    with pytest.raises(QuiiConnectionError):
        service.fetch_call_events(config)
    cloud["login_cloud"].assert_not_called()
    cloud["request_userauth"].assert_not_called()


def test_discovery_rejection_reports_codes_without_private_urls(
    config: AutonomousConfig, cloud: dict[str, Mock]
) -> None:
    response = cloud["query_service_addresses"].return_value
    response.result = -1
    response.servers[0].url = "https://private.example/?token=private-value"
    with pytest.raises(QuiiConnectionError) as exc_info:
        service.fetch_call_events(config)
    message = str(exc_info.value)
    assert "result=-1" in message
    assert "'alarmapp'(query_result=0, url_present=True)" in message
    assert "private.example" not in message
    assert "private-value" not in message
    cloud["login_cloud"].assert_not_called()


def test_missing_discovery_result_is_distinguishable_from_missing_service(
    config: AutonomousConfig, cloud: dict[str, Mock]
) -> None:
    cloud["query_service_addresses"].return_value = (
        parse_service_query_response(
            "<envelope><header><seq>1</seq></header><content><server>"
            "<server-type>alarmapp</server-type><query-result>0</query-result>"
            "<url>https://alarm.example</url></server></content></envelope>"
        )
    )
    with pytest.raises(QuiiConnectionError, match="result=-1.*'alarmapp'"):
        service.fetch_call_events(config)
    cloud["login_cloud"].assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError(),
        urllib.error.URLError("offline"),
        ET.ParseError(),
        urllib.error.HTTPError(
            "https://alarm.example", 403, "Denied", {}, None
        ),
    ],
)
def test_transport_errors_are_domain_errors(
    config: AutonomousConfig, cloud: dict[str, Mock], error: Exception
) -> None:
    cloud["request_userauth"].side_effect = error
    with pytest.raises(QuiiConnectionError):
        service.fetch_call_events(config)
    assert cloud["request_userauth"].call_count == 1


def test_camera_facade_never_opens_preview_or_fetches_device_token(
    config: AutonomousConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = replace(config, connection_mode="cloud")
    camera = Camera(config)
    camera.connector = Mock()
    fetch = Mock(return_value=CameraCallEventPage([], "0", 0, 0))
    monkeypatch.setattr("quii_helper.camera.api.fetch_call_events", fetch)
    assert camera.get_call_events() == CameraCallEventPage([], "0", 0, 0)
    fetch.assert_called_once_with(config, **QUERY)
    assert camera.connector.mock_calls == []


def test_missing_login_session_never_queries_journal(
    config: AutonomousConfig, cloud: dict[str, Mock]
) -> None:
    cloud["login_cloud"].return_value = {"session_id": ""}
    with pytest.raises(QuiiConnectionError, match="no session id"):
        service.fetch_call_events(config)
    cloud["request_userauth"].assert_not_called()


def test_missing_account_id_never_logs_alarm_client_in(
    config: AutonomousConfig,
    cloud: dict[str, Mock],
) -> None:
    cloud["login_cloud"].return_value = {"session_id": "test-session"}
    with pytest.raises(QuiiConnectionError, match="session or account id"):
        service.fetch_call_events(config)
    cloud["request_userauth"].assert_not_called()


@pytest.mark.parametrize("code", [1012, 1021])
def test_alarm_login_failure_stops_before_history_without_retry(
    config: AutonomousConfig,
    cloud: dict[str, Mock],
    code: int,
) -> None:
    cloud["request_userauth"].side_effect = [(_login_response(code), "")]
    with pytest.raises(
        QuiiConnectionError, match=f"client-login failed: result={code}"
    ):
        service.fetch_call_events(config)
    assert cloud["request_userauth"].call_count == 1


def test_expired_alarm_session_does_not_trigger_push_or_login_retry(
    config: AutonomousConfig,
    cloud: dict[str, Mock],
) -> None:
    cloud["request_userauth"].side_effect = [
        (_login_response(), ""),
        (_login_response(1012), ""),
    ]
    with pytest.raises(
        QuiiConnectionError, match="ALARM_RESULT_SESSION_ERROR"
    ):
        service.fetch_call_events(config)
    assert cloud["request_userauth"].call_count == 2


def test_example_only_reads_history(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    camera = Mock()
    camera.get_call_events.return_value = parse_call_event_page(
        _response(_row(recordresurl="https://media.example/private-token")),
        device_id="device-1",
    )
    factory = Mock(return_value=camera)
    load = Mock()
    configure = Mock()
    monkeypatch.setattr("quii_helper.Camera", factory)
    monkeypatch.setattr("quii_helper.load_config", load)
    monkeypatch.setattr("quii_helper.support.log.configure_logging", configure)
    monkeypatch.setattr(
        "quii_helper.config.settings_loader.dotenv_values",
        Mock(side_effect=AssertionError("unexpected .env read")),
    )
    runpy.run_module("examples.call_events", run_name="__main__")
    factory.assert_called_once_with(
        config=load.return_value, connection_mode="cloud"
    )
    load.assert_called_once_with()
    configure.assert_called_once_with(replace_existing=True)
    assert [call[0] for call in camera.mock_calls] == ["get_call_events"]
    output = capsys.readouterr().out
    assert "Incoming calls: 1" in output
    assert "private-token" not in output
