from typing import Any

from quii_helper.preview.pipeline.config import PreviewCaptureSettings


def remaining_pending_drain_seconds(
    settings: PreviewCaptureSettings,
    elapsed_seconds: float,
) -> float:
    return settings.pending_quii_drain_seconds - elapsed_seconds


def tunnel_has_pending_receive_stream_buffers(tunnel: Any) -> bool:
    has_pending_receive_streams = getattr(
        tunnel, "has_pending_receive_stream_buffers", None
    )
    return bool(has_pending_receive_streams and has_pending_receive_streams())


def tunnel_capture_summary_fields(tunnel: Any) -> dict[str, Any]:
    return {
        "tunnel_config": tunnel.config,
        "play_sync": tunnel.play_sync_summary(),
        "rbudp_fragments": tunnel.fragment_summary(),
        "stream_payload_count": tunnel.stream_payload_count,
        "stream_payload_filler_count": tunnel.stream_payload_filler_count,
        "stream_payload_early_count": tunnel.stream_payload_early_count,
        "stream_payload_early_filler_count": (
            tunnel.stream_payload_early_filler_count
        ),
    }


def processor_capture_summary_fields(processor: Any) -> dict[str, Any]:
    return {
        "decoded_messages": processor.decoded_messages,
        "media_messages": processor.media_messages,
        "fragmented_media": processor.fragmented_media_summary(),
        "quii_packet_chaining": processor.chained_packet_summary(),
        "implausible_direct_suppressed": (
            processor.implausible_direct_suppressed
        ),
    }


def pending_drain_summary_fields(
    *, packets: int, elapsed_seconds: float
) -> dict[str, Any]:
    return {
        "pending_quii_drain_packets": packets,
        "pending_quii_drain_elapsed_seconds": elapsed_seconds,
    }
