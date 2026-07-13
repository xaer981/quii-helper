"""Stable public API for QUII camera helpers.

Internal protocol, preview, media, and diagnostic modules remain importable
through their direct module paths, but they are intentionally not re-exported
from the package root.
"""

from quii_helper.camera import (
    Camera,
    CameraCaptureError,
    CameraCaptureResult,
    CameraDeviceAllInfo,
    CameraDeviceInfo,
    CameraDeviceNetworkInfo,
    CameraDeviceStorageInfo,
)
from quii_helper.config import (
    AutonomousConfig,
    RuntimeCredentials,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.support.errors import (
    AssetMissingError,
    ConfigurationError,
    MediaRenderError,
    QuiiConnectionError,
    QuiiHelperError,
)

__all__ = [
    "AssetMissingError",
    "AutonomousConfig",
    "Camera",
    "CameraCaptureError",
    "CameraCaptureResult",
    "CameraDeviceAllInfo",
    "CameraDeviceInfo",
    "CameraDeviceNetworkInfo",
    "CameraDeviceStorageInfo",
    "ConfigurationError",
    "MediaRenderError",
    "PreviewCaptureSettings",
    "QuiiConnectionError",
    "QuiiHelperError",
    "RuntimeCredentials",
]
