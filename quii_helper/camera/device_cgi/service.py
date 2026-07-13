"""Camera-level read-only device CGI service."""

from dataclasses import dataclass

from quii_helper.config import AutonomousConfig, get_default_settings
from quii_helper.device.cgi import (
    DEFAULT_CGI_HTTP_PORT,
    DeviceAllInfo,
    DeviceNetworkInfo,
    DeviceStorageInfo,
    request_device_all_info,
    request_network_info,
    request_storage_info,
)
from quii_helper.support.errors import ConfigurationError


@dataclass(frozen=True)
class DeviceCgiEndpoint:
    """HTTP endpoint parameters for local `/tdkcgi` requests."""

    host: str
    port: int = DEFAULT_CGI_HTTP_PORT
    scheme: str = "http"
    auth_code: str = ""
    verify_tls: bool = True
    debug: bool = False


def resolve_device_cgi_endpoint(
    config: AutonomousConfig,
    *,
    host: str,
    port: int,
    scheme: str,
    auth_code: str | None,
    verify_tls: bool | None,
    debug: bool,
) -> DeviceCgiEndpoint:
    """Resolve local CGI endpoint settings for a `Camera` instance."""

    resolved_auth_code = auth_code
    if resolved_auth_code is None:
        resolved_auth_code = get_default_settings().auth_code
    if not resolved_auth_code:
        raise ConfigurationError(
            "AUTH_CODE is required for local /tdkcgi read-only requests; "
            "pass auth_code=... or set AUTH_CODE in .env"
        )
    return DeviceCgiEndpoint(
        host=host,
        port=port,
        scheme=scheme,
        auth_code=resolved_auth_code,
        verify_tls=config.tls_verify if verify_tls is None else verify_tls,
        debug=debug,
    )


def fetch_device_all_info(endpoint: DeviceCgiEndpoint) -> DeviceAllInfo:
    """Fetch read-only device status via `/tdkcgi`."""

    return request_device_all_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_storage_info(endpoint: DeviceCgiEndpoint) -> DeviceStorageInfo:
    """Fetch read-only storage status via `/tdkcgi`."""

    return request_storage_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_network_info(endpoint: DeviceCgiEndpoint) -> DeviceNetworkInfo:
    """Fetch read-only network settings via `/tdkcgi`."""

    return request_network_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )
