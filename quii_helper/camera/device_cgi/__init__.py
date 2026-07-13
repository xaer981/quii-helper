"""Camera-level read-only device CGI API."""

from quii_helper.camera.device_cgi.models import (
    CameraDeviceAllInfo,
    CameraDeviceLanInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceStorageDisk,
    CameraDeviceStorageInfo,
)
from quii_helper.camera.device_cgi.service import (
    DeviceCgiEndpoint,
    fetch_device_all_info,
    fetch_network_info,
    fetch_storage_info,
    resolve_device_cgi_endpoint,
)

__all__ = [
    "CameraDeviceAllInfo",
    "CameraDeviceLanInfo",
    "CameraDeviceNetworkInfo",
    "CameraDeviceStorageDisk",
    "CameraDeviceStorageInfo",
    "DeviceCgiEndpoint",
    "fetch_device_all_info",
    "fetch_network_info",
    "fetch_storage_info",
    "resolve_device_cgi_endpoint",
]
