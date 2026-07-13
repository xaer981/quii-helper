"""Read-only client helpers for the device `/tdkcgi` endpoint."""

from quii_helper.device.cgi.models import (
    DeviceAllInfo,
    DeviceCgiResponse,
    DeviceNetworkInfo,
    DeviceStorageInfo,
)
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_device_all_info,
    parse_network_info,
    parse_storage_info,
)
from quii_helper.device.http.transport import request_cgi
from quii_helper.device.security.auth import encode_device_password

COMMAND_GET_DEVICE_ALL_INFO = "get.device.status"
COMMAND_GET_STORAGE_INFO = "get.hdd.base"
COMMAND_GET_NETWORK_INFO = "get.network.config"
DEFAULT_CGI_USERNAME = "adminapp2"
DEFAULT_CGI_HTTP_PORT = 80


def request_readonly_cgi(
    command: str,
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    username: str = DEFAULT_CGI_USERNAME,
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceCgiResponse:
    """Request a read-only CGI command using the original LAN auth header."""

    result = request_cgi(
        command=command,
        host=host,
        port=port,
        username=username,
        password=encode_device_password(auth_code),
        encrypted=False,
        scheme=scheme,
        passwordencode="1",
        verify_tls=verify_tls,
        debug=debug,
    )
    return parse_cgi_response(command, result["raw"])


def request_device_all_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceAllInfo:
    """Fetch `get.device.status` from `/tdkcgi`."""

    return parse_device_all_info(
        request_readonly_cgi(
            COMMAND_GET_DEVICE_ALL_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_storage_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceStorageInfo:
    """Fetch `get.hdd.base` from `/tdkcgi`."""

    return parse_storage_info(
        request_readonly_cgi(
            COMMAND_GET_STORAGE_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_network_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceNetworkInfo:
    """Fetch `get.network.config` from `/tdkcgi`."""

    return parse_network_info(
        request_readonly_cgi(
            COMMAND_GET_NETWORK_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )
