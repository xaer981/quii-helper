from types import SimpleNamespace

import pytest

from quii_helper.preview.outputs.writer.output_writer import CaptureArtifacts
from quii_helper.preview.pipeline.capture_pipeline import (
    PreviewCapturePipeline,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings


class _FakeOutputWriter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def write_capture_outputs(self, **kwargs: object) -> CaptureArtifacts:
        self.calls.append(kwargs)
        return CaptureArtifacts(
            media_result={"written": True},
            embedded_fallback=None,
            container_probe_summary=None,
            cpacket_probe_summary=None,
        )


class _FakeProcessor:
    def __init__(self) -> None:
        self.decoded_messages = [{"decoded": True}]
        self.media_messages = []
        self.fragment_partial_collector = object()
        self.implausible_direct_suppressed = 0
        self.calls: list[tuple[str, dict]] = []

    def process_packet(self, packet: dict, *, phase: str) -> bool:
        self.calls.append((phase, packet))
        return False

    def has_pending_live_buffers(self) -> bool:
        return False

    def fragmented_media_summary(self) -> dict:
        return {}

    def chained_packet_summary(self) -> dict:
        return {}


class _FakePacketStream:
    def __init__(self, *, raise_on_live: bool = False) -> None:
        self.raise_on_live = raise_on_live
        self.live = [{"packet": "live"}]
        self.flush = [{"packet": "flush"}]
        self.close_packets = [{"packet": "close"}]
        self.calls: list[tuple[str, dict]] = []
        self.closed = False

    def live_packets(self, **kwargs: object):
        self.calls.append(("live_packets", kwargs))
        if self.raise_on_live:
            raise RuntimeError("live failed")
        yield from self.live

    def drain_live(self, **kwargs: object):
        self.calls.append(("drain_live", kwargs))
        return iter(())

    def flush_fragment_partials(self, **kwargs: object):
        self.calls.append(("flush_fragment_partials", kwargs))
        yield from self.flush

    def close_and_drain(self, **kwargs: object):
        self.calls.append(("close_and_drain", kwargs))
        yield from self.close_packets

    def close(self) -> None:
        self.closed = True


class _FakeTunnel:
    config = SimpleNamespace(
        live_play_payload="path",
        stream=1,
        live_inner=False,
        live_newcn=True,
        play_sync_iterations=0,
    )
    stream_payload_count = 0
    stream_payload_filler_count = 0
    stream_payload_early_count = 0
    stream_payload_early_filler_count = 0

    def play_sync_summary(self) -> list:
        return []

    def fragment_summary(self) -> dict:
        return {}

    def has_pending_receive_stream_buffers(self) -> bool:
        return False


class PreviewCapturePipelineTests:
    def _pipeline(self, *, raise_on_live: bool = False) -> tuple[
        PreviewCapturePipeline,
        _FakeOutputWriter,
        _FakeProcessor,
        _FakePacketStream,
    ]:
        output_writer = _FakeOutputWriter()
        processor = _FakeProcessor()
        packet_stream = _FakePacketStream(raise_on_live=raise_on_live)
        settings = PreviewCaptureSettings(
            capture_seconds=2.0,
            stop_when_decodable=False,
        )
        pipeline = PreviewCapturePipeline(
            output_writer=output_writer,
            preview_settings=settings,
            processor=processor,
            packet_stream=packet_stream,
            tunnel=_FakeTunnel(),
            credentials=object(),
        )
        return pipeline, output_writer, processor, packet_stream

    def test_capture_processes_live_flush_close_and_writes_summary(
        self,
    ) -> None:
        pipeline, output_writer, processor, packet_stream = self._pipeline()

        summary = pipeline.capture()

        assert not packet_stream.closed
        assert pipeline.elapsed_seconds >= 0
        assert [
            ("live", {"packet": "live"}),
            ("flush", {"packet": "flush"}),
            ("close", {"packet": "close"}),
        ] == (processor.calls)
        assert [
            "live_packets",
            "flush_fragment_partials",
            "close_and_drain",
        ] == ([name for name, _kwargs in packet_stream.calls])
        assert {
            "duration": 2.0,
            "timeout": 5.0,
            "keepalive_credentials": pipeline.credentials,
        } == (packet_stream.calls[0][1])
        assert {"drain_seconds": 1.0, "timeout": 0.1} == (
            packet_stream.calls[1][1]
        )
        assert {"drain_seconds": 0.5, "timeout": 0.05} == (
            packet_stream.calls[2][1]
        )
        assert 2.0 == (output_writer.calls[0]["target_duration_seconds"])
        assert 1 == summary["decoded_messages"]
        assert {"written": True} == summary["media_result"]

    def test_capture_closes_packet_stream_after_live_exception(self) -> None:
        pipeline, output_writer, _processor, packet_stream = self._pipeline(
            raise_on_live=True
        )

        with pytest.raises(RuntimeError):
            pipeline.capture()

        assert packet_stream.closed
        assert pipeline.elapsed_seconds >= 0
        assert [] == output_writer.calls
