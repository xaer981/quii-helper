"""Typed payload models for preview capture summaries."""

from typing import Any, TypedDict


class H264NalUnitSummary(TypedDict, total=False):
    """Summary of one H.264 NAL unit inside an Annex-B stream."""

    offset: int
    start_code_len: int
    nal_type: int
    nal_name: str
    payload_len: int
    header_byte: str


class H264AnalysisSummary(TypedDict, total=False):
    """Analysis of an Annex-B H.264 byte stream."""

    stream_len: int
    start_code_count: int
    nal_count: int
    counts: dict[str, int]
    has_sps: bool
    has_pps: bool
    has_idr: bool
    has_vcl: bool
    has_sei: bool
    decodable_h264_context: bool
    false_positive_sps_only: bool
    epb_count: int
    largest_payload_len: int
    nal_units: list[H264NalUnitSummary]


class MediaFrameSummary(TypedDict, total=False):
    """Parsed media frame metadata included in artifact summaries."""

    payload_offset: int
    frame_tag: str
    frame_type: int
    frame_len: int
    frame_stamp: int
    codec: int
    fps: int
    width: int
    height: int
    nal_offset: int
    cframe_fragments: int


class MediaNalSample(TypedDict, total=False):
    """Compact H.264 sample attached to media collection summaries."""

    frame_tag: str
    frame_len: int
    cframe_fragments: int
    nal: H264AnalysisSummary


class MediaCollectionSummary(TypedDict, total=False):
    """Summary of media messages collected during preview capture."""

    media_messages: int
    media_frame_count: int
    cframe_pack: dict[str, int]
    media_decrypt_candidate_packets: int
    media_decrypt_candidate_bytes: int
    media_decrypt_packets: int
    media_decrypt_bytes: int
    keyframes: int
    has_sps: bool
    has_pps: bool
    has_idr: bool
    has_vcl: bool
    counts: dict[str, int]
    nal_samples: list[MediaNalSample]
    decodable_h264_context: bool


class MediaArtifactSummary(TypedDict, total=False):
    """Summary of files produced by media rendering."""

    stream_path: str
    mp4_path: str
    snapshot_path: str
    frames: list[MediaFrameSummary]
    summary: dict[str, Any]
    written: bool
    mp4: bool
    mp4_error: str
    snapshot: bool
    snapshot_error: str
    ffmpeg_skipped_reason: str
    embedded_fallback: dict[str, Any]


class CaptureSummary(TypedDict, total=False):
    """Top-level summary returned by the preview capture pipeline."""

    decoded_messages: int
    media_messages: int
    capture_settings: dict[str, Any]
    play_sync: list[dict[str, Any]]
    rbudp_fragments: dict[str, Any]
    fragmented_media: dict[str, Any]
    quii_packet_chaining: dict[str, int]
    media_collection: MediaCollectionSummary
    implausible_direct_suppressed: int
    stream_payload_count: int
    stream_payload_filler_count: int
    stream_payload_early_count: int
    stream_payload_early_filler_count: int
    diagnostic_artifacts_saved: bool
    container_probe_summary: dict[str, Any] | None
    cpacket_probe_summary: dict[str, Any] | None
    media_result: MediaArtifactSummary | None
    embedded_fallback: MediaArtifactSummary | None
