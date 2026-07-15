from quii_helper.cloud.oauth import fetch_oauth_access_token
from quii_helper.cloud.services.discovery import (
    fetch_runtime_credentials,
    query_service_addresses,
)
from quii_helper.cloud.shadow.client import request_device_shadow_info
from quii_helper.cloud.shadow.models import CameraDeviceShadowInfo
from quii_helper.config import (
    AutonomousConfig,
    RuntimeCredentials,
    ServiceEntry,
)
from quii_helper.support.errors import QuiiConnectionError

SHADOW_SERVICE_TYPES = ("iot", "openapi", "shadow")


def fetch_device_shadow_info(
    config: AutonomousConfig,
    *,
    credentials: RuntimeCredentials | None = None,
) -> CameraDeviceShadowInfo:
    """Fetch read-only cloud shadow status for `config.device_id`."""

    _ = credentials or fetch_runtime_credentials(config)
    token = fetch_oauth_access_token(config).access_token
    service_url = resolve_shadow_service_url(config)
    return request_device_shadow_info(
        service_url,
        token=token,
        thing_id=config.device_id,
        timeout=config.connect_timeout,
        verify_tls=config.tls_verify,
    )


def resolve_shadow_service_url(config: AutonomousConfig) -> str:
    """Resolve the cloud OpenAPI/IoT base URL used by device shadow."""

    response = query_service_addresses(
        config, server_types=SHADOW_SERVICE_TYPES
    )
    for service_type in SHADOW_SERVICE_TYPES:
        entry = response.find(service_type)
        if entry is not None and entry.url:
            return _entry_base_url(entry)
    available = ", ".join(entry.server_type for entry in response.servers)
    raise QuiiConnectionError(
        "query-hlrv2 did not return shadow service"
        + (f"; available: {available}" if available else "")
    )


def _entry_base_url(entry: ServiceEntry) -> str:
    base = entry.url.rstrip("/")
    uri = entry.uri.strip("/")
    return f"{base}/{uri}" if uri else base
