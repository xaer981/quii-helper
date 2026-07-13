"""Read-only helpers for the local device `/tdkcgi` endpoint."""

from quii_helper.device.cgi.client import (
    COMMAND_GET_DEVICE_ALL_INFO,
    COMMAND_GET_NETWORK_INFO,
    COMMAND_GET_STORAGE_INFO,
    DEFAULT_CGI_HTTP_PORT,
    DEFAULT_CGI_USERNAME,
    request_device_all_info,
    request_network_info,
    request_readonly_cgi,
    request_storage_info,
)
from quii_helper.device.cgi.models import (
    DeviceAllInfo,
    DeviceCgiResponse,
    DeviceLanInfo,
    DeviceNetworkInfo,
    DeviceStorageDisk,
    DeviceStorageInfo,
)

__all__ = [
    "COMMAND_GET_DEVICE_ALL_INFO",
    "COMMAND_GET_NETWORK_INFO",
    "COMMAND_GET_STORAGE_INFO",
    "DEFAULT_CGI_HTTP_PORT",
    "DEFAULT_CGI_USERNAME",
    "DeviceAllInfo",
    "DeviceCgiResponse",
    "DeviceLanInfo",
    "DeviceNetworkInfo",
    "DeviceStorageDisk",
    "DeviceStorageInfo",
    "request_device_all_info",
    "request_network_info",
    "request_readonly_cgi",
    "request_storage_info",
]
