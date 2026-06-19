"""Preview use-case package."""

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CameraPreviewApplication": (
        "quii_helper.preview.application",
        "CameraPreviewApplication",
    ),
    "DEFAULT_PREVIEW_CAPTURE_SETTINGS": (
        "quii_helper.preview.config",
        "DEFAULT_PREVIEW_CAPTURE_SETTINGS",
    ),
    "PreviewCapturePipeline": (
        "quii_helper.preview.capture_pipeline",
        "PreviewCapturePipeline",
    ),
    "PreviewCaptureSettings": (
        "quii_helper.preview.config",
        "PreviewCaptureSettings",
    ),
    "PreviewPipelineFactory": (
        "quii_helper.preview.pipeline_factory",
        "PreviewPipelineFactory",
    ),
    "TunnelPacketStream": ("quii_helper.preview.stream", "TunnelPacketStream"),
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}"
        ) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value
