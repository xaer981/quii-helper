from types import SimpleNamespace

from quii_helper.preview.processing.packets.capture_stats import CaptureStats
from quii_helper.preview.processing.packets.diagnostics_collector import (
    PacketDiagnosticsResult,
)
from quii_helper.preview.processing.packets.recorder import (
    DecodedPacketRecorder,
)
from quii_helper.preview.processing.summaries.emitter import (
    PreviewSummaryEmitter,
)


class _FakeDiagnosticsCollector:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def collect(self, **kwargs):
        self.calls.append(kwargs)
        return PacketDiagnosticsResult(
            decode_candidates=[{"mode": "candidate"}],
            wrapped_tail_analysis={"tail": True},
            fragment_partial_analysis={"fragment": True},
        )


def _decoded() -> dict:
    return {
        "header": SimpleNamespace(
            packet_type=0xA0,
            payload_size=3,
            raw_size=3,
            flag15=0,
            flag16=0,
            flag17=0,
        ),
        "is_media": True,
        "plausible": True,
        "offset": 0,
        "payload": b"abc",
        "text_preview": "",
        "media_frame": {
            "frame_tag": 0xE1,
            "frame_len": 42,
            "frame_stamp": 123,
            "width": 960,
            "height": 576,
        },
    }


class DecodedPacketRecorderTests:
    def test_record_collects_diagnostics_stats_and_emits_summary(self) -> None:
        emitted = []
        decoded = _decoded()
        diagnostics = _FakeDiagnosticsCollector()
        stats = CaptureStats()
        recorder = DecodedPacketRecorder(
            diagnostics_collector=diagnostics,
            capture_stats=stats,
            summary_emitter=PreviewSummaryEmitter(
                emit=emitted.append,
                direct_blob_summary_limit=16,
            ),
        )

        summary = recorder.record(
            blob=b"x" * 32 + b"abc",
            decoded=decoded,
            message_index=7,
            source="wrapped_quii",
            meta={"src_id": 1},
            phase="live",
        )

        assert 1 == len(diagnostics.calls)
        assert decoded is diagnostics.calls[0]["decoded"]
        assert [decoded] == stats.decoded_messages
        assert [decoded] == stats.media_messages
        assert [summary] == emitted
        assert 7 == summary["msg_index"]
        assert {"src_id": 1} == summary["meta"]
        assert [{"mode": "candidate"}] == summary["decode_candidates"]
        assert {"tail": True} == summary["wrapped_tail_analysis"]
        assert {"fragment": True} == summary["fragment_partial_analysis"]
        assert "0xe1" == summary["frame_tag"]
        assert 42 == summary["frame_len"]
