"""High-level camera API."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "Camera": ("quii_helper.camera.api", "Camera"),
    "CameraCaptureError": (
        "quii_helper.camera.outputs.results",
        "CameraCaptureError",
    ),
    "CameraCaptureResult": (
        "quii_helper.camera.outputs.results",
        "CameraCaptureResult",
    ),
    "CameraConnector": (
        "quii_helper.camera.connection.session",
        "CameraConnector",
    ),
    "CameraPreviewSession": (
        "quii_helper.camera.connection.session",
        "CameraPreviewSession",
    ),
    "options": ("quii_helper.camera.settings.options", None),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
