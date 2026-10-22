import xml.etree.ElementTree as ET
from datetime import datetime
from typing import cast
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from quii_helper.cloud.alarms.models import (
    CameraCallEvent,
    CameraCallEventPage,
)
from quii_helper.config import AutonomousConfig
from quii_helper.support.error_codes import describe_error_code
from quii_helper.support.errors import ConfigurationError, QuiiConnectionError

CALL_EVENT_TYPE = 19
CALL_QUERY_COMMAND = "client-query-recordlist"


def build_alarm_login_query(
    config: AutonomousConfig, *, session_id: str, account_id: str
) -> bytes:
    """Build the native client-login envelope without any push credentials.

    The dedicated UUID prevents reuse of the original Android client's id.
    Token, HS, and LT fields are deliberately absent, not empty placeholders.
    """
    try:
        auth_host = urlsplit(config.auth_url).hostname
    except ValueError:
        raise ConfigurationError("cloud auth URL is invalid") from None
    if not auth_host:
        raise ConfigurationError("cloud auth URL has no hostname")
    if not session_id.strip() or not account_id.strip():
        raise QuiiConnectionError(
            "cloud login returned no session or account id"
        )
    reader_uuid = uuid5(
        NAMESPACE_URL,
        f"quii-helper:call-history:{config.client_id}:{account_id}",
    )
    root = _alarm_envelope("client-login", session_id)
    content = ET.SubElement(root, "content")
    client = ET.SubElement(content, "client")
    for name, value in (
        ("id", f"00{config.client_type}-{config.app_id}-{reader_uuid}"),
        ("tokentype", "0"),  # SDK's Getui default, not a "push disabled" flag.
        ("type", str(config.client_type)),
        ("oemid", config.oem),
        ("appid", str(config.app_id)),
        ("notifylang", "en"),
    ):
        ET.SubElement(client, name).text = value
    account = ET.SubElement(content, "account")
    ET.SubElement(account, "id").text = account_id
    ET.SubElement(account, "authserver").text = auth_host
    return cast(
        bytes, ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )


def require_alarm_success(root: ET.Element, *, operation: str) -> None:
    """Reject malformed acknowledgements and preserve native alarm errors."""
    if root.tag != "envelope":
        raise QuiiConnectionError(f"invalid cloud {operation} envelope")
    result = _integer(root, "header/result")
    if result != 0:
        raise QuiiConnectionError(
            f"cloud {operation} failed: result={result}; "
            f"{describe_error_code(result, domain='sdk')}"
        )


def validate_call_event_query(
    *, page: int, page_size: int, max_id: str, start_time: str, end_time: str
) -> None:
    """Reject invalid paging and vendor-local time bounds before network I/O."""
    if type(page) is not int or page < 0:
        raise ConfigurationError("page must be a non-negative integer")
    if type(page_size) is not int or page_size <= 0:
        raise ConfigurationError("page_size must be a positive integer")
    if not isinstance(max_id, str) or not max_id.strip():
        raise ConfigurationError("max_id must be a non-empty string")
    for name, value in (("start_time", start_time), ("end_time", end_time)):
        if not isinstance(value, str):
            raise ConfigurationError(
                f"{name} must have format YYYY-MM-DD HH:MM:SS"
            )
        if value:
            try:
                parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                raise ConfigurationError(
                    f"{name} must have format YYYY-MM-DD HH:MM:SS"
                ) from None
            if parsed.strftime("%Y-%m-%d %H:%M:%S") != value:
                raise ConfigurationError(
                    f"{name} must have format YYYY-MM-DD HH:MM:SS"
                )
    if start_time and end_time and start_time > end_time:
        raise ConfigurationError("start_time must not be after end_time")


def build_call_event_query(
    session_id: str,
    device_id: str,
    *,
    page: int,
    page_size: int,
    max_id: str,
    start_time: str,
    end_time: str,
) -> bytes:
    """Mirror AlarmRequestHelper.getQueryAlarmListReq with a call-only filter."""
    root = _alarm_envelope(CALL_QUERY_COMMAND, session_id)
    content = ET.SubElement(root, "content")
    for name, value in (
        ("maxid", max_id),
        ("pageno", str(page)),
        ("pagelinenum", str(page_size)),
    ):
        ET.SubElement(content, name).text = value
    filters = ET.SubElement(content, "filter")
    ET.SubElement(ET.SubElement(filters, "devid"), "id").text = device_id
    ET.SubElement(ET.SubElement(filters, "event"), "type").text = str(
        CALL_EVENT_TYPE
    )
    # Both misspellings (peroid, totoalcnt) are part of the vendor wire format.
    period = ET.SubElement(filters, "peroid")
    if start_time:
        ET.SubElement(period, "start").text = start_time
    if end_time:
        ET.SubElement(period, "end").text = end_time
    return cast(
        bytes, ET.tostring(root, encoding="utf-8", xml_declaration=True)
    )


def parse_call_event_page(
    root: ET.Element, *, device_id: str
) -> CameraCallEventPage:
    """Parse AlarmListQueryResp, retaining only this camera's incoming calls."""
    require_alarm_success(root, operation="call history query")
    record = root.find("content/record")
    if record is None:
        raise QuiiConnectionError("cloud call history response has no record")
    events = []
    for row in record.findall("data"):
        if (
            _integer(row, "event") != CALL_EVENT_TYPE
            or _text(row, "devid") != device_id
        ):
            continue
        sensor_channel = row.findtext("sensor/ch")
        events.append(
            CameraCallEvent(
                record_id=_text(row, "id"),
                alarm_id=_text(row, "alarmid"),
                device_id=device_id,
                channel=_integer(row, "chno"),
                time=_text(row, "time"),
                alarm_state=_integer(row, "alarmstate"),
                message_state=_integer(row, "msgstate"),
                message_save_type=_integer(row, "msgsavetype"),
                channel_name=row.findtext("chname", ""),
                alarm_info=row.findtext("alarminfo", ""),
                source=row.findtext("alarmsource", ""),
                source_name=row.findtext("alarmsourcename", ""),
                sensor_id=row.findtext("sensor/id", ""),
                sensor_channel=(
                    _integer(row, "sensor/ch")
                    if sensor_channel is not None
                    else None
                ),
                sensor_name=row.findtext("sensor/name", ""),
                record_url=row.findtext("recordresurl", ""),
                record_sub_url=row.findtext("recordsubresurl", ""),
            )
        )
    total_count = _integer(root, "content/totoalcnt")
    unread_count = _integer(root, "content/unreadcnt")
    if total_count < 0 or unread_count < 0:
        raise QuiiConnectionError("negative cloud call history count")
    return CameraCallEventPage(
        events=events,
        max_id=_text(root, "content/maxid"),
        total_count=total_count,
        unread_count=unread_count,
    )


def _alarm_envelope(command: str, session_id: str) -> ET.Element:
    root = ET.Element("envelope")
    header = ET.SubElement(root, "header")
    for name, value in (
        ("command", command),
        ("flag", "tdkcloud"),
        ("seq", "0"),
        ("session", session_id),
    ):
        ET.SubElement(header, name).text = value
    return root


def _text(element: ET.Element, name: str) -> str:
    value = element.findtext(name)
    if value is None or not value.strip():
        raise QuiiConnectionError(
            f"cloud call history response missing {name}"
        )
    return value.strip()


def _integer(element: ET.Element, name: str) -> int:
    try:
        return int(_text(element, name))
    except ValueError:
        raise QuiiConnectionError(
            f"cloud call history response has invalid {name}"
        ) from None
