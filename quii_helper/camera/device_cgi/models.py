"""Camera-facing aliases for read-only device CGI models."""

from quii_helper.device.cgi import (
    DeviceAllInfo as CameraDeviceAllInfo,
)
from quii_helper.device.cgi import (
    DeviceLanInfo as CameraDeviceLanInfo,
)
from quii_helper.device.cgi import (
    DeviceNetworkInfo as CameraDeviceNetworkInfo,
)
from quii_helper.device.cgi import (
    DeviceStorageDisk as CameraDeviceStorageDisk,
)
from quii_helper.device.cgi import (
    DeviceStorageInfo as CameraDeviceStorageInfo,
)

__all__ = [
    "CameraDeviceAllInfo",
    "CameraDeviceLanInfo",
    "CameraDeviceNetworkInfo",
    "CameraDeviceStorageDisk",
    "CameraDeviceStorageInfo",
]
