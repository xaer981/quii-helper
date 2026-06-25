from dataclasses import dataclass


@dataclass(frozen=True)
class PreviewCaptureSettings:
    """Low-level capture settings used by `Camera.capture()`.

    Attributes:
        direct_blob_sample_limit: Maximum direct blob samples kept for
            diagnostics.
        direct_blob_summary_limit: Maximum direct blob summary entries.
        wrapped_tail_sample_limit: Maximum wrapped packet tail samples.
        fragment_partial_sample_limit: Maximum partial fragment samples.
        save_diagnostic_artifacts: Whether to write diagnostic JSONL artifacts.
        capture_seconds: Default capture duration.
        stop_when_decodable: Stop early when enough H.264 data is available.
        min_media_messages: Minimum media message target before stopping.
        max_media_messages: Hard media message cap for one capture.
        pending_quii_drain_seconds: Drain window after capture for pending QUII
            packets.
        pending_quii_drain_timeout: Per-packet timeout while draining.
    """

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
