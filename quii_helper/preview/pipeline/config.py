from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewCaptureSettings:
    direct_blob_sample_limit: int = 16
    direct_blob_summary_limit: int = 16
    wrapped_tail_sample_limit: int = 16
    fragment_partial_sample_limit: int = 16
    save_diagnostic_artifacts: bool = False
    capture_seconds: float = 35.0
    stop_when_decodable: bool = True
    min_media_messages: int = 12
    max_media_messages: int = 160
    pending_quii_drain_seconds: float = 12.0
    pending_quii_drain_timeout: float = 0.25


DEFAULT_PREVIEW_CAPTURE_SETTINGS = PreviewCaptureSettings()
