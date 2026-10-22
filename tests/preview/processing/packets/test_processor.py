from types import SimpleNamespace
from unittest.mock import patch

import pytest

from quii_helper.preview.pipeline.capture_pipeline import (
    PreviewCapturePipeline,
)
from quii_helper.preview.pipeline.config import PreviewCaptureSettings
from quii_helper.preview.processing.packets.processor import (
    PreviewPacketProcessor,
)


class _NoopFragmentPartialCollector:
    def analyze(
        self, blob: bytes, *, source: str, meta: dict, message_index: int
    ) -> None:
        return None


def _processor(
    *,
    diagnostics_enabled: bool = False,
) -> tuple[PreviewPacketProcessor, list[object]]:
    emitted = []
    processor = PreviewPacketProcessor(
        key="key",
        artifacts=SimpleNamespace(diagnostics_enabled=diagnostics_enabled),
        fragment_partial_collector=_NoopFragmentPartialCollector(),
        emit=emitted.append,
        min_media_messages=1,
        max_media_messages=3,
        direct_blob_summary_limit=16,
    )
    return processor, emitted


def _decoded(*, read_size: int, payload: bytes = b"payload") -> dict:
    return {
        "header": SimpleNamespace(
            packet_type=1,
            payload_size=len(payload),
            raw_size=read_size,
            flag15=0,
            flag16=0,
            flag17=0,
        ),
        "is_media": False,
        "plausible": True,
        "offset": 0,
        "payload": payload,
        "payload_raw": payload,
        "text_preview": "",
        "read_size": read_size,
        "body_available": read_size,
    }


def _implausible_decoded(
    *, read_size: int, payload: bytes = b"payload"
) -> dict:
    decoded = _decoded(read_size=read_size, payload=payload)
    decoded["plausible"] = False
    return decoded


