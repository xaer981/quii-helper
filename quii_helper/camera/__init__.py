"""High-level camera API."""

from quii_helper.camera.api import Camera
from quii_helper.camera.connection.session import (
    CameraConnector,
    CameraPreviewSession,
)
from quii_helper.camera.device_cgi import (
    CameraDeviceAllInfo,
    CameraDeviceCapabilitiesInfo,
    CameraDeviceGeneralInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceProductInfo,
    CameraDeviceScreenFlipInfo,
    CameraDeviceStorageInfo,
    CameraDeviceTimeInfo,
    CameraDeviceTimeTitleInfo,
    CameraDeviceVideoConfigInfo,
    CameraDeviceVideoSwitchInfo,
    CameraDeviceWifiListInfo,
)
from quii_helper.camera.metadata import CameraDeviceInfo
from quii_helper.camera.outputs.results import (
    CameraCaptureError,
    CameraCaptureResult,
)
from quii_helper.camera.settings import options

__all__ = [
    "Camera",
    "CameraCaptureError",
    "CameraCaptureResult",
    "CameraConnector",
    "CameraDeviceAllInfo",
    "CameraDeviceCapabilitiesInfo",
    "CameraDeviceGeneralInfo",
    "CameraDeviceInfo",
    "CameraDeviceNetworkInfo",
    "CameraPreviewSession",
    "CameraDeviceProductInfo",
    "CameraDeviceScreenFlipInfo",
    "CameraDeviceStorageInfo",
    "CameraDeviceTimeInfo",
    "CameraDeviceTimeTitleInfo",
    "CameraDeviceVideoConfigInfo",
    "CameraDeviceVideoSwitchInfo",
    "CameraDeviceWifiListInfo",
    "options",
]
