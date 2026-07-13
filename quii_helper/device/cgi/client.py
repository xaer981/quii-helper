"""Read-only client helpers for the device `/tdkcgi` endpoint."""

from quii_helper.device.cgi.models import (
    DeviceAllInfo,
    DeviceCapabilitiesInfo,
    DeviceCgiResponse,
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
)
from quii_helper.device.cgi.parser import (
    parse_cgi_response,
    parse_device_all_info,
    parse_network_info,
    parse_product_info,
    parse_screen_flip_info,
    parse_storage_info,
    parse_system_capabilities,
    parse_system_general_info,
    parse_time_info,
    parse_time_title_info,
    parse_video_config_info,
    parse_video_switch_info,
    parse_wifi_list_info,
)
from quii_helper.device.http.transport import request_cgi
from quii_helper.device.security.auth import encode_device_password

COMMAND_GET_DEVICE_ALL_INFO = "get.device.status"
COMMAND_GET_STORAGE_INFO = "get.hdd.base"
COMMAND_GET_NETWORK_INFO = "get.network.config"
COMMAND_GET_SYSTEM_GENERAL = "get.system.general"
COMMAND_GET_SYSTEM_ABILITY = "get.system.ability"
COMMAND_GET_VIDEO_CONFIG = "get.encode"
COMMAND_GET_PRODUCT_INFO = "get.product.info"
COMMAND_GET_TIME_INFO = "get.product.time"
COMMAND_GET_WIFI_LIST = "get.wifi.list"
COMMAND_GET_SCREEN_FLIP = "get.shape.mirror"
COMMAND_GET_VIDEO_SWITCH = "get.videoswitch.vionoff"
COMMAND_GET_TIME_TITLE = "get.video.timetitle"
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


def request_product_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceProductInfo:
    """Fetch `get.product.info` from `/tdkcgi`."""

    return parse_product_info(
        request_readonly_cgi(
            COMMAND_GET_PRODUCT_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_time_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceTimeInfo:
    """Fetch `get.product.time` from `/tdkcgi`."""

    return parse_time_info(
        request_readonly_cgi(
            COMMAND_GET_TIME_INFO,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_wifi_list_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceWifiListInfo:
    """Fetch `get.wifi.list` from `/tdkcgi`."""

    return parse_wifi_list_info(
        request_readonly_cgi(
            COMMAND_GET_WIFI_LIST,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_screen_flip_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceScreenFlipInfo:
    """Fetch `get.shape.mirror` from `/tdkcgi`."""

    return parse_screen_flip_info(
        request_readonly_cgi(
            COMMAND_GET_SCREEN_FLIP,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_video_switch_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceVideoSwitchInfo:
    """Fetch `get.videoswitch.vionoff` from `/tdkcgi`."""

    return parse_video_switch_info(
        request_readonly_cgi(
            COMMAND_GET_VIDEO_SWITCH,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_time_title_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceTimeTitleInfo:
    """Fetch `get.video.timetitle` from `/tdkcgi`."""

    return parse_time_title_info(
        request_readonly_cgi(
            COMMAND_GET_TIME_TITLE,
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


def request_system_general_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceGeneralInfo:
    """Fetch `get.system.general` from `/tdkcgi`."""

    return parse_system_general_info(
        request_readonly_cgi(
            COMMAND_GET_SYSTEM_GENERAL,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_system_capabilities(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceCapabilitiesInfo:
    """Fetch `get.system.ability` from `/tdkcgi`."""

    return parse_system_capabilities(
        request_readonly_cgi(
            COMMAND_GET_SYSTEM_ABILITY,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )


def request_video_config_info(
    *,
    host: str,
    auth_code: str,
    port: int = DEFAULT_CGI_HTTP_PORT,
    scheme: str = "http",
    verify_tls: bool = True,
    debug: bool = False,
) -> DeviceVideoConfigInfo:
    """Fetch `get.encode` from `/tdkcgi`."""

    return parse_video_config_info(
        request_readonly_cgi(
            COMMAND_GET_VIDEO_CONFIG,
            host=host,
            auth_code=auth_code,
            port=port,
            scheme=scheme,
            verify_tls=verify_tls,
            debug=debug,
        )
    )