class PreviewPacketProcessorTests:
    @pytest.mark.parametrize("stop_when_decodable", [False, True])
    def test_pipeline_threshold_does_not_drop_packets_from_received_blob(
        self, stop_when_decodable
    ):
        processor, _ = _processor()
        processor.media_messages.extend([{}, {}, {}])
        packet = {
            "payload": b"x" * 32 + b"body" + b"y" * 32 + b"tail",
            "source": "direct_quii_blob",
        }
        pipeline = PreviewCapturePipeline(
            output_writer=None,
            processor=processor,
            packet_stream=SimpleNamespace(
                live_packets=lambda **kwargs: iter([packet])
            ),
            preview_settings=PreviewCaptureSettings(
                stop_when_decodable=stop_when_decodable
            ),
            tunnel=None,
        )
        with patch.object(
            type(processor.decoder),
            "decode",
            side_effect=[_decoded(read_size=4), _decoded(read_size=4)],
        ):
            pipeline._consume_live_packets()
        assert len(processor.decoded_messages) == 2
        assert not processor.quii_packet_buffers

    @pytest.mark.parametrize("tail_size", [4, 36])
    def test_fragment_completion_keeps_remainder_despite_capture_threshold(
        self, tail_size
    ):
        processor, _ = _processor()
        processor.media_messages.extend([{}, {}, {}])
        key = ("rb_data", 1, 2)
        processor.fragmented_media_states[key] = {
            "body": b"",
            "expected_body_len": 40,
        }
        tail = b"t" * tail_size
        with (
            patch.object(
                processor.fragment_flow,
                "looks_like_new_media_packet",
                return_value=False,
            ),
            patch.object(
                processor.fragment_flow, "record_fragmented_media_decoded"
            ),
            patch(
                "quii_helper.preview.fragments.fragment_flow.append_fragmented_media",
                return_value=(
                    _decoded(read_size=0),
                    tail,
                    {"expected_body_len": 40},
                ),
            ),
            patch.object(
                type(processor.decoder),
                "decode",
                return_value=_decoded(read_size=4),
            ) as decode,
        ):
            assert processor.process_packet(
                {
                    "payload": b"c" * 80,
                    "source": "wrapped_quii",
                    "meta": {"src_id": 1, "dest_id": 2},
                },
                phase="live",
            )
        if tail_size < 32:
            assert processor.quii_packet_buffers == {key: tail}
            decode.assert_not_called()
        else:
            assert processor.quii_packet_buffers == {}
            decode.assert_called_once_with(tail)

    def test_process_packet_buffers_short_header_without_decoding(
        self,
    ) -> None:
        processor, emitted = _processor()

        stopped = processor.process_packet(
            {"payload": b"short", "source": "direct_quii_blob"},
            phase="live",
        )

        assert not stopped
        assert processor.quii_packet_buffers == {
            ("global", "direct_quii_blob"): b"short"
        }
        assert processor.chained_packet_stats["buffered_packets"] == 1
        assert processor.chained_packet_stats["buffered_packet_bytes"] == 5
        assert processor.chained_packet_stats["buffered_short_header"] == 1
        assert processor.message_index == 0
        assert emitted == []

    def test_process_packet_buffers_incomplete_decoded_packet(self) -> None:
        processor, emitted = _processor()
        blob = b"x" * 0x20
        decoded = _decoded(read_size=64)
        decoded["body_available"] = 10

        with patch(
            (
                "quii_helper.preview.processing."
                "packets.decoder.decode_quii_blob"
            ),
            return_value=decoded,
        ):
            stopped = processor.process_packet(
                {"payload": blob, "source": "direct_quii_blob"},
                phase="live",
            )

        assert not stopped
        assert processor.quii_packet_buffers == {
            ("global", "direct_quii_blob"): blob
        }
        assert processor.chained_packet_stats["buffered_packets"] == 1
        assert (
            processor.chained_packet_stats["buffered_incomplete_packet"] == 1
        )
        assert processor.message_index == 1
        assert processor.decoded_messages == []
        assert emitted == []

    def test_process_packet_processes_chained_remainder_in_order(self) -> None:
        processor, emitted = _processor()
        second_blob = b"s" * 0x20 + b"tail"
        blob = b"x" * 0x20 + b"body" + second_blob

        with patch(
            (
                "quii_helper.preview.processing."
                "packets.decoder.decode_quii_blob"
            ),
            side_effect=[
                _decoded(read_size=4, payload=b"body"),
                _decoded(read_size=4, payload=b"tail"),
            ],
        ):
            stopped = processor.process_packet(
                {"payload": blob, "source": "direct_quii_blob"},
                phase="live",
            )

        assert not stopped
        assert processor.message_index == 2
        assert len(processor.decoded_messages) == 2
        assert processor.chained_packet_stats["split_remainders"] == 1
        assert processor.chained_packet_stats["split_remainder_bytes"] == len(
            second_blob
        )
        assert len(emitted) == 2
        assert "meta" not in emitted[0]
        assert emitted[1]["meta"] == {
            "from_chained_msg_index": 1,
            "chained_packet": 1,
            "remainder_len": len(second_blob),
        }

    def test_process_packet_attaches_direct_decode_candidates(self) -> None:
        processor, emitted = _processor(diagnostics_enabled=True)
        blob = b"x" * 0x20 + b"body"
        candidates = [{"mode": "candidate"}]

        with (
            patch(
                (
                    "quii_helper.preview.processing."
                    "packets.decoder.decode_quii_blob"
                ),
                return_value=_implausible_decoded(
                    read_size=4,
                    payload=b"body",
                ),
            ),
            patch(
                "quii_helper.preview.processing.packets.diagnostics."
                "direct_blob_decode_candidates",
                return_value=candidates,
            ) as decode_candidates,
            patch(
                "quii_helper.preview.processing.packets.diagnostics."
                "record_direct_blob_sample",
            ) as record_sample,
        ):
            stopped = processor.process_packet(
                {"payload": blob, "source": "direct_quii_blob"},
                phase="live",
            )

        assert not stopped
        decode_candidates.assert_called_once()
        record_sample.assert_called_once()
        assert emitted[0]["decode_candidates"] == candidates
        assert processor.decoded_messages == []

    def test_process_packet_attaches_wrapped_tail_analysis(self) -> None:
        processor, emitted = _processor(diagnostics_enabled=True)
        blob = b"x" * 0x20 + b"body"
        tail_analysis = {"tail": "analysis"}

        with (
            patch(
                (
                    "quii_helper.preview.processing."
                    "packets.decoder.decode_quii_blob"
                ),
                return_value=_decoded(read_size=4, payload=b"body"),
            ),
            patch(
                "quii_helper.preview.processing.packets.diagnostics."
                "wrapped_tail_diagnostics",
                return_value=tail_analysis,
            ) as wrapped_tail,
        ):
            stopped = processor.process_packet(
                {"payload": blob, "source": "wrapped_quii"},
                phase="live",
            )

        assert not stopped
        wrapped_tail.assert_called_once()
        assert emitted[0]["wrapped_tail_analysis"] == tail_analysis
        assert len(processor.decoded_messages) == 1
