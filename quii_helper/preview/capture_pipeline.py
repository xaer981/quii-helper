import time
from dataclasses import dataclass
from typing import Any

from quii_helper.preview.config import PreviewCaptureSettings
from quii_helper.preview.media_summary import media_collection_summary
from quii_helper.preview.output_writer import PreviewOutputWriter
from quii_helper.preview.packet_processor import PreviewPacketProcessor
from quii_helper.preview.stream import TunnelPacketStream


@dataclass
class PreviewCapturePipeline:
    output_writer: PreviewOutputWriter
    preview_settings: PreviewCaptureSettings
    processor: PreviewPacketProcessor
    packet_stream: TunnelPacketStream
    tunnel: Any
    credentials: Any | None = None
    elapsed_seconds: float = 0.0
    pending_quii_drain_packets: int = 0
    pending_quii_drain_elapsed_seconds: float = 0.0

    def capture(self) -> dict:
        started_at = time.monotonic()
        tunnel_closed = False
        try:
            self._consume_live_packets()
            self._drain_pending_live_buffers()
            self._flush_fragment_partials()
            self._drain_pending_live_buffers()
            self._close_and_drain()
            tunnel_closed = True
            self.elapsed_seconds = time.monotonic() - started_at
            return self._build_capture_summary()
        finally:
            if not tunnel_closed:
                self.elapsed_seconds = time.monotonic() - started_at
            if not tunnel_closed:
                self.packet_stream.close()

    def _consume_live_packets(self) -> None:
        for packet in self.packet_stream.live_packets(
            duration=self.preview_settings.capture_seconds,
            timeout=5.0,
            keepalive_credentials=self.credentials,
        ):
            should_stop = self.processor.process_packet(packet, phase="live")
            if self.preview_settings.stop_when_decodable and should_stop:
                break

    def _flush_fragment_partials(self) -> None:
        for packet in self.packet_stream.flush_fragment_partials(
            drain_seconds=1.0, timeout=0.1
        ):
            self.processor.process_packet(packet, phase="flush")

    def _drain_pending_live_buffers(self) -> None:
        if not self._has_pending_live_buffers():
            return

        remaining_drain = (
            self.preview_settings.pending_quii_drain_seconds
            - self.pending_quii_drain_elapsed_seconds
        )
        if remaining_drain <= 0:
            return

        started_at = time.monotonic()
        for packet in self.packet_stream.drain_live(
            drain_seconds=remaining_drain,
            timeout=self.preview_settings.pending_quii_drain_timeout,
            keepalive_credentials=self.credentials,
        ):
            self.pending_quii_drain_packets += 1
            self.processor.process_packet(packet, phase="live")
            if not self._has_pending_live_buffers():
                break
        self.pending_quii_drain_elapsed_seconds += (
            time.monotonic() - started_at
        )

    def _has_pending_live_buffers(self) -> bool:
        if self.processor.has_pending_live_buffers():
            return True
        has_pending_receive_streams = getattr(
            self.tunnel, "has_pending_receive_stream_buffers", None
        )
        return bool(
            has_pending_receive_streams and has_pending_receive_streams()
        )

    def _close_and_drain(self) -> None:
        for packet in self.packet_stream.close_and_drain(
            drain_seconds=0.5, timeout=0.05
        ):
            self.processor.process_packet(packet, phase="close")

    def _build_capture_summary(self) -> dict:
        capture_artifacts = self.output_writer.write_capture_outputs(
            decoded_messages=self.processor.decoded_messages,
            fragment_partial_collector=(
                self.processor.fragment_partial_collector
            ),
            target_duration_seconds=self.preview_settings.capture_seconds,
        )
        common = {
            "capture_settings": {
                "capture_seconds": self.preview_settings.capture_seconds,
                "stop_when_decodable": (
                    self.preview_settings.stop_when_decodable
                ),
                "elapsed_seconds": round(self.elapsed_seconds, 3),
                "live_play_payload": getattr(
                    self.tunnel.config, "live_play_payload", ""
                ),
                "stream": getattr(self.tunnel.config, "stream", 0),
                "live_inner": getattr(self.tunnel.config, "live_inner", False),
                "live_newcn": getattr(self.tunnel.config, "live_newcn", False),
                "play_sync_iterations": getattr(
                    self.tunnel.config, "play_sync_iterations", 0
                ),
                "pending_quii_drain_seconds": (
                    self.preview_settings.pending_quii_drain_seconds
                ),
                "pending_quii_drain_packets": self.pending_quii_drain_packets,
                "pending_quii_drain_elapsed_seconds": round(
                    self.pending_quii_drain_elapsed_seconds, 3
                ),
            },
            "play_sync": self.tunnel.play_sync_summary(),
            "rbudp_fragments": self.tunnel.fragment_summary(),
            "fragmented_media": self.processor.fragmented_media_summary(),
            "quii_packet_chaining": self.processor.chained_packet_summary(),
            "media_collection": media_collection_summary(
                self.processor.media_messages
            ),
            "implausible_direct_suppressed": (
                self.processor.implausible_direct_suppressed
            ),
            "stream_payload_count": self.tunnel.stream_payload_count,
            "stream_payload_filler_count": (
                self.tunnel.stream_payload_filler_count
            ),
            "diagnostic_artifacts_saved": (
                self.preview_settings.save_diagnostic_artifacts
            ),
            "container_probe_summary": (
                capture_artifacts.container_probe_summary
            ),
            "cpacket_probe_summary": capture_artifacts.cpacket_probe_summary,
        }

        if self.processor.decoded_messages:
            return {
                "decoded_messages": len(self.processor.decoded_messages),
                "media_messages": len(self.processor.media_messages),
                **common,
                "media_result": capture_artifacts.media_result,
            }

        return {
            "decoded_messages": 0,
            **common,
            "stream_payload_early_count": (
                self.tunnel.stream_payload_early_count
            ),
            "stream_payload_early_filler_count": (
                self.tunnel.stream_payload_early_filler_count
            ),
            "embedded_fallback": capture_artifacts.embedded_fallback,
        }
