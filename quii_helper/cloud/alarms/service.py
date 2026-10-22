import urllib.error
import xml.etree.ElementTree as ET
from http.cookiejar import CookieJar
from urllib.parse import urlsplit

from quii_helper.cloud.alarms.client import (
    build_alarm_login_query,
    build_call_event_query,
    parse_call_event_page,
    require_alarm_success,
    validate_call_event_query,
)
from quii_helper.cloud.alarms.models import CameraCallEventPage
from quii_helper.cloud.authentication.auth import login_cloud
from quii_helper.cloud.config.runtime import validate_runtime_config
from quii_helper.cloud.http.transport import request_userauth
from quii_helper.cloud.services.discovery import query_service_addresses
from quii_helper.cloud.services.discovery_state import cloud_login_kwargs
from quii_helper.config import AutonomousConfig, validate_camera_app_config
from quii_helper.support.errors import QuiiConnectionError


def fetch_call_events(
    config: AutonomousConfig,
    *,
    page: int = 0,
    page_size: int = 15,
    max_id: str = "0",
    start_time: str = "",
    end_time: str = "",
) -> CameraCallEventPage:
    """Read UserAlarm after a tokenless login with an isolated reader identity."""
    validate_call_event_query(
        page=page,
        page_size=page_size,
        max_id=max_id,
        start_time=start_time,
        end_time=end_time,
    )
    validate_runtime_config(config)
    validate_camera_app_config(config)
    try:
        url = _resolve_alarm_url(config)
        login = login_cloud(
            config.cloud_account,
            config.cloud_password,
            **cloud_login_kwargs(config),
            cookie_jar=CookieJar(),
        )
        if not login.get("session_id"):
            raise QuiiConnectionError("cloud login returned no session id")
        cookie_jar = CookieJar()
        alarm_login = build_alarm_login_query(
            config,
            session_id=login["session_id"],
            account_id=login.get("account_id", ""),
        )
        root, _ = request_userauth(
            alarm_login,
            auth_url=url,
            verify_tls=config.tls_verify,
            cookie_jar=cookie_jar,
        )
        require_alarm_success(root, operation="alarm client-login")
        body = build_call_event_query(
            login["session_id"],
            config.device_id,
            page=page,
            page_size=page_size,
            max_id=max_id,
            start_time=start_time,
            end_time=end_time,
        )
        root, _ = request_userauth(
            body,
            auth_url=url,
            verify_tls=config.tls_verify,
            cookie_jar=cookie_jar,
        )
    except urllib.error.HTTPError as exc:
        raise QuiiConnectionError(
            f"cloud call history HTTP request failed: status={exc.code}"
        ) from exc
    except (OSError, ET.ParseError) as exc:
        if isinstance(exc, QuiiConnectionError):
            raise
        raise QuiiConnectionError(
            "could not read cloud call history; check cloud connectivity, "
            "TLS settings, and service-discovery assets"
        ) from exc
    return parse_call_event_page(root, device_id=config.device_id)


def _resolve_alarm_url(config: AutonomousConfig) -> str:
    response = query_service_addresses(config, server_types=("alarmapp",))
    entry = response.find("alarmapp")
    if (
        response.result != 0
        or entry is None
        # Native QvLocationManager accepts a discovered address; 1 is not
        # an error here, unlike the envelope's result field.
        or entry.query_result not in (0, 1)
        or not entry.url
    ):
        services = (
            ", ".join(
                f"{item.server_type!r}(query_result={item.query_result}, "
                f"url_present={bool(item.url)})"
                for item in response.servers
            )
            or "none"
        )
        raise QuiiConnectionError(
            "query-hlrv2 did not return a usable alarmapp service; "
            f"result={response.result}; services={services}"
        )
    base = entry.url.rstrip("/")
    # QvP2PClientV2 supplies address + "/" to Retrofit; uri is not an alarm path.
    try:
        parts = urlsplit(base)
        _ = parts.port
    except ValueError:
        raise QuiiConnectionError("invalid alarmapp service URL") from None
    if (
        parts.scheme not in ("http", "https")
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
    ):
        raise QuiiConnectionError("invalid alarmapp service URL")
    return f"{base}/UserAlarm"
