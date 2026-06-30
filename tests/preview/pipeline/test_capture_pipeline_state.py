from types import SimpleNamespace

from quii_helper.preview.pipeline.capture_pipeline_state import (
    pending_drain_summary_fields,
    processor_capture_summary_fields,
    remaining_pending_drain_seconds,
    tunnel_capture_summary_fields,
    tunnel_has_pending_receive_stream_buffers,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings


class _FakeProcessor:
    decoded_messages = [{"decoded": True}]
    media_messages = [{"media": True}]
    implausible_direct_suppressed = 3

    def fragmented_media_summary(self) -> dict:
        return {"fragmented": True}

    def chained_packet_summary(self) -> dict:
        return {"chained": True}


class _FakeTunnel:
    config = SimpleNamespace(stream=1)
    stream_payload_count = 1
    stream_payload_filler_count = 2
    stream_payload_early_count = 3
    stream_payload_early_filler_count = 4

    def __init__(self, *, pending: bool = False) -> None:
        self.pending = pending

    def play_sync_summary(self) -> list:
        return [{"sync": True}]

    def fragment_summary(self) -> dict:
        return {"fragments": True}

    def has_pending_receive_stream_buffers(self) -> bool:
        return self.pending


class PreviewCapturePipelineStateTests:
    def test_remaining_pending_drain_seconds_subtracts_elapsed(self) -> None:
        settings = PreviewCaptureSettings(pending_quii_drain_seconds=12.0)

        assert 7.5 == remaining_pending_drain_seconds(settings, 4.5)

    def test_tunnel_has_pending_receive_stream_buffers_is_optional(
        self,
    ) -> None:
        assert not tunnel_has_pending_receive_stream_buffers(object())
        assert not tunnel_has_pending_receive_stream_buffers(_FakeTunnel())
        assert tunnel_has_pending_receive_stream_buffers(
            _FakeTunnel(pending=True)
        )

    def test_tunnel_capture_summary_fields_shape(self) -> None:
        fields = tunnel_capture_summary_fields(_FakeTunnel())

        assert 1 == fields["tunnel_config"].stream
        assert [{"sync": True}] == fields["play_sync"]
        assert {"fragments": True} == fields["rbudp_fragments"]
        assert 1 == fields["stream_payload_count"]
        assert 2 == fields["stream_payload_filler_count"]
        assert 3 == fields["stream_payload_early_count"]
        assert 4 == fields["stream_payload_early_filler_count"]

    def test_processor_capture_summary_fields_shape(self) -> None:
        fields = processor_capture_summary_fields(_FakeProcessor())

        assert [{"decoded": True}] == fields["decoded_messages"]
        assert [{"media": True}] == fields["media_messages"]
        assert {"fragmented": True} == fields["fragmented_media"]
        assert {"chained": True} == fields["quii_packet_chaining"]
        assert 3 == fields["implausible_direct_suppressed"]

    def test_pending_drain_summary_fields_shape(self) -> None:
        assert {
            "pending_quii_drain_packets": 5,
            "pending_quii_drain_elapsed_seconds": 1.25,
        } == (pending_drain_summary_fields(packets=5, elapsed_seconds=1.25))
