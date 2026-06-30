from typing import Any

from quii_helper.models.capture import MediaCollectionSummary


def capture_settings_summary(
    *,
    preview_settings: Any,
    elapsed_seconds: float,
    tunnel_config: Any,
    pending_quii_drain_packets: int,
    pending_quii_drain_elapsed_seconds: float,
) -> dict[str, Any]:
    return {
        "capture_seconds": preview_settings.capture_seconds,
        "stop_when_decodable": preview_settings.stop_when_decodable,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "live_play_payload": getattr(tunnel_config, "live_play_payload", ""),
        "stream": getattr(tunnel_config, "stream", 0),
        "live_inner": getattr(tunnel_config, "live_inner", False),
        "live_newcn": getattr(tunnel_config, "live_newcn", False),
        "play_sync_iterations": getattr(
            tunnel_config, "play_sync_iterations", 0
        ),
        "pending_quii_drain_seconds": (
            preview_settings.pending_quii_drain_seconds
        ),
        "pending_quii_drain_packets": pending_quii_drain_packets,
        "pending_quii_drain_elapsed_seconds": round(
            pending_quii_drain_elapsed_seconds, 3
        ),
    }


def common_capture_summary_fields(
    *,
    capture_settings: dict[str, Any],
    play_sync: list[dict[str, Any]],
    rbudp_fragments: dict[str, Any],
    fragmented_media: dict[str, Any],
    quii_packet_chaining: dict[str, int],
    media_collection: MediaCollectionSummary,
    implausible_direct_suppressed: int,
    stream_payload_count: int,
    stream_payload_filler_count: int,
    diagnostic_artifacts_saved: bool,
    container_probe_summary: dict[str, Any] | None,
    cpacket_probe_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "capture_settings": capture_settings,
        "play_sync": play_sync,
        "rbudp_fragments": rbudp_fragments,
        "fragmented_media": fragmented_media,
        "quii_packet_chaining": quii_packet_chaining,
        "media_collection": media_collection,
        "implausible_direct_suppressed": implausible_direct_suppressed,
        "stream_payload_count": stream_payload_count,
        "stream_payload_filler_count": stream_payload_filler_count,
        "diagnostic_artifacts_saved": diagnostic_artifacts_saved,
        "container_probe_summary": container_probe_summary,
        "cpacket_probe_summary": cpacket_probe_summary,
    }
