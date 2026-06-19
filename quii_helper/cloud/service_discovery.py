import ssl
import urllib.request
from dataclasses import replace
from urllib.parse import urlparse

from quii_helper.cloud import get_device_token, login_cloud
from quii_helper.cloud.service_config_apply import apply_discovered_services
from quii_helper.cloud.service_query_parser import parse_service_query_response
from quii_helper.cloud.service_query_xml import build_service_query_xml
from quii_helper.config import (
    DEFAULT_SERVICE_QUERY_PATH,
    AutonomousConfig,
    RuntimeCredentials,
    ServiceQueryResponse,
)


def query_service_addresses(
    config: AutonomousConfig,
    *,
    seq: int = 1,
    server_types: tuple[str, ...] = ("p2papp", "natcheck", "appinfo"),
) -> ServiceQueryResponse:
    service_url = config.service_url.rstrip("/")
    request_url = f"{service_url}{DEFAULT_SERVICE_QUERY_PATH}"
    xml_body = build_service_query_xml(
        config, seq=seq, server_types=server_types
    )

    ctx = ssl.create_default_context(cafile=str(config.ca_path))
    ctx.check_hostname = False
    ctx.load_cert_chain(
        certfile=str(config.cert_path), keyfile=str(config.key_path)
    )
    req = urllib.request.Request(
        request_url,
        data=xml_body,
        method="GET",
        headers={
            "Content-Type": "application/xml;charset=utf-8",
            "Host": urlparse(config.service_url).hostname or "",
        },
    )
    with urllib.request.urlopen(
        req, context=ctx, timeout=config.connect_timeout
    ) as resp:
        xml_text = resp.read().decode("utf-8", errors="ignore")

    return parse_service_query_response(xml_text)


def fetch_runtime_credentials(
    config: AutonomousConfig | str | None = None,
    *,
    device_id: str | None = None,
    cloud_account: str | None = None,
    cloud_password: str | None = None,
    client_id: str | None = None,
    ip_region_id: int | None = None,
) -> RuntimeCredentials:
    resolved = _resolve_runtime_config(
        config,
        device_id=device_id,
        cloud_account=cloud_account,
        cloud_password=cloud_password,
        client_id=client_id,
        ip_region_id=ip_region_id,
    )
    _validate_runtime_config(resolved)
    login = login_cloud(
        resolved.cloud_account,
        resolved.cloud_password,
        ip_region_id=resolved.ip_region_id,
        client_id=resolved.client_id,
        debug=False,
    )
    token = get_device_token(
        login["session_id"],
        resolved.device_id,
        client_id=resolved.client_id,
        debug=False,
    )
    return RuntimeCredentials(
        session_id=login["session_id"],
        dynamic_password=token["dynamic_password"],
        data_encode_key=token["data_encode_key"],
        auth_code=token["auth_code"],
        transparent_basedata=token["transparent_basedata"],
        raw={"login": login, "token": token},
    )


def _resolve_runtime_config(
    config: AutonomousConfig | str | None,
    *,
    device_id: str | None,
    cloud_account: str | None,
    cloud_password: str | None,
    client_id: str | None,
    ip_region_id: int | None,
) -> AutonomousConfig:
    if isinstance(config, AutonomousConfig):
        resolved = config
    else:
        resolved = (
            AutonomousConfig(device_id=config)
            if isinstance(config, str)
            else AutonomousConfig()
        )

    values = {
        key: value
        for key, value in {
            "device_id": device_id,
            "cloud_account": cloud_account,
            "cloud_password": cloud_password,
            "client_id": client_id,
            "ip_region_id": ip_region_id,
        }.items()
        if value is not None
    }
    return replace(resolved, **values) if values else resolved


def _validate_runtime_config(config: AutonomousConfig) -> None:
    missing = [
        name
        for name, value in {
            "device_id": config.device_id,
            "cloud_account": config.cloud_account,
            "cloud_password": config.cloud_password,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(
            f"missing required camera credentials: {', '.join(missing)}"
        )


def populate_discovered_services(
    config: AutonomousConfig,
) -> ServiceQueryResponse:
    response = query_service_addresses(config)
    apply_discovered_services(config, response)
    return response
