from quii_helper.preview.processing.packets.processor_state import (
    process_chained_packet_blob,
    should_build_media_collection_summary,
)


def _fake_process_blob(calls: list[dict], results: list[object]):
    def process_blob(
        blob: bytes, *, source: str, meta: dict, phase: str
    ) -> tuple[bool, bytes]:
        calls.append(
            {"blob": blob, "source": source, "meta": meta, "phase": phase}
        )
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    return process_blob


class PreviewPacketProcessorStateTests:
    def test_process_chained_packet_buffers_short_header_without_callback(
        self,
    ) -> None:
        calls = []
        buffers = {}
        stats = {}

        stopped = process_chained_packet_blob(
            blob=b"short",
            source="direct",
            meta={},
            phase="live",
            buffers=buffers,
            stats=stats,
            process_blob=_fake_process_blob(calls, []),
            message_index_provider=lambda: 0,
        )

        assert not stopped
        assert [] == calls
        assert {("global", "direct"): b"short"} == buffers
        assert 1 == stats["buffered_packets"]
        assert 1 == stats["buffered_short_header"]

    def test_process_chained_packet_prepends_buffered_prefix(self) -> None:
        calls = []
        key = ("global", "direct")
        buffers = {key: b"prefix"}
        stats = {}

        process_chained_packet_blob(
            blob=b"x" * 32,
            source="direct",
            meta={},
            phase="live",
            buffers=buffers,
            stats=stats,
            process_blob=_fake_process_blob(calls, [(False, b"")]),
            message_index_provider=lambda: 0,
        )

        assert b"prefix" + b"x" * 32 == calls[0]["blob"]
        assert {} == buffers
        assert 1 == stats["buffered_prefixes"]
        assert 6 == stats["buffered_prefix_bytes"]

    def test_process_chained_packet_buffers_decode_error(self) -> None:
        calls = []
        buffers = {}
        stats = {}
        blob = b"x" * 32

        stopped = process_chained_packet_blob(
            blob=blob,
            source="direct",
            meta={},
            phase="live",
            buffers=buffers,
            stats=stats,
            process_blob=_fake_process_blob(calls, [ValueError("bad")]),
            message_index_provider=lambda: 0,
        )

        assert not stopped
        assert {("global", "direct"): blob} == buffers
        assert 1 == stats["buffered_decode_error"]

    def test_process_chained_packet_processes_remainder_with_meta(
        self,
    ) -> None:
        calls = []
        buffers = {}
        stats = {}
        remainder = b"y" * 36

        stopped = process_chained_packet_blob(
            blob=b"x" * 40,
            source="direct",
            meta={},
            phase="live",
            buffers=buffers,
            stats=stats,
            process_blob=_fake_process_blob(
                calls, [(False, remainder), (False, b"")]
            ),
            message_index_provider=lambda: 7,
        )

        assert not stopped
        assert 2 == len(calls)
        assert {
            "from_chained_msg_index": 7,
            "chained_packet": 1,
            "remainder_len": len(remainder),
        } == calls[1]["meta"]
        assert 1 == stats["split_remainders"]
        assert len(remainder) == stats["split_remainder_bytes"]

    def test_process_chained_packet_records_invalid_remainder(self) -> None:
        buffers = {}
        stats = {}
        blob = b"x" * 32

        stopped = process_chained_packet_blob(
            blob=blob,
            source="direct",
            meta={},
            phase="live",
            buffers=buffers,
            stats=stats,
            process_blob=_fake_process_blob([], [(False, blob)]),
            message_index_provider=lambda: 0,
        )

        assert not stopped
        assert {} == buffers
        assert 1 == stats["invalid_remainders"]

    def test_should_build_media_collection_summary_within_threshold_window(
        self,
    ) -> None:
        assert not should_build_media_collection_summary(
            media_message_count=0,
            min_media_messages=2,
            max_media_messages=4,
        )
        assert should_build_media_collection_summary(
            media_message_count=2,
            min_media_messages=2,
            max_media_messages=4,
        )
        assert should_build_media_collection_summary(
            media_message_count=3,
            min_media_messages=2,
            max_media_messages=4,
        )
        assert not should_build_media_collection_summary(
            media_message_count=4,
            min_media_messages=2,
            max_media_messages=4,
        )
