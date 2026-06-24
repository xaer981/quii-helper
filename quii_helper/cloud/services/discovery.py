import ssl
import urllib.request

from quii_helper.cloud import get_device_token, login_cloud
from quii_helper.cloud.config.runtime import (
    resolve_runtime_config,
    validate_runtime_config,
)
from quii_helper.cloud.services.config_apply import apply_discovered_services
from quii_helper.cloud.services.discovery_state import (
    cloud_login_kwargs,
    device_token_kwargs,
    runtime_credentials_from_cloud_results,
    service_query_request_parts,
)
from quii_helper.cloud.services.query_parser import (
    parse_service_query_response,
)
from quii_helper.config import (
    AutonomousConfig,
    RuntimeCredentials,
    ServiceQueryResponse,
    validate_camera_app_config,
)


def query_service_addresses(
    config: AutonomousConfig,
    *,
    seq: int = 1,
    server_types: tuple[str, ...] = ("p2papp", "natcheck", "appinfo"),
) -> ServiceQueryResponse:
    request_url, xml_body, host = service_query_request_parts(
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
            "Host": host,
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
    cloud_username: str | None = None,
    cloud_account: str | None = None,
    cloud_password: str | None = None,
    client_id: str | None = None,
    auth_url: str | None = None,
    service_url: str | None = None,
    oem: str | None = None,
    app_id: int | None = None,
    client_type: int | None = None,
    ip_region_id: int | None = None,
) -> RuntimeCredentials:
    resolved = resolve_runtime_config(
        config,
        device_id=device_id,
        cloud_username=cloud_username,
        cloud_account=cloud_account,
        cloud_password=cloud_password,
        client_id=client_id,
        auth_url=auth_url,
        service_url=service_url,
        oem=oem,
        app_id=app_id,
        client_type=client_type,
        ip_region_id=ip_region_id,
    )
    validate_runtime_config(resolved)
    validate_camera_app_config(resolved)
    login = login_cloud(
        resolved.cloud_account,
        resolved.cloud_password,
        **cloud_login_kwargs(resolved),
    )
    token = get_device_token(
        login["session_id"],
        resolved.device_id,
        **device_token_kwargs(resolved),
    )
    return runtime_credentials_from_cloud_results(login=login, token=token)


def populate_discovered_services(
    config: AutonomousConfig,
) -> ServiceQueryResponse:
    validate_camera_app_config(config)
    response = query_service_addresses(config)
    apply_discovered_services(config, response)
    return response
