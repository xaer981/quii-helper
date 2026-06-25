import unittest

from quii_helper.preview.processing.packets.processor_state import (
    process_chained_packet_blob,
    record_processed_packet,
    should_build_media_collection_summary,
)


class _FakeEmitter:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def emit_packet_summary(
        self, summary: dict, *, source: str, decoded: dict
    ) -> None:
        self.calls.append(
            {"summary": summary, "source": source, "decoded": decoded}
        )


def _decoded(*, plausible: bool = True, media_frame: dict | None = None):
    decoded = {"plausible": plausible}
    if media_frame is not None:
        decoded["media_frame"] = media_frame
    return decoded


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


class PreviewPacketProcessorStateTests(unittest.TestCase):
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

        self.assertFalse(stopped)
        self.assertEqual([], calls)
        self.assertEqual({("global", "direct"): b"short"}, buffers)
        self.assertEqual(1, stats["buffered_packets"])
        self.assertEqual(1, stats["buffered_short_header"])

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

        self.assertEqual(b"prefix" + b"x" * 32, calls[0]["blob"])
        self.assertEqual({}, buffers)
        self.assertEqual(1, stats["buffered_prefixes"])
        self.assertEqual(6, stats["buffered_prefix_bytes"])

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

        self.assertFalse(stopped)
        self.assertEqual({("global", "direct"): blob}, buffers)
        self.assertEqual(1, stats["buffered_decode_error"])

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

        self.assertFalse(stopped)
        self.assertEqual(2, len(calls))
        self.assertEqual(
            {
                "from_chained_msg_index": 7,
                "chained_packet": 1,
                "remainder_len": len(remainder),
            },
            calls[1]["meta"],
        )
        self.assertEqual(1, stats["split_remainders"])
        self.assertEqual(len(remainder), stats["split_remainder_bytes"])

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

        self.assertFalse(stopped)
        self.assertEqual({}, buffers)
        self.assertEqual(1, stats["invalid_remainders"])

    def test_record_processed_packet_appends_plausible_decoded_messages(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        emitter = _FakeEmitter()
        decoded = _decoded(plausible=True)
        summary = {}

        record_processed_packet(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            summary=summary,
            decoded=decoded,
            source="direct",
            phase="live",
        )

        self.assertEqual([decoded], decoded_messages)
        self.assertEqual([], media_messages)
        self.assertEqual(
            [{"summary": summary, "source": "direct", "decoded": decoded}],
            emitter.calls,
        )

    def test_record_processed_packet_suppresses_implausible_decoded_append(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        emitter = _FakeEmitter()
        decoded = _decoded(plausible=False)

        record_processed_packet(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            summary={},
            decoded=decoded,
            source="direct",
            phase="live",
        )

        self.assertEqual([], decoded_messages)
        self.assertEqual([], media_messages)
        self.assertEqual(1, len(emitter.calls))

    def test_record_processed_packet_appends_live_media_and_updates_summary(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        emitter = _FakeEmitter()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )
        summary = {}

        record_processed_packet(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            summary=summary,
            decoded=decoded,
            source="direct",
            phase="live",
        )

        self.assertEqual([decoded], decoded_messages)
        self.assertEqual([decoded], media_messages)
        self.assertEqual("0xe1", summary["frame_tag"])
        self.assertEqual(42, summary["frame_len"])

    def test_record_processed_packet_can_stream_media_without_storing(
        self,
    ) -> None:
        decoded_messages = []
        media_messages = []
        streamed = []
        emitter = _FakeEmitter()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )

        record_processed_packet(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            summary={},
            decoded=decoded,
            source="direct",
            phase="live",
            media_message_sink=streamed.append,
            store_media_messages=False,
        )

        self.assertEqual([decoded], decoded_messages)
        self.assertEqual([], media_messages)
        self.assertEqual([decoded], streamed)

    def test_record_processed_packet_does_not_append_flush_media(self) -> None:
        decoded_messages = []
        media_messages = []
        emitter = _FakeEmitter()
        decoded = _decoded(
            media_frame={
                "frame_tag": 0xE1,
                "frame_len": 42,
                "frame_stamp": 123,
                "width": 960,
                "height": 576,
            }
        )
        summary = {}

        record_processed_packet(
            decoded_messages=decoded_messages,
            media_messages=media_messages,
            summary_emitter=emitter,
            summary=summary,
            decoded=decoded,
            source="direct",
            phase="flush",
        )

        self.assertEqual([decoded], decoded_messages)
        self.assertEqual([], media_messages)
        self.assertNotIn("frame_tag", summary)

    def test_should_build_media_collection_summary_within_threshold_window(
        self,
    ) -> None:
        self.assertFalse(
            should_build_media_collection_summary(
                media_message_count=0,
                min_media_messages=2,
                max_media_messages=4,
            )
        )
        self.assertTrue(
            should_build_media_collection_summary(
                media_message_count=2,
                min_media_messages=2,
                max_media_messages=4,
            )
        )
        self.assertTrue(
            should_build_media_collection_summary(
                media_message_count=3,
                min_media_messages=2,
                max_media_messages=4,
            )
        )
        self.assertFalse(
            should_build_media_collection_summary(
                media_message_count=4,
                min_media_messages=2,
                max_media_messages=4,
            )
        )


if __name__ == "__main__":
    unittest.main()
