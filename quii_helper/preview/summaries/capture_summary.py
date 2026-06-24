from typing import Any

from quii_helper.preview.outputs.writer.output_writer import CaptureArtifacts
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.summaries.capture_summary_state import (
    capture_settings_summary,
    common_capture_summary_fields,
)
from quii_helper.preview.summaries.media_summary import (
    media_collection_summary,
)


def build_capture_summary(
    *,
    preview_settings: PreviewCaptureSettings,
    capture_artifacts: CaptureArtifacts,
    decoded_messages: list[dict],
    media_messages: list[dict],
    elapsed_seconds: float,
    tunnel_config: Any,
    play_sync: list[dict],
    rbudp_fragments: dict,
    fragmented_media: dict,
    quii_packet_chaining: dict,
    implausible_direct_suppressed: int,
    stream_payload_count: int,
    stream_payload_filler_count: int,
    stream_payload_early_count: int,
    stream_payload_early_filler_count: int,
    pending_quii_drain_packets: int,
    pending_quii_drain_elapsed_seconds: float,
) -> dict:
    common = common_capture_summary_fields(
        capture_settings=capture_settings_summary(
            preview_settings=preview_settings,
            elapsed_seconds=elapsed_seconds,
            tunnel_config=tunnel_config,
            pending_quii_drain_packets=pending_quii_drain_packets,
            pending_quii_drain_elapsed_seconds=(
                pending_quii_drain_elapsed_seconds
            ),
        ),
        play_sync=play_sync,
        rbudp_fragments=rbudp_fragments,
        fragmented_media=fragmented_media,
        quii_packet_chaining=quii_packet_chaining,
        media_collection=media_collection_summary(media_messages),
        implausible_direct_suppressed=implausible_direct_suppressed,
        stream_payload_count=stream_payload_count,
        stream_payload_filler_count=stream_payload_filler_count,
        diagnostic_artifacts_saved=(
            preview_settings.save_diagnostic_artifacts
        ),
        container_probe_summary=capture_artifacts.container_probe_summary,
        cpacket_probe_summary=capture_artifacts.cpacket_probe_summary,
    )

    if decoded_messages:
        return {
            "decoded_messages": len(decoded_messages),
            "media_messages": len(media_messages),
            **common,
            "media_result": capture_artifacts.media_result,
        }

    return {
        "decoded_messages": 0,
        **common,
        "stream_payload_early_count": stream_payload_early_count,
        "stream_payload_early_filler_count": stream_payload_early_filler_count,
        "embedded_fallback": capture_artifacts.embedded_fallback,
    }
