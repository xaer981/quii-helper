from urllib.parse import urlparse

from quii_helper.cloud.services.query_xml import build_service_query_xml
from quii_helper.config import (
    DEFAULT_SERVICE_QUERY_PATH,
    AutonomousConfig,
    RuntimeCredentials,
)


def service_query_request_parts(
    config: AutonomousConfig,
    *,
    seq: int,
    server_types: tuple[str, ...],
) -> tuple[str, bytes, str]:
    service_url = config.service_url.rstrip("/")
    request_url = f"{service_url}{DEFAULT_SERVICE_QUERY_PATH}"
    xml_body = build_service_query_xml(
        config, seq=seq, server_types=server_types
    )
    host = urlparse(config.service_url).hostname or ""
    return request_url, xml_body, host


def cloud_login_kwargs(config: AutonomousConfig) -> dict:
    return {
        "auth_url": config.auth_url,
        "ip_region_id": config.ip_region_id,
        "client_id": config.client_id,
        "oem": config.oem,
        "app_id": config.app_id,
        "client_type": config.client_type,
        "debug": False,
    }


def device_token_kwargs(config: AutonomousConfig) -> dict:
    return {
        "auth_url": config.auth_url,
        "client_id": config.client_id,
        "oem": config.oem,
        "app_id": config.app_id,
        "client_type": config.client_type,
        "debug": False,
    }


def runtime_credentials_from_cloud_results(
    *, login: dict, token: dict
) -> RuntimeCredentials:
    return RuntimeCredentials(
        session_id=login["session_id"],
        dynamic_password=token["dynamic_password"],
        data_encode_key=token["data_encode_key"],
        auth_code=token["auth_code"],
        transparent_basedata=token["transparent_basedata"],
        raw={"login": login, "token": token},
    )
