"""Preview use-case package."""

from quii_helper.support.lazy import lazy_exports

_EXPORTS = {
    "CameraPreviewApplication": (
        "quii_helper.preview.tools.application",
        "CameraPreviewApplication",
    ),
    "DEFAULT_PREVIEW_CAPTURE_SETTINGS": (
        "quii_helper.preview.pipeline.config",
        "DEFAULT_PREVIEW_CAPTURE_SETTINGS",
    ),
    "PreviewCapturePipeline": (
        "quii_helper.preview.pipeline.capture_pipeline",
        "PreviewCapturePipeline",
    ),
    "PreviewCaptureSettings": (
        "quii_helper.preview.pipeline.config",
        "PreviewCaptureSettings",
    ),
    "PreviewPipelineFactory": (
        "quii_helper.preview.pipeline.factory",
        "PreviewPipelineFactory",
    ),
    "TunnelPacketStream": (
        "quii_helper.preview.pipeline.stream",
        "TunnelPacketStream",
    ),
}

__all__, __getattr__ = lazy_exports(__name__, _EXPORTS, globals())
