import time
from dataclasses import dataclass
from typing import Any

from quii_helper.preview.outputs.writer.output_writer import (
    PreviewOutputWriter,
)
from quii_helper.preview.pipeline.capture_pipeline_state import (
    pending_drain_summary_fields,
    processor_capture_summary_fields,
    remaining_pending_drain_seconds,
    tunnel_capture_summary_fields,
    tunnel_has_pending_receive_stream_buffers,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.pipeline.stream import TunnelPacketStream
from quii_helper.preview.processing.packets.processor import (
    PreviewPacketProcessor,
)
from quii_helper.preview.summaries.capture_summary import build_capture_summary

LIVE_PACKET_TIMEOUT_SECONDS = 5.0
FRAGMENT_PARTIAL_DRAIN_SECONDS = 1.0
FRAGMENT_PARTIAL_PACKET_TIMEOUT_SECONDS = 0.1
CLOSE_DRAIN_SECONDS = 0.5
CLOSE_DRAIN_PACKET_TIMEOUT_SECONDS = 0.05


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
        stream_drained = False
        try:
            self._consume_live_packets()
            self._drain_pending_live_buffers()
            self._flush_fragment_partials()
            self._drain_pending_live_buffers()
            self._close_and_drain()
            stream_drained = True
            self.elapsed_seconds = time.monotonic() - started_at
            return self._build_capture_summary()
        finally:
            if not stream_drained:
                self.elapsed_seconds = time.monotonic() - started_at
                self.packet_stream.close()

    def _consume_live_packets(self) -> None:
        for packet in self.packet_stream.live_packets(
            duration=self.preview_settings.capture_seconds,
            timeout=LIVE_PACKET_TIMEOUT_SECONDS,
            keepalive_credentials=self.credentials,
        ):
            should_stop = self.processor.process_packet(packet, phase="live")
            if self.preview_settings.stop_when_decodable and should_stop:
                break

    def _flush_fragment_partials(self) -> None:
        for packet in self.packet_stream.flush_fragment_partials(
            drain_seconds=FRAGMENT_PARTIAL_DRAIN_SECONDS,
            timeout=FRAGMENT_PARTIAL_PACKET_TIMEOUT_SECONDS,
        ):
            self.processor.process_packet(packet, phase="flush")

    def _drain_pending_live_buffers(self) -> None:
        if not self._has_pending_live_buffers():
            return

        remaining_drain = remaining_pending_drain_seconds(
            self.preview_settings,
            self.pending_quii_drain_elapsed_seconds,
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
        return tunnel_has_pending_receive_stream_buffers(self.tunnel)

    def _close_and_drain(self) -> None:
        for packet in self.packet_stream.close_and_drain(
            drain_seconds=CLOSE_DRAIN_SECONDS,
            timeout=CLOSE_DRAIN_PACKET_TIMEOUT_SECONDS,
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
        return build_capture_summary(
            preview_settings=self.preview_settings,
            capture_artifacts=capture_artifacts,
            elapsed_seconds=self.elapsed_seconds,
            **processor_capture_summary_fields(self.processor),
            **tunnel_capture_summary_fields(self.tunnel),
            **pending_drain_summary_fields(
                packets=self.pending_quii_drain_packets,
                elapsed_seconds=self.pending_quii_drain_elapsed_seconds,
            ),
        )
