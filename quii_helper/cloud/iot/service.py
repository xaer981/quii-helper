from quii_helper.cloud.iot.client import request_iot_command_support
from quii_helper.cloud.iot.models import CameraIotCommandSupportInfo
from quii_helper.cloud.oauth import fetch_oauth_access_token
from quii_helper.cloud.services.discovery import (
    fetch_runtime_credentials,
    query_service_addresses,
)
from quii_helper.config import (
    AutonomousConfig,
    RuntimeCredentials,
    ServiceEntry,
)
from quii_helper.support.errors import QuiiConnectionError

IOT_SERVICE_TYPES = ("iot", "openapi", "shadow")


def fetch_iot_command_support(
    config: AutonomousConfig,
    *,
    credentials: RuntimeCredentials | None = None,
) -> CameraIotCommandSupportInfo:
    """Fetch read-only IoT/RRPC command support for `config.device_id`."""

    resolved_credentials = credentials or fetch_runtime_credentials(config)
    if not resolved_credentials.dynamic_password:
        raise QuiiConnectionError(
            "cloud device-token did not return dynamic password"
        )

    token = fetch_oauth_access_token(config).access_token
    service_url = resolve_iot_service_url(config)
    return request_iot_command_support(
        service_url,
        token=token,
        device_id=config.device_id,
        password=resolved_credentials.dynamic_password,
        timeout=config.connect_timeout,
        verify_tls=config.tls_verify,
    )


def resolve_iot_service_url(config: AutonomousConfig) -> str:
    """Resolve the cloud IoT control base URL used by native service type 8."""

    response = query_service_addresses(config, server_types=IOT_SERVICE_TYPES)
    for service_type in IOT_SERVICE_TYPES:
        entry = response.find(service_type)
        if entry is not None and entry.url:
            return _entry_base_url(entry)
    available = ", ".join(entry.server_type for entry in response.servers)
    raise QuiiConnectionError(
        "query-hlrv2 did not return IoT control service"
        + (f"; available: {available}" if available else "")
    )


def _entry_base_url(entry: ServiceEntry) -> str:
    base = entry.url.rstrip("/")
    uri = entry.uri.strip("/")
    return f"{base}/{uri}" if uri else base
