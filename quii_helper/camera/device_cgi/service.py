"""Camera-level read-only device CGI service."""

from dataclasses import dataclass

from quii_helper.config import AutonomousConfig
from quii_helper.device.cgi import (
    DEFAULT_CGI_HTTP_PORT,
    DeviceAllInfo,
    DeviceCapabilitiesInfo,
    DeviceGeneralInfo,
    DeviceNetworkInfo,
    DeviceProductInfo,
    DeviceScreenFlipInfo,
    DeviceStorageInfo,
    DeviceTimeInfo,
    DeviceTimeTitleInfo,
    DeviceVideoConfigInfo,
    DeviceVideoSwitchInfo,
    DeviceWifiListInfo,
    request_device_all_info,
    request_network_info,
    request_product_info,
    request_screen_flip_info,
    request_storage_info,
    request_system_capabilities,
    request_system_general_info,
    request_time_info,
    request_time_title_info,
    request_video_config_info,
    request_video_switch_info,
    request_wifi_list_info,
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
    port: int,
    scheme: str,
    auth_code: str | None,
    verify_tls: bool | None,
    debug: bool,
) -> DeviceCgiEndpoint:
    """Resolve local CGI endpoint settings for a `Camera` instance."""

    host = config.device_host.strip()
    if not host:
        raise ConfigurationError(
            "CAMERA_DEVICE_HOST is required for local /tdkcgi read-only "
            "requests; set CAMERA_DEVICE_HOST in .env or pass "
            "device_host=... to Camera(...)"
        )
    resolved_auth_code = auth_code
    if resolved_auth_code is None:
        resolved_auth_code = config.auth_code
    if not resolved_auth_code:
        raise ConfigurationError(
            "AUTH_CODE is required for local /tdkcgi read-only requests; "
            "set AUTH_CODE in .env, pass auth_code=... to Camera(...), or "
            "pass auth_code=... to this method"
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


def fetch_product_info(endpoint: DeviceCgiEndpoint) -> DeviceProductInfo:
    """Fetch read-only product identity via `/tdkcgi`."""

    return request_product_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_time_info(endpoint: DeviceCgiEndpoint) -> DeviceTimeInfo:
    """Fetch read-only device time/timezone via `/tdkcgi`."""

    return request_time_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_wifi_list_info(endpoint: DeviceCgiEndpoint) -> DeviceWifiListInfo:
    """Fetch read-only Wi-Fi scan results via `/tdkcgi`."""

    return request_wifi_list_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_screen_flip_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceScreenFlipInfo:
    """Fetch read-only screen flip state via `/tdkcgi`."""

    return request_screen_flip_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_video_switch_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceVideoSwitchInfo:
    """Fetch read-only video switch state via `/tdkcgi`."""

    return request_video_switch_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_time_title_info(endpoint: DeviceCgiEndpoint) -> DeviceTimeTitleInfo:
    """Fetch read-only time-title overlay geometry via `/tdkcgi`."""

    return request_time_title_info(
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


def fetch_system_general_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceGeneralInfo:
    """Fetch read-only system general settings via `/tdkcgi`."""

    return request_system_general_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_system_capabilities(
    endpoint: DeviceCgiEndpoint,
) -> DeviceCapabilitiesInfo:
    """Fetch read-only system capabilities via `/tdkcgi`."""

    return request_system_capabilities(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )


def fetch_video_config_info(
    endpoint: DeviceCgiEndpoint,
) -> DeviceVideoConfigInfo:
    """Fetch read-only video encode configuration via `/tdkcgi`."""

    return request_video_config_info(
        host=endpoint.host,
        auth_code=endpoint.auth_code,
        port=endpoint.port,
        scheme=endpoint.scheme,
        verify_tls=endpoint.verify_tls,
        debug=endpoint.debug,
    )
